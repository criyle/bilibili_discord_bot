import subprocess
import threading
import asyncio
from os import path
from common import *


class FFMpegRunner(threading.Thread):
    def __init__(self, input_file=None, output_file=None, args=None, *, after=None):
        self.input_file = input_file
        self.output_file = output_file
        self.args = args
        self.after = after
        super().__init__()

    def _do_run(self):
        args = []
        # run in lower priority
        if is_linux_or_mac():
            args.extend(['nice'])
        # overwrite without confirm
        args.extend(['ffmpeg', '-y'])
        if self.input_file is not None:
            args.extend(['-i', self.input_file])

        if self.args is not None:
            try:
                args.extend(self.args)
            except:
                pass

        if self.output_file is not None:
            args.append(self.output_file)

        subprocess.run(args)
        print('finished')

    def _call_after(self):
        if self.after is not None:
            self.after()

    def run(self):
        try:
            self._do_run()
        except Exception as e:
            self.error = e
            self.stop()
        finally:
            self._call_after()


class Flv2Mp3(FFMpegRunner):
    _ext = '.mp3'

    def __init__(self, input_file, after=None):
        filename, file_extension = path.splitext(input_file)
        self.output_file = filename + self._ext
        super().__init__(input_file, self.output_file, after=after)


class Mp3AddMeta(FFMpegRunner):
    _new_suffix = '_.mp3'

    # ffmpeg -i 1.mp3 -i 1.jpg -map 0:0 -map 1:0 -metadata title="虹之间" -metadata artist="乐正龙牙" -metadata album_artist="他城" -metadata album="VOCALOID" 2.mp3
    # album, composer, genre, copyright, encoded_by, title, language, artist, album_artist, performer
    # disc, publisher, tracker, encoder, lyrics

    def __init__(self, input_file, meta_dict, art_file, after=None):
        filename, file_extension = path.splitext(input_file)
        output_file = filename + self._new_suffix
        # use args store all parameters
        args = []
        # input files (mp3 and art)
        args.extend(['-i', input_file, '-i', art_file])
        # map
        args.extend(['-map', '0:0', '-map', '1:0'])
        # copy
        args.extend(['-acodec', 'copy'])

        for k, v in meta_dict.items():
            args.extend(['-metadata', k + '=' + v])

        super().__init__(None, output_file, args, after=after)


class Flv2M4a(FFMpegRunner):
    _ext = '.m4a'

    def __init__(self, input_file, after=None):
        filename, file_extension = path.splitext(input_file)
        self.output_file = filename + self._ext
        args = []
        args.extend(['-vn', '-acodec', 'copy'])
        super().__init__(input_file, self.output_file, args, after=after)


class M4aAddMeta(FFMpegRunner):
    _new_suffix = '_.m4a'

    # ffmpeg -i 1.m4a -acodec copy -metadata title="虹之间" -metadata artist="乐正龙牙" -metadata album_artist="他城" -metadata album="VOCALOID" 2.mp3
    # album, composer, genre, copyright, encoded_by, title, language, artist, album_artist, performer
    # disc, publisher, tracker, encoder, lyrics
    # atomicparsley 1.m4a --artwork cropped.png --overWrite

    def __init__(self, input_file, meta_dict, art_file, after=None):
        self.art_file = art_file
        filename, file_extension = path.splitext(input_file)
        output_file = filename + self._new_suffix
        # use args store all parameters
        args = []
        # copy
        args.extend(['-acodec', 'copy'])

        for k, v in meta_dict.items():
            args.extend(['-metadata', k + '=' + v])

        super().__init__(input_file, output_file, args, after=after)

    def _do_run(self):
        super()._do_run()
        # set art file
        args = []
        if is_linux_or_mac():
            args.extend(['nice'])
        args = ['atomicparsley', self.output_file]
        args.extend(['--artwork', self.art_file, '--overWrite'])
        subprocess.run(args)
