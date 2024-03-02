import locale
import logging
import threading
from contextlib import contextmanager

from zimscraperlib.logging import getLogger as lib_getLogger

from ifixit2zim.constants import NAME

logger = lib_getLogger(
    NAME,
    level=logging.INFO,
    log_format="[%(threadName)s::%(asctime)s] %(levelname)s:%(message)s",
)


def set_debug(value):
    level = logging.DEBUG if value else logging.INFO
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


LOCALE_LOCK = threading.Lock()


@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)
