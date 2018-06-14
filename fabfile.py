from invoke import task, Exit
import os
from os import path
import re
import datetime

_TAR_FILE = 'deploy.tar'
_REMOTE_DIR = '/srv/discord_bot'
_REMOTE_TMP = '/tmp/%s' % _TAR_FILE
_SUPERVISOR_CONF = 'discord_bot.conf'
_SUPERVISOR_TMP = '/tmp/%s' % _SUPERVISOR_CONF
_SUPERVISOR_REMOTE = '/etc/supervisor/conf.d/%s' % _SUPERVISOR_CONF
_LOCAL_CONF = 'configure_remote.py'
_REMOTE_CONF = _REMOTE_DIR + '/configure.py'


@task
def generate(c):
    # make tar file
    c.local('rm %s' % _TAR_FILE, warn=True)
    args = ['tar', '-czvf', _TAR_FILE, '--exclude=\'configure.py\'', '*.py', ]
    c.local(' '.join(args))


@task
def restart(c):
    c.sudo('supervisorctl stop discord_bot', warn=True)
    c.sudo('supervisorctl start discord_bot', warn=True)


@task
def deploy_srv(c):
    # deploy supervisor conf file
    c.put(_SUPERVISOR_CONF, _SUPERVISOR_TMP)
    args = ['mv', _SUPERVISOR_TMP, _SUPERVISOR_REMOTE]
    c.sudo(' '.join(args))
    c.sudo('chown root:root %s' % _SUPERVISOR_REMOTE)
    c.sudo('chmod 771 %s' % _SUPERVISOR_REMOTE)
    c.sudo('systemctl stop supervisor')
    c.sudo('systemctl start supervisor')


@task
def deploy_conf(c):
    c.put(_LOCAL_CONF, _REMOTE_CONF)


@task
def deploy(c):
    # upload tar file and extract
    c.run('rm %s' % _REMOTE_TMP, warn=True)
    c.put(_TAR_FILE, _REMOTE_TMP)
    c.sudo('mkdir %s' % _REMOTE_DIR, warn=True)
    c.sudo('mkdir %s/log' % _REMOTE_DIR, warn=True)

    args = ['tar', '-xzvf', _REMOTE_TMP, '-C', _REMOTE_DIR, ]
    c.sudo(' '.join(args))

    # clean up
    c.run('rm %s' % _REMOTE_TMP, warn=True)

    # run the bot
    restart(c)
