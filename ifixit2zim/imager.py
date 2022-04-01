#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import io
import pathlib
import re
import urllib.parse
from typing import Optional

from kiwixstorage import KiwixStorage, NotFoundError
from PIL import Image
from zimscraperlib.download import stream_file
from zimscraperlib.image.optimization import optimize_webp

from .constants import IMAGES_ENCODER_VERSION
from .shared import Global
from .utils import get_digest, get_version_ident_for, normalize_ident, to_url

logger = Global.logger


class Imager:
    def __init__(self):
        self.aborted = False
        # list of source URLs that we've processed and added to ZIM
        self.handled = set()
        self.nb_requested = 0
        self.nb_done = 0

        Global.img_executor.start()

    def abort(self):
        """request imager to cancel processing of futures"""
        self.aborted = True

    def get_image_data(self, url: str) -> io.BytesIO:
        """Bytes stream of an optimized version of source image

        Bitmap images are converted to WebP and optimized
        SVG images are kept as is"""
        src, webp = io.BytesIO(), io.BytesIO()
        # logger.debug(f"retrieving {url}")
        stream_file(url=url, byte_stream=src)

        if pathlib.Path(url).suffix == ".svg" or "/math/render/svg/" in url:
            return src

        with Image.open(src) as img:
            img.save(webp, format="WEBP")
        # digest = get_digest(url)
        # with open(f"/tmp/{digest}.jpg", 'wb') as f:
        #     src.seek(0)
        #     f.write(src.read())
        # with open(f"/tmp/{digest}.webp", 'wb') as f:
        #     webp.seek(0)
        #     f.write(webp.read())
        del src
        return optimize_webp(
            src=webp,
            lossless=False,
            quality=60,
            method=6,
        )

    def get_s3_key_for(self, url: str) -> str:
        """S3 key to use for that url"""
        return re.sub(r"^(https?)://", r"\1/", url)

    def get_path_for(self, url: urllib.parse.ParseResult) -> str:
        suffix = ".svg" if url.path.endswith(".svg") else ".webp"
        digest = get_digest(url.geturl())
        return f"images/{digest}-{normalize_ident(pathlib.Path(url.path).stem)}{suffix}"

    def defer(
        self,
        url: str,
        path: Optional[str] = None,
    ) -> str:
        """request full processing of url, returning in-zim path immediately"""

        # find actual URL should it be from a provider
        try:
            url = urllib.parse.urlparse(to_url(url))
        except Exception:
            logger.warning(f"Can't parse image URL `{url}`. Skipping")
            return

        if url.scheme not in ("http", "https"):
            logger.warning(f"Not supporting image URL `{url.geturl()}`. Skipping")
            return

        # skip processing if we already processed it or have it in pipe
        digest = get_digest(url.geturl())
        path = self.get_path_for(url) if path is None else path

        if digest in self.handled:
            logger.debug(f"URL `{url.geturl()}` already processed.")
            return path

        # record that we are processing this one
        self.handled.add(digest)
        self.nb_requested += 1

        Global.img_executor.submit(
            self.process_image,
            url=url,
            path=path,
            mimetype="image/svg+xml" if path.endswith(".svg") else "image/webp",
            dont_release=True,
        )

        return path

    def once_done(self):
        """default callback for single image processing"""
        self.nb_done += 1
        logger.debug(f"Images {self.nb_done}/{self.nb_requested}")

    def process_image(self, url: str, path: str, mimetype: str) -> str:
        """download image from url or S3 and add to Zim at path. Upload if req."""

        if self.aborted:
            return

        # just download, optimize and add to ZIM if not using S3
        if not Global.conf.s3_url:
            with Global.lock:
                Global.creator.add_item_for(
                    path=path,
                    content=self.get_image_data(url.geturl()).getvalue(),
                    mimetype=mimetype,
                    callback=self.once_done,
                )
            return path

        # we are using S3 cache
        ident = get_version_ident_for(url.geturl())
        if ident is None:
            logger.error(f"Unable to query {url.geturl()}. Skipping")
            return path

        key = self.get_s3_key_for(url.geturl())
        s3_storage = KiwixStorage(Global.conf.s3_url)
        meta = {"ident": ident, "encoder_version": str(IMAGES_ENCODER_VERSION)}

        download_failed = False  # useful to trigger reupload or not
        try:
            logger.debug(f"Attempting download of S3::{key} into ZIM::{path}")
            fileobj = io.BytesIO()
            s3_storage.download_matching_fileobj(key, fileobj, meta=meta)
        except NotFoundError:
            # don't have it, not a donwload error. we'll upload after processing
            pass
        except Exception as exc:
            logger.error(f"failed to download {key} from cache: {exc}")
            logger.exception(exc)
            download_failed = True
        else:
            with Global.lock:
                Global.creator.add_item_for(
                    path=path,
                    content=fileobj.getvalue(),
                    mimetype=mimetype,
                    callback=self.once_done,
                )
            return path

        # we're using S3 but don't have it or failed to download
        try:
            fileobj = self.get_image_data(url.geturl())
        except Exception as exc:
            logger.error(f"Failed to download/convert/optim source  at {url.geturl()}")
            logger.exception(exc)
            return path

        with Global.lock:
            Global.creator.add_item_for(
                path=path,
                content=fileobj.getvalue(),
                mimetype=mimetype,
                callback=self.once_done,
            )

        # only upload it if we didn't have it in cache
        if not download_failed:
            logger.debug(f"Uploading {url.geturl()} to S3::{key} with {meta}")
            try:
                s3_storage.upload_fileobj(fileobj=fileobj, key=key, meta=meta)
            except Exception as exc:
                logger.error(f"{key} failed to upload to cache: {exc}")

        return path
