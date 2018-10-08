import io
import threading
import queue
import logging

logger = logging.getLogger(__name__)


def save_to_file(file_name:str, content: io.BytesIO):
    with open(file_name, 'wb') as f:
        f.write(content.getvalue())


class FileWriter(threading.Thread):
    '''Queue file write operations to avoid thread blocking.
    '''

    _page_size = 4096
    _default_buff_size = 32 * _page_size

    def __init__(self, f, *, buff_size=_default_buff_size):
        '''f should be a file like object that support write(bytes)
        '''
        if isinstance(f, str):
            self._f = open(f, 'wb')
        else:
            self._f = f
        self._queue = queue.Queue()
        self.buff_size = buff_size
        self._is_started = False
        self._is_stopped = False
        self.buff = None
        super().__init__()

    def run(self):
        self._is_started = True
        while True:
            b = self._queue.get()
            if b is None:
                break

            self._f.write(b)
            self._queue.task_done()

    def write(self, content):
        if self._is_stopped:
            return

        b = None
        if isinstance(content, io.BytesIO):
            b = content.getvalue()
        else:
            b = content

        if self.buff is None:
            self.buff = io.BytesIO()

        if not self._is_started:
            self.start()

        #logger.info('write bytes length: %s' % len(b))
        self.buff.write(b)
        length = len(self.buff.getbuffer())
        if length >= self.buff_size:
            self._queue.put(self.buff.getvalue())
            self.buff.close()
            self.buff = None

    def stop(self):
        self._is_stopped = True
        if self.buff is not None:
            self._queue.put(self.buff.getvalue())
            self.buff.close()
            self.buff = None

        self._queue.join()
        # stop worker
        self._queue.put(None)

    def close(self):
        self.stop()
