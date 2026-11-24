# iFixit

`ifixit2zim` is an [openZIM](https://openzim.org) scraper to create offline versions of [iFixit](https://www.ifixit.com/) website, in all its supported languages.

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/ifixit/badge)](https://www.codefactor.io/repository/github/openzim/ifixit)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/openzim/ifixit/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/ifixit)
[![PyPI version shields.io](https://img.shields.io/pypi/v/ifixit2zim.svg)](https://pypi.org/project/ifixit2zim/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ifixit2zim.svg)](https://pypi.org/project/ifixit2zim)
[![Docker](https://ghcr-badge.egpl.dev/openzim/ifixit/latest_tag?label=docker)](https://ghcr.io/openzim/ifixit)

This scraper downloads the iFixit resources (categories, guides, ...) and puts them in a ZIM file, a clean and user friendly format for storing content for offline usage.

## Usage

`ifixit2zim` works off a *language version* that you must provide via the `--language` argument. The list of supported languages is visible in the `--help` message.

### Docker

```bash
docker run -v my_dir:/output ghcr.io/openzim/ifixit ifixit2zim --help
```

### Python

`ifixit2zim` requires **Python 3.14**. The project uses [Hatch](https://hatch.pypa.io/) as its build backend and environment manager. If you are not using the [Docker](https://docker.com) image, install Hatch once (for example with `pip install hatch`) and use it to run from source in an isolated environment:

```bash
# running from source
hatch shell
python3 -m ifixit2zim --help

# using published version
pip3 install ifixit2zim
ifixit2zim --help
```

Exit the Hatch shell with `exit`.

See `pyproject.toml` for the list of Python dependencies.


## Contributing

**All contributions are welcome!**

Please open an issue on Github and/or submit a Pull-request.

This project adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

This project adheres to openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/blob/main/docs/Policy.md) **v2.0.0**.

### Guidelines

- Don't take assigned issues. Comment if those get staled.
- If your contribution is far from trivial, open an issue to discuss it first.
- Ensure your code passes linting and formatting with [Ruff](https://docs.astral.sh/ruff/) and strict static type checking with [Pyright](https://microsoft.github.io/pyright/).

### Quality assurance

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting, and [Pyright](https://microsoft.github.io/pyright/) in strict mode for static type checking. The same checks run in CI.

Install the pre-commit hooks after clone so they run automatically before each commit:

```bash
pre-commit install
```

Inside the Hatch shell (see [Create an appropriate Python environment](#create-an-appropriate-python-environment)):

```bash
inv check-lint     # ruff check
inv check-format   # ruff format --check
inv check-type     # pyright
inv check-all      # all of the above
```

Automatic fixes are available with `inv fix-lint`, `inv fix-format` and `inv fix-all`.

Tests are run with:

```bash
inv test           # pytest
inv coverage       # pytest with coverage report
```

### Create an appropriate Python environment

The project uses [Hatch](https://hatch.pypa.io/) as its build backend and environment manager. Install it once (for example with `pip install hatch`), then from the repository root run:

```bash
hatch shell
```



NOTA: there are some limitations to the execution of the underlying libzim library on
macOS with some known bugs. The main issue is that the full-text index is not working,
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
mkdir -p output
docker run -it -v $(pwd)/output:/output --rm local-ifixit ifixit2zim --language fr --output /output --tmp-dir /tmp --category Apple_PDA
```

This will produce a ZIM in the output folder of your current directory.

### Test the ZIM produced

To test if the ZIM produced is OK, you should run kiwix-serve, once more with Docker.

For instance, if you produced a file named `ifixit_fr_selection_2022-04.zim` in the
`output` subfolder, and port 37000 is unused on your machine, you might run:

```bash
docker run -it --rm -v $(pwd)/output:/data -p 37000:8080 ghcr.io/kiwix/kiwix-serve ifixit_fr_selection_2022-04.zim
```

And then navigate to http://localhost:37000 on your favorite browser.

Once tests are complete, you may stop the Docker container by pressing Ctrl-C.

### Update static assets

**Advanced users only.** This is only needed when upstream iFixit changes its
frontend. iFixit generates hashed CSS filenames, so assets must be refreshed when the
upstream site changes. Mirror the site with [HTTrack](https://www.httrack.com/) into `tmp/www.ifixit.com`
```bash
mkdir -p tmp
httrack https://www.ifixit.com/ --path=tmp --verbose
```

and run:

```bash
python scripts/update_assets.py --mirror-dir tmp/www.ifixit.com
```

The script discovers the current CSS URLs from the mirrored HTML, downloads
the CSS files and their `url(...)` dependencies, rewrites those URLs to local
`../assets/...` paths, updates the template references to the new hashed
filenames, and removes stale managed CSS files. Use `--dry-run` to preview the
changes.
