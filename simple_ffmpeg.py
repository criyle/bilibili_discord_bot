import subprocess
import threading
import asyncio
from os import path

class FFMpegRunner(threading.Thread):
    def __init__(self, input_file=None, output_file=None, args=None):
        self.input_file = input_file
        self.output_file = output_file
        self.args = args
        # make async function can wait
        self.async_wait = asyncio.Event()

    def run(self):
        # overwrite without confirm
        args = ['ffmpeg', '-y']
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
        self.async_wait.set()

class Flv2Mp3(FFMpegRunner):
    _ext = '.mp3'

    def __init__(self, input_file):
        filename, file_extension = path.splitext(input_file)
        self.output_file = filename + self._ext
        super().__init__(input_file, self.output_file)

class Mp3AddMeta(FFMpegRunner):
    _new_suffix = '_.mp3'

    #ffmpeg -i 1.mp3 -i 1.jpg -map 0:0 -map 1:0 -metadata title="虹之间" -metadata artist="乐正龙牙" -metadata album_artist="他城" -metadata album="VOCALOID" 2.mp3
    # album, composer, genre, copyright, encoded_by, title, language, artist, album_artist, performer
    # disc, publisher, tracker, encoder, lyrics

    def __init__(self, input_file, meta_dict, art_file):
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

        args.append(output_file)
        super().__init__(None, None, args)
