#!/usr/bin/env python3
import subprocess
import time

_args = ['python3', 'main.py']

if __name__ == '__main__':
    while True:
        subprocess.run(_args)
        time.sleep(10)
