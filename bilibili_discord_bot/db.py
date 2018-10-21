import sqlite3
import pkg_resources
import click
import enum

class VideoStatus(enum.IntEnum):
    New = 1
    Downloading = 2
    Playing = 3
    Downloaded = 10


class VideoDatabase:
    '''Manage the downloaded files
    '''

    def __init__(self, db_path='bot.sqlite'):
        self.db_path = db_path
        self.conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self.conn.row_factory = sqlite3.Row

    def init_db(self):
        resource_package = __name__
        sql = pkg_resources.resource_string(resource_package, 'schema.sql')
        self.conn.executescript(sql.decode('utf-8'))
        self.conn.commit()

    def get_video(self, aid):
        sql = 'SELECT * FROM video WHERE aid=?'
        return self.conn.execute(sql, (aid,)).fetchone()

    def insert_video(self, aid):
        if self.get_video(aid) is not None:
            return
        sql = 'INSERT INTO video(aid, status) VALUES (?,?)'
        self.conn.execute(sql, (aid, 0))
        self.conn.commit()

    def update_status(self, aid, status):
        sql = 'UPDATE video SET status=? WHERE aid=?'
        self.conn.execute(sql, (int(status), aid))
        self.conn.commit()

    def update_videoinfo(self, aid, videoinfo):
        sql = 'UPDATE video SET videoinfo=? WHERE aid=?'
        self.conn.execute(sql, (videoinfo, aid))
        self.conn.commit()

    def update_segmentinfo(self, aid, seginfo):
        sql = 'UPDATE video SET segmentinfo=? WHERE aid=?'
        self.conn.execute(sql, (seginfo, aid))
        self.conn.commit()

    def __del__(self):
        self.conn.close()
