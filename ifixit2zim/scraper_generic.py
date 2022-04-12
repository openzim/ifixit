import traceback
from abc import ABC, abstractmethod

from .exceptions import FinalScrapingFailure
from .shared import Global, logger


class ScraperGeneric(ABC):
    def __init__(self, add_item_methods):
        self.expected_items = dict()
        self.missing_items = dict()
        self.error_items = dict()
        self.add_item_methods = add_item_methods

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
        self.expected_items[item_key] = item_data

    def scrape_one_item(self, item_key, item_data):

        item_content = self.get_one_item_content(item_key, item_data)

        if item_content is None:
            logger.warning(f"Missing {self.get_items_name()} {item_key}")
            self.missing_items[item_key] = item_data
            return

        logger.debug(f"Processing {self.get_items_name()} {item_key}")

        self.process_one_item(item_key, item_data, item_content)

    def scrape_items(self):

        logger.info(f"Scraping {len(self.expected_items)} {self.get_items_name()}")

        num_items = 1
        for item_key, item_data in self.expected_items.items():
            try:
                logger.info(
                    f"Scraping {self.get_items_name()} {item_key} "
                    f"({num_items}/{len(self.expected_items)})"
                )
                self.scrape_one_item(item_key, item_data)
            except Exception as ex:
                self.error_items[item_key] = item_data
                logger.warning(f"Error while processing item {item_key}: {ex}")
                traceback.print_exc()
            finally:
                if (
                    len(self.missing_items) * 100 / len(self.expected_items)
                    > Global.conf.max_missing_items_percent
                ):
                    raise FinalScrapingFailure(
                        f"Too many {self.get_items_name()}s found missing: "
                        f"{len(self.missing_items)}"
                    )
                if (
                    len(self.error_items) * 100 / len(self.expected_items)
                    > Global.conf.max_error_items_percent
                ):
                    raise FinalScrapingFailure(
                        f"Too many {self.get_items_name()}s failed to be processed: "
                        f"{len(self.error_items)}"
                    )
                num_items += 1
