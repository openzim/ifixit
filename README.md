# iFixit

`ifixit2zim` is an [openZIM](https://openzim.org) scraper to create offline versions of [iFixit](https://www.ifixit.com/) website, in all its supported languages.

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/ifixit/badge)](https://www.codefactor.io/repository/github/openzim/ifixit)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/openzim/ifixit/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/ifixit)
[![PyPI version shields.io](https://img.shields.io/pypi/v/ifixit2zim.svg)](https://pypi.org/project/ifixit2zim/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ifixit2zim.svg)](https://pypi.org/project/ifixit2zim)

This scraper downloads the iFixit resources (categories, guides, ...) and puts them in a ZIM file, a clean and user friendly format for storing content for offline usage.

## Usage

`ifixit2zim` works off a *language version* that you must provide via the `--language` argument. The list of supported languages is visible in the `--help` message.

### Docker

```bash
docker run -v my_dir:/output ghcr.io/openzim/ifixit ifixit2zim --help
```

### Python

`ifixit2zim` is a Python3 (**3.6+**) software. If you are not using the [Docker](https://docker.com) image, you are advised to use it in a virtual environment to avoid installing software dependencies on your system. In addition to Python3, you also need to have an up-to-date installation of pip, setuptools and wheel as recommanded [here](https://packaging.python.org/en/latest/tutorials/installing-packages/#id14) (wheel is important since you will have to build some dependencies).

```bash
python3 -m venv .venv
source .venv/bin/activate

# using published version
pip3 install ifixit2zim
ifixit2zim --help

# running from source
pip3 install -r requirements.pip
python3 ifixit2zim/ --help
```

Call `deactivate` to quit the virtual environment.

See `requirements.txt` for the list of python dependencies.


## Contributing

**All contributions are welcome!**

Please open an issue on Github and/or submit a Pull-request.

This project adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

This project has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/blob/main/docs/Policy.md) **v1.0.0**.

### Guidelines

- Don't take assigned issues. Comment if those get staled.
- If your contribution is far from trivial, open an issue to discuss it first.
- Ensure your code passed [black formatting](https://pypi.org/project/black/), [isort](https://pypi.org/project/isort/) and [flake8](https://pypi.org/project/flake8/) (88 chars)

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
docker build -t local-ifixit .
```

Then run the scraper with CLI arguments needed for your test (everything after `ifixit2zim` in the example below).

For instance, if you want to run a scrape of only the `Apple_PDA` category, including its guides,
in French :
```
docker run -it -v $(pwd)/output:/output --rm local-ifixit ifixit2zim --language fr --output /output --tmp-dir /tmp --category Apple_PDA
```

This will produce a ZIM in the output folder of your current directory.

### Test the ZIM produced

To test if the ZIM produced is OK, you should run kiwix-serve, once more with Docker.

For instance, if you produced a file named `ifixit_fr_selection_2022-04.zim` in the
`output` subfolder, and port 1256 is unused on your machine, you might run:
```
docker run -it --rm -v $(pwd)/output:/data -p 1256:80 ghcr.io/kiwix/kiwix-tools kiwix-serve /data/ifixit_fr_selection_2022-04.zim
```
And then navigate to (https://localhost:1256) on your favorite browser.

Once test are complete, you might stop the Docker container by pressing Ctrl-C
