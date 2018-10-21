import aiohttp
import asyncio
import hashlib
import json
import re
import os
import io
import logging
from os import path
import logging
from bs4 import BeautifulSoup
# for bilibili player classes
from .player import *
# for trans_code
from .simple_ffmpeg import *
# for non blocking file write
from .buffered_writer import FileWriter
# for bilibili video api
from .bilibili_api import Video, VideoDownloader
# for database
from .db import VideoDatabase

logger = logging.getLogger(__name__)

_bilibili_url = 'https://www.bilibili.com'
_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'


class BilibiliVideo:
    def __init__(self, url, *, file_path=None, loop=None, db=None):
        logger.info('create BilibiliVideo object with url: %s' % url)
        self.session = aiohttp.ClientSession()
        self.video = Video(url, self.session)
        self.url = self.video.url
        self.name = self.video.name
        self.path = None
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.db = db if db is not None else VideoDatabase()
        if file_path is not None:
            self.path = path.join(file_path, self.name)
            if not path.exists(self.path):
                os.makedirs(self.path)

    def _is_downloaded(self):
        if self.path is None:
            return False
        data = self.db.get_video(self.video.aid)
        if data is not None:
            return data['segmentinfo'] is not None and len(data['segmentinfo']) > 0
        return False

    def _read_segments(self):
        if self.path is None:
            return None
        logger.info('loading segments for %s' % self.name)
        seg_json = self.db.get_video(self.video.aid)['segmentinfo']
        return VideoSegmentInfo.from_json(seg_json)

    def _write_segments(self, segments):
        if self.path is None:
            return
        logger.info('saving segments for %s' % self.name)
        seg_json = json.dumps(segments, default=obj_dict)
        self.db.update_segmentinfo(self.video.aid, seg_json)

    async def download_segments(self):
        logger.info('start download: %s' % self.name)
        if self.path is None:
            return
        if self._is_downloaded():
            segments = self._read_segments()
            file_name = 'local: ' + ', '.join(map(str, segments))
            return file_name

        self.db.insert_video(self.video.aid)
        video_data = await self.video.get_video_data()
        video_info = VideoInfo(self.url, video_data)
        if self.path is not None:
            self.db.insert_video(self.video.aid)
            self.db.update_videoinfo(self.video.aid, video_info.to_json())

        logger.info('video info: %s, %s' % (self.name, str(video_info)))
        segments = await self.video.get_segment_info()
        downloader = VideoDownloader(self.url, self.session, segments)
        msgs = await downloader.download(self.path)
        self._write_segments(segments)
        return 'online: ' + ', '.join(msgs)

    async def get_player(self, voice, loop, *, after=None):
        logger.info('retriving player for %s' % self.name)
        if self._is_downloaded():
            d = self.db.get_video(self.video.aid)
            logger.info('local player for %s' % self.name)
            video_info = VideoInfo.from_json(d['videoinfo'])
            segments = self._read_segments()
            return BiliLocalPlayer(voice, loop, segments, after, video_info=video_info, path=self.path)

        logger.info('online player for %s' % self.name)
        video_data = await self.video.get_video_data()
        video_info = VideoInfo(self.url, video_data)
        if self.path is not None:
            self.db.insert_video(self.video.aid)
            self.db.update_videoinfo(self.video.aid, video_info.to_json())

        logger.info('video info: %s, %s' % (self.name, str(video_info)))
        segments = await self.video.get_segment_info()
        return BiliOnlinePlayer(voice, loop, segments, self.url, after, video_info=video_info, path=self.path)

    async def download_title_pic(self):
        logger.info('retriving title pic for %s' % self.name)
        video_data = await self.video.get_video_data()
        # pic is the address for the title image
        headers = {
            'Origin': _bilibili_url,
            'User-Agent': _user_agent,
            'Referer': self.url,
            'Connection': 'keep-alive',
        }
        async with self.session.get(video_data['pic'], headers=headers) as resp:
            status = resp.status
            f = io.BytesIO()
            f.write(await resp.read())
            return f

        return None

    def get_filename(self, filename):
        invalid = '/\|'
        return ''.join([c for c in filename if c not in invalid])

    async def download_audio(self):
        logger.info('retriving audio file for %s' % self.name)
        if self.path is None:
            return "Path is not set"
        if not self._is_downloaded():
            await self.download_segments()

        title_file = path.join(self.path, 'title.png')
        cropped_title_file = path.join(self.path, 'cropped.png')

        title_f = None
        cropped_f = None
        # if the title pic did not download, then download it
        if not path.exists(title_file):
            title_f = await self.download_title_pic()
        else:
            title_f = open(title_file, 'rb')

        if title_f is None:
            msg = 'fail to download title pic for %s' % self.name
            logger.error(msg)
            return msg

        json_vi = self.db.get_video(self.video.aid)['videoinfo']
        video_info = VideoInfo.from_json(json_vi)
        segments = self._read_segments()
        file_name = self.get_filename(video_info.title) + '.m4a'
        file_name = path.join(self.path, file_name)
        msg = None
        if path.exists(file_name):
            msg = 'audio file existed for %s' % self.name
            logger.info(msg)
            # return msg

        # crop to square for album
        cropped_f = io.BytesIO()
        square_crop(title_f, cropped_f)

        # used for asyncio
        loop = asyncio.get_event_loop()
        event = asyncio.Event()

        def after(): return loop.call_soon_threadsafe(event.set)

        # save to disk
        if not path.exists(title_file):
            await loop.run_in_executor(None, save_to_file, title_file, title_f)
            title_f.close()

        if not path.exists(cropped_title_file):
            await loop.run_in_executor(None, save_to_file, cropped_title_file, cropped_f)
            cropped_f.close()

        ffmpeg = Flv2M4a(path.join(self.path, segments[0].file_name), after)
        ffmpeg.start()
        await event.wait()
        event.clear()

        output_file = ffmpeg.output_file
        # album, composer, genre, copyright, encoded_by, title, language, artist, album_artist, performer
        # disc, publisher, tracker, encoder, lyrics}
        metadata = {
            'title': video_info.title,
            'lyrics': video_info.url + '\n' + video_info.description,
            'artist': video_info.uploader,
            'album_artist': video_info.uploader,
            'album': 'BILIBILI',
        }
        ffmpeg = M4aAddMeta(output_file, metadata, cropped_title_file, after)
        ffmpeg.start()
        await event.wait()
        event.clear()

        output_file = ffmpeg.output_file
        os.rename(output_file, file_name)
        return file_name if msg is None else msg

    def __del__(self):
        self.loop.call_soon(self.session.close)
