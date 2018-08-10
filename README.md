# Discord Bot for Bilibili

Under developing.

Music bot that plays the audio of Bilibili video and doing local cache.
It can also download video as audio files with format mp3 or m4a

Require python version >= 3.4 and library bs4, discord.py with audio.
FFmpeg is also required for media decoding.
atomicparsley is also required for album art for m4a files

Using fabric to deploy and supervisor to run as service

## Usage

Create `configure.json` with configurations

``` json
{
  "token": "discord_token",
  "file_path": "/cache_path"
}
```

and run in command line

``` bash
python3 -m DiscordBilibiliBot
```

## Data Object

### BiliVideoInfo

Store the original url and video information including title, duration, uploader and description

### BiliVideoSegmentInfo

Store the one segment of the video

### DiscordPlayer

Base class of players

#### BiliLocalPlayer

Plays the local cache video

#### BiliOnlinePlayer

Plays the online video and doing the local cache

### BiliVideo

Modified from youtube_dl to decode the video address
