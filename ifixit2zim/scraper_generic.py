import traceback
from abc import ABC, abstractmethod
from queue import Queue

from .exceptions import FinalScrapingFailure
from .shared import Global, logger


class ScraperGeneric(ABC):
    def __init__(self):
        self.expected_items_keys = set()
        self.expected_items_queue = Queue()
        self.missing_items_keys = set()
        self.error_items_keys = set()

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def get_items_name(self):
        pass

    @abstractmethod
    def build_expected_items(self):
        pass

    @abstractmethod
    def get_one_item_content(self, item_key, item_data):
        pass

    @abstractmethod
    def process_one_item(self, item_key, item_data, item_content):
        pass

    def add_item_to_scrape(self, item_key, item_data):
        if item_key in self.expected_items_keys:
            return
        logger.debug(f"Adding {self.get_items_name()} {item_key} to scraping queue")
        self.expected_items_keys.add(item_key)
        self.expected_items_queue.put(
            {
                "key": item_key,
                "data": item_data,
            }
        )

    def scrape_one_item(self, item_key, item_data):

        item_content = self.get_one_item_content(item_key, item_data)

        if item_content is None:
            logger.warning(f"Missing {self.get_items_name()} {item_key}")
            self.missing_items_keys.add(item_key)
            return

        logger.debug(f"Processing {self.get_items_name()} {item_key}")

        self.process_one_item(item_key, item_data, item_content)

    def scrape_items(self):

        logger.info(
            f"Scraping about {self.expected_items_queue.qsize()}"
            f" {self.get_items_name()}"
        )

        num_items = 1
        while not self.expected_items_queue.empty():
            try:
                item = self.expected_items_queue.get(block=False)
                item_key = item["key"]
                item_data = item["data"]
                logger.info(
                    f"Scraping {self.get_items_name()} {item_key} "
                    f"({num_items}/{len(self.expected_items_keys)})"
                )
                self.scrape_one_item(item_key, item_data)
            except Exception as ex:
                self.error_items_keys.add(item_key)
                logger.warning(f"Error while processing item {item_key}: {ex}")
                traceback.print_exc()
            finally:
                if (
                    len(self.missing_items_keys) * 100 / len(self.expected_items_keys)
                    > Global.conf.max_missing_items_percent
                ):
                    raise FinalScrapingFailure(
                        f"Too many {self.get_items_name()}s found missing: "
                        f"{len(self.missing_items_keys)}"
                    )
                if (
                    len(self.error_items_keys) * 100 / len(self.expected_items_keys)
                    > Global.conf.max_error_items_percent
                ):
                    raise FinalScrapingFailure(
                        f"Too many {self.get_items_name()}s failed to be processed: "
                        f"{len(self.error_items_keys)}"
                    )
                num_items += 1
