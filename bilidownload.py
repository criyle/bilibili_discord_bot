import aiohttp
import asyncio
import hashlib
import json
import re
import os
import io
from os import path
import logging
from bs4 import BeautifulSoup
# for bilibili player classes
from player import *
# for trans_code
from simple_ffmpeg import *


class BiliVideo:
    _app_key = '84956560bc028eb7'
    _app_secret = '94aba54af9065f71de72f5508f1cd42e'
    _app_address = 'https://interface.bilibili.com/v2/playurl'

    _bili_address = 'https://www.bilibili.com'
    _user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

    _headers = {
        'User-Agent': _user_agent,
    }

    _initial_state = 'window.__INITIAL_STATE__='
    _initial_state_end = ';(function()'

    _page_size = 4096
    _block_size = 32 * _page_size

    def __init__(self, url, *, file_path=None):
        idx = url.find('?')
        if idx >= 0:
            url = url[0: idx]

        self.name = re.search(r'(av\d+)', url).group(1)
        self.url = url
        self._app_headers = {
            'Origin': self._bili_address,
            'User-Agent': self._user_agent,
            'Referer': url,
            'Connection': 'keep-alive',
        }
        self._path = '/Users/criyle/temp'
        if file_path is not None:
            self._path = file_path
        self.path = path.join(self._path, self.name)
        if not path.exists(self.path):
            os.makedirs(self.path)

    def _get_sign(self, params):
        keys = list(params.keys())
        keys.sort()
        l = []
        for key in keys:
            l.append(key + '=' + params[key])
        s = '&'.join(l) + self._app_secret
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    async def _get_video_data(self, session):
        async with session.get(self.url, headers=self._headers) as resp:
            status = resp.status
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            for script in scripts:
                if len(script.contents) == 0:
                    continue
                content = script.contents[0]
                idx = content.find(self._initial_state)
                if idx >= 0:
                    length = len(self._initial_state)
                    end_idx = content.find(self._initial_state_end)
                    data = json.loads(content[idx + length:end_idx])
                    return data['videoData']

    def _get_cid(self, video_data):
        embedPlayer = video_data['embedPlayer']
        m = re.search(r'cid=(\d+)', embedPlayer)
        return m.group(1)

    async def _get_durls(self, session, cid):
        quality = '80'
        params = {
            'cid': cid,
            'appkey': self._app_key,
            'otype': 'json',
            'type': '',
            'quality': quality,
            'qn': quality,
        }
        params['sign'] = self._get_sign(params)

        async with session.get(self._app_address, params=params, headers=self._app_headers) as resp:
            status = resp.status
            data = await resp.json()
            durls = data['durl']
            format = data['format']
            results = []
            for durl in durls:
                results.append(BiliVideoSegmentInfo(durl, format))
            return results

    async def _download_segment(self, session, seg_info: BiliVideoSegmentInfo):
        video_headers = {
            'Range': 'byte=0-',
            'Origin': self._bili_address,
            'User-Agent': self._user_agent,
            'Referer': self.url,
            'Connection': 'keep-alive',
        }
        video_url = seg_info.url
        file_name = path.join(self.path, seg_info.file_name)
        print('start download %s' % str(seg_info))
        file_info = FileDownloadInfo(seg_info.size)
        file_info.start()

        async with session.get(video_url, headers=video_headers) as resp:
            status = resp.status
            f = io.BytesIO()
            # with open(file_name, 'wb') as f:
            while True:
                data = await resp.content.read(self._block_size)
                data_len = len(data)
                file_info.log(data_len)
                if file_info.is_timeout() or data_len == 0:
                    print(file_info.get_status())
                if data_len == 0:
                    break

                f.write(data)

        file_writer = FileWriter(file_name, f)
        file_writer.start()

        file_info.end()
        return 'file: %s average speed: %s' % (file_name, file_info.avg_speed())

    def _is_downloaded(self):
        file_name = path.join(self.path, 'segments.json')
        return path.exists(file_name)

    def _read_segments(self):
        file_name = path.join(self.path, 'segments.json')
        results = []
        with open(file_name, 'r') as f:
            l = json.load(f)
            for s in l:
                si = BiliVideoSegmentInfo(s, s['format'])
                results.append(si)

        return results

    def _write_segments(self, segments):
        file_name = path.join(self.path, 'segments.json')
        with open(file_name, 'w') as f:
            json.dump(segments, f, default=obj_dict)

    async def download_segments(self):
        if self._is_downloaded():
            segments = self._read_segments()
            file_name = 'local: ' + ', '.join(map(str, segments))
            return file_name

        async with aiohttp.ClientSession() as session:
            video_data = await self._get_video_data(session)
            cid = self._get_cid(video_data)
            video_info = BiliVideoInfo(self.url, video_data)
            video_info.save(self.path)

            print(cid)
            print(str(video_info))

            segments = await self._get_durls(session, cid)
            file_name = ''
            for segment in segments:
                file_name += await self._download_segment(session, segment)

            self._write_segments(segments)
            return file_name

    async def get_bili_player(self, voice, *, after=None):
        if self._is_downloaded():
            video_info = None
            segments = self._read_segments()
            try:
                video_info = BiliVideoInfo()
                video_info.load(self.path)
                print(str(video_info))
            except Exception as e:
                pass
            return BiliLocalPlayer(voice, self.path, segments, after, video_info=video_info)

        async with aiohttp.ClientSession() as session:
            video_data = await self._get_video_data(session)
            cid = self._get_cid(video_data)
            video_info = BiliVideoInfo(self.url, video_data)
            video_info.save(self.path)

            print(cid)
            print(str(video_info))

            segments = await self._get_durls(session, cid)
            for segment in segments:
                return BiliOnlinePlayer(voice, self.path, segments, self.url, after, video_info=video_info)

    async def download_title_pic(self):
        async with aiohttp.ClientSession() as session:
            video_data = await self._get_video_data(session)
            # pic is the address for the title image
            async with session.get(video_data['pic'], headers=self._app_headers) as resp:
                status = resp.status
                f = io.BytesIO()
                f.write(await resp.read())
                return f

        return None

    async def download_audio(self):
        if not self._is_downloaded():
            await self.download_segments()

        title_file_name = path.join(self.path, 'title.png')
        cropped_title_file_name = path.join(self.path, 'cropped.png')

        title_f = None
        cropped_f = None
        # if the title pic did not download, then download it
        if not path.exists(title_file_name):
            title_f = await self.download_title_pic()
        else:
            title_f = open(title_file_name, 'rb')

        if title_f is None:
            return ''

        video_info = BiliVideoInfo()
        video_info.load(self.path)
        segments = self._read_segments()

        ext = '.m4a'
        file_name = path.join(self._path, video_info.title + ext)
        if path.exists(file_name):
            return ''

        # crop to square for album
        cropped_f = io.BytesIO()
        square_crop(title_f, cropped_f)

        # used for asyncio
        loop = asyncio.get_event_loop()
        event = asyncio.Event()

        def after(): return loop.call_soon_threadsafe(event.set)

        # save to disk
        if not path.exists(title_file_name):
            title_writer = FileWriter(title_file_name, title_f)
            title_writer.start()

        if not path.exists(cropped_title_file_name):
            cropped_writer = FileWriter(
                cropped_title_file_name, cropped_f, after)
            cropped_writer.start()
            await event.wait()
            event.clear()

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
        ffmpeg = M4aAddMeta(output_file, metadata,
                            cropped_title_file_name, after)
        ffmpeg.start()
        await event.wait()
        event.clear()

        output_file = ffmpeg.output_file
        os.rename(output_file, file_name)
        return file_name


async def audio_generate(file_path):
    base_url = 'https://www.bilibili.com/video/'
    for file in os.listdir(file_path):
        full_name = path.join(file_path, file)
        if not path.isdir(full_name):
            continue

        url = base_url + file
        bv = BiliVideo(url, file_path=file_path)
        file_name = await bv.download_audio()
        print(file_name)


async def main():
    file_path = '/Users/criyle/temp'
    # bv = BiliVideo('https://www.bilibili.com/video/av22973250',
    #    file_path=file_path)
    # await bv.download_segments()
    # await bv.download_mp3()
    await audio_generate(file_path)
    pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
