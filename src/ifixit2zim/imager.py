#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

import hashlib
import io
import pathlib
import re
import threading
import urllib.parse

from kiwixstorage import KiwixStorage, NotFoundError
from PIL import Image
from zimscraperlib.download import stream_file
from zimscraperlib.image.optimization import optimize_webp
from zimscraperlib.zim.creator import Creator

from ifixit2zim.constants import IMAGES_ENCODER_VERSION
from ifixit2zim.executor import Executor
from ifixit2zim.scraper import Configuration
from ifixit2zim.shared import logger
from ifixit2zim.utils import Utils


class Imager:
    def __init__(
        self,
        img_executor: Executor,
        lock: threading.Lock,
        creator: Creator,
        utils: Utils,
        configuration: Configuration,
    ):
        self.aborted = False
        # list of source URLs that we've processed and added to ZIM
        self.handled = set()
        self.dedup_items = {}
        self.img_executor = img_executor
        self.lock = lock
        self.creator = creator
        self.utils = utils
        self.configuration = configuration

        self.img_executor.start()

    def abort(self):
        """request imager to cancel processing of futures"""
        self.aborted = True

    def get_image_data(self, url: str) -> io.BytesIO:
        """Bytes stream of an optimized version of source image

        Bitmap images are converted to WebP and optimized
        SVG images are kept as is"""
        src, webp = io.BytesIO(), io.BytesIO()
        stream_file(url=url, byte_stream=src)

        if pathlib.Path(url).suffix == ".svg" or "/math/render/svg/" in url:
            return src

        with Image.open(src) as img:
            img.save(webp, format="WEBP")

        del src
        return optimize_webp(
            src=webp,
            lossless=False,
            quality=60,
            method=6,
        )  # pyright: ignore[reportReturnType]

    def get_path_for(self, url: urllib.parse.ParseResult) -> str:
        url_with_only_path = urllib.parse.ParseResult(
            scheme=url.scheme,
            netloc=url.netloc,
            path=url.path,
            query="",
            params="",
            fragment="",
        )
        unquoted_url = urllib.parse.unquote(url_with_only_path.geturl())
        return "images/{}".format(re.sub(r"^(https?)://", r"\1/", unquoted_url))

    def defer(self, url: str) -> str | None:
        """request full processing of url, returning in-zim path immediately"""

        # find actual URL should it be from a provider
        try:
            parsed_url = urllib.parse.urlparse(self.utils.to_url(url))
        except Exception:
            logger.warning(f"Can't parse image URL `{url}`. Skipping")
            return

        if parsed_url.scheme not in ("http", "https"):
            logger.warning(
                f"Not supporting image URL `{parsed_url.geturl()}`. Skipping"
            )
            return

        path = self.get_path_for(parsed_url)

        if path in self.handled:
            return path

        # record that we are processing this one
        self.handled.add(path)

        self.img_executor.submit(
            self.process_image,
            url=parsed_url,
            path=path,
            mimetype="image/svg+xml" if path.endswith(".svg") else "image/webp",
            dont_release=True,
        )

        return path

    def check_for_duplicate(self, path, content):
        digest = hashlib.sha256(content).digest()
        if digest in self.dedup_items:
            return self.dedup_items[digest]
        self.dedup_items[digest] = path
        return None

    def add_image_to_zim(self, path, content, mimetype):
        duplicate_path = self.check_for_duplicate(path, content)
        with self.lock:
            if duplicate_path:
                self.creator.add_redirect(
                    path=path,
                    target_path=duplicate_path,
                )
            else:
                self.creator.add_item_for(
                    path=path,
                    content=content,
                    mimetype=mimetype,
                )

    def add_missing_image_to_zim(self, path):
        with self.lock:
            self.creator.add_redirect(
                path=path,
                target_path="assets/NoImage_300x225.jpg",
            )

    def process_image(
        self, url: urllib.parse.ParseResult, path: str, mimetype: str
    ) -> str | None:
        """download image from url or S3 and add to Zim at path. Upload if req."""

        if self.aborted:
            return

        # just download, optimize and add to ZIM if not using S3
        if not self.configuration.s3_url:
            try:
                fileobj = self.get_image_data(url.geturl())
            except Exception as exc:
                logger.error(
                    f"Failed to download/convert/optim source  at {url.geturl()}",
                    exc_info=exc,
                )
                self.add_missing_image_to_zim(
                    path=path,
                )
                return path

            self.add_image_to_zim(
                path=path,
                content=fileobj.getvalue(),
                mimetype=mimetype,
            )

            return path

        # we are using S3 cache
        ident = self.utils.get_version_ident_for(url.geturl())
        if ident is None:
            logger.error(f"Unable to query {url.geturl()}. Skipping")
            self.add_missing_image_to_zim(
                path=path,
            )
            return path

        # key = self.get_s3_key_for(url.geturl())
        s3_storage = KiwixStorage(self.configuration.s3_url)
        meta = {"ident": ident, "encoder_version": str(IMAGES_ENCODER_VERSION)}

        download_failed = False  # useful to trigger reupload or not
        try:
            fileobj = io.BytesIO()
            s3_storage.download_matching_fileobj(path, fileobj, meta=meta)
            logger.debug(f"'{path}' found in S3")
        except NotFoundError:
            # don't have it, not a donwload error. we'll upload after processing
            pass
        except Exception as exc:
            logger.error(f"Failed to download '{path}' from cache", exc_info=exc)
            download_failed = True
        else:
            self.add_image_to_zim(
                path=path,
                content=fileobj.getvalue(),
                mimetype=mimetype,
            )
            return path

        # we're using S3 but don't have it or failed to download
        logger.debug(f"'{path}' not found in S3, downloading from origin")
        try:
            fileobj = self.get_image_data(url.geturl())
        except Exception as exc:
            logger.error(
                f"Failed to download/convert/optim source  at {url.geturl()}",
                exc_info=exc,
            )
            self.add_missing_image_to_zim(
                path=path,
            )
            return path

        self.add_image_to_zim(
            path=path,
            content=fileobj.getvalue(),
            mimetype=mimetype,
        )

        # only upload it if we didn't have it in cache
        if not download_failed:
            logger.debug(f"Uploading {url.geturl()} to S3::{path} with {meta}")
            try:
                s3_storage.upload_fileobj(fileobj=fileobj, key=path, meta=meta)
            except Exception as exc:
                logger.error(f"{path} failed to upload to cache", exc_info=exc)

        return path
