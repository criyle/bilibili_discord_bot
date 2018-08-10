import DiscordBilibiliBot
import sys
import json

if __name__ == '__main__':
    try:
        with open('config.json') as f:
            config = json.load(f)

    except:
        exit('no config file founded')

    token = config.get('token')
    file_path = config.get('file_path')

    if token is None:
        exit('Invalid Token')

    if file_path is None:
        exit('Invalid file path')

    DiscordBilibiliBot.main(token=token, file_path=file_path)
