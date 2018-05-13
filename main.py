import discord
import asyncio
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
        fmt = '*{0.title}* uploadered by {0.uploader}'
        #duration = self.player.duration
        # if duration:
        #    fmt += ' [length: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))

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

    def __init__(self, bot):
        self.bot = bot
        self.voice_state = {}

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
        if url.find(self._bili_video_url) < 0:
            await self.bot.send_message(ctx.message.channel, 'It is not bilibili url %s' % url)
            return

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            success = await ctx.invoke(self.summon)
            if not success:
                return

        try:
            bili_video = BiliVideo(url)
            player = await bili_video.get_bili_player(state.voice)
        except Exception as e:
            fmt = 'An error occurred: ```py\n{}: {}\n ```'
            await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
            raise e
        else:
            entry = VoiceEntry(ctx.message, player)
            await self.bot.say('Enqueued ' + str(entry))
            await state.songs.put(entry)

    @commands.command(pass_context=True, no_pm=True)
    async def download(self, ctx, *, url: str):
        msg = await self.bot.send_message(ctx.message.channel, 'Downloading %s' % url)
        if url.find(self._bili_video_url) < 0:
            await self.bot.edit_message(msg, 'It is not bilibili url %s' % url)
            return

        video = BiliVideo(url)
        file_name = await video.download_segments()
        await self.bot.edit_message(msg, 'Downloaded %s' % file_name)

    @commands.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            pass

        try:
            pass
            del self.voice_state[server.id]
            await state.voice.disconnnect()
        except:
            pass


bot = commands.Bot(command_prefix=commands.when_mentioned_or('\''),
                   description='The bilibili playlist')
bot.add_cog(Music(bot))


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

bot.run('token')
