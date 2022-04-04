# -*- coding: utf-8 -*-

import pathlib

# import re
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Set

from zimscraperlib.i18n import get_language_details

ROOT_DIR = pathlib.Path(__file__).parent
NAME = ROOT_DIR.name
DEFAULT_HOMEPAGE = "Main-Page"
# MAX_HTTP_404_THRESHOLD = 200

with open(ROOT_DIR.joinpath("VERSION"), "r") as fh:
    VERSION = fh.read().strip()

SCRAPER = f"{NAME} {VERSION}"

IMAGES_ENCODER_VERSION = 1
# VIDEOS_ENCODER_VERSION = 1
URLS = {
    "en": "https://www.ifixit.com",
    "pt": "https://pt.ifixit.com",
}

DEFAULT_GUIDE_IMAGE_URL = (
    "https://assets.cdn.ifixit.com/static/images/"
    "default_images/GuideNoImage_300x225.jpg"
)

DEFAULT_DEVICE_IMAGE_URL = (
    "https://assets.cdn.ifixit.com/static/images/"
    "default_images/DeviceNoImage_300x225.jpg"
)

DEFAULT_WIKI_IMAGE_URL = (
    "https://assets.cdn.ifixit.com/static/images/"
    "default_images/WikiNoImage_300x225.jpg"
)

DIFFICULTY_VERY_EASY = [
    "Very easy",
    "Muito fácil",
    "Très facile",
    "Sehr einfach",
    "Muy fácil",
    "Molto facile",
    "Çok kolay",
    "とても簡単",
    "Zeer eenvoudig",
    "Очень просто",
    "아주 쉬움",
    "非常容易",
]  # guide 219
DIFFICULTY_EASY = [
    "Easy",
    "Fácil",
    "Facile",
    "Einfach",
    "Fácil",
    "Facile",
    "Kolay",
    "簡単",
    "Eenvoudig",
    "Просто",
    "쉬움",
    "简单",
]  # guide 220
DIFFICULTY_MODERATE = [
    "Moderate",
    "Moderado",
    "Modérée",
    "Mittel",
    "Moderado",
    "Moderato",
    "Orta",
    "普通",
    "Gemiddeld",
    "Средняя",
    "보통",
    "中等",
]  # guide 202
DIFFICULTY_HARD = [
    "Difficult",
    "Difícil",
    "Difficile",
    "Schwierig",
    "Difícil",
    "Difficile",
    "Zor",
    "難しい",
    "Moeilijk",
    "Сложно",
    "어려움",
    "困难",
]  # guide 206
DIFFICULTY_VERY_HARD = [
    "Very difficult",
    "Muito difícil",
    "Très difficile",
    "Sehr schwierig",
    "Muy difícil",
    "Molto difficile",
    "Çok zor",
    "とても難しい",
    "Zeer moeilijk",
    "Очень сложно",
    "매우 어려움",
    "非常困难",
]  # guide 46465
CATEGORY_LABELS = {
    "en": {
        "author": "Author: ",
        "categories": " Categories",
        "featured_guides": "Featured Guides",
        "technique_guides": "Techniques",
        "replacement_guides": "Replacement Guides",
        "teardown_guides": "Teardowns",
        "related_pages": "Related Pages",
        "in_progress_guides": "In Progress Guides",
        "disassembly_guides": "Disassembly Guides",
        "repairability": "Repairability:",
    },
    "pt": {
        "author": "Autor: ",
        "categories": " categorias",
        "featured_guides": "Guia em destaque",
        "technique_guides": "Técnicas",
        "replacement_guides": "Guias de reposição",
        "teardown_guides": "Teardowns",
        "related_pages": "Páginas relacionadas",
        "in_progress_guides": "Guias em andamento",
        "disassembly_guides": "Guias de Desmontagem",
        "repairability": "Reparabilidade:",
    },
}
# https://pt.ifixit.com/Device/Mac
# https://pt.ifixit.com/Device/Apple_Watch
# https://pt.ifixit.com/Device/Logitech__G502_Hero
# https://pt.ifixit.com/Guide/MacBook+Air+11-Inch+Late+2010+Battery+Replacement/4384

GUIDE_LABELS = {
    "en": {
        "written_by": "Written By:",
        "difficulty": "Difficulty",
        "steps": "Steps",
        "time_required": " Time Required",
        "sections": "Sections",
        "flags": "Flags",
        "introduction": "Introduction",
        "step_no": "Step ",
        "conclusion": "Conclusion",
        "author": "Author",
        "reputation": "Reputation",
        "member_since": "Member since: ",
        "published": "Published: ",
        "teardown": "Teardown",
    },
    "fr": {
        "written_by": "Rédigé par :",
        "difficulty": "Difficulté",
        "steps": "Étapes",
        "time_required": "Temps nécessaire",
        "sections": "Sections",
        "flags": "Drapeaux",
        "introduction": "Introduction",
        "step_no": "Étape ",
        "conclusion": "Conclusion",
        "author": "Auteur",
        "reputation": "Réputation",
        "member_since": "Membre depuis le ",
        "published": "Publication : ",
        "teardown": "Vue éclatée",
    },
    "pt": {
        "written_by": "Escrito Por:",
        "difficulty": "Dificuldade",
        "steps": "Passos",
        "time_required": "Tempo necessário",
        "sections": "Partes",
        "flags": "Sinalizadores",
        "introduction": "Introdução",
        "step_no": "Passo ",
        "conclusion": "Conclusão",
        "author": "Autor(a)",
        "reputation": "Reputação",
        "member_since": "Membro desde: ",
        "published": "Publicado em: ",
        "teardown": "Teardown",
    },
}

# https://pt.ifixit.com/Teardown/Apple+Watch+Teardown/40655

API_PREFIX = "/api/2.0"


@dataclass
class Conf:
    required = [
        "lang_code",
        "output_dir",
    ]

    lang_code: str = ""
    language: dict = field(default_factory=dict)
    main_url: str = ""

    # zim params
    name: str = ""
    title: Optional[str] = ""
    description: Optional[str] = ""
    author: Optional[str] = ""
    publisher: Optional[str] = ""
    fname: Optional[str] = ""
    tag: List[str] = field(default_factory=list)

    # customization
    icon: Optional[str] = ""
    categories: Set[str] = field(default_factory=set)

    # filesystem
    _output_dir: Optional[str] = "."
    _tmp_dir: Optional[str] = "."
    output_dir: Optional[pathlib.Path] = None
    tmp_dir: Optional[pathlib.Path] = None

    # performances
    nb_threads: Optional[int] = -1
    s3_url_with_credentials: Optional[str] = ""

    #     # quality
    #     without_videos: Optional[bool] = False
    #     without_external_links: Optional[bool] = False
    #     exclude: Optional[str] = ""
    #     only: Optional[str] = ""
    #     low_quality: Optional[bool] = False
    #     video_format: Optional[str] = "webm"

    # debug/devel
    build_dir_is_tmp_dir: Optional[bool] = False
    keep_build_dir: Optional[bool] = False
    debug: Optional[bool] = False
    delay: Optional[float] = 0
    api_delay: Optional[float] = 0
    cdn_delay: Optional[float] = 0
    stats_filename: Optional[str] = None
    skip_checks: Optional[bool] = False
    #     skip_footer_links: Optional[bool] = False
    #     single_article: Optional[str] = ""
    #     full_mode: Optional[bool] = False
    #     single_category: Optional[str] = None

    @staticmethod
    def get_url(lang_code: str) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(URLS[lang_code])

    @property
    def domain(self) -> str:
        return self.main_url.netloc

    @property
    def api_url(self) -> str:
        return self.main_url + API_PREFIX

    @property
    def s3_url(self) -> str:
        return self.s3_url_with_credentials

    def __post_init__(self):
        self.main_url = Conf.get_url(self.lang_code)
        self.language = get_language_details(self.lang_code)
        self.output_dir = pathlib.Path(self._output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.tmp_dir = pathlib.Path(self._tmp_dir).expanduser().resolve()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        if self.build_dir_is_tmp_dir:
            self.build_dir = self.tmp_dir
        else:
            self.build_dir = pathlib.Path(
                tempfile.mkdtemp(prefix=f"ifixit_{self.lang_code}_", dir=self.tmp_dir)
            )
        # self.build_dir.joinpath("videos").mkdir(parents=True, exist_ok=True)

        if self.stats_filename:
            self.stats_filename = pathlib.Path(self.stats_filename).expanduser()
            self.stats_filename.parent.mkdir(parents=True, exist_ok=True)

        # support semi-colon separated tags as well
        if self.tag:
            for tag in self.tag.copy():
                if ";" in tag:
                    self.tag += [p.strip() for p in tag.split(";")]
                    self.tag.remove(tag)

        self.categories = set() if self.categories is None else self.categories


#         # the solely requested category or None
#         self.single_category = (
#             re.sub(r"/$", "", list(self.categories)[0])
#             if len(self.categories) == 1
#             else None
#         )
#         # whether requesting a _full mode_ (complete wiki)
#         self.full_mode = not self.categories and not self.only and not self.exclude
