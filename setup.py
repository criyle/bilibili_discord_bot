import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = []
with open('requires.txt') as f:
  requires = f.read().splitlines()

setuptools.setup(
    name="DiscordBilibiliBot",
    version="0.0.1",
    author="criyle",
    author_email="criyle@example.com",
    description="Package of Discord Bot for Bilibili",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/criyle/DiscordBilibiliBot",
    packages=setuptools.find_packages(),
    install_requires=requires
)
