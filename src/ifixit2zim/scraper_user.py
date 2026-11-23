import urllib.parse
from typing import Any

from ifixit2zim.constants import UNKNOWN_TITLE, USER_LABELS
from ifixit2zim.context import Context
from ifixit2zim.exceptions import UnexpectedDataKindExceptionError
from ifixit2zim.scraper_generic import ScraperGeneric
from ifixit2zim.shared import logger


class ScraperUser(ScraperGeneric):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.user_id_to_titles: dict[str, list[str]] = {}

    def setup(self) -> None:
        self.user_template = self.env.get_template("user.html")

    def get_items_name(self) -> str:
        return "user"

    def _add_user_to_scrape(
        self,
        userid: str,
        usertitle: str,
        is_expected: bool,  # noqa: FBT001
    ) -> None:
        self.add_item_to_scrape(
            userid,
            {
                "userid": userid,
                "usertitle": usertitle,
            },
            is_expected,
            warn_unexpected=False,
        )
        if userid in self.user_id_to_titles:
            self.user_id_to_titles[userid].append(usertitle)
        else:
            self.user_id_to_titles[userid] = [usertitle]

    def _build_user_path(self, userid: str, usertitle: str) -> str:
        href = (
            self.configuration.main_url.geturl()
            + f"/User/{userid}/{usertitle.replace('/', ' ')}"
        )
        final_href = self.processor.normalize_href(href)
        return final_href[1:]

    def get_user_link_from_obj(self, user: dict[str, Any]) -> str:
        if "userid" not in user or not user["userid"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract user id from {user}"
            )
        userid = user["userid"]
        usertitle = user["username"]
        if not usertitle:
            usertitle = "User"
        # override unknown title if needed
        if (
            userid in self.expected_items_keys
            and self.expected_items_keys[userid]["usertitle"] == UNKNOWN_TITLE
        ):
            self.expected_items_keys[userid]["usertitle"] = usertitle
        return self.get_user_link_from_props(userid=userid, usertitle=usertitle)

    def get_user_link_from_props(self, userid: str, usertitle: str) -> str:
        user_path = urllib.parse.quote(
            self._build_user_path(userid=userid, usertitle=usertitle)
        )
        if self.configuration.no_user:
            return f"home/not_scrapped?url={user_path}"
        if self.configuration.users and str(userid) not in self.configuration.users:
            return f"home/not_scrapped?url={user_path}"
        self._add_user_to_scrape(userid, usertitle, False)
        return user_path

    def build_expected_items(self) -> None:
        if self.configuration.no_user:
            logger.info("No user required")
            return
        if self.configuration.users:
            logger.info("Adding required users as expected")
            for userid in self.configuration.users:
                self._add_user_to_scrape(userid, UNKNOWN_TITLE, True)
            return
        # WE DO NOT BUILD A LIST OF EXPECTED USERS, THE LIST IS WAY TOO BIG WITH LOTS
        # OF USERS WHICH DID NOT CONTRIBUTED AND ARE HENCE NOT NEEDED IN THE ARCHIVE
        # logger.info("Downloading list of user")
        # limit = 200
        # offset = 0
        # while True:
        #     users = get_api_content("/users", limit=limit, offset=offset)
        #     if len(users) == 0:
        #         break
        #     for user in users:
        #         userid = user["userid"]
        #         self._add_user_to_scrape(userid, True)
        #     offset += limit
        # logger.info("{} user found".format(len(self.expected_items_keys)))

    def get_one_item_content(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
    ) -> Any:
        userid = item_key
        user_content = self.client.get_api_content(f"/users/{userid}")
        # other content is available in other endpoints, but not retrieved for now
        # (badges: not easy to process ; guides: does not seems to work properly)
        return user_content

    def add_item_redirect(
        self,
        item_key: str,  # noqa: ARG002
        item_data: dict[str, Any],
        redirect_kind: str,
    ) -> None:
        userid = item_data["userid"]
        usertitle = item_data["usertitle"]
        if usertitle == UNKNOWN_TITLE:
            logger.warning(f"Cannot add redirect for user {userid} in error")
            return
        path = self._build_user_path(userid, usertitle)
        self.processor.add_redirect(
            path=path,
            target_path=f"home/{redirect_kind}?{urllib.parse.urlencode({'url': path})}",
        )

    def process_one_item(
        self,
        item_key: str,  # noqa: ARG002
        item_data: dict[str, Any],
        item_content: Any,
    ) -> None:
        userid = item_data["userid"]
        usertitle = item_data["usertitle"]
        user_content = item_content

        user_rendered = self.user_template.render(
            user=user_content,
            label=USER_LABELS[self.configuration.lang_code],
            metadata=self.metadata,
        )

        normal_path = self._build_user_path(
            userid=user_content["userid"],
            usertitle=user_content["username"],
        )
        self.processor.add_html_item(
            path=normal_path,
            title=user_content["username"],
            content=user_rendered,
            is_front=False,
        )

        for other_user_title in self.user_id_to_titles[userid]:
            if other_user_title == UNKNOWN_TITLE:
                continue
            if other_user_title == usertitle:
                continue
            alternate_path = self._build_user_path(
                userid=userid,
                usertitle=other_user_title,
            )
            logger.debug(
                "Adding user redirect for alternate user path from "
                f"{alternate_path} to {normal_path}"
            )
            self.processor.add_redirect(
                path=alternate_path,
                target_path=normal_path,
            )
