#!/usr/bin/env python3
import discord
import asyncio
import sys
import os
import logging
import json
import click

from discord.ext import commands
# the command control
from .bot import Music
# for database
from .db import VideoDatabase

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


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        ctx.forward(run)


@main.command('run')
def run():
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

@main.command('init-db')
def init_db_command():
    req_keys = ['db']
    config = get_config(req_keys)
    db_path = config.get('db')
    db_path = db_path if db_path is not None else 'bot.sqlite'
    db = VideoDatabase(db_path)
    db.init_db()
    click.echo('Initialized the database.')

__all__ = ['main']
