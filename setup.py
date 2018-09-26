import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requires.txt') as f:
    requires = f.read().splitlines()

setuptools.setup(
    name="DiscordBilibiliBot",
    version="0.0.1a0",
    author="criyle",
    author_email="criyle@example.com",
    description="Package of Discord Bot for Bilibili",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/criyle/DiscordBilibiliBot",
    packages=setuptools.find_packages(),
    install_requires=requires,
    dependency_links=[
        'git+https://github.com/Rapptz/discord.py@rewrite#egg=discord.py-1.0.0a'
    ],
    entry_points={
        'console_scripts': [
            'discord_bili_bot=DiscordBilibiliBot:main',
        ],
    },
)
