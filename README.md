# iFixit

`ifixit2zim` is an [openZIM](https://openzim.org) scraper to create offline versions of [iFixit](https://www.ifixit.com/) website, in all its supported languages.

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/ifixit/badge)](https://www.codefactor.io/repository/github/openzim/ifixit)
[![Docker](https://img.shields.io/docker/v/openzim/ifixit?label=docker&sort=semver)](https://hub.docker.com/r/openzim/ifixit)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PyPI version shields.io](https://img.shields.io/pypi/v/ifixit2zim.svg)](https://pypi.org/project/ifixit2zim/)

This scraper downloads the iFixit resources (categories, guides, ...) and puts them in a ZIM file, a clean and user friendly format for storing content for offline usage.

For now, this tool is still under active development. Most recent version of the tool is located in the `develop` branch or any of its sub-branches.

## Develop

If you want to help us by enhancing this scraper with some additional / better code, 
feel free to choose an open issue without assignee and work on it. If you are not used 
to Kiwix scrapper development, you will find some guidance below.

### Create an appropriate Python environment

First time:
```
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.pip
```

Next times:
```
source .venv/bin/activate
```


NOTA : there is some limitations to the execution of the underlying libzim library on 
MacOS with some known bugs. The main issue is that the full-text index is not working,
so this shouldn't be a problem for quick tests. In doubt, execute the scraper in a
Docker container as explained below.

### Test the scraper in a Docker container

First, build the Docker image (to be ran in the main folder of this repo):
```
docker build -t openzim/fixit:local .
```

Then run the scraper with CLI arguments needed for your test (everything after `ifixit2zim` in the example below).

For instance, if you want to run a scrape of only the `Apple_PDA` category, including its guides,
in French :
```
docker run -it -v $(pwd)/output:/output --rm openzim/fixit:local ifixit2zim --language fr --output /output --tmp-dir /tmp --category Apple_PDA
```

This will produce a ZIM in the output folder of your current directory.

### Test the ZIM produced

To test if the ZIM produced is OK, you should run kiwix-serve, once more with Docker.

For instance, if you produced a file named `ifixit_fr_selection_2022-04.zim` in the 
`output` subfolder, and port 1256 is unused on your machine, you might run:
```
docker run -it --rm -v $(pwd)/output:/data -p 1256:80 kiwix/kiwix-tools kiwix-serve /data/ifixit_fr_selection_2022-04.zim
```
And then navigate to (https://localhost:1256) on your favorite browser.

Once test are complete, you might stop the Docker container by pressing Ctrl-C
