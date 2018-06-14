import aiohttp
import asyncio
import io
import os
import threading
from os import path
# for setting pipe buffer size
try:
    import fcntl
    import platform
except:
    pass
# for simple util functions
from common import *
# for bilibili data classes
from data import *


def write_to_file(file_name, content):
    with open(file_name, 'wb') as f:
        try:
            content.seek(0)
            f.write(content.read())
        except Exception as e:
            logging.error(e)
        finally:
            content.close()


class FileWriter(threading.Thread):
    '''Write file in another thread to avoid thread blocking
    '''

    def __init__(self, file_name, content, after=None):
        self.file_name = file_name
        self.content = content
        self.after = after
        super().__init__()

    def _do_run(self):
        write_to_file(self.file_name, self.content)

    def run(self):
        self._do_run()
        if self.after is not None:
            self.after()


class DiscordPlayer(threading.Thread):
    '''Base class for bilibili player
    '''
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
            if system == 'Linux':
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
    '''Local player for bilibili
    '''

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
    '''Online Player for bilibili
    '''
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

    async def _do_download_one_segment(self, session, f, seg_info):
        file_info = FileDownloadInfo(seg_info.size)
        file_info.start()
        print('start download')

        async with session.get(seg_info.url, headers=self._headers) as resp:
            status = resp.status
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

                try:
                    if f is not None:
                        f.write(data)
                    self.pin.write(data)
                except:
                    pass

        file_info.end()

    async def _do_download(self):
        async with aiohttp.ClientSession() as session:
            for segment in self.segments:
                file_name = path.join(self.path, segment.file_name)
                f = None
                try:
                    #f = open(file_name, 'wb')
                    f = io.BytesIO()
                    self.pin = self._create_piped_player()
                    self.is_start = False
                    await self._do_download_one_segment(session, f, segment)
                except:
                    pass

                if f is not None:
                    # write file in another thread
                    file_writer = FileWriter(file_name, f)
                    file_writer.start()

                self.pin.close()
                if self._end.is_set():
                    break

        self._write_segments(self.segments)

    def _write_segments(self, segments):
        file_name = path.join(self.path, 'segments.json')
        with open(file_name, 'w') as f:
            json.dump(segments, f, default=obj_dict)

    def _do_run(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._do_download())
        loop.close()
