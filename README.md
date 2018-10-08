# Discord Bot for Bilibili

Under developing.

Music bot that plays the audio of Bilibili video and doing local cache. It can also download video as audio files with format mp3 or m4a.

Require python version >= 3.4 and library bs4, discord.py\[audio\] (directly from github), PIL. FFmpeg is also required for media decoding. Atomicparsley is also required for album art for m4a files.

Using fabric to deploy and supervisor to run as service.

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
bilibili_discord_bot
```
