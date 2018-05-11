import aiohttp
import asyncio
import hashlib
import urllib
import json
import re
import os
from os import path
import logging
from bs4 import BeautifulSoup
import threading

class BiliDiscordPlayer(threading.Thread):
    _UserAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

    _VideoHeaders = {
        'Range': 'byte=0-',
        'Origin': 'https://www.bilibili.com',
        'User-Agent': _UserAgent,
        'Referer': '',
        'Connection': 'keep-alive',
    }
    _Block = 128 * 1024

    def __init__(self, durl, file_name, url, voice, **kwargs):
        threading.Thread.__init__(self, **kwargs)

        self.durl = durl
        self.player = None
        self._end = threading.Event()
        self.voice = voice
        #self._resumed = True
        self.file_name = file_name
        self.current = 0
        if durl is not None:
            self.total = durl['size']
        self._VideoHeaders['Referer'] = url

    def _feedFile(self, pin):
        with open(self.file_name, 'rb') as fin:
            while not self._end.is_set():
                data = fin.read(self._Block)
                if len(data) == 0:
                    break
                try:
                    pin.write(data)
                except:
                    pass

    def _isDownloaded(self):
        return path.exists(self.file_name)

    async def _do_run(self):
        pipeout, pipein = os.pipe()
        self.player = self.voice.create_ffmpeg_player(os.fdopen(pipeout, 'rb') , pipe = True)
        pin = os.fdopen(pipein, 'wb')

        if self._isDownloaded():
            self.player.start()
            self._feedFile(pin)
            pin.close()
            return

        print('start download')
        async with aiohttp.ClientSession() as session:
            async with session.get(self.durl['url'], headers = self._VideoHeaders) as resp:
                status = resp.status
                with open(self.file_name, 'wb') as f:
                    while not self._end.is_set():
                        data = await resp.content.read(self._Block)
                        if self.current == 0:
                            self.player.start()
                        data_len = len(data)
                        self.current += data_len
                        print('Read %d (%d / %d)' % (data_len, self.current, self.total))
                        if data_len == 0:
                            break
                        f.write(data)
                        try:
                            pin.write(data)
                        except:
                            pass
                    if self._end.is_set():
                        pin.close()
                        os.remove(self.file_name)
                        return

    def run(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._do_run())
        loop.close()

    async def stop(self):
        self.player.stop()
        self._end.set()

class BiliDownload:
    _AppKey = '84956560bc028eb7'
    _AppSecret = '94aba54af9065f71de72f5508f1cd42e'

    _UserAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

    _Headers = {
        'User-Agent': _UserAgent,
    }
    _VideoHeaders = {
        'Range': 'byte=0-',
        'Origin': 'https://www.bilibili.com',
        'User-Agent': _UserAgent,
        'Referer': '',
        'Connection': 'keep-alive',
    }

    _Initial = 'window.__INITIAL_STATE__='
    _Path = '/Users/criyle/temp'

    def __init__(self, url, loop):
        idx = url.find('?')
        if idx >= 0:
            url = url[0: idx]
        self.name = re.search(r'(av\d+)', url).group(1)
        self.url = url
        self._VideoHeaders['Referer'] = url
        self.path = path.join(self._Path, self.name)
        self.loop = loop
        if not path.exists(self.path):
            os.makedirs(self.path)

    def _GetSign(self, params):
        keys = list(params.keys())
        keys.sort()
        l = []
        for key in keys:
            l.append(key + '=' + params[key])
        s = '&'.join(l) + self._AppSecret
        m = hashlib.md5()
        m.update(s.encode('utf-8'))
        return m.hexdigest()

    async def _GetCid(self, session):
        async with session.get(self.url, headers = self._Headers) as resp:
            status = resp.status
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            for script in scripts:
                if len(script.contents) == 0:
                    continue
                content = script.contents[0]
                length = len(self._Initial)
                idx = content.find(self._Initial)
                if idx >= 0:
                    end_idx = content.find(';(function()')
                    data = json.loads(content[idx + length:end_idx])
                    embedPlayer = data['videoData']['embedPlayer']
                    m = re.search(r'cid=(\d+)', embedPlayer)
                    return m.group(1)

    async def _GetPlayAddress(self, session, cid):
        quality = '80'
        url = 'https://interface.bilibili.com/v2/playurl'
        params = {
            'cid': cid,
            'appkey': self._AppKey,
            'otype': 'json',
            'type': '',
            'quality': quality,
            'qn': quality,
        }
        params['sign'] = self._GetSign(params)
        async with session.get(url, params = params, headers = self._VideoHeaders) as resp:
            status = resp.status
            data = await resp.json()
            return data['durl']

    async def _DownloadOneSegment(self, session, durl):
        #b = bytes()
        current = 0
        total = durl['size']
        print('start download')

        async with session.get(durl['url'], headers = self._VideoHeaders) as resp:
            status = resp.status
            file_name = path.join(self.path, '1.flv')
            with open(file_name, 'wb') as f:
                while True:
                    data = await resp.content.read(self._Block)
                    current += len(data)
                    print('Read %d (%d / %d)' % (len(data), current, total))
                    if len(data) == 0:
                        break
                    f.write(data)
            return file_name

    def _isDownloaded(self):
        file_name = path.join(self.path, '1.flv')
        return path.exists(file_name)

    async def DownloadStream(self):
        if self._isDownloaded():
            file_name = path.join(self.path, '1.flv')
            return file_name

        async with aiohttp.ClientSession() as session:
            cid = await self._GetCid(session)
            print(cid)
            addresses = await self._GetPlayAddress(session, cid)
            for durl in addresses:
                filename = await self._DownloadOneSegment(session, durl)
                #return os.fdopen(pipeout, 'rb')
                return filename

    async def GetBiliPlayer(self, voice):
        file_name = path.join(self.path, '1.flv')
        if self._isDownloaded():
            return BiliDiscordPlayer(None, file_name, self.url, voice)

        async with aiohttp.ClientSession() as session:
            cid = await self._GetCid(session)
            print(cid)
            addresses = await self._GetPlayAddress(session, cid)
            for durl in addresses:
                return BiliDiscordPlayer(durl, file_name, self.url, voice)

async def main():
    bd = BiliDownload('https://www.bilibili.com/video/av22973250', loop)
    await bd.GetStream()

if __name__ == '__main__':
    logging.basicConfig(level = logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
