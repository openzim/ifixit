# -*- coding: utf-8 -*-

import pathlib
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Set

from zimscraperlib.i18n import get_language_details

ROOT_DIR = pathlib.Path(__file__).parent
NAME = ROOT_DIR.name
DEFAULT_HOMEPAGE = "Main-Page"
UNKNOWN_LOCALE = "unknown"

with open(ROOT_DIR.joinpath("VERSION"), "r") as fh:
    VERSION = fh.read().strip()

SCRAPER = f"{NAME} {VERSION}"

IMAGES_ENCODER_VERSION = 1
URLS = {
    "en": "https://www.ifixit.com",
    "fr": "https://fr.ifixit.com",
    "pt": "https://pt.ifixit.com",
    "de": "https://de.ifixit.com",
    "ru": "https://ru.ifixit.com",
    "ko": "https://ko.ifixit.com",
    "zh": "https://zh.ifixit.com",
    "nl": "https://nl.ifixit.com",
    "ja": "https://jp.ifixit.com",
    "tr": "https://tr.ifixit.com",
    "es": "https://es.ifixit.com",
    "it": "https://it.ifixit.com",
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

# Open this URL in the various languages to retrieve labels below
# https://www.ifixit.com/api/2.0/guides?guideids=219,220,202,206,46465
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

# Browse these pages in the various languages to retrieve category + guide labels
# https://www.ifixit.com/Device/Mac
# https://www.ifixit.com/Device/Apple_Watch
# https://www.ifixit.com/Device/Logitech__G502_Hero
# https://www.ifixit.com/Guide/MacBook+Air+11-Inch+Late+2010+Battery+Replacement/4384
# https://www.ifixit.com/Teardown/Apple+Watch+Teardown/40655

HOME_LABELS = {
    "en": {"top_title": "Repair guides for every thing, written by everyone."},
    "fr": {"top_title": "Tutoriels de réparation pour tout, écrits par tous."},
    "pt": {"top_title": "Guias de reparo para tudo, escritos por todos."},
    "de": {"top_title": "Reparaturanleitungen für alles, geschrieben von allen."},
    "ko": {"top_title": "모두가 작성한, 모든 것을 수리하는 안내서."},
    "zh": {"top_title": "大家齐心协力写出的包罗万象的免费修理指南。"},
    "ru": {"top_title": "Руководства по ремонту всего, от всех."},
    "nl": {"top_title": "Reparatiehandleidingen voor alles, door iedereen."},
    "ja": {"top_title": "修理を愛する人たちが作った、あらゆるモノへの修理ガイド"},
    "tr": {"top_title": "Herkes tarafından, her şey için yazılmış tamir kılavuzları."},
    "es": {"top_title": "Guías de reparación para todo, escritas por todos."},
    "it": {"top_title": "Guide di riparazione per ogni cosa, scritte da tutti."},
}
CATEGORY_LABELS = {
    "en": {
        "author": "Author: ",
        "categories_before": "",
        "categories_after": " Categories",
        "featured_guides": "Featured Guides",
        "related_pages": "Related Pages",
        "in_progress_guides": "In Progress Guides",
        "technique_guides": "Techniques",
        "repairability": "Repairability:",
        "replacement_guides": "Replacement Guides",
        "teardown_guides": "Teardowns",
        "disassembly_guides": "Disassembly Guides",
    },
    "fr": {
        "author": "Auteur: ",
        "categories_before": "",
        "categories_after": " catégories",
        "featured_guides": "Tutoriels vedettes",
        "related_pages": "Pages connexes",
        "in_progress_guides": "Tutoriels en cours",
        "technique_guides": "Techniques",
        "repairability": "Réparabilité:",
        "replacement_guides": "Tutoriels de remplacement",
        "teardown_guides": "Vues éclatées",
        "disassembly_guides": "Tutoriels de démontage",
    },
    "pt": {
        "author": "Autor: ",
        "categories_before": "",
        "categories_after": " categorias",
        "featured_guides": "Guia em destaque",
        "technique_guides": "Técnicas",
        "related_pages": "Páginas relacionadas",
        "in_progress_guides": "Guias em andamento",
        "repairability": "Reparabilidade:",
        "replacement_guides": "Guias de reposição",
        "teardown_guides": "Teardowns",
        "disassembly_guides": "Guias de Desmontagem",
    },
    "de": {
        "author": "Autor: ",
        "categories_before": "",
        "categories_after": " Kategorien",
        "featured_guides": "Empfohlene Anleitungen",
        "technique_guides": "Techniken",
        "related_pages": "Verwandte Seiten",
        "in_progress_guides": "Anleitungen in Arbeit",
        "repairability": "Reparierbarkeit:",
        "replacement_guides": "Reparaturanleitungen",
        "teardown_guides": "Teardowns",
        "disassembly_guides": "Demontageanleitungen",
    },
    "ko": {
        "author": "작성자: ",
        "categories_before": "범주 ",
        "categories_after": "개",
        "featured_guides": "주요 가이드",
        "technique_guides": "기술",
        "related_pages": "관련 페이지",
        "in_progress_guides": "작성 중인 안내서",
        "repairability": "수리 용이성:",
        "replacement_guides": "교체 가이드",
        "teardown_guides": "분해도",
        "disassembly_guides": "분해 안내서",
    },
    "zh": {
        "author": "作者: ",
        "categories_before": "",
        "categories_after": " 个类别",
        "featured_guides": "精选指南",
        "technique_guides": "技术",
        "related_pages": "相关页面",
        "in_progress_guides": "正在编写中的指南",
        "repairability": "可修复性:",
        "replacement_guides": "更换指南",
        "teardown_guides": "拆​解",
        "disassembly_guides": "拆卸指南",
    },
    "ru": {
        "author": "Автор: ",
        "categories_before": "",
        "categories_after": " категорий",
        "featured_guides": "Связанные инструкции",
        "technique_guides": "Техника",
        "related_pages": "Связанные страницы",
        "in_progress_guides": "Многоступенчатые руководства",
        "repairability": "Ремонтопригодность:",
        "replacement_guides": "Инструкции по заменам",
        "teardown_guides": "Разбираем",
        "disassembly_guides": "Инструкции по демонтажу",
    },
    "nl": {
        "author": "Auteur: ",
        "categories_before": "",
        "categories_after": " Categorieën",
        "featured_guides": "Aanbevolen Handleidingen",
        "technique_guides": "Technieken",
        "related_pages": "Gerelateerde pagina's",
        "in_progress_guides": "Handleidingen in wording",
        "repairability": "Repareerbaarheid:",
        "replacement_guides": "Vervangingshandleidingen",
        "teardown_guides": "Demontages",
        "disassembly_guides": "Demontagehandleidingen",
    },
    "ja": {
        "author": "作成者: ",
        "categories_before": "",
        "categories_after": " カテゴリー",
        "featured_guides": "おすすめのガイド",
        "technique_guides": "テクニック",
        "related_pages": "関連ページ",
        "in_progress_guides": "作成中のガイド",
        "repairability": "リペアビリティ:",
        "replacement_guides": "交換ガイド",
        "teardown_guides": "分解",
        "disassembly_guides": "分解ガイド",
    },
    "tr": {
        "author": "Yazar: ",
        "categories_before": "",
        "categories_after": " Kategori",
        "featured_guides": "Featured Guides",  # not present for now on website ...
        "technique_guides": "Teknikler",
        "related_pages": "İlgili Sayfalar",
        "in_progress_guides": "Yapım Aşamasındaki Kılavuzlar",
        "repairability": "Onarılabilirlik:",
        "replacement_guides": "Parça Değişim Kılavuzları",
        "teardown_guides": "Teardown'lar",
        "disassembly_guides": "Söküm Kılavuzları",
    },
    "it": {
        "author": "Autore: ",
        "categories_before": "",
        "categories_after": " Categorie",
        "featured_guides": "Guide In Evidenza",
        "technique_guides": "Tecniche",
        "related_pages": "Pagine Correlate",
        "in_progress_guides": "Guide in lavorazione",
        "repairability": "Riparabilità:",
        "replacement_guides": "Guide Sostituzione",
        "teardown_guides": "Smontaggi",
        "disassembly_guides": "Guide di smontaggio",
    },
    "es": {
        "author": "Autor/a: ",
        "categories_before": "",
        "categories_after": " Categorías",
        "featured_guides": "Guías Destacadas",
        "technique_guides": "Técnicas",
        "related_pages": "Páginas Relacionadas",
        "in_progress_guides": "Guías en Progreso",
        "repairability": "Reparabilidad:",
        "replacement_guides": "Guías de reemplazo",
        "teardown_guides": "Desmontajes",
        "disassembly_guides": "Guías de Desmontaje",
    },
}

GUIDE_LABELS = {
    "en": {
        "written_by": "Written By:",
        "difficulty": "Difficulty",
        "steps": "Steps",
        "time_required": " Time Required",
        "sections": "Sections",
        "flags": "Flags",
        "introduction": "Introduction",
        "step_no_before": "Step ",
        "step_no_after": "",
        "conclusion": "Conclusion",
        "author": "Author",
        "reputation": "Reputation",
        "member_since_before": "Member since: ",
        "member_since_after": "",
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
        "step_no_before": "Étape ",
        "step_no_after": "",
        "conclusion": "Conclusion",
        "author": "Auteur",
        "reputation": "Réputation",
        "member_since_before": "Membre depuis le ",
        "member_since_after": "",
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
        "step_no_before": "Passo ",
        "step_no_after": "",
        "conclusion": "Conclusão",
        "author": "Autor(a)",
        "reputation": "Reputação",
        "member_since_before": "Membro desde: ",
        "member_since_after": "",
        "published": "Publicado em: ",
        "teardown": "Teardown",
    },
    "de": {
        "written_by": "Geschrieben von:",
        "difficulty": "Schwierigkeitsgrad",
        "steps": "Schritte",
        "time_required": "Zeitaufwand",
        "sections": "Abschnitte",
        "flags": "Kennzeichnungen",
        "introduction": "Einleitung",
        "step_no_before": "Schritt ",
        "step_no_after": "",
        "conclusion": "Abschluss",
        "author": "Tinte & Feder",
        "reputation": "Reputation",
        "member_since_before": "Mitglied seit: ",
        "member_since_after": "",
        "published": "Veröffentlicht: ",
        "teardown": "Teardown",
    },
    "ko": {
        "written_by": "작성자",
        "difficulty": "난이도",
        "steps": " 단계",
        "time_required": " 소요 시간",
        "sections": "섹션",
        "flags": "플래그",
        "introduction": "소개",
        "step_no_before": "",
        "step_no_after": " 단계",
        "conclusion": "결론",
        "author": "작성자",
        "reputation": "평판",
        "member_since_before": "회원 가입일: ",
        "member_since_after": "",
        "published": "게시일: ",
        "teardown": "분해도",
    },
    "zh": {
        "written_by": "撰写者：",
        "difficulty": "难度",
        "steps": "步骤",
        "time_required": "所需时间",
        "sections": " 节",
        "flags": " 标志",
        "introduction": "简介",
        "step_no_before": "步骤 1",
        "step_no_after": "",
        "conclusion": " 结论",
        "author": "作者",
        "reputation": "信誉积分",
        "member_since_before": "",
        "member_since_after": "日注册",
        "published": "发布于：",
        "teardown": " 拆解",
    },
    "ru": {
        "written_by": "Автор:",
        "difficulty": "Сложность",
        "steps": "Шаги",
        "time_required": "Необходимое время",
        "sections": "Разделы",
        "flags": "Флаги",
        "introduction": "Введение",
        "step_no_before": "Шаг ",
        "step_no_after": "",
        "conclusion": "Заключение",
        "author": "Автор",
        "reputation": "Репутация",
        "member_since_before": "Участник с: ",
        "member_since_after": "",
        "published": "Опубликовано: ",
        "teardown": "Разбираем",
    },
    "nl": {
        "written_by": "Geschreven door:",
        "difficulty": "Moeilijkheid",
        "steps": "Stappen",
        "time_required": " Tijd vereist",
        "sections": "Secties",
        "flags": "Markeringen",
        "introduction": "Inleiding",
        "step_no_before": "Stap ",
        "step_no_after": "",
        "conclusion": "Conclusie",
        "author": "Auteur",
        "reputation": "Reputatie",
        "member_since_before": "Lid sinds: ",
        "member_since_after": "",
        "published": "Gepubliceerd: ",
        "teardown": "Uit elkaar gehaald",
    },
    "ja": {
        "written_by": "作成者：",
        "difficulty": "難易度",
        "steps": "手順",
        "time_required": "所要時間",
        "sections": "セクション",
        "flags": "フラグ",
        "introduction": "はじめに",
        "step_no_before": "手順 ",
        "step_no_after": "",
        "conclusion": "終わりに",
        "author": "作成者",
        "reputation": "ポイント",
        "member_since_before": "メンバー登録日: ",
        "member_since_after": "",
        "published": "公開日: ",
        "teardown": "分解",
    },
    "tr": {
        "written_by": "Yazan:",
        "difficulty": "Zorluk",
        "steps": " Adımlar",
        "time_required": "Gerekli Süre",
        "sections": "Bölümler",
        "flags": "İşaretler",
        "introduction": "Giriş",
        "step_no_before": "Adım ",
        "step_no_after": "",
        "conclusion": "Sonuç",
        "author": "Yazar",
        "reputation": "İtibar",
        "member_since_before": "Üyelik tarihi: ",
        "member_since_after": "",
        "published": "Yayımlama: ",
        "teardown": "Teardown",
    },
    "it": {
        "written_by": "Scritto Da:",
        "difficulty": "Difficoltà",
        "steps": "Passi",
        "time_required": "Tempo Necessario",
        "sections": "Sezioni",
        "flags": "Contrassegni",
        "introduction": "Introduzione",
        "step_no_before": "Passo ",
        "step_no_after": "",
        "conclusion": "Conclusione",
        "author": "Autore",
        "reputation": "Reputazione",
        "member_since_before": "Membro da: ",
        "member_since_after": "",
        "published": "Pubblicato: ",
        "teardown": "Smontaggio",
    },
    "es": {
        "written_by": "Escrito Por:",
        "difficulty": "Dificultad",
        "steps": "Pasos",
        "time_required": "Tiempo Requerido",
        "sections": "Secciones",
        "flags": "Banderas",
        "introduction": "Introducción",
        "step_no_before": "Paso ",
        "step_no_after": "",
        "conclusion": "Conclusión",
        "author": "Autor",
        "reputation": "Reputación",
        "member_since_before": "Miembro Desde ",
        "member_since_after": "",
        "published": "Publicado: ",
        "teardown": "Desmontaje",
    },
}


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
    no_category: Optional[bool] = False
    guides: Set[str] = field(default_factory=set)
    no_guide: Optional[bool] = False
    infos: Set[str] = field(default_factory=set)
    no_info: Optional[bool] = False

    # filesystem
    _output_dir: Optional[str] = "."
    _tmp_dir: Optional[str] = "."
    output_dir: Optional[pathlib.Path] = None
    tmp_dir: Optional[pathlib.Path] = None

    # performances
    nb_threads: Optional[int] = -1
    s3_url_with_credentials: Optional[str] = ""

    # error handling
    max_missing_items_percent: Optional[int] = 0
    max_error_items_percent: Optional[int] = 0

    # debug/devel
    build_dir_is_tmp_dir: Optional[bool] = False
    keep_build_dir: Optional[bool] = False
    scrape_only_first_items: Optional[bool] = False
    debug: Optional[bool] = False
    delay: Optional[float] = 0
    api_delay: Optional[float] = 0
    cdn_delay: Optional[float] = 0
    stats_filename: Optional[str] = None
    skip_checks: Optional[bool] = False

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

        if self.stats_filename:
            self.stats_filename = pathlib.Path(self.stats_filename).expanduser()
            self.stats_filename.parent.mkdir(parents=True, exist_ok=True)

        # support semi-colon separated tags as well
        if self.tag:
            for tag in self.tag.copy():
                if ";" in tag:
                    self.tag += [p.strip() for p in tag.split(";")]
                    self.tag.remove(tag)
