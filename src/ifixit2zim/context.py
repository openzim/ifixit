import threading
from dataclasses import dataclass

from jinja2 import Environment
from zimscraperlib.zim.creator import Creator

from ifixit2zim.constants import Configuration
from ifixit2zim.models import IFixitMetadata
from ifixit2zim.processor import Processor
from ifixit2zim.utils import IFixitRequestClient


@dataclass
class Context:
    lock: threading.Lock
    configuration: Configuration
    creator: Creator
    client: IFixitRequestClient
    metadata: IFixitMetadata
    env: Environment
    processor: Processor
