import pathlib
import tempfile
import urllib.parse

from zimscraperlib.i18n import get_language_details

from ifixit2zim.__about__ import __version__

ROOT_DIR = pathlib.Path(__file__).parent
NAME = ROOT_DIR.name
DEFAULT_HOMEPAGE = "Main-Page"
UNKNOWN_LOCALE = "unknown"
UNKNOWN_TITLE = "unknown_title"

SCRAPER = f"{NAME} {__version__}"

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

DEFAULT_USER_IMAGE_URLS = [
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-1.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-2.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-3.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-4.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-5.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-6.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-7.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-8.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/avatar-9.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/"
    "avatar-10.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/"
    "avatar-11.standard",
    "https://assets.cdn.ifixit.com/static/images/avatars/User/ifixit/"
    "avatar-12.standard",
]

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

TITLE = {
    "en": {
        "title_en": "iFixit in English",
        "title_fr": "iFixit in French",
        "title_pt": "iFixit in Portuguese",
        "title_de": "iFixit in German",
        "title_ko": "iFixit in Korean",
        "title_zh": "iFixit in Chinese",
        "title_ru": "iFixit in Russian",
        "title_nl": "iFixit in Dutch",
        "title_ja": "iFixit in Japanese",
        "title_tr": "iFixit in Turkish",
        "title_es": "iFixit in Spanish",
        "title_it": "iFixit in Italian",
    },
    "fr": {"title_fr": "iFixit en Français"},
}

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
    "tr": {"top_title": "Herkes tarafindan, her şey için yazilmiş tamir kilavuzlari."},
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
        "tools": "Tools",
        "parts": "Parts",
        "tools_introduction": (
            "These are some common tools used to work on this device. You might not "
            "need every tool for every procedure."
        ),
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
        "tools": "Outils",
        "parts": "Pièces",
        "tools_introduction": (
            "Voici quelques outils couramment utilisés pour travailler sur cet "
            "appareil. Vous ne devriez pas avoir besoin de tous les outils pour chaque "
            "procédure."
        ),
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
        "tools": "Ferramentas",
        "parts": "Peças",
        "tools_introduction": (
            "Estas são algumas ferramentas comuns usadas para executar trabalhos neste "
            "dispositivo. Talvez você não precise usar todas elas em cada procedimento."
        ),
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
        "tools": "Werkzeuge",
        "parts": "Ersatzteile",
        "tools_introduction": (
            "Es werden einige allgemeine Werkzeuge verwendet, um an diesem Gerät zu "
            "arbeiten. Du wirst nicht jedes Werkzeug für jeden Vorgang benötigen."
        ),
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
        "tools": "도구",
        "parts": "부품",
        "tools_introduction": "해당 기기를 고치는데 사용하는 일반 도구들 입니다. 매 단계에 모든 도구를 사용하지는 않습니다.",  # noqa E501
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
        "teardown_guides": "拆\u200b解",
        "disassembly_guides": "拆卸指南",
        "tools": "工具",
        "parts": "配件",
        "tools_introduction": "这是用于在这个设备上工作的一些常用工具。你可能不需要在每个过程中使用到每个工具。",  # noqa E501
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
        "tools": "Инструменты",
        "parts": "Запчасти",
        "tools_introduction": (
            "Вот некоторые основные инструменты, используемые для работы на данном "
            "устройстве. Вам, возможно, не понадобиться каждый инструмент для каждой "
            "процедуры."
        ),
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
        "tools": "Gereedschap",
        "parts": "Onderdelen",
        "tools_introduction": (
            "Dit is een aantal algemene gereedschappen dat gebruikt wordt om aan dit"
            " apparaat te werken. Je hebt niet elk stuk gereedschap voor elke procedure"
            " nodig."
        ),
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
        "tools": "ツール",
        "parts": "パーツ",
        "tools_introduction": "以前、このデバイスの修理に使われていた一般的な工具です。修理過程において全部の工具が必要とは限りません。",  # noqa E501
    },
    "tr": {
        "author": "Yazar: ",
        "categories_before": "",
        "categories_after": " Kategori",
        "featured_guides": "Featured Guides",  # not present for now on website ...
        "technique_guides": "Teknikler",
        "related_pages": "İlgili Sayfalar",
        "in_progress_guides": "Yapim Aşamasindaki Kilavuzlar",
        "repairability": "Onarilabilirlik:",
        "replacement_guides": "Parça Değişim Kilavuzlari",
        "teardown_guides": "Teardown'lar",
        "disassembly_guides": "Söküm Kilavuzlari",
        "tools": "Aletler",
        "parts": "Parçalar",
        "tools_introduction": (
            "Bunlar, bu cihaz için yayginca kullanilan bazi aletler. Her işlem için "
            "her alete ihtiyaciniz yoktur."
        ),
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
        "tools": "Strumenti",
        "parts": "Ricambi",
        "tools_introduction": (
            "Questi sono alcuni strumenti di uso comune usati per lavorare su questo "
            "dispositivo. Potrebbe non essere necessario ogni strumento per ogni "
            "procedura."
        ),
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
        "tools": "Herramientas",
        "parts": "Partes",
        "tools_introduction": (
            "Estas son algunas de las herramientas comunes que se utilizaron para "
            "trabajar en este dispositivo. Es posible que no necesites todas las "
            "herramientas para cada procedimiento."
        ),
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
        "comments_count_before": "",
        "comments_count_after": " comments",
        "comments_count_one": "One comment",
        "comments_stats_title": "Comments: ",
        "comments_show_more": "Load more comments",
        "tools": "Tools",
        "parts": "Parts",
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
        "comments_count_before": "",
        "comments_count_after": " commentaires",
        "comments_count_one": "Un commentaire",
        "comments_stats_title": "Commentaires : ",
        "comments_show_more": "Charger plus de commentaires",
        "tools": "Outils",
        "parts": "Pièces",
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
        "comments_count_before": "",
        "comments_count_after": " comentários",
        "comments_count_one": "Um comentário",
        "comments_stats_title": "Comentários: ",
        "comments_show_more": "Carregar mais comentários",
        "tools": "Ferramentas",
        "parts": "Peças",
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
        "comments_count_before": "",
        "comments_count_after": " Kommentare",
        "comments_count_one": "Ein Kommentar",
        "comments_stats_title": "Kommentare: ",
        "comments_show_more": "Weitere Kommentare anzeigen",
        "tools": "Werkzeuge",
        "parts": "Ersatzteile",
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
        "comments_count_before": "댓글 ",
        "comments_count_after": "개",
        "comments_count_one": "댓글 한 개",
        "comments_stats_title": "댓글 ",
        "comments_show_more": "댓글 더 불러오기",
        "tools": "도구",
        "parts": "부품",
    },
    "zh": {
        "written_by": "撰写者:",
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
        "published": "发布于:",
        "teardown": " 拆解",
        "comments_count_before": "",
        "comments_count_after": "条评论",
        "comments_count_one": "一条评论",
        "comments_stats_title": "评论: ",
        "comments_show_more": "显示更多评论",
        "tools": "工具",
        "parts": "配件",
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
        "member_since_before": "Участник c: ",
        "member_since_after": "",
        "published": "Опубликовано: ",
        "teardown": "Разбираем",
        "comments_count_before": "",
        "comments_count_after": " комментариев",
        "comments_count_one": "Один комментарий",
        "comments_stats_title": "Комментарии: ",
        "comments_show_more": "Загрузить больше комментариев",
        "tools": "Инструменты",
        "parts": "Запчасти",
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
        "comments_count_before": "",
        "comments_count_after": " commentaren",
        "comments_count_one": "Een commentaar",
        "comments_stats_title": "Reacties: ",
        "comments_show_more": "Meer commentaren laden",
        "tools": "Gereedschap",
        "parts": "Onderdelen",
    },
    "ja": {
        "written_by": "作成者:",
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
        "comments_count_before": "",
        "comments_count_after": " 件のコメント",
        "comments_count_one": "コメント1件",
        "comments_stats_title": "コメント: ",
        "comments_show_more": "コメントをさらに表示する",
        "tools": "ツール",
        "parts": "パーツ",
    },
    "tr": {
        "written_by": "Yazan:",
        "difficulty": "Zorluk",
        "steps": " Adimlar",
        "time_required": "Gerekli Süre",
        "sections": "Bölümler",
        "flags": "İşaretler",
        "introduction": "Giriş",
        "step_no_before": "Adim ",
        "step_no_after": "",
        "conclusion": "Sonuç",
        "author": "Yazar",
        "reputation": "İtibar",
        "member_since_before": "Üyelik tarihi: ",
        "member_since_after": "",
        "published": "Yayimlama: ",
        "teardown": "Teardown",
        "comments_count_before": "",
        "comments_count_after": " yorum",
        "comments_count_one": "Bir yorum",
        "comments_stats_title": "Yorumlar: ",
        "comments_show_more": "Daha fazla yorum yükle",
        "tools": "Aletler",
        "parts": "Parçalar",
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
        "comments_count_before": "",
        "comments_count_after": " commenti",
        "comments_count_one": "Un commento",
        "comments_stats_title": "Commenti: ",
        "comments_show_more": "Carica altri commenti",
        "tools": "Strumenti",
        "parts": "Ricambi",
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
        "comments_count_before": "",
        "comments_count_after": " comentarios",
        "comments_count_one": "Un comentario",
        "comments_stats_title": "Comentarios: ",
        "comments_show_more": "Cargar más comentarios",
        "tools": "Herramientas",
        "parts": "Partes",
    },
}


USER_LABELS = {
    "en": {
        "reputation": "Reputation",
        "member_since": "Member Since ",
        "member_since_after": "",
    },
    "fr": {
        "reputation": "Réputation",
        "member_since": "Membre depuis ",
        "member_since_after": "",
    },
    "pt": {
        "reputation": "Reputação",
        "member_since": "Membro desde ",
        "member_since_after": "",
    },
    "de": {
        "reputation": "Reputation",
        "member_since": "Mitglied seit ",
        "member_since_after": "",
    },
    "ko": {
        "reputation": "평판",
        "member_since_before": "",
        "member_since_after": " 부터 회원",
    },
    "zh": {
        "reputation": "信誉积分",
        "member_since_before": "",
        "member_since_after": " 注册",
    },
    "ru": {
        "reputation": "Репутация",
        "member_since_before": "Пользователь c ",
        "member_since_after": "",
    },
    "nl": {
        "reputation": "Reputatie",
        "member_since_before": "Lid sinds ",
        "member_since_after": "",
    },
    "ja": {
        "reputation": "ポイント",
        "member_since_before": "メンバー登録日 ",
        "member_since_after": "",
    },
    "tr": {
        "reputation": "İtibar",
        "member_since_before": "Üyelik tarihi: ",
        "member_since_after": "",
    },
    "it": {
        "reputation": "Reputazione",
        "member_since_before": "Membro dal ",
        "member_since_after": "",
    },
    "es": {
        "reputation": "Reputación",
        "member_since_before": "Miembro Desde ",
        "member_since_after": "",
    },
}

NOT_YET_AVAILABLE = [
    "team",
    "wiki",
    "answers",
    "contribute",
    "document",
    "help",
    "aide",
    "item",
    "mac-parts",
    "troubleshoot",
    "userwiki",
    "users",
    "stories",
    "blog",
    "ewaste",
    "pledge",
    "right",
    "manifesto",
    "tools",
    "user/contributions",
    "guide/document",
    "guide/first-look",
    "guide/how+to+sold",
    "news",
    "kits",
    "teardown",
    "vue+%c3%89clat%c3%a9e",
    "r%c3%a9ponses",
    "article",
]

UNAVAILABLE_OFFLINE = [
    "store",
    "boutique",
    "tienda",
    "products",
    "game-console-parts",
    "guide/survey",
    "upgrade/laptop",
    "search",
]

API_PREFIX = "/api/2.0"

UNAVAILABLE_OFFLINE_INFOS = ["toolkits"]


class Configuration:
    fpath: pathlib.Path

    # zim params
    name: str
    title: str
    description: str
    long_description: str | None
    author: str
    publisher: str
    fname: str
    tag: list[str]

    # filesystem
    _output_name: str
    _tmp_name: str
    output_path: pathlib.Path
    tmp_path: pathlib.Path

    required = (
        "lang_code",
        "output_path",
    )

    lang_code: str
    language: dict
    main_url: urllib.parse.ParseResult

    # customization
    icon: str
    categories: set[str]
    no_category: bool
    guides: set[str]
    no_guide: bool
    infos: set[str]
    no_info: bool
    users: set[str]
    no_user: bool
    no_cleanup: bool

    # performances
    s3_url_with_credentials: str | None

    # error handling
    max_missing_items_percent: int
    max_error_items_percent: int

    # debug/devel
    build_dir_is_tmp_dir: bool
    keep_build_dir: bool
    scrape_only_first_items: bool
    debug: bool
    delay: float
    api_delay: float
    cdn_delay: float
    stats_filename: str | None
    skip_checks: bool

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.__setattr__(key, value)
        self.main_url = Configuration.get_url(self.lang_code)
        self.language = get_language_details(self.lang_code)
        self.output_path = pathlib.Path(self._output_name).expanduser().resolve()
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.tmp_path = pathlib.Path(self._tmp_name).expanduser().resolve()
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        if self.build_dir_is_tmp_dir:
            self.build_path = self.tmp_path
        else:
            self.build_path = pathlib.Path(
                tempfile.mkdtemp(prefix=f"ifixit_{self.lang_code}_", dir=self.tmp_path)
            )

        self.stats_path = None
        if self.stats_filename:
            self.stats_path = pathlib.Path(self.stats_filename).expanduser()
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)

        # support semi-colon separated tags as well
        if self.tag:
            for tag in self.tag.copy():
                if ";" in tag:
                    self.tag += [p.strip() for p in tag.split(";")]
                    self.tag.remove(tag)

    @staticmethod
    def get_url(lang_code: str) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(URLS[lang_code])

    @property
    def domain(self) -> str:
        return self.main_url.netloc

    @property
    def api_url(self) -> str:
        return self.main_url.geturl() + API_PREFIX

    @property
    def s3_url(self) -> str | None:
        return self.s3_url_with_credentials
