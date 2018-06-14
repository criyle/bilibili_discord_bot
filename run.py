#!/usr/bin/env python3
import subprocess
import time
import os

_args = ['python3', 'main.py']

if __name__ == '__main__':
    os.umask(0o002)
    while True:
        subprocess.run(_args)
        time.sleep(10)
