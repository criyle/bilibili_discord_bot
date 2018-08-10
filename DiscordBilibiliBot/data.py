from os import path
import json
from .common import *

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
        return fmt.format(self, size2str(self.size), divmod(self.length // 1000, 60))
