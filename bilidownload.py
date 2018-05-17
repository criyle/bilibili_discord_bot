import aiohttp
import asyncio
import hashlib
import urllib
import json
import re
import os
import time
from os import path
import logging
from bs4 import BeautifulSoup
import threading
from datetime import datetime
# for setting pipe buffer size
import fcntl
import platform


def size2str(num, suffix='B'):
    '''helper function to produce human readable size format'''
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def obj_dict(obj):
    '''helper function to json serialize object'''
    return obj.__dict__


class FileDownloadInfo:
    _timeout = 3

    def __init__(self, total):
        self.current = 0
        self.total = total
        self.start_time = None
        self.end_time = None
        self.last_current = 0
        self.last_time = None

    def start(self):
        self.start_time = time.time()
        self.last_time = self.start_time

    def end(self):
        self.end_time = time.time()

    def is_timeout(self):
        current_time = time.time()
        return current_time - self.last_time > self._timeout

    def log(self, length):
        self.current += length

    def get_status(self):
        current_time = time.time()
        fmt = 'Read ({0} / {1}) {2}'
        result = fmt.format(size2str(self.current), size2str(self.total),
                            size2str((self.current - self.last_current) / (current_time - self.last_time), 'B/s'))
        self.last_current = self.current
        self.last_time = current_time
        return result

    def avg_speed(self):
        if self.start_time is None or self.end_time is None:
            return 0

        return total / (self.end_time / self.start_time)


class BiliVideoInfo:
    _file_name = 'videoinfo.json'

    def __init__(self, url=None, video_data=None):
        self.url = ''
        self.title = ''
        self.upload_time = ''
        self.description = ''
        self.duration = 0
        self.uploader = ''

        if url is not None:
            self.url = url

        if video_data is not None:
            self.title = video_data['title']
            self.upload_time = video_data['ctime']
            self.description = video_data['desc']
            self.duration = video_data['duration']
            self.uploader = video_data['owner']['name']

    def load(self, file_path):
        file_name = path.join(file_path, self._file_name)
        with open(file_name, 'r') as f:
            self.__dict__ = json.load(f)

    def save(self, file_path):
        file_name = path.join(file_path, self._file_name)
        with open(file_name, 'w') as f:
            json.dump(self, f, default=obj_dict)

    def __str__(self):
        fmt = 'title: {0.title} uploader: {0.uploader} \ndescription: {0.description}'
        return fmt.format(self)


class BiliVideoSegmentInfo:
    _flv = 'flv'
    _mp4 = 'mp4'

    def __init__(self, durl, format: str):
        if format.find(self._flv) >= 0:
            self.format = self._flv
        else:
            self.format = self._mp4

        self.url = durl['url']
        self.length = durl['length']
        self.size = durl['size']
        self.order = durl['order']

    @property
    def file_name(self):
        return '%d.%s' % (self.order, self.format)

    def __str__(self):
        fmt = 'format: {0.format} size: {1} length: {2[0]}m {2[1]}s'
        return fmt.format(self, size2str(self.size), divmod(self.length))


class DiscordPlayer(threading.Thread):
    _page_size = 4096
    _block_size = 32 * _page_size
    _pipe_buffer_size = 256 * _page_size

    def __init__(self, voice, path, segments, after, *, video_info=None, **kwargs):
        threading.Thread.__init__(self, **kwargs)

        self.voice = voice
        self.path = path
        self.segments = segments
        self.after = after
        self.video_info = video_info

        self._end = threading.Event()
        self.pin = None
        self.player = None

    def _set_pipe_buffer_size(self, fd, size):
        try:
            system = platform.system()
            if system == 'Linux' or system == 'Darwin':
                fcntl.F_SETPIPE_SZ = 1031
                fcntl.fcntl(fd, fcntl.F_SETPIPE_SZ, size)
        except IOError:
            print('change pipe buffer size failed')

    def _create_piped_player(self):
        pipeout, pipein = os.pipe()
        self._set_pipe_buffer_size(pipein, self._pipe_buffer_size)
        self._set_pipe_buffer_size(pipeout, self._pipe_buffer_size)
        self.player = self.voice.create_ffmpeg_player(
            os.fdopen(pipeout, 'rb'), pipe=True, after=self.after)
        return os.fdopen(pipein, 'wb')

    def run(self):
        self._do_run()

    def stop(self):
        self.player.stop()
        self._end.set()

    def is_done(self):
        return self.player.is_done()

    @property
    def title(self):
        if self.video_info is not None:
            return self.video_info.title
        return ''

    @property
    def duration(self):
        if self.video_info is not None:
            return self.video_info.duration
        return 0

    @property
    def uploader(self):
        if self.video_info is not None:
            return self.video_info.uploader
        return ''


class BiliLocalPlayer(DiscordPlayer):
    def __init__(self, voice, path, segments, after, *, video_info=None, **kwargs):
        super().__init__(voice, path, segments, after, video_info=video_info, **kwargs)

    def _feedFile(self, segment):
        file_name = path.join(self.path, segment.file_name)
        with open(file_name, 'rb') as fin:
            while not self._end.is_set():
                data = fin.read(self._block_size)
                data_len = len(data)
                if data_len == 0:
                    break
                try:
                    self.pin.write(data)
                except:
                    pass

    def _do_run(self):
        for segment in self.segments:
            self.pin = self._create_piped_player()
            self.player.start()
            self._feedFile(segment)
            if self._end.is_set():
                return

            self.pin.close()


class BiliOnlinePlayer(DiscordPlayer):
    _bili_address = 'https://www.bilibili.com'
    _user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

    def __init__(self, voice, path, segments, ref_url, after, *, video_info=None, **kwargs):
        super().__init__(voice, path, segments, after, video_info=video_info, **kwargs)
        self._headers = {
            'Range': 'byte=0-',
            'Origin': self._bili_address,
            'User-Agent': self._user_agent,
            'Referer': ref_url,
            'Connection': 'keep-alive',
        }
        self.segments = segments
        self.is_start = False
        #self._video_url = seg_info.url
        #self.total = seg_info.size

    async def _do_download_one_segment(self, session, seg_info):
        file_name = path.join(self.path, seg_info.file_name)
        file_info = FileDownloadInfo(seg_info.size)
        file_info.start()
        print('start download')

        async with session.get(seg_info.url, headers=self._headers) as resp:
            status = resp.status
            with open(file_name, 'wb') as f:
                while not self._end.is_set():
                    data = await resp.content.read(self._block_size)
                    if not self.is_start:
                        self.player.start()
                        self.is_start = True

                    data_len = len(data)
                    file_info.log(data_len)
                    if file_info.is_timeout() or data_len == 0:
                        print(file_info.get_status())

                    if data_len == 0:
                        break

                    f.write(data)
                    try:
                        self.pin.write(data)
                    except:
                        pass

            file_info.end()

    async def _do_download(self):
        async with aiohttp.ClientSession() as session:
            for segment in self.segments:
                self.pin = self._create_piped_player()
                self.is_start = False
                await self._do_download_one_segment(session, segment)
                if self._end.is_set():
                    return

                self.pin.close()

        self._write_segments(self.segments)

    def _write_segments(self, segments):
        file_name = path.join(self.path, 'segments.json')
        with open(file_name, 'w') as f:
            json.dump(segments, f, default=obj_dict)

    def _do_run(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._do_download())
        loop.close()


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
            with open(file_name, 'wb') as f:
                while True:
                    data = await resp.content.read(self._block_size)
                    data_len = len(data)
                    file_info.log(data_len)
                    if file_info.is_timeout() or data_len == 0:
                        print(file_info.get_status())
                    if data_len == 0:
                        break

                    f.write(data)

        file_info.end()
        return 'file: %s average speed: %lf' % (file_name, avg_speed)

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


async def main():
    #bv = BiliVideo('https://www.bilibili.com/video/av22973250', file_path='/Users/criyle/temp')
    # await bv.download_segments()
    pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
