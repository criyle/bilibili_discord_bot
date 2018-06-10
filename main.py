import discord
import asyncio
import sys
from bilidownload import BiliVideo
from discord.ext import commands

if not discord.opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    discord.opus.load_opus('opus')


class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '**{0.title}** uploadered by **{0.uploader}**'
        duration = self.player.duration
        if duration:
            fmt += ' `[length: {0[0]}m {0[1]}s]`'.format(divmod(duration, 60))

        return fmt.format(self.player)


class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        if self.is_playing():
            self.player.stop()

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Now playing %s' % str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()


class Music:
    """Voice related commands.

    Works in multiple servers at once
    """

    _bili_video_url = 'www.bilibili.com/video/'

    def __init__(self, bot, *, file_path=None):
        self.bot = bot
        self.voice_state = {}
        self.path = file_path

    def __unload(self):
        for state in self.voice_state.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnnect())
            except:
                pass

    def get_voice_state(self, server):
        state = self.voice_state.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_state[server.id] = state

        return state

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        await self.bot.send_message(ctx.message.channel, 'I am alive')

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summon the bot to join the voice channel"""
        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx, *, url: str):
        msg = await self.bot.send_message(ctx.message.channel, 'Querying `%s`' % url)
        if url.find(self._bili_video_url) < 0:
            await self.bot.edit_message(msg, '`%s` is not bilibili url' % url)
            return

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            success = await ctx.invoke(self.summon)
            if not success:
                return

        try:
            bili_video = BiliVideo(url, file_path=self.path)
            player = await bili_video.get_bili_player(state.voice, after=state.toggle_next)
        except Exception as e:
            fmt = 'An error occurred: ```py\n{}: {}\n ```'
            await self.bot.edit_message(msg, fmt.format(type(e).__name__, e))
            raise e
        else:
            entry = VoiceEntry(ctx.message, player)
            await self.bot.edit_message(msg, 'Enqueued ' + str(entry))
            await state.songs.put(entry)

    @commands.command(pass_context=True, no_pm=True)
    async def download(self, ctx, *, url: str):
        msg = await self.bot.send_message(ctx.message.channel, 'Downloading `%s`' % url)
        if url.find(self._bili_video_url) < 0:
            await self.bot.edit_message(msg, '`%s` is not bilibili url' % url)
            return

        video = BiliVideo(url, file_path=self.path)
        file_name = await video.download_segments()
        await self.bot.edit_message(msg, 'Downloaded `%s`' % file_name)

    @commands.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            msg = await self.bot.send_message(ctx.message.channel, 'Stopped %s' % str(state.current))
            player = state.player
            player.stop()
        else:
            msg = await self.bot.send_message(ctx.message.channel, 'Not Playing')

        try:
            state.audio_player.cancel()
            await state.voice.disconnect()
            del self.voice_state[server.id]
        except Exception as e:
            raise e

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            msg = await self.bot.send_message(ctx.message.channel, 'Skipped %s' % str(state.current))
            player = state.player
            player.stop()
        else:
            msg = await self.bot.send_message(ctx.message.channel, 'Not Playing')

    @commands.command(pass_context=True, no_pm=True)
    async def queue(self, ctx):
        server = ctx.message.server
        state = self.get_voice_state(server)

        msg = 'Not playing'
        if state.is_playing():
            msg = 'Waiting Queue Size: %d' % state.songs.qsize()
        await self.bot.send_message(ctx.message.channel, msg)

    @commands.command(pass_context=True, no_pm=True)
    async def download_mp3(self, ctx):
        msg = await self.bot.send_message(ctx.message.channel, 'Downloading `%s`' % url)
        if url.find(self._bili_video_url) < 0:
            await self.bot.edit_message(msg, '`%s` is not bilibili url' % url)
            return

        video = BiliVideo(url, file_path=self.path)
        file_name = await video.download_mp3()
        await self.bot.edit_message(msg, 'Downloaded `%s`' % file_name)

async def sysin_commander(loop, stdin):
    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, stdin)
    while True:
        line = await reader.readline()
        if not line:
            break
        print(line)

try:
    from configure import *
except:
    pass

bot = commands.Bot(command_prefix=commands.when_mentioned_or('\''),
                   description='The bilibili playlist')
bot.add_cog(Music(bot, file_path=file_path))


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    for server in bot.servers:
        print('server: ' + server.name)
        for user in server.members:
            print(user.name)
        print('------')
    bot.loop.create_task(sysin_commander(bot.loop, sys.stdin))

bot.run(token)
