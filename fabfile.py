from invoke import task, Exit
import os
from os import path
import re
import datetime

_REMOTE_DIR = '/srv/discord_bot'
_REMOTE_VENV = '%s/venv' % _REMOTE_DIR
_SUPERVISOR_CONF = 'discord_bot.conf'
_SUPERVISOR_TMP = '/tmp/%s' % _SUPERVISOR_CONF
_SUPERVISOR_REMOTE = '/etc/supervisor/conf.d/%s' % _SUPERVISOR_CONF
_LOCAL_CONF = 'config_remote.json'
_REMOTE_CONF = '%s/config.json' % _REMOTE_DIR


def pack_name(c):
    # figure out the package name and version
    dist = c.local('python setup.py --fullname', hide=True)
    filename = '%s.tar.gz' % dist.stdout.strip()
    return filename


@task
def pack(c):
    # make package
    c.local('python setup.py sdist --formats=gztar')


@task
def stop_srv(c):
    c.sudo('supervisorctl stop discord_bot', warn=True)


@task
def start_srv(c):
    c.sudo('supervisorctl start discord_bot', warn=True)


@task
def restart_srv(c):
    stop_srv(c)
    start_srv(c)


@task
def deploy_srv(c):
    # deploy supervisor conf file
    c.put(_SUPERVISOR_CONF, _SUPERVISOR_TMP)
    args = ['mv', _SUPERVISOR_TMP, _SUPERVISOR_REMOTE]
    c.sudo(' '.join(args))
    c.sudo('chown root:root %s' % _SUPERVISOR_REMOTE)
    c.sudo('chmod 771 %s' % _SUPERVISOR_REMOTE)
    c.sudo('supervisorctl update', warn=True)


@task
def deploy_conf(c):
    c.put(_LOCAL_CONF, '/tmp/%s' % _LOCAL_CONF)
    c.sudo('mv /tmp/%s %s' % (_LOCAL_CONF, _REMOTE_CONF))


@task
def deploy(c):
    # repack
    pack(c)

    # ensure path exists
    c.sudo('mkdir %s' % _REMOTE_DIR, warn=True)
    c.sudo('mkdir %s/log' % _REMOTE_DIR, warn=True)

    # upload tar file and extract
    filename = pack_name(c)
    remote_filename = '/tmp/%s' % filename
    c.put('dist/%s' % filename, remote_filename)

    # install in virtual environment
    args = ['%s/bin/pip' % _REMOTE_VENV, 'install', remote_filename, ]
    c.run(' '.join(args))

    # clean up
    c.run('rm %s' % remote_filename, warn=True)

    # run the bot
    restart_srv(c)
