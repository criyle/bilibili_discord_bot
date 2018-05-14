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


class BiliVideoInfo:
    _file_name = 'videoinfo.json'

    def __init__(self, url=None, video_data=None):
        self._info = {
            'url': '',
            'title': '',
            'upload_time': '',
            'description': '',
            'duration': '',
            'uploader': '',
        }
        if url is not None:
            self._info['url'] = url

        if video_data is not None:
            self._info['title'] = video_data['title']
            self._info['upload_time'] = video_data['ctime']
            self._info['description'] = video_data['desc']
            self._info['duration'] = video_data['duration']
            self._info['uploader'] = video_data['owner']['name']

    def load(self, file_path):
        file_name = path.join(file_path, self._file_name)
        with open(file_name, 'r') as f:
            self._info = json.load(f)

    def save(self, file_path):
        file_name = path.join(file_path, self._file_name)
        with open(file_name, 'w') as f:
            json.dump(self._info, f)

    @property
    def url(self):
        return self._info['url']

    @property
    def title(self):
        return self._info['title']

    @property
    def upload_time(self):
        return self._info['upload_time']

    @property
    def description(self):
        return self._info['description']

    @property
    def duration(self):
        return self._info['duration']

    @property
    def uploader(self):
        return self._info['uploader']

    def __str__(self):
        fmt = 'title: {0.title} uploader: {0.uploader} \ndescription: {0.description}'
        return fmt.format(self)


class DiscordPlayer(threading.Thread):
    _page_size = 4096
    _block_size = 32 * _page_size
    _pipe_buffer_size = 256 * _page_size

    def __init__(self, voice, file_name, after, **kwargs):
        threading.Thread.__init__(self, **kwargs)

        self.voice = voice
        self.file_name = file_name
        self.after = after
        self._end = threading.Event()
        self.current = 0
        self.total = 0
        self.title = ''
        self.uploader = ''
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
        self.pin = self._create_piped_player()
        self._do_run()

    def stop(self):
        self.player.stop()
        self._end.set()

    @property
    def duration(self):
        return self.player.duration

    def is_done(self):
        return self.player.is_done()


class BiliLocalPlayer(DiscordPlayer):
    def __init__(self, voice, file_name, after, *, video_info=None, **kwargs):
        super().__init__(voice, file_name, after, **kwargs)
        self.total = path.getsize(file_name)
        self.video_info = video_info
        if video_info is not None:
            self.title = video_info.title
            self.uploader = video_info.uploader

    def _feedFile(self):
        with open(self.file_name, 'rb') as fin:
            while not self._end.is_set():
                data = fin.read(self._block_size)
                data_len = len(data)
                if data_len == 0:
                    break
                self.current += data_len
                try:
                    self.pin.write(data)
                except:
                    pass
        self.pin.close()

    def _do_run(self):
        self.player.start()
        self._feedFile()


class BiliOnlinePlayer(DiscordPlayer):
    _bili_address = 'https://www.bilibili.com'
    _user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

    def __init__(self, voice, file_name, durl, ref_url, after, *, video_info=None, **kwargs):
        super().__init__(voice, file_name, after, **kwargs)
        self._headers = {
            'Range': 'byte=0-',
            'Origin': self._bili_address,
            'User-Agent': self._user_agent,
            'Referer': ref_url,
            'Connection': 'keep-alive',
        }
        self._video_url = durl['url']
        self.total = durl['size']
        self.video_info = video_info
        if video_info is not None:
            self.title = video_info.title
            self.uploader = video_info.uploader

    async def _do_download(self):
        print('start download')
        last_time = time.time()
        last_current = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(self._video_url, headers=self._headers) as resp:
                status = resp.status
                with open(self.file_name, 'wb') as f:
                    while not self._end.is_set():
                        data = await resp.content.read(self._block_size)
                        if self.current == 0:
                            self.player.start()
                        data_len = len(data)
                        self.current += data_len
                        current_time = time.time()
                        if current_time - last_time > 3:
                            print('Read %d (%d / %d) %lf' %
                                  (data_len, self.current, self.total,
                                   (self.current - last_current) / (current_time - last_time)))
                            last_time = current_time
                            last_current = self.current
                        if data_len == 0:
                            break
                        f.write(data)
                        try:
                            self.pin.write(data)
                        except:
                            pass
                    self.pin.close()
                    if self._end.is_set():
                        os.remove(self.file_name)

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
    _path = '/Users/criyle/temp'
    _page_size = 4096
    _block_size = 32 * _page_size

    def __init__(self, url):
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
                    end_idx = content.find(';(function()')
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
            return data['durl']

    async def _download_segment(self, session, durl):
        current = 0
        total = durl['size']
        video_headers = {
            'Range': 'byte=0-',
            'Origin': self._bili_address,
            'User-Agent': self._user_agent,
            'Referer': self.url,
            'Connection': 'keep-alive',
        }
        video_url = durl['url']
        file_name = path.join(self.path, '1.flv')
        print('start download')
        last_time = time.time()
        last_current = 0

        async with session.get(video_url, headers=video_headers) as resp:
            status = resp.status
            with open(file_name, 'wb') as f:
                while True:
                    data = await resp.content.read(self._block_size)
                    data_len = len(data)
                    current += data_len
                    current_time = time.time()
                    if current_time - last_time > 3:
                        print('Read %d (%d / %d) %lf' %
                              (data_len, current, total,
                               (current - last_current) / (current_time - last_time)))
                        last_time = current_time
                        last_current = current
                    if data_len == 0:
                        break
                    f.write(data)
            return file_name

    def _is_downloaded(self):
        file_name = path.join(self.path, '1.flv')
        return path.exists(file_name)

    async def download_segments(self):
        if self._is_downloaded():
            file_name = path.join(self.path, '1.flv')
            return file_name

        async with aiohttp.ClientSession() as session:
            video_data = await self._get_video_data(session)
            cid = self._get_cid(video_data)
            print(cid)
            video_info = BiliVideoInfo(self.url, video_data)
            video_info.save(self.path)
            print(str(video_info))
            addresses = await self._get_durls(session, cid)
            for durl in addresses:
                filename = await self._download_segment(session, durl)
                # return os.fdopen(pipeout, 'rb')
                return filename

    async def get_bili_player(self, voice, *, after=None):
        file_name = path.join(self.path, '1.flv')
        if self._is_downloaded():
            video_info = None
            try:
                video_info = BiliVideoInfo()
                video_info.load(self.path)
                print(str(video_info))
            except Exception as e:
                pass
            return BiliLocalPlayer(voice, file_name, after, video_info=video_info)

        async with aiohttp.ClientSession() as session:
            video_data = await self._get_video_data(session)
            cid = self._get_cid(video_data)
            print(cid)
            video_info = BiliVideoInfo(self.url, video_data)
            video_info.save(self.path)
            print(str(video_info))
            addresses = await self._get_durls(session, cid)
            for durl in addresses:
                return BiliOnlinePlayer(voice, file_name, durl, self.url, after, video_info=video_info)


async def main():
    bv = BiliVideo('https://www.bilibili.com/video/av22973250', loop)
    await bv.download_segments()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
