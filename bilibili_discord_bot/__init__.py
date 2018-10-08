#!/usr/bin/env python3
import discord
import asyncio
import sys
import os
import logging
import json

from discord.ext import commands
# the command control
from .bot import Music

logger = logging.getLogger(__name__)

# import voice for discord
if not discord.opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    discord.opus.load_opus('opus')


def get_config(req):
    ret = {}
    try:
        with open('config.json') as f:
            config = json.load(f)
            for key in req:
                ret[key] = config.get(key)
            return ret
    except:
        pass
    try:
        import config
        for key in req:
            ret[key] = get_attr(config, key)
        return ret
    except:
        pass
    exit('No config file found.')


def main():
    req_keys = ['token', 'file_path']
    config = get_config(req_keys)
    token = config.get('token')
    file_path = config.get('file_path')

    if token is None:
        exit('Token is not configured.')

    if file_path is None:
        exit('File path is not configured.')

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

    logging.basicConfig(level=logging.INFO)
    bot.run(token)


__all__ = ['main']
