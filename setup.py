import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    requires = f.read().splitlines()

setuptools.setup(
    name="bilibili_discord_bot",
    version="0.0.1a0",
    author="criyle",
    author_email="criyle@example.com",
    description="Discord Bot for Bilibili",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/criyle/DiscordBilibiliBot",
    packages=setuptools.find_packages(),
    install_requires=requires,
    dependency_links=[
        #'git+https://github.com/Rapptz/discord.py.git@rewrite#egg=discord.py-1.0.0'
    ],
    entry_points={
        'console_scripts': [
            'bilibili_discord_bot=bilibili_discord_bot:main',
        ],
    },
)
