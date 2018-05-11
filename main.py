import discord
import asyncio
from bilidownload import BiliDownload

client = discord.Client()
player = None

if not discord.opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    discord.opus.load_opus('opus')

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    for server in client.servers:
        print(server.name)
        for user in server.members:
            print(user.name)


@client.event
async def on_message(message):
    global player
    if message.content.startswith('!test'):
        counter = 0
        tmp = await client.send_message(message.channel, 'Calculating messages...')
        async for log in client.logs_from(message.channel, limit=100):
            if log.author == message.author:
                counter += 1

        await client.edit_message(tmp, 'You have {} messages.'.format(counter))
    elif message.content.startswith('!sleep'):
        await asyncio.sleep(5)
        await client.send_message(message.channel, 'Done sleeping')
    elif message.content.startswith('!music'):
        tmp = await client.send_message(message.channel, 'playing using ffmpeg...')
        voice1 = message.author.voice
        channel = voice1.voice_channel
        if channel == None:
            await client.edit_message(tmp, 'You have not join a voice channel')
            return
        voice = None
        if not client.is_voice_connected(message.server):
            voice = await client.join_voice_channel(channel)
        else:
            voice = client.voice_client_in(message.server)
        idx = message.content.find(' ')
        url = 'https://www.bilibili.com/video/av22973250'
        if idx >= 0:
            url = message.content[idx + 1:]
        biliDown = BiliDownload(url, client.loop)
        filename = await biliDown.GetStream()
        print('start ffmpeg')
        #player = voice.create_ffmpeg_player(pipeout, pipe = True)
        player = voice.create_ffmpeg_player(filename)
        print('created ffmpeg')
        player.start()
    elif message.content.startswith('!stop'):
        if player != None:
            player.stop()


client.run('token')
