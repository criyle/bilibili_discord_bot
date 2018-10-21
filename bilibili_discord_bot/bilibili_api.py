import io
import aiohttp
import asyncio
import re
import hashlib
from bs4 import BeautifulSoup

from .bilibili_data import *
from .buffered_writer import FileWriter

_bilibili_url = 'https://www.bilibili.com'
_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'

logger = logging.getLogger(__name__)

class NotBilibiliVideo(Exception):
    '''Exception for init Video with non bilibili url
    '''

    def __init__(self, message):
        logger.warning(message)
        super().__init__(message)


def get_sign(params, app_secret):
    keys = list(params.keys())
    keys.sort()
    l = []
    for key in keys:
        l.append(key + '=' + params[key])
    s = '&'.join(l) + app_secret
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def parse_initial_state(html):
    '''Get init JSON from bilibili video index HTML
    '''
    _initial_state = 'window.__INITIAL_STATE__='
    _initial_state_end = ';(function()'

    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    for script in scripts:
        if len(script.contents) == 0:
            continue
        content = script.contents[0]
        idx = content.find(_initial_state)
        if idx >= 0:
            length = len(_initial_state)
            end_idx = content.find(_initial_state_end)
            data = json.loads(content[idx + length:end_idx])
            return data
    logger.error("Cannot find init state from web" + html)
    return None


class VideoPlayUrl:
    def __init__(self, url, aid, cid, qn):
        self.url = url
        self.aid = aid
        self.cid = cid
        self.qn = qn
        self._app_headers = {
            'Origin': _bilibili_url,
            'User-Agent': _user_agent,
            'Referer': self.url,
            'Connection': 'keep-alive',
        }

    async def get_data(session: aiohttp.ClientSession):
        pass


class VideoPlayUrlSession(VideoPlayUrl):
    def __init__(self, url, aid, cid, qn, session_id):
        super().__init__(url, aid, cid, qn)
        self.session_id = session_id

    async def get_data(session: aiohttp.ClientSession):
        pass


class VideoPlayUrlV2(VideoPlayUrl):
    # get from youtube_dl
    _app_key = '84956560bc028eb7'
    _app_secret = '94aba54af9065f71de72f5508f1cd42e'
    _app_url = 'https://interface.bilibili.com/v2/playurl'

    def __init__(self, url, aid, cid, qn):
        super().__init__(url, aid, cid, qn)

    async def get_data(self, session: aiohttp.ClientSession):
        params = {
            'cid': str(self.cid),
            'appkey': self._app_key,
            'otype': 'json',
            'type': '',
            'quality': str(self.qn),
            'qn': str(self.qn),
        }
        params['sign'] = get_sign(params, self._app_secret)
        async with session.get(self._app_url, params=params, headers=self._app_headers) as resp:
            logger.info(params)
            status = resp.status
            data = await resp.json()
            return data


class VideoSegmentDownloader:
    _block_size = 32 * 4096

    def __init__(self, url: str, session: aiohttp.ClientSession, segment: VideoSegmentInfo, loop=None):
        self.url = url
        self.session = session
        self.segment = segment
        self.loop = loop if loop is not None else asyncio.get_event_loop()

    async def download(self, file, dup_f=None):
        '''file can be blocked and dup_f cannot be blocked
        '''
        logger.info('start download for %s, %s' % (self.url, str(self.segment)))
        video_url = self.segment.url
        headers = {
            'Range': 'byte=0-',
            'Origin': _bilibili_url,
            'User-Agent': _user_agent,
            'Referer': self.url,
            'Connection': 'keep-alive',
        }
        # keep track the byte and time of download
        file_info = FileDownloadInfo(self.segment.size)
        file_info.start()
        #f = FileWriter(file)
        # f is a file-like object and it can be blocked
        f = file
        async with self.session.get(video_url, headers=headers) as resp:
            status = resp.status
            while True:
                data = await resp.content.read(self._block_size)
                data_len = len(data)
                file_info.log(data_len)
                if file_info.is_timeout() or data_len == 0:
                    logger.info('downloading: %s' % file_info.get_status())
                if data_len == 0:
                    break
                await self.loop.run_in_executor(None, f.write, data)
                if dup_f is not None:
                    dup_f.write(data)

        file_info.end()
        msg = 'average speed: %s' % file_info.avg_speed()
        logger.info(msg)
        return msg


class VideoDownloader:
    def __init__(self, url: str, session: aiohttp.ClientSession, segments):
        self.url = url
        self.session = session
        self.segments = segments

    async def download(self, file_path):
        msgs = []
        for segment in self.segments:
            downloader = VideoSegmentDownloader(
                self.url, self.session, segment)
            file_name = segment.file_name
            full_path = path.join(file_path, file_name)
            with open(full_path, 'wb') as f:
                msgs.append(await downloader.download(f))

        return msgs


class Video:
    _bilibili_video_url = 'https://www.bilibili.com/video/'

    def __init__(self, url: str, session: aiohttp.ClientSession):
        logger.info('create Video object with url: %s' % url)
        match = re.search(r'av(\d+)', url)
        if match is None:
            raise NotBilibiliVideo('This is not bilibili url: %s.' % url)
        self.aid = int(match.group(1))
        self.name = 'av' + match.group(1)
        match = re.search(r'p=(\d+)', url)
        if match is None:
            self.pnum = 1
        else:
            self.pnum = int(match.group(1))
        # remake the url to avoid miss paste
        self.url = self._bilibili_video_url + self.name
        self.session = session
        self.web_data = None
        self.page_data = None

    async def get_web(self):
        headers = {
            'User-Agent': _user_agent
        }
        async with self.session.get(self.url, headers=headers) as resp:
            status = resp.status
            return await resp.text()

    async def get_web_data(self):
        if self.web_data is not None:
            return self.web_data
        html = await self.get_web()
        loop = asyncio.get_event_loop()
        self.web_data = await loop.run_in_executor(None, parse_initial_state, html)
        return self.web_data

    async def get_video_data(self):
        logger.info('retriving video_data for: %s' % self.name)
        web_data = await self.get_web_data()
        return web_data['videoData']

    async def get_cid(self):
        video_data = await self.get_video_data()
        pages = video_data['pages']
        self.page_data = pages[self.pnum - 1]
        return self.page_data['cid']

    async def get_segment_info(self, qn=80):
        logger.info('get segments info for: %s' % self.name)
        cid = await self.get_cid()
        player = VideoPlayUrlV2(self.url, self.aid, cid, qn)
        data = await player.get_data(self.session)
        durls = data['durl']
        format = data['format']
        results = [VideoSegmentInfo(durl, format) for durl in durls]
        logger.info('segments results %s' % str(results))
        return results
