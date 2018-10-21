DROP TABLE IF EXISTS video;

CREATE TABLE video(
  aid INTEGER PRIMARY KEY,
  status INTEGER NOT NULL,
  videoinfo TEXT,
  segmentinfo TEXT
);
