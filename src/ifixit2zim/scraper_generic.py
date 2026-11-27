import threading
from abc import ABC, abstractmethod
from queue import Queue
from typing import TYPE_CHECKING, Any

from schedule import run_pending

from ifixit2zim.exceptions import FinalScrapingFailureError
from ifixit2zim.shared import logger
from ifixit2zim.utils import build_dynamic_page_link

if TYPE_CHECKING:
    from jinja2 import Environment
    from zimscraperlib.zim.creator import Creator

    from ifixit2zim.constants import Configuration
    from ifixit2zim.context import Context
    from ifixit2zim.processor import Processor
    from ifixit2zim.scraper import IFixitMetadata
    from ifixit2zim.utils import IFixitRequestClient


class ScraperGeneric(ABC):
    expected_items_keys: dict[str, dict[str, Any]]
    unexpected_items_keys: dict[str, dict[str, Any]]
    items_queue: Queue[dict[str, Any]]
    missing_items_keys: set[str]
    error_items_keys: set[str]

    def __init__(self, context: Context) -> None:
        self.context = context
        self.expected_items_keys = {}
        self.unexpected_items_keys = {}
        self.items_queue = Queue()
        self.missing_items_keys = set()
        self.error_items_keys = set()

    @property
    def configuration(self) -> Configuration:
        return self.context.configuration

    @property
    def client(self) -> IFixitRequestClient:
        return self.context.client

    @property
    def metadata(self) -> IFixitMetadata:
        return self.context.metadata

    @property
    def env(self) -> Environment:
        return self.context.env

    @property
    def lock(self) -> threading.Lock:
        return self.context.lock

    @property
    def creator(self) -> Creator:
        return self.context.creator

    @property
    def processor(self) -> Processor:
        return self.context.processor

    @abstractmethod
    def setup(self) -> None:
        pass

    @abstractmethod
    def get_items_name(self) -> str:
        pass

    @abstractmethod
    def build_expected_items(self) -> None:
        pass

    @abstractmethod
    def get_one_item_content(self, item_key: str, item_data: dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def add_item_redirect(
        self, item_key: str, item_data: dict[str, Any], redirect_kind: str
    ) -> None:
        pass

    @abstractmethod
    def process_one_item(
        self, item_key: str, item_data: dict[str, Any], item_content: Any
    ) -> None:
        pass

    def finalize(self) -> None:
        """Hook called after every scraper queue has been drained."""

    def add_item_to_scrape(
        self,
        item_key: str | int,
        item_data: Any,
        is_expected: bool,  # noqa: FBT001
        *,
        warn_unexpected: bool = True,
    ) -> None:
        item_key = str(item_key)  # just in case it's an int
        if (
            item_key in self.expected_items_keys
            or item_key in self.unexpected_items_keys
        ):
            return
        if is_expected:
            logger.debug(f"Adding {self.get_items_name()} {item_key} to scraping queue")
            self.expected_items_keys[item_key] = item_data
        else:
            message = (
                f"Adding unexpected {self.get_items_name()} {item_key} "
                "to scraping queue"
            )
            if warn_unexpected:
                logger.warning(message)
            else:
                logger.debug(message)
            self.unexpected_items_keys[item_key] = item_data
        self.items_queue.put(
            {
                "key": item_key,
                "data": item_data,
            }
        )

    def add_dynamic_html_redirect(
        self,
        *,
        path: str,
        kind: str,
        value: str,
        title: str = "",
    ) -> None:
        """Add a small HTML page redirecting to a dynamically generated page.

        A ZIM redirect target is an entry path and cannot carry the original
        URL. A real HTML page can redirect to the placeholder with the original
        URL stored in a magic anchor instead.
        """
        root_prefix = "../" * path.count("/")
        target = build_dynamic_page_link(kind, value, root_prefix)
        content = self.env.get_template("redirect.html").render(
            metadata=self.metadata,
            root_prefix=root_prefix,
            target=target,
            title=title or path,
        )
        self.processor.add_html_item(
            path=path,
            title=title or path,
            content=content,
            is_front=False,
        )

    def add_item_missing_redirect(self, item_key: str, item_data: Any) -> None:
        self.add_item_redirect(item_key, item_data, "missing")

    def add_item_error_redirect(self, item_key: str, item_data: Any) -> None:
        try:
            self.add_item_redirect(item_key, item_data, "error")
        except Exception:
            logger.warning("Failed to add redirect for item in error")
            pass  # ignore exceptions, we are already inside an exception handling

    def scrape_one_item(self, item_key: str, item_data: Any) -> None:
        item_content = self.get_one_item_content(item_key, item_data)

        if item_content is None:
            logger.warning(f"Missing {self.get_items_name()} {item_key}")
            self.missing_items_keys.add(item_key)
            self.add_item_missing_redirect(item_key, item_data)
            return

        logger.debug(f"Processing {self.get_items_name()} {item_key}")

        self.process_one_item(item_key, item_data, item_content)

    def scrape_items(self) -> None:
        logger.info(
            f"Scraping {self.get_items_name()} items ({self.items_queue.qsize()}"
            " items remaining)"
        )

        num_items = 1
        while not self.items_queue.empty():
            run_pending()
            if 0 < self.configuration.max_items_per_type < num_items:
                break
            item = self.items_queue.get(block=False)
            item_key = item["key"]
            item_data = item["data"]
            logger.info(
                f"  Scraping {self.get_items_name()} {item_key}"
                f" ({self.items_queue.qsize()} items remaining)"
            )
            try:
                self.scrape_one_item(item_key, item_data)
            except Exception as exc:
                self.error_items_keys.add(item_key)
                logger.warning(
                    f"Error while processing {self.get_items_name()} {item_key}",
                    exc_info=exc,
                )
                self.add_item_error_redirect(item_key, item_data)
            finally:
                if (
                    len(self.missing_items_keys)
                    * 100
                    / (len(self.expected_items_keys) + len(self.unexpected_items_keys))
                    > self.configuration.max_missing_items_percent
                ):
                    raise FinalScrapingFailureError(
                        f"Too many {self.get_items_name()}s found missing: "
                        f"{len(self.missing_items_keys)}"
                    )
                if (
                    len(self.error_items_keys)
                    * 100
                    / (len(self.expected_items_keys) + len(self.unexpected_items_keys))
                    > self.configuration.max_error_items_percent
                ):
                    raise FinalScrapingFailureError(
                        f"Too many {self.get_items_name()}s failed to be processed: "
                        f"{len(self.error_items_keys)}"
                    )
                num_items += 1
