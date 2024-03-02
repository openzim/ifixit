import threading
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment
from zimscraperlib.zim.creator import Creator

from ifixit2zim.processor import Processor
from ifixit2zim.scraper import Configuration
from ifixit2zim.utils import Utils


@dataclass
class Context:
    lock: threading.Lock
    configuration: Configuration
    creator: Creator
    utils: Utils
    metadata: dict[str, Any]
    env: Environment
    processor: Processor
