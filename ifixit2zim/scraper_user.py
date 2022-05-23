import urllib

from .constants import UNKNOWN_TITLE, USER_LABELS
from .exceptions import UnexpectedDataKindException
from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_api_content


class ScraperUser(ScraperGeneric):
    def __init__(self):
        super().__init__()
        self.user_id_to_titles = dict()

    def setup(self):
        self.user_template = Global.env.get_template("user.html")

    def get_items_name(self):
        return "user"

    def _add_user_to_scrape(self, userid, usertitle, is_expected):
        self.add_item_to_scrape(
            userid,
            {
                "userid": userid,
                "usertitle": usertitle,
            },
            is_expected,
            False,
        )
        if userid in self.user_id_to_titles:
            self.user_id_to_titles[userid].append(usertitle)
        else:
            self.user_id_to_titles[userid] = [usertitle]

    def _build_user_path(self, userid, usertitle):
        href = (
            Global.conf.main_url.geturl()
            + f"/User/{userid}/{usertitle.replace('/', ' ')}"
        )
        final_href = Global.normalize_href(href)
        return final_href[1:]

    def get_user_link_from_obj(self, user):
        if "userid" not in user or not user["userid"]:
            raise UnexpectedDataKindException(
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

    def get_user_link_from_props(self, userid, usertitle):
        user_path = urllib.parse.quote(
            self._build_user_path(userid=userid, usertitle=usertitle)
        )
        if Global.conf.no_user:
            return f"home/not_scrapped?url={user_path}"
        if Global.conf.users and str(userid) not in Global.conf.users:
            return f"home/not_scrapped?url={user_path}"
        self._add_user_to_scrape(userid, usertitle, False)
        return user_path

    def build_expected_items(self):
        if Global.conf.no_user:
            logger.info("No user required")
            return
        if Global.conf.users:
            logger.info("Adding required users as expected")
            for userid in Global.conf.users:
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

    def get_one_item_content(self, item_key, item_data):
        userid = item_key
        user_content = get_api_content(f"/users/{userid}")
        # other content is available in other endpoints, but not retrieved for now
        # (badges: not easy to process ; guides: does not seems to work properly)
        return user_content

    def add_item_redirect(self, item_key, item_data, redirect_kind):
        userid = item_data["userid"]
        usertitle = item_data["usertitle"]
        if usertitle == UNKNOWN_TITLE:
            logger.warning(f"Cannot add redirect for user {userid} in error")
            return
        path = self._build_user_path(userid, usertitle)
        Global.add_redirect(
            path=path,
            target_path=f"home/{redirect_kind}?{urllib.parse.urlencode({'url':path})}",
        )

    def process_one_item(self, item_key, item_data, item_content):
        userid = item_data["userid"]
        usertitle = item_data["usertitle"]
        user_content = item_content

        user_rendered = self.user_template.render(
            user=user_content,
            label=USER_LABELS[Global.conf.lang_code],
            metadata=Global.metadata,
        )

        normal_path = self._build_user_path(
            userid=user_content["userid"],
            usertitle=user_content["username"],
        )
        Global.add_html_item(
            path=normal_path,
            title=user_content["username"],
            content=user_rendered,
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
            Global.add_redirect(
                path=alternate_path,
                target_path=normal_path,
            )
