# for croping the image
from PIL import Image
import time
import platform


def is_linux_or_mac():
    system = platform.system()
    return system == 'Linux' or system == 'Darwin'


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


def square_crop(file_in, file_out):
    '''helper function to crop image to square'''
    im = Image.open(file_in)
    width, height = im.size
    new_dim = min(width, height)
    left = (width - new_dim) // 2
    top = (height - new_dim) // 2
    right = (width + new_dim) // 2
    bottom = (height + new_dim) // 2
    print(left, top, right, bottom)
    om = im.crop((left, top, right, bottom))
    om.save(file_out, 'PNG')


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

        return size2str(self.total / (self.end_time - self.start_time), 'B/s')
