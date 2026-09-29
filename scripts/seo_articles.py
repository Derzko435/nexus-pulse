"""Editorial SEO articles under guides/<slug>/ (standard library only, no network).

Four long-read pages that are rendered by scripts/build_static_pages.py together with the other
static pages (same layout, header, footer, sitemap entry, write-only-if-changed):

  guides/game-length/    — «Сколько часов проходить игру» (HowLongToBeat hours)
  guides/russian-voice/  — «Игры с русской озвучкой 2026» (Steam language table)
  guides/steam-refund/   — «Как вернуть игру в Steam» (Valve refund policy FAQ)
  guides/local-coop/     — «Игры на двоих на одном ПК» (Steam local co-op categories)

Every number here was checked by hand on CHECKED_ISO (see the source notes on each page). The data is
a frozen snapshot on purpose: re-check the sources before changing a number. Games that are not
in the catalog (app.js GAMES) are shown without a catalog link; catalog games link to games/<id>/.
"""
from __future__ import annotations

import html
import json
import re

CHECKED = "29 сентября 2026 года"
CHECKED_ISO = "2026-09-29"
SALE = "1–8 октября 2026"  # Steam Autumn Sale 2026 (partner.steamgames.com, starts 10:00 PT = 20:00 МСК)
R = "../../"  # every article lives at guides/<slug>/

HLTB_URL = "https://howlongtobeat.com/game/{}"
STEAM_URL = "https://store.steampowered.com/app/{}/"
REFUND_URL = "https://store.steampowered.com/steam_refunds/"
REFUND_METHODS_URL = "https://store.steampowered.com/steam_refunds_methods"
SALE_URL = "https://partner.steamgames.com/doc/marketing/upcoming_events/2026_autumn_sale"
REMOTE_PLAY_URL = "https://store.steampowered.com/remoteplay"

# Steam appdetails (l=russian), checked 2026-09-29: appid -> (voice, local, ru_store)
#   voice: 'audio' = русский в колонке «Озвучка», 'text' = только интерфейс/субтитры, '' = русского нет
#   local: 'coop' = «Кооператив (общий/разделённый экран)», 'pvp' = «Игрок против игрока (общий/разделённый экран)», 'both', 'screen' = только «Общий/разделённый экран», '' = нет
#   ru_store (appdetails cc=ru): 'price' = есть цена в ₽, 'free' = бесплатная, 'none' = без цены, 'no' = страница недоступна для региона RU
STEAM = {
    620: ('audio', 'coop', 'price'),  # Portal 2
    204360: ('text', 'both', 'price'),  # Castle Crashers®
    238370: ('text', 'screen', 'price'),  # Magicka 2
    242550: ('audio', 'coop', 'no'),  # Rayman® Legends
    250760: ('text', 'both', 'price'),  # Shovel Knight: Treasure Trove
    251470: ('', 'both', 'price'),  # TowerFall Ascension
    252110: ('text', 'coop', 'price'),  # Lovers in a Dangerous Spacetime
    252950: ('text', 'both', 'none'),  # Rocket League®
    268910: ('text', 'coop', 'price'),  # Cuphead
    271590: ('text', '', ''),  # Grand Theft Auto V Legacy
    285900: ('', 'pvp', 'price'),  # Gang Beasts
    286690: ('audio', '', 'none'),  # Metro 2033 Redux
    289070: ('audio', 'pvp', 'no'),  # Sid Meier’s Civilization® VI
    291550: ('text', 'both', 'free'),  # Brawlhalla
    292030: ('audio', '', 'no'),  # Ведьмак 3: Дикая Охота — Обновлённое издание
    311690: ('text', 'screen', 'price'),  # Enter the Gungeon
    313690: ('text', 'screen', 'no'),  # LEGO® Batman™ 3: Beyond Gotham
    330020: ('text', 'coop', 'price'),  # Children of Morta
    359550: ('audio', '', 'no'),  # Tom Clancy's Rainbow Six Siege
    386940: ('audio', 'both', 'price'),  # Ultimate Chicken Horse
    412020: ('audio', '', 'no'),  # Metro Exodus
    413150: ('text', 'coop', 'price'),  # Stardew Valley
    435150: ('text', 'both', 'price'),  # Divinity: Original Sin 2 - Definitive Edition
    471550: ('text', 'coop', 'price'),  # Nine Parchments
    471810: ('text', 'both', 'price'),  # Death Squared
    477160: ('text', 'coop', 'price'),  # Human Fall Flat
    489830: ('audio', '', 'no'),  # The Elder Scrolls V: Skyrim Special Edition
    534380: ('audio', '', 'no'),  # Dying Light 2 Stay Human: Reloaded Edition
    534550: ('text', 'coop', 'price'),  # Guacamelee! 2
    609110: ('text', 'both', 'price'),  # Blazing Chrome
    668580: ('audio', '', 'price'),  # Atomic Heart
    728880: ('text', 'both', 'no'),  # Overcooked! 2
    782330: ('audio', '', 'no'),  # DOOM Eternal
    814380: ('text', '', ''),  # Sekiro™: Shadows Die Twice - GOTY Edition
    870780: ('text', '', ''),  # CONTROL Ultimate Edition
    905340: ('text', 'both', 'price'),  # Heave Ho
    920210: ('text', 'coop', 'no'),  # LEGO® Звездные Войны™: Скайуокер. Сага
    972660: ('text', 'coop', 'price'),  # Издание Spiritfarer®: Farewell
    985890: ('text', 'both', 'price'),  # Streets of Rage 4
    990080: ('text', '', ''),  # Хогвартс. Наследие
    996770: ('text', 'coop', 'no'),  # Moving Out
    1004490: ('text', 'coop', 'no'),  # Tools Up!
    1016920: ('text', 'both', 'price'),  # Unrailed!
    1030840: ('audio', '', 'no'),  # Mafia: Definitive Edition
    1071870: ('text', 'coop', 'price'),  # Biped
    1085660: ('audio', '', 'free'),  # Destiny 2
    1086940: ('text', '', ''),  # Baldur's Gate 3
    1091500: ('audio', '', 'no'),  # Cyberpunk 2077
    1145360: ('text', '', ''),  # Hades
    1172470: ('audio', '', 'free'),  # Apex Legends™
    1174180: ('text', '', ''),  # Red Dead Redemption 2
    1196590: ('audio', '', 'no'),  # Resident Evil Village
    1222700: ('text', 'coop', 'no'),  # A Way Out
    1225570: ('', 'coop', 'no'),  # Unravel Two
    1237970: ('audio', '', 'no'),  # Titanfall® 2
    1240440: ('audio', '', 'no'),  # Halo Infinite
    1243830: ('text', 'both', 'no'),  # Overcooked! All You Can Eat
    1245620: ('text', '', ''),  # ELDEN RING
    1259420: ('audio', '', 'no'),  # Days Gone
    1285190: ('text', '', ''),  # Borderlands 4
    1313140: ('text', 'coop', 'price'),  # Cult of the Lamb
    1328670: ('text', '', ''),  # Mass Effect™ издание Legendary
    1364780: ('text', 'pvp', 'no'),  # Street Fighter™ 6
    1426210: ('text', 'coop', 'none'),  # It Takes Two
    1436700: ('text', 'coop', 'price'),  # Trine 5: A Clockwork Conspiracy
    1509960: ('', 'coop', 'price'),  # PICO PARK
    1551360: ('text', '', ''),  # Forza Horizon 5
    1599600: ('text', 'coop', 'price'),  # PlateUp!
    1599660: ('audio', 'coop', 'no'),  # Сэкбой™: Большое приключение
    1627720: ('text', '', ''),  # Lies of P
    1641700: ('text', 'coop', 'no'),  # Moving Out 2
    1643320: ('text', '', ''),  # S.T.A.L.K.E.R. 2: Heart of Chornobyl
    1659420: ('audio', '', 'no'),  # UNCHARTED™: Наследие воров. Коллекция
    1672970: ('text', 'coop', 'no'),  # Minecraft Dungeons
    1687950: ('', '', ''),  # Persona 5 Royal
    1693980: ('', '', ''),  # Dead Space
    1716740: ('', '', ''),  # Starfield
    1771300: ('text', '', ''),  # Kingdom Come: Deliverance II
    1774580: ('', '', ''),  # STAR WARS Jedi: Survivor™
    1778820: ('text', 'pvp', 'price'),  # TEKKEN 8
    1817070: ('audio', '', 'no'),  # Marvel’s Spider-Man Remastered
    1850570: ('audio', '', 'price'),  # DEATH STRANDING DIRECTOR'S CUT
    1888930: ('audio', '', 'no'),  # Одни из нас™: Часть I
    1895880: ('audio', '', 'no'),  # Ratchet & Clank: Сквозь миры
    1903340: ('text', '', ''),  # Clair Obscur: Expedition 33
    1941540: ('audio', '', 'no'),  # Mafia: The Old Country
    1971870: ('text', 'pvp', 'no'),  # Mortal Kombat 1
    2001120: ('', 'coop', 'no'),  # Split Fiction
    2050650: ('audio', '', 'no'),  # Resident Evil 4
    2124490: ('text', '', ''),  # SILENT HILL 2
    2153350: ('text', 'coop', 'price'),  # Brothers: A Tale of Two Sons Remake
    2183900: ('audio', '', 'price'),  # Warhammer 40,000: Space Marine 2
    2208920: ('audio', '', 'no'),  # Assassin's Creed Valhalla
    2215430: ('audio', '', 'no'),  # Призрак Цусимы: Режиссёрская версия
    2246340: ('audio', '', 'no'),  # Monster Hunter Wilds
    2322010: ('audio', '', 'no'),  # God of War Рагнарёк
    2344520: ('audio', '', 'no'),  # Diablo® IV
    2357570: ('audio', '', 'free'),  # Overwatch®
    2358720: ('text', '', ''),  # Black Myth: Wukong
    2369390: ('audio', '', 'no'),  # Far Cry® 6
    2379780: ('', '', ''),  # Balatro
    2420110: ('audio', '', 'no'),  #  Полное издание «Horizon Запретный Запад»
    2461850: ('text', '', ''),  # Hellblade II: Senua’s Saga
    2488620: ('', 'pvp', 'no'),  # F1® 24
    2519060: ('audio', '', 'none'),  # Call of Duty®: Modern Warfare® III
    2531310: ('audio', '', 'no'),  # Одни из нас™: Часть II Обновленная версия
    2561580: ('audio', '', 'no'),  # Horizon Zero Dawn™ Remastered
    2651280: ('audio', '', 'no'),  # Marvel Человек-Паук 2
    2669320: ('audio', 'both', 'none'),  # EA SPORTS FC™ 25
    2677660: ('text', '', ''),  # Indiana Jones and the Great Circle
    3008130: ('audio', '', 'no'),  # Dying Light: The Beast
    3017860: ('audio', '', 'no'),  # DOOM: The Dark Ages
    3159330: ('text', '', ''),  # Assassin’s Creed Shadows
    3280350: ('audio', '', 'no'),  # DEATH STRANDING 2: ON THE BEACH
    3405690: ('text', 'both', 'no'),  # EA SPORTS FC™ 26
    3489700: ('text', '', ''),  # Stellar Blade™
    4384550: ('text', '', ''),  # Call of Duty®: Black Ops 6
}
# HowLongToBeat game pages (howlongtobeat.com/game/<id>), checked 2026-09-29: key -> (hltb_id, main, main+extras, 100%, polls main)
HLTB = {
    'cp2077': (2127, 26.1, 63.2, 109.0, 2089),  # Cyberpunk 2077
    'elden': (68151, 60.1, 101.3, 136.2, 1751),  # Elden Ring
    'bg3': (68033, 73.1, 117.2, 181.3, 682),  # Baldur's Gate 3
    'witcher3': (10270, 51.7, 103.8, 175.3, 2729),  # The Witcher 3: Wild Hunt
    'rdr2': (27100, 50.7, 84.6, 195.5, 2471),  # Red Dead Redemption 2
    'gtav': (4064, 32.1, 51.2, 89.5, 3361),  # Grand Theft Auto V
    'skyrim': (14996, 25.9, 110.7, 203.2, 497),  # The Elder Scrolls V: Skyrim - Special Edition
    'wukong': (82089, 37.7, 48.4, 67.5, 296),  # Black Myth: Wukong
    'persona5': (66630, 101.3, 122.6, 140.5, 1595),  # Persona 5 Royal
    'diablo4': (71960, 25.8, 48.9, 195.3, 554),  # Diablo IV
    'doom': (57506, 14.5, 20.6, 29.8, 1450),  # Doom Eternal
    'halo': (57454, 11.3, 19.5, 29.2, 522),  # Halo Infinite
    'codmw': (132689, 5.5, 7.6, 19.6, 411),  # Call of Duty: Modern Warfare III
    'titanfall2': (38000, 6.1, 8.3, 16.1, 3363),  # Titanfall 2
    'ultrakill': (75153, 6.5, 14.6, 46.9, 163),  # ULTRAKILL
    'xcom2': (28279, 33.2, 48.1, 89.5, 351),  # XCOM 2
    'civ6': (37867, 23.3, 100.8, 387.6, 224),  # Sid Meier's Civilization VI
    'rimworld': (24212, 65.6, 109.1, 279.3, 77),  # RimWorld
    'hollow': (26286, 27.0, 41.6, 65.6, 2753),  # Hollow Knight
    'hades': (62941, 23.6, 48.6, 95.2, 2809),  # Hades
    'celeste': (42818, 8.3, 14.7, 39.2, 3573),  # Celeste
    'stardew': (34716, 53.4, 94.9, 172.6, 585),  # Stardew Valley
    'hades2': (118218, 32.0, 53.2, 104.6, 420),  # Hades II
    'balatro': (132112, 7.7, 46.4, 251.0, 896),  # Balatro
    'vampire': (102750, 16.4, 30.1, 58.2, 406),  # Vampire Survivors
    'outerwilds': (57527, 17.1, 22.7, 29.2, 887),  # Outer Wilds
    're4': (108881, 16.2, 21.7, 64.5, 1800),  # Resident Evil 4
    'reVillage': (80038, 9.8, 12.9, 38.4, 2105),  # Resident Evil Village
    'alanwake2': (101237, 19.1, 26.3, 32.6, 605),  # Alan Wake 2
    'deadspace': (95927, 12.2, 16.2, 30.2, 758),  # Dead Space
    'forza5': (93948, 21.3, 46.6, 143.6, 371),  # Forza Horizon 5
    'gow': (83146, 26.6, 40.7, 55.7, 1460),  # God of War: Ragnarök
    'spiderman2': (79769, 17.2, 23.9, 28.6, 887),  # Marvel's Spider-Man 2
    'sekiro': (57415, 30.3, 43.0, 69.9, 1214),  # Sekiro: Shadows Die Twice
    'mhwilds': (141854, 18.1, 45.6, 114.7, 481),  # Monster Hunter Wilds
    'hogwarts': (83145, 26.7, 45.3, 72.2, 1108),  # Hogwarts Legacy
    'acvalhalla': (77729, 61.3, 99.5, 152.7, 641),  # Assassin's Creed Valhalla
    'totk': (72589, 59.3, 117.2, 247.5, 703),  # The Legend of Zelda: Tears of the Kingdom
    'silksong': (65945, 28.3, 47.3, 65.5, 571),  # Hollow Knight: Silksong
    'clair': (152016, 29.3, 46.3, 68.8, 2053),  # Clair Obscur: Expedition 33
    'kcd2': (148973, 55.5, 100.8, 146.1, 122),  # Kingdom Come: Deliverance II
    'liesofp': (92418, 28.3, 36.3, 58.2, 774),  # Lies of P
    'indiana': (144234, 16.2, 25.8, 39.3, 501),  # Indiana Jones and the Great Circle
    'ittakestwo': (80199, 12.8, 14.2, 16.5, 1781),  # It Takes Two
    'splitfiction': (160592, 13.8, 14.7, 16.2, 472),  # Split Fiction
    'cuphead': (21680, 10.6, 16.1, 28.0, 1165),  # Cuphead
    'portal2': (7231, 8.6, 13.8, 22.9, 5539),  # Portal 2
    'metroexodus': (46401, 15.9, 24.0, 41.8, 850),  # Metro Exodus
    'atomicheart': (56297, 16.2, 25.1, 37.7, 571),  # Atomic Heart
    'ghost': (51225, 25.1, 46.3, 62.5, 1111),  # Ghost of Tsushima
    'tlou1': (109104, 14.3, 18.0, 24.5, 1281),  # The Last of Us Part I
    'hfw': (79775, 28.7, 62.8, 89.9, 551),  # Horizon Forbidden West
    'dsdc': (93457, 38.3, 59.4, 111.8, 687),  # Death Stranding: Director's Cut
}


# ---------------------------------------------------------------- helpers
def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def hrs(x) -> str:
    return (f"{x:.1f}".replace(".", ",") + "\u00a0ч") if x else "—"


def num(x) -> str:
    return f"{x:.1f}".replace(".", ",")


def plural(n, a, b, c):
    return a if n % 10 == 1 and n % 100 != 11 else b if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else c


def ext(url: str, text: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'


def and_join(names: list) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " и " + names[-1] if names else ""


def plain_text(body: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def word_count(body: str) -> int:
    return len(re.findall(r"[\w'’-]+", plain_text(body)))


def table(head: list, rows: list, cls: str = "sp-table") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    return f'<div class="sp-table-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def toc_html(items: list) -> str:
    return '<nav class="guide-toc sp-toc" aria-label="Содержание"><p>Содержание</p><ol>' + "".join(
        f'<li><a href="#{a}">{e(b)}</a></li>' for a, b in items) + "</ol></nav>"


def faq_html(faq: list, anchor: str) -> str:
    return (f'<section class="guide-sec ed-faq" id="{anchor}"><h2>Частые вопросы</h2>'
            + "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faq) + "</section>")


def aside(quick: list, useful: list) -> str:
    li = lambda items: '<ul class="sp-links">' + "".join(  # noqa: E731
        f'<li><a href="{e(h)}">{e(t)}</a>' + (f' <span class="sp-note">{e(n)}</span>' if n else "") + "</li>" for h, t, n in items) + "</ul>"
    return f'<aside class="sp-aside glass">\n<h2 class="sp-h2">На этой странице</h2>\n{li(quick)}\n<h2 class="sp-h2">Полезное</h2>\n{li(useful)}\n</aside>'


VOICE = {"audio": "озвучка + текст", "text": "только текст", "": "нет"}
LOCAL = {"coop": "кооператив", "pvp": "PvP", "both": "кооператив и PvP", "screen": "общий экран", "": "—"}
STORE = {"price": "продаётся", "free": "бесплатно", "none": "без цены", "no": "нет в регионе", "": "—"}

# the four articles (slug, short name for hubs / cross links, card blurb)
ARTICLES = [
    ("game-length", "Сколько часов проходить игру", "Время прохождения популярных игр по данным HowLongToBeat: сюжет, сюжет с допами и 100%. Таблицы для выбора игр к распродаже Steam."),
    ("russian-voice", "Игры с русской озвучкой 2026", "Список игр с полной русской озвучкой, проверенный по таблице языков Steam, и хиты, где русский есть только в субтитрах."),
    ("steam-refund", "Как вернуть игру в Steam", "Правила возврата 14 дней и 2 часа, пошаговая заявка через help.steampowered.com, предзаказы, DLC, подарки и российские аккаунты."),
    ("local-coop", "Игры на двоих на одном ПК", "Локальный кооператив и разделённый экран на одном компьютере: сюжетные игры, пати-хаос, экшены и файтинги с проверкой по Steam."),
]


def cross_links(cur: str) -> list:
    return [(f"{R}guides/{s}/", n, "") for s, n, _ in ARTICLES if s != cur]


def game_link(gid, title: str, games_by_id: dict) -> str:
    if gid and gid in games_by_id:
        return f'<a href="{R}games/{e(gid)}/">{e(title)}</a>'
    return e(title)


def article_ld(site: str, path: str, headline: str, desc: str, section: str, words: int, og_image: str, publisher: dict, sources: list) -> dict:
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline[:110], "description": desc, "inLanguage": "ru",
            "articleSection": section, "url": site + path, "mainEntityOfPage": site + path, "image": og_image,
            "author": publisher, "publisher": publisher, "wordCount": words, "citation": sources}


def faq_ld(faq: list) -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


# ================================================================ 1. game-length
# key (HLTB dict) -> display title, catalog id (app.js GAMES) or None, note
GL_GAMES = {
    "persona5": ("Persona 5 Royal", "persona5", ""),
    "bg3": ("Baldur's Gate 3", "bg3", ""),
    "acvalhalla": ("Assassin's Creed Valhalla", "acvalhalla", "без дополнений"),
    "elden": ("Elden Ring", "elden", "без Shadow of the Erdtree"),
    "totk": ("Zelda: Tears of the Kingdom", "totk", "только консоли Nintendo"),
    "kcd2": ("Kingdom Come: Deliverance II", None, "вышла в 2025 году"),
    "witcher3": ("The Witcher 3: Wild Hunt", "witcher3", "без дополнений"),
    "rdr2": ("Red Dead Redemption 2", "rdr2", "сюжетный режим"),
    "dsdc": ("Death Stranding Director's Cut", None, ""),
    "wukong": ("Black Myth: Wukong", "wukong", ""),
    "gtav": ("GTA V", "gtav", "сюжет, без GTA Online"),
    "clair": ("Clair Obscur: Expedition 33", None, "вышла в 2025 году"),
    "hfw": ("Horizon Forbidden West", None, "без Burning Shores"),
    "liesofp": ("Lies of P", None, "без Overture"),
    "sekiro": ("Sekiro: Shadows Die Twice", "sekiro", ""),
    "hogwarts": ("Hogwarts Legacy", "hogwarts", ""),
    "gow": ("God of War Ragnarök", "gow", "без Valhalla"),
    "cp2077": ("Cyberpunk 2077", "cp2077", "без Phantom Liberty"),
    "skyrim": ("The Elder Scrolls V: Skyrim", "skyrim", "Special Edition"),
    "ghost": ("Ghost of Tsushima", None, "без острова Ики"),
    "diablo4": ("Diablo IV", "diablo4", "кампания"),
    "forza5": ("Forza Horizon 5", "forza5", "без дополнений"),
    "mhwilds": ("Monster Hunter Wilds", "mhwilds", ""),
    "alanwake2": ("Alan Wake 2", "alanwake2", ""),
    "spiderman2": ("Marvel's Spider-Man 2", "spiderman2", ""),
    "re4": ("Resident Evil 4 (2023)", "re4", "ремейк"),
    "indiana": ("Indiana Jones and the Great Circle", None, ""),
    "atomicheart": ("Atomic Heart", None, "без дополнений"),
    "metroexodus": ("Metro Exodus", None, "без дополнений"),
    "doom": ("DOOM Eternal", "doom", "без The Ancient Gods"),
    "tlou1": ("The Last of Us Part I", None, ""),
    "splitfiction": ("Split Fiction", None, "только кооператив"),
    "ittakestwo": ("It Takes Two", None, "только кооператив"),
    "deadspace": ("Dead Space (2023)", "deadspace", "ремейк"),
    "halo": ("Halo Infinite", "halo", "кампания"),
    "cuphead": ("Cuphead", None, "без The Delicious Last Course"),
    "reVillage": ("Resident Evil Village", "reVillage", "без Shadows of Rose"),
    "portal2": ("Portal 2", None, "одиночная кампания"),
    "ultrakill": ("ULTRAKILL", "ultrakill", ""),
    "titanfall2": ("Titanfall 2", "titanfall2", "кампания"),
    "codmw": ("Call of Duty: Modern Warfare III", "codmw", "кампания"),
    "silksong": ("Hollow Knight: Silksong", None, "вышла в 2025 году"),
    "hollow": ("Hollow Knight", "hollow", ""),
    "stardew": ("Stardew Valley", "stardew", "песочница"),
    "hades2": ("Hades II", "hades2", "роглайк"),
    "hades": ("Hades", "hades", "роглайк"),
    "outerwilds": ("Outer Wilds", "outerwilds", "без Echoes of the Eye"),
    "vampire": ("Vampire Survivors", "vampire", "роглайк"),
    "celeste": ("Celeste", "celeste", ""),
    "balatro": ("Balatro", "balatro", "роглайк"),
    "rimworld": ("RimWorld", "rimworld", "мало отчётов"),
    "xcom2": ("XCOM 2", "xcom2", "без War of the Chosen"),
    "civ6": ("Civilization VI", "civ6", "одна партия"),
}
GL_GROUPS = [
    ("gl-rpg", "Большие RPG и открытые миры",
     "Игры, на которые уйдёт месяц вечеров и больше. Отсортированы по времени на сюжет: сверху самые длинные.",
     ["persona5", "bg3", "acvalhalla", "elden", "totk", "kcd2", "witcher3", "rdr2", "dsdc", "wukong", "gtav", "clair", "hfw", "liesofp",
      "sekiro", "hogwarts", "gow", "cp2077", "skyrim", "ghost", "diablo4", "forza5", "mhwilds"]),
    ("gl-short", "Экшены, хорроры и шутеры на несколько вечеров",
     "Сюжет до 20 часов: такие игры реально пройти за одну-две недели, даже если играть только по вечерам.",
     ["alanwake2", "spiderman2", "re4", "indiana", "atomicheart", "metroexodus", "doom", "tlou1", "splitfiction", "ittakestwo", "deadspace",
      "halo", "cuphead", "reVillage", "portal2", "ultrakill", "titanfall2", "codmw"]),
    ("gl-indie", "Инди, метроидвании и роглайки",
     "У роглайков (Hades, Balatro, Vampire Survivors) «сюжет» — это первая победа или финальные титры, после которых игра продолжается сколько угодно. "
     "Поэтому разрыв между «сюжетом» и «100%» тут огромный. Для метроидваний вроде Hollow Knight средний столбец — это сюжет плюс большая часть необязательных боссов и зон.",
     ["silksong", "hollow", "stardew", "hades2", "hades", "outerwilds", "vampire", "celeste", "balatro"]),
    ("gl-strategy", "Стратегии и песочницы",
     "В стратегиях HowLongToBeat считает время одной кампании или партии, а «100%» — это обычно все достижения. Ориентируйтесь на средний столбец и помните, что в такие игры часто возвращаются годами.",
     ["rimworld", "xcom2", "civ6"]),
]


def gl_row(key: str, games_by_id: dict) -> str:
    title, gid, note = GL_GAMES[key]
    hid, main, plus, full, polls = HLTB[key]
    note_html = f'<span class="sp-note">{e(note)}</span> ' if note else ""
    return (f'<tr><th scope="row">{game_link(gid, title, games_by_id)}</th><td>{hrs(main)}</td><td>{hrs(plus)}</td><td>{hrs(full)}</td>'
            f'<td>{note_html}<a class="sp-note" href="{HLTB_URL.format(hid)}" target="_blank" rel="noopener nofollow">HLTB ↗</a></td></tr>')


def gl_buckets() -> list:
    keys = [k for _, _, _, ks in GL_GROUPS for k in ks]
    b = [("до 10 часов", 0, 10), ("10–20 часов", 10, 20), ("20–40 часов", 20, 40), ("40–60 часов", 40, 60), ("больше 60 часов", 60, 10 ** 6)]
    out = []
    for label, lo, hi in b:
        items = sorted([k for k in keys if lo <= HLTB[k][1] < hi], key=lambda k: HLTB[k][1])
        out.append((label, items))
    return out


def game_length_page(games_by_id: dict, site: str, og_image: str, publisher: dict):
    path = "guides/game-length/"
    keys = [k for _, _, _, ks in GL_GROUPS for k in ks]
    n = len(keys)
    H = lambda k, i: num(HLTB[k][i])  # noqa: E731
    title = f"Сколько часов проходить игру: время прохождения {n} игр (таблица)"
    desc = (f"Сколько часов уходит на сюжет, допы и 100% в Elden Ring, Cyberpunk 2077, BG3 и ещё {n - 3} играх. "
            "Данные HowLongToBeat — выбирайте игры к распродаже Steam.")
    short = [k for k in keys if HLTB[k][1] < 10]
    short.sort(key=lambda k: HLTB[k][1])
    short_names = [f"{GL_GAMES[k][0]} ({hrs(HLTB[k][1])})" for k in short]
    faq = [
        ("Сколько часов проходить Elden Ring?",
         f"По данным HowLongToBeat, сюжет Elden Ring проходят в среднем за {H('elden', 1)} часа, сюжет с побочными заданиями — за {H('elden', 2)} часа, "
         f"а на 100% уходит около {H('elden', 3)} часа. Дополнение Shadow of the Erdtree в эти цифры не входит."),
        ("Сколько часов проходить Cyberpunk 2077?",
         f"Сюжет Cyberpunk 2077 в среднем занимает {H('cp2077', 1)} часа, сюжет с дополнительными заданиями — {H('cp2077', 2)} часа, полное прохождение — {H('cp2077', 3)} часа. "
         "Это данные HowLongToBeat для основной игры без дополнения Phantom Liberty."),
        ("Сколько часов в Baldur's Gate 3?",
         f"Только сюжет Baldur's Gate 3 проходят в среднем за {H('bg3', 1)} часа, с побочными квестами — за {H('bg3', 2)} часа, на 100% — примерно за {H('bg3', 3)} часа. "
         "Это одна из самых длинных игр в нашей таблице."),
        ("Какие игры можно пройти за выходные?",
         "Из нашей таблицы сюжет меньше чем за 10 часов проходят в " + and_join(short_names) +
         ". В роглайках вроде Balatro первая победа тоже приходит быстро, но потом в них можно играть сотни часов."),
        ("Откуда берутся цифры и насколько им можно верить?",
         "Все часы взяты со страниц игр на HowLongToBeat — это средние значения по отчётам игроков, которые сами отмечают время прохождения. "
         f"Мы проверили их {CHECKED}. Ваше время может отличаться: всё зависит от сложности, стиля игры и того, сколько вы исследуете мир."),
        ("Почему у Balatro и Hades такое большое время на 100%?",
         f"Это роглайки: сюжет или первая победа приходят быстро, а 100% требуют открыть всё содержимое и пройти высокие уровни сложности. "
         f"Например, в Balatro сюжет занимает {hrs(HLTB['balatro'][1])}, а 100% — {hrs(HLTB['balatro'][3])}."),
        ("Когда осенняя распродажа Steam в 2026 году?",
         f"Осенняя распродажа Steam 2026 идёт с 1 по 8 октября. По расписанию Valve она начинается 1 октября в 10:00 по тихоокеанскому времени, то есть в 20:00 по Москве."),
    ]
    rows_by_group = ""
    for anchor, h, intro, ks in GL_GROUPS:
        rows_by_group += (f'<section class="guide-sec" id="{anchor}"><h2>{e(h)}</h2><p>{e(intro)}</p>'
                          + table(["Игра", "Сюжет", "Сюжет + допы", "100%", "Примечание"], [gl_row(k, games_by_id) for k in ks], "sp-table sp-table-num")
                          + "</section>")
    bucket_rows = [f'<tr><th scope="row">{e(label)}</th><td>{e(", ".join(GL_GAMES[k][0] for k in items)) or "—"}</td></tr>' for label, items in gl_buckets()]
    toc = [("gl-how", "Откуда цифры и как их читать"), ("gl-quick", "Быстрый выбор по времени")] + [(a, h) for a, h, _, _ in GL_GROUPS] + [
        ("gl-sale", "Как выбрать игру к распродаже"), ("gl-faq", "Частые вопросы")]
    body = f"""<article class="sp-article glass ed-page">
<p class="eyebrow">Гайд · Покупки · Время прохождения</p>
<h1 class="sp-h1">Сколько часов проходить игру: время прохождения {n} популярных игр</h1>
<p class="sp-meta">Проверено: {CHECKED} · источник: HowLongToBeat</p>
<div class="npv-body guide-body">
<p class="guide-lead">Коротко: сюжет Elden Ring в среднем проходят за {hrs(HLTB['elden'][1])}, Cyberpunk 2077 — за {hrs(HLTB['cp2077'][1])}, Baldur's Gate 3 — за {hrs(HLTB['bg3'][1])}, а Titanfall 2 — всего за {hrs(HLTB['titanfall2'][1])}. Ниже — таблицы для {n} игр с тремя цифрами: только сюжет, сюжет с дополнительными заданиями и 100%. Все часы взяты со страниц HowLongToBeat и проверены {CHECKED}. Используйте их, чтобы выбрать игры к осенней распродаже Steam ({SALE}) и не купить то, на что никогда не найдётся времени.</p>
{toc_html(toc)}
<section class="guide-sec" id="gl-how"><h2>Откуда цифры и как их читать</h2>
<p>{ext("https://howlongtobeat.com/", "HowLongToBeat")} (HLTB) — большая база, куда игроки сами отправляют, сколько времени у них ушло на прохождение. Сайт считает среднее по всем отчётам и показывает три цифры:</p>
<ul>
<li><strong>«Сюжет»</strong> (Main Story) — только основные задания, без побочных активностей. Так играют те, кто хочет увидеть финал и двигаться дальше.</li>
<li><strong>«Сюжет + допы»</strong> (Main + Extras) — сюжет плюс заметная часть побочных квестов и активностей. Это ближе всего к тому, как играет большинство.</li>
<li><strong>«100%»</strong> (Completionist) — все задания, коллекционные предметы и достижения.</li>
</ul>
<p>Цифры — среднее по отчётам игроков, а не обещание разработчика. Если вы любите читать каждую записку и заглядывать в каждый угол, закладывайте запас. Если играете на высокой сложности в «соулслайках», тоже: на одном боссе можно провести целый вечер.</p>
<p>Часы округлены до десятых. Дополнения (DLC) в цифры не входят, если в примечании не сказано иное: HLTB считает их отдельно. Мы взяли игры из <a href="{R}games/">каталога NEXUS PULSE</a> и добавили популярные новинки, которые часто ищут на распродажах. В таблицы не попали игры без сюжета: онлайн-шутеры, MMO, гонки-симуляторы и симуляторы вроде Euro Truck Simulator 2. Для них «время прохождения» не имеет смысла. Path of Exile 2 мы тоже не включили: у неё на HLTB пока слишком мало отчётов, а сама игра всё ещё в раннем доступе.</p>
</section>
<section class="guide-sec" id="gl-quick"><h2>Быстрый выбор: сколько часов на сюжет</h2>
<p>Если нужно просто понять, во что можно уложиться, вот все игры из таблиц, разбитые по времени на основной сюжет.</p>
{table(["Сюжет", "Игры"], bucket_rows)}
</section>
{rows_by_group}
<section class="guide-sec" id="gl-sale"><h2>Как выбрать игру к распродаже по времени прохождения</h2>
<p>Осенняя распродажа Steam 2026 идёт с 1 по 8 октября. По {ext(SALE_URL, "расписанию Valve для разработчиков")}, старт — 1 октября в 10:00 по тихоокеанскому времени, то есть в 20:00 МСК. Чтобы не набрать игр, до которых не дойдут руки, пройдитесь по этому списку:</p>
<ol class="guide-steps">
<li><strong>Честно посчитайте свободное время.</strong> Если вы играете 5–6 часов в неделю, игра на 60 часов сюжета займёт примерно три месяца. Лучше взять одну большую игру и пару коротких, чем пять больших, которые будут лежать в библиотеке.</li>
<li><strong>Считайте цену за час.</strong> Разделите цену со скидкой на время из среднего столбца. Игра за 1000 ₽ на 25 часов обойдётся в 40 ₽ за час, а игра за 500 ₽ на 5 часов — в 100 ₽ за час. Это не единственный критерий, но так удобно сравнивать две игры, между которыми вы выбираете.</li>
<li><strong>Смотрите на средний столбец.</strong> «Сюжет» — это минимум, «100%» — для фанатов достижений. Обычная игра с частью побочных заданий ближе к столбцу «Сюжет + допы».</li>
<li><strong>Проверьте, потянет ли ПК.</strong> Перед покупкой загляните в <a href="{R}tools/system-requirements/">системные требования</a> и прикиньте FPS в <a href="{R}tools/fps-calculator/">калькуляторе FPS</a>. Если кадров не хватает, поможет гайд <a href="{R}guides/fps-boost/">как поднять FPS</a>.</li>
<li><strong>Помните про возврат.</strong> Steam возвращает деньги за игру, если с покупки прошло не больше 14 дней и вы играли меньше 2 часов. Valve прямо пишет, что не считает злоупотреблением вернуть игру, купленную перед распродажей, и тут же купить её дешевле. Подробности — в гайде <a href="{R}guides/steam-refund/">как вернуть игру в Steam</a>.</li>
<li><strong>Проверьте язык и регион.</strong> Не у всех игр есть русская озвучка, а часть игр не продаётся в российском регионе Steam. Проверенный список — в подборке <a href="{R}guides/russian-voice/">игр с русской озвучкой</a>.</li>
<li><strong>Добавьте игры в список желаемого.</strong> Steam присылает письмо, когда на игру из списка появляется скидка, так что ничего не нужно проверять вручную. Текущие скидки можно смотреть в разделе <a href="{R}#deals">«Скидки»</a> на главной, а бесплатные игры — на странице <a href="{R}free-games/">раздач</a>.</li>
</ol>
<p>Играете вдвоём? Для совместного вечера подойдут It Takes Two ({hrs(HLTB['ittakestwo'][1])} на сюжет) и Split Fiction ({hrs(HLTB['splitfiction'][1])}), а другие варианты для одного компьютера собраны в подборке <a href="{R}guides/local-coop/">игр на двоих на одном ПК</a>. Если не можете решить, с чего начать, попробуйте <a href="{R}tools/game-picker/">подбор игры под настроение и время</a>.</p>
</section>
{faq_html(faq, "gl-faq")}
<p class="sp-note ed-source">Источник: страницы игр на HowLongToBeat (ссылка «HLTB» в каждой строке), проверено {CHECKED}. Средние значения меняются по мере того, как игроки присылают новые отчёты. Дата распродажи — {ext(SALE_URL, "Steamworks")}.</p>
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="{R}games/">Каталог игр</a>
<a class="btn btn-ghost btn-sm" href="{R}guides/">Все гайды</a>
</div>
</article>
{aside([("#gl-quick", "Быстрый выбор по времени", ""), ("#gl-rpg", "Большие RPG", ""), ("#gl-short", "Игры на несколько вечеров", ""), ("#gl-sale", "Советы к распродаже", ""), ("#gl-faq", "Частые вопросы", "")],
       cross_links("game-length") + [(f"{R}tools/game-picker/", "Во что поиграть", ""), (f"{R}free-games/", "Бесплатные игры", "")])}"""
    words = word_count(body.split('<aside')[0])
    sources = [HLTB_URL.format(HLTB[k][0]) for k in keys] + [SALE_URL]
    art = article_ld(site, path, "Сколько часов проходить игру: время прохождения популярных игр", desc, "Покупки", words, og_image, publisher, sources)
    return path, title, desc, body, [("Главная", ""), ("Гайды", "guides/"), ("Сколько часов проходить игру", path)], "article", "", [art, faq_ld(faq)]


# ================================================================ 2. russian-voice
# (appid, catalog id) — titles / genres come from the catalog
RV_CATALOG = [(1091500, "cp2077"), (292030, "witcher3"), (489830, "skyrim"), (2322010, "gow"), (2651280, "spiderman2"), (2050650, "re4"),
              (1196590, "reVillage"), (2208920, "acvalhalla"), (782330, "doom"), (1237970, "titanfall2"), (1240440, "halo"), (2344520, "diablo4"),
              (2246340, "mhwilds"), (289070, "civ6"), (1172470, "apex"), (2357570, "ow2"), (359550, "r6"), (1085660, "destiny2"), (2519060, "codmw")]
# (appid, title, genre) — not in the catalog
RV_MORE = [
    (668580, "Atomic Heart", "шутер, экшен"), (412020, "Metro Exodus", "шутер"), (286690, "Metro 2033 Redux", "шутер"),
    (2420110, "Horizon Forbidden West Complete Edition", "экшен, открытый мир"), (2561580, "Horizon Zero Dawn Remastered", "экшен, открытый мир"),
    (2215430, "Ghost of Tsushima Director's Cut", "экшен, открытый мир"), (1888930, "The Last of Us Part I", "экшен, хоррор"),
    (2531310, "The Last of Us Part II Remastered", "экшен, хоррор"), (1659420, "Uncharted: Legacy of Thieves Collection", "приключенческий экшен"),
    (1259420, "Days Gone", "экшен, открытый мир"), (1850570, "Death Stranding Director's Cut", "экшен, открытый мир"),
    (3280350, "Death Stranding 2: On the Beach", "экшен, открытый мир"), (1895880, "Ratchet & Clank: Rift Apart", "платформер, экшен"),
    (1817070, "Marvel's Spider-Man Remastered", "экшен, открытый мир"), (1030840, "Mafia: Definitive Edition", "экшен"),
    (1941540, "Mafia: The Old Country", "экшен"), (2369390, "Far Cry 6", "шутер, открытый мир"), (534380, "Dying Light 2 Stay Human", "экшен, выживание"),
    (3008130, "Dying Light: The Beast", "экшен, выживание"), (2183900, "Warhammer 40,000: Space Marine 2", "экшен"),
    (3017860, "DOOM: The Dark Ages", "шутер"), (620, "Portal 2", "головоломка"), (1599660, "Sackboy: A Big Adventure", "платформер"),
    (2669320, "EA SPORTS FC 25", "спорт"),
]
# popular games with Russian text only / without Russian (appid, title, catalog id or None)
RV_SUBS = [(1245620, "Elden Ring", "elden"), (1086940, "Baldur's Gate 3", "bg3"), (1174180, "Red Dead Redemption 2", "rdr2"), (271590, "GTA V", "gtav"),
           (2358720, "Black Myth: Wukong", "wukong"), (990080, "Hogwarts Legacy", "hogwarts"), (814380, "Sekiro: Shadows Die Twice", "sekiro"),
           (1551360, "Forza Horizon 5", "forza5"), (1145360, "Hades", "hades"), (1771300, "Kingdom Come: Deliverance II", None),
           (1903340, "Clair Obscur: Expedition 33", None), (1643320, "S.T.A.L.K.E.R. 2: Heart of Chornobyl", None),
           (2677660, "Indiana Jones and the Great Circle", None), (1627720, "Lies of P", None), (3159330, "Assassin's Creed Shadows", None),
           (1328670, "Mass Effect Legendary Edition", None), (870780, "Control Ultimate Edition", None), (2124490, "Silent Hill 2", None),
           (2461850, "Hellblade II: Senua's Saga", None), (3489700, "Stellar Blade", None), (4384550, "Call of Duty: Black Ops 6", None),
           (1285190, "Borderlands 4", None), (3405690, "EA SPORTS FC 26", None)]
RV_NONE = [(1716740, "Starfield", None), (1687950, "Persona 5 Royal", "persona5"), (1693980, "Dead Space (2023)", "deadspace"),
           (1774580, "Star Wars Jedi: Survivor", None), (2001120, "Split Fiction", None), (2379780, "Balatro", "balatro")]
RV_NONVERBAL = ["Hollow Knight", "Hollow Knight: Silksong", "Ultimate Chicken Horse", "Rayman Legends"]


def rv_rows(items, games_by_id, with_genre=True) -> list:
    rows = []
    for appid, title, gid, genre in items:
        voice, _, store = STEAM[appid]
        if voice != "audio":
            continue  # the snapshot is the source of truth
        rows.append(f'<tr><th scope="row">{game_link(gid, title, games_by_id)}</th><td>{e(genre)}</td><td>{e(STORE[store])}</td>'
                    f'<td><a class="sp-note" href="{STEAM_URL.format(appid)}" target="_blank" rel="noopener">Steam ↗</a></td></tr>')
    return rows


def russian_voice_page(games_by_id: dict, site: str, og_image: str, publisher: dict):
    path = "guides/russian-voice/"
    cat = [(a, games_by_id[g]["title"], g, games_by_id[g].get("genre") or "") for a, g in RV_CATALOG if g in games_by_id]
    more = [(a, t, None, gen) for a, t, gen in RV_MORE]
    cat_rows, more_rows = rv_rows(cat, games_by_id), rv_rows(more, games_by_id)
    n = len(cat_rows) + len(more_rows)
    subs = [(a, t, g) for a, t, g in RV_SUBS if STEAM[a][0] == "text"]
    none = [(a, t, g) for a, t, g in RV_NONE if STEAM[a][0] == ""]
    subs_rows = [f'<tr><th scope="row">{game_link(g, t, games_by_id)}</th><td>интерфейс и субтитры</td>'
                 f'<td><a class="sp-note" href="{STEAM_URL.format(a)}" target="_blank" rel="noopener">Steam ↗</a></td></tr>' for a, t, g in subs]
    none_rows = [f'<tr><th scope="row">{game_link(g, t, games_by_id)}</th><td>русского нет</td>'
                 f'<td><a class="sp-note" href="{STEAM_URL.format(a)}" target="_blank" rel="noopener">Steam ↗</a></td></tr>' for a, t, g in none]
    sold = sum(1 for a, *_ in cat + more if STEAM[a][0] == "audio" and STEAM[a][2] in ("price", "free"))
    title = f"Игры с русской озвучкой 2026: {n} {plural(n, 'игра', 'игры', 'игр')} с проверкой по Steam"
    desc = (f"Полная русская озвучка по данным Steam: Cyberpunk 2077, Ведьмак 3, God of War, Atomic Heart и ещё {n - 4}. "
            "Плюс хиты только с субтитрами и продажи в РФ.")
    faq = [
        ("В каких играх есть русская озвучка в 2026 году?",
         f"По таблице языков Steam полная русская озвучка есть, например, в Cyberpunk 2077, «Ведьмак 3», Skyrim, God of War Ragnarök, Marvel's Spider-Man 2, "
         f"Resident Evil 4, Atomic Heart, Metro Exodus, The Last of Us Part I, Ghost of Tsushima и DOOM: The Dark Ages. Всего в нашем списке {n} {plural(n, 'игра', 'игры', 'игр')}, данные проверены {CHECKED}."),
        ("Есть ли русская озвучка в Baldur's Gate 3?",
         "Нет. По данным Steam, в Baldur's Gate 3 русский язык есть только в интерфейсе и субтитрах, а голоса остаются английскими."),
        ("Есть ли русская озвучка в Elden Ring и Hogwarts Legacy?",
         "Нет, в обеих играх русский только в тексте: интерфейс и субтитры переведены, озвучки на русском в Steam не указано."),
        ("Есть ли русская озвучка в Kingdom Come: Deliverance II?",
         "По данным Steam — нет: русский язык есть в интерфейсе и субтитрах, но не в колонке «Озвучка». То же у Clair Obscur: Expedition 33, Assassin's Creed Shadows и Indiana Jones and the Great Circle."),
        ("Как понять, что в игре русская озвучка, а не только субтитры?",
         "Откройте страницу игры в Steam и найдите таблицу «Языки». Если у строки «Русский» стоит галочка в колонке «Озвучка», игра полностью озвучена на русском. "
         "Галочки только в колонках «Интерфейс» и «Субтитры» означают перевод текстом."),
        ("Почему игры с русской озвучкой нет в российском Steam?",
         "Часть издателей с 2022 года не продаёт игры в российском регионе Steam. Тогда страница игры для России не открывается или на ней нет цены в рублях. "
         "Озвучка при этом никуда не девается: если игра уже есть в библиотеке, русский язык можно выбрать в её свойствах."),
        ("Как включить русскую озвучку в Steam?",
         "Нажмите правой кнопкой по игре в библиотеке, откройте «Свойства» и на вкладке «Общие» выберите русский язык. Steam докачает нужные файлы. "
         "В некоторых играх язык озвучки дополнительно выбирается в настройках самой игры."),
    ]
    toc = [("rv-check", "Как проверить озвучку в Steam"), ("rv-catalog", "Игры из каталога с русской озвучкой"), ("rv-more", "Другие игры с русской озвучкой"),
           ("rv-subs", "Только субтитры или без русского"), ("rv-region", "Что значит «нет в регионе»"), ("rv-howto", "Как включить русскую озвучку"),
           ("rv-fan", "Любительская озвучка"), ("rv-faq", "Частые вопросы")]
    head = ["Игра", "Жанр", "В российском Steam", "Проверить"]
    body = f"""<article class="sp-article glass ed-page">
<p class="eyebrow">Гайд · Языки · Русская озвучка</p>
<h1 class="sp-h1">Игры с русской озвучкой: список 2026 года с проверкой по Steam</h1>
<p class="sp-meta">Проверено: {CHECKED} · источник: таблица языков в магазине Steam</p>
<div class="npv-body guide-body">
<p class="guide-lead">В этом списке {n} {plural(n, 'игра', 'игры', 'игр')}, у которых русский язык отмечен в колонке «Озвучка» на странице Steam. Это значит, что персонажи говорят по-русски, а не просто есть субтитры. Среди них Cyberpunk 2077, «Ведьмак 3», God of War Ragnarök, Marvel's Spider-Man 2, Atomic Heart и Metro Exodus. Ниже есть и отдельная таблица с популярными играми, где русский только в тексте или его нет совсем. Все данные сверены со Steam {CHECKED}.</p>
{toc_html(toc)}
<section class="guide-sec" id="rv-check"><h2>Озвучка, субтитры, интерфейс: как проверить в Steam</h2>
<p>На странице любой игры в Steam есть таблица «Языки» с тремя колонками: «Интерфейс», «Озвучка» и «Субтитры». Галочка в колонке «Озвучка» у строки «Русский» означает полную русскую озвучку. Если галочки стоят только в «Интерфейсе» и «Субтитрах», игра переведена текстом, а голоса остаются на языке оригинала. В коротком списке языков Steam отмечает языки с озвучкой звёздочкой.</p>
<p>Каждую игру из списка мы проверили через официальный API магазина Steam с русским языком ответа: там та же строка языков, что и на странице игры. Ссылка «Steam» в каждой строке ведёт на страницу игры, где это легко перепроверить.</p>
<p>Важная оговорка: Steam показывает то, что указал издатель. У игр почти без речи — например, {e(and_join(RV_NONVERBAL))} — русский тоже может стоять в колонке «Озвучка», хотя персонажи говорят на выдуманном языке или почти молчат. Такие игры мы в список не включили, чтобы не вводить в заблуждение.</p>
</section>
<section class="guide-sec" id="rv-catalog"><h2>Игры из каталога NEXUS PULSE с русской озвучкой</h2>
<p>Игры из нашего <a href="{R}games/">каталога</a>, у которых по данным Steam есть полная русская озвучка. По клику на название откроется страница игры с описанием, системными требованиями и оценкой FPS. В списке есть и онлайн-игры: в Apex Legends, Overwatch 2 и Destiny 2 русская озвучка тоже указана в Steam.</p>
{table(head, cat_rows)}
</section>
<section class="guide-sec" id="rv-more"><h2>Другие популярные игры с русской озвучкой</h2>
<p>Игры, которых пока нет в каталоге, но которые часто ищут с русской озвучкой. Здесь много игр Sony для PC и шутеров. Обратите внимание на колонку «В российском Steam»: многие из этих игр в российском регионе не продаются.</p>
{table(head, more_rows)}
<p>Всего из {n} игр с русской озвучкой в списке {sold} {plural(sold, "продаётся", "продаются", "продаются")} в российском Steam или {plural(sold, "бесплатна", "бесплатны", "бесплатны")} — по нашему снимку на {CHECKED}. Сколько часов займёт каждая из больших игр, смотрите в таблице <a href="{R}guides/game-length/">времени прохождения</a>.</p>
</section>
<section class="guide-sec" id="rv-subs"><h2>Только субтитры: популярные игры без русской озвучки</h2>
<p>Эти игры часто считают озвученными, но по данным Steam русский в них есть только в интерфейсе и субтитрах. Играть можно, но читать придётся много.</p>
{table(["Игра", "Русский язык", "Проверить"], subs_rows)}
<p>Заметно, что у многих крупных новинок 2025 года русский есть только в тексте: Kingdom Come: Deliverance II, Clair Obscur: Expedition 33, Assassin's Creed Shadows и Borderlands 4. А в серии EA SPORTS FC видно, как это меняется: в FC 25 русская озвучка по данным Steam есть, а в FC 26 — только текст.</p>
<p>А в этих играх русского языка в Steam нет вообще — ни в озвучке, ни в тексте:</p>
{table(["Игра", "Русский язык", "Проверить"], none_rows)}
</section>
<section class="guide-sec" id="rv-region"><h2>Что значит «нет в регионе» и «без цены»</h2>
<p>Колонка «В российском Steam» — это снимок на {CHECKED}. Мы запросили у API Steam страницу каждой игры для региона RU:</p>
<ul>
<li><strong>«продаётся»</strong> — Steam показывает цену в рублях, игру можно купить с российского аккаунта;</li>
<li><strong>«бесплатно»</strong> — free-to-play, скачать можно без покупки;</li>
<li><strong>«нет в регионе»</strong> — Steam не отдаёт страницу игры для России. Обычно так бывает, когда издатель остановил продажи в регионе;</li>
<li><strong>«без цены»</strong> — страница есть, но цены в рублях Steam не показывает, поэтому купить игру напрямую не получится.</li>
</ul>
<p>Доступность меняется: издатели то закрывают, то возвращают продажи. Перед покупкой откройте страницу игры в Steam. Менять регион аккаунта через VPN ради покупки не стоит: пользовательское соглашение Steam запрещает скрывать своё местоположение, и за это могут ограничить аккаунт.</p>
</section>
<section class="guide-sec" id="rv-howto"><h2>Как включить русскую озвучку в Steam</h2>
<ol class="guide-steps">
<li>Нажмите правой кнопкой по игре в библиотеке Steam и выберите «Свойства».</li>
<li>На вкладке «Общие» найдите пункт «Язык» и выберите «Русский». Steam докачает нужные языковые файлы.</li>
<li>Запустите игру и проверьте настройки звука или языка в её меню: во многих играх язык озвучки и язык субтитров выбираются отдельно.</li>
<li>Если русского нет ни в свойствах, ни в меню игры, значит, издатель его не добавил. Проверьте таблицу «Языки» на странице игры.</li>
</ol>
<p>Озвучка занимает место: в больших играх языковой пакет может весить несколько гигабайт. Если диск почти заполнен, освободите место заранее. А если игра после смены языка стала работать хуже, загляните в гайд <a href="{R}guides/fps-boost/">как поднять FPS</a>.</p>
</section>
<section class="guide-sec" id="rv-fan"><h2>Любительская озвучка: стоит ли ставить</h2>
<p>Для многих игр без официального дубляжа есть любительские озвучки от фанатских студий. Мы их не проверяли и в список не включали. Это неофициальные модификации: они могут ломаться после обновлений игры, а скачивать их безопасно только с сайтов самих студий. Официальная озвучка из Steam надёжнее, потому что обновляется вместе с игрой.</p>
<p>Ищете, во что поиграть вдвоём и на русском? Загляните в подборку <a href="{R}guides/local-coop/">игр на двоих на одном ПК</a>: там у каждой игры тоже указан русский язык по данным Steam.</p>
</section>
{faq_html(faq, "rv-faq")}
<p class="sp-note ed-source">Источник: таблица языков на страницах игр в Steam (API магазина, язык ответа — русский) и данные Steam для региона RU. Проверено {CHECKED}. Игры, где озвучка есть только на выдуманном языке, исключены.</p>
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="{R}games/">Каталог игр</a>
<a class="btn btn-ghost btn-sm" href="{R}guides/">Все гайды</a>
</div>
</article>
{aside([("#rv-catalog", "Игры из каталога", f"{len(cat_rows)} {plural(len(cat_rows), 'игра', 'игры', 'игр')}"), ("#rv-more", "Другие игры", f"{len(more_rows)} {plural(len(more_rows), 'игра', 'игры', 'игр')}"), ("#rv-subs", "Только субтитры", ""), ("#rv-howto", "Как включить озвучку", ""), ("#rv-faq", "Частые вопросы", "")],
       cross_links("russian-voice") + [(f"{R}tools/system-requirements/", "Системные требования", ""), (f"{R}free-games/", "Бесплатные игры", "")])}"""
    words = word_count(body.split('<aside')[0])
    sources = [STEAM_URL.format(a) for a, *_ in cat + more + [(a, t, g, "") for a, t, g in subs + none]]
    art = article_ld(site, path, "Игры с русской озвучкой 2026: список с проверкой по Steam", desc, "Языки", words, og_image, publisher, sources)
    return path, title, desc, body, [("Главная", ""), ("Гайды", "guides/"), ("Игры с русской озвучкой", path)], "article", "", [art, faq_ld(faq)]


# ================================================================ 3. steam-refund
# Valve refund policy (store.steampowered.com/steam_refunds/, "Last updated April 23, 2024"), checked CHECKED_ISO
RF_POLICY_UPDATED = "23 апреля 2024 года"
RF_RULES = [
    ("Игры и программы", "14 дней с покупки", "В игре меньше 2 часов. Причина не важна."),
    ("DLC (дополнения)", "14 дней с покупки", "В основной игре меньше 2 часов с момента покупки DLC; DLC не израсходовано, не изменено и не передано. Некоторые DLC сторонних издателей заранее помечены в магазине как невозвратные."),
    ("Предзаказ", "В любой момент до выхода", "После релиза действуют обычные 14 дней и 2 часа, отсчёт — с даты выхода."),
    ("Ранний доступ, Advance Access", "14 дней с покупки", "Любое время в игре идёт в лимит 2 часов."),
    ("Внутриигровые покупки в играх Valve", "48 часов", "Предмет не использован, не изменён и не передан."),
    ("Внутриигровые покупки в других играх", "Только если разработчик включил возврат", "Steam сообщает об этом при покупке. Иначе через Steam не возвращаются."),
    ("Наборы (bundles)", "14 дней с покупки", "Суммарно меньше 2 часов во всех играх набора, ничего из набора не передано."),
    ("Подарки", "14 дней / 2 часа", "Неактивированный подарок возвращает покупатель. Активированный — только если запрос отправит получатель; деньги вернутся покупателю."),
    ("Средства кошелька Steam", "14 дней", "Куплены в Steam, и из них ничего не потрачено."),
    ("Подписки", "48 часов после покупки или продления", "Подпиской не пользовались в текущем периоде."),
    ("Фильмы и видео", "Не возвращаются", "Кроме наборов, где есть и не видео-контент."),
    ("Ключи и карты пополнения от сторонних продавцов", "Не возвращаются через Steam", "Это покупки вне Steam — обращаться нужно к продавцу."),
    ("Игра, в которой получен VAC-бан", "Не возвращается", "Право на возврат этой игры теряется."),
]


def steam_refund_page(games_by_id: dict, site: str, og_image: str, publisher: dict):
    path = "guides/steam-refund/"
    title = "Как вернуть игру в Steam: правила 14 дней и 2 часа, пошаговая инструкция"
    desc = ("Возврат денег за игру в Steam: 14 дней с покупки и меньше 2 часов в игре. Заявка через help.steampowered.com, "
            "предзаказы, DLC, подарки, Россия.")
    faq = [
        ("Можно ли вернуть игру в Steam, если играл больше 2 часов?",
         "Гарантированный возврат действует, только если в игре меньше 2 часов и с покупки прошло не больше 14 дней. "
         "Но Valve пишет, что запрос можно отправить и вне этих правил — его рассмотрят. Гарантий в таком случае нет."),
        ("Сколько дней даётся на возврат игры в Steam?",
         "14 дней с момента покупки. Для предзаказов отсчёт 14 дней начинается с даты выхода игры, а до релиза предзаказ можно вернуть в любой момент."),
        ("Сколько ждать деньги после возврата в Steam?",
         "По официальным правилам Valve полная сумма возвращается в течение недели после одобрения заявки: на кошелёк Steam или тем же способом, которым вы платили."),
        ("Как вернуть предзаказ в Steam?",
         "До выхода игры предзаказ можно вернуть в любой момент через help.steampowered.com. После релиза действуют обычные условия: 14 дней с даты выхода и меньше 2 часов в игре. "
         "Если по предзаказу открыт ранний запуск (Advance Access), время в нём идёт в лимит 2 часов; исключение — бета-тесты."),
        ("Можно ли вернуть DLC в Steam?",
         "Да, в течение 14 дней с покупки, если в основной игре меньше 2 часов с момента покупки DLC и дополнение не израсходовано, не изменено и не передано. "
         "Часть DLC сторонних издателей невозвратная — это указано на странице в магазине до покупки."),
        ("Можно ли вернуть подарок в Steam?",
         "Неактивированный подарок можно вернуть на обычных условиях: 14 дней и 2 часа. Если подарок уже активирован, запрос должен отправить получатель, а деньги вернутся тому, кто его покупал."),
        ("Куда вернутся деньги на российском аккаунте Steam?",
         "Правила возврата одинаковы для всех регионов. Если способ оплаты не поддерживает возврат, Valve зачисляет деньги на кошелёк Steam. "
         "Если игра куплена со средств кошелька, деньги вернутся на кошелёк. Пополнение через сторонний сервис Valve не возвращает — это покупка вне Steam."),
        ("Можно ли вернуть игру, если она подешевела на распродаже?",
         "Да, если соблюдены 14 дней и 2 часа. Valve прямо пишет, что не считает злоупотреблением вернуть игру, купленную перед распродажей, и сразу купить её по цене со скидкой."),
        ("Вернут ли деньги за ключ Steam, купленный на другом сайте?",
         "Через Steam — нет: Valve не возвращает деньги за покупки вне Steam, включая ключи и карты пополнения от сторонних продавцов. Обращаться нужно к магазину, где вы купили ключ."),
    ]
    rules_rows = [f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td><td>{e(c)}</td></tr>' for a, b, c in RF_RULES]
    toc = [("rf-rules", "Главные правила в одной таблице"), ("rf-steps", "Пошагово: как подать заявку"), ("rf-time", "Как не выйти за 2 часа"),
           ("rf-preorder", "Предзаказы и ранний доступ"), ("rf-dlc", "DLC, покупки в игре и наборы"), ("rf-gifts", "Подарки"),
           ("rf-sale", "Возврат и распродажа"), ("rf-russia", "Российский аккаунт: куда придут деньги"), ("rf-denied", "Если в возврате отказали"),
           ("rf-faq", "Частые вопросы")]
    body = f"""<article class="sp-article glass ed-page">
<p class="eyebrow">Гайд · Steam · Возврат денег</p>
<h1 class="sp-h1">Как вернуть игру в Steam: пошаговая инструкция и все правила возврата</h1>
<p class="sp-meta">Проверено: {CHECKED} · источник: официальная политика возврата Valve</p>
<div class="npv-body guide-body">
<p class="guide-lead">Steam вернёт деньги за игру по любой причине, если с покупки прошло не больше 14 дней и вы играли меньше 2 часов. Заявка подаётся на help.steampowered.com, а после одобрения деньги приходят в течение недели — на кошелёк Steam или тем же способом, которым вы платили. Ниже — пошаговая инструкция и все исключения по {ext(REFUND_URL, "официальной политике возврата Valve")} (последнее обновление страницы — {RF_POLICY_UPDATED}, мы сверились с ней {CHECKED}).</p>
{toc_html(toc)}
<section class="guide-sec" id="rf-rules"><h2>Главные правила возврата в одной таблице</h2>
<p>Базовое правило Valve звучит так: игру или программу можно вернуть в течение двух недель с покупки, если в ней меньше двух часов. Не важно, почему: не потянул компьютер, купили по ошибке или просто не понравилось. Для других покупок условия отличаются:</p>
{table(["Что купили", "Срок", "Условия"], rules_rows)}
<p>Устройства Steam (например, Steam Deck) возвращаются по отдельным правилам возврата оборудования. Жителям Евросоюза дополнительно доступно право на отказ от покупки, а в некоторых странах закон даёт дополнительные права, если игра неисправна.</p>
</section>
<section class="guide-sec" id="rf-steps"><h2>Пошагово: как вернуть игру через help.steampowered.com</h2>
<ol class="guide-steps">
<li>Откройте {ext("https://help.steampowered.com/", "help.steampowered.com")} в браузере или в клиенте Steam через меню «Справка» → «Служба поддержки Steam». Войдите в свой аккаунт.</li>
<li>Выберите раздел «Покупки». Появится список последних покупок — найдите в нём нужную игру. Если её там нет, найдите игру через раздел с играми и программами или через поиск.</li>
<li>Выберите проблему вроде «Я хотел бы вернуть деньги», а затем пункт с запросом возврата средств.</li>
<li>Выберите, куда вернуть деньги: на кошелёк Steam или на исходный способ оплаты, если он поддерживает возврат.</li>
<li>Укажите причину из списка и при желании добавьте комментарий. На стандартный возврат причина не влияет: Valve возвращает деньги «по любой причине».</li>
<li>Отправьте запрос. Подтверждение придёт на почту, а статус виден в списке ваших обращений в поддержку. После одобрения деньги вернутся в течение недели.</li>
</ol>
<p>Названия пунктов в интерфейсе поддержки Steam иногда меняются, поэтому ориентируйтесь на смысл: «Покупки» → нужная игра → возврат средств. Вся заявка занимает пару минут.</p>
</section>
<section class="guide-sec" id="rf-time"><h2>Как не выйти за 2 часа</h2>
<ul>
<li>Время в игре видно в библиотеке Steam на странице игры. Steam считает всё время, пока игра запущена, в том числе в главном меню и на экранах загрузки.</li>
<li>Если игра не запускается, вылетает или выдаёт мало кадров, не сидите в ней часами в попытках всё настроить. Сначала решите, будете ли вы её оставлять: запрос на возврат лучше отправить сразу.</li>
<li>Чтобы не покупать вслепую, заранее сверьте <a href="{R}tools/system-requirements/">системные требования</a> и прикиньте FPS в <a href="{R}tools/fps-calculator/">калькуляторе FPS</a>.</li>
<li>Если 2 часа или 14 дней уже прошли, запрос всё равно можно отправить: Valve обещает его рассмотреть. Но решение в таком случае остаётся за поддержкой.</li>
</ul>
</section>
<section class="guide-sec" id="rf-preorder"><h2>Предзаказы и ранний доступ</h2>
<p>Если вы оформили предзаказ игры, в которую до релиза нельзя играть, вернуть его можно в любой момент до выхода. После релиза начинают действовать обычные условия: 14 дней с даты выхода и меньше 2 часов в игре.</p>
<p>С ранним доступом по-другому. Если игра уже доступна в раннем доступе (Early Access) или по предзаказу открыт ранний запуск (Advance Access), любое время в ней идёт в лимит 2 часов. Исключение Valve делает только для бета-тестов. Поэтому, если вы купили издание с ранним доступом на несколько дней раньше релиза и наиграли три часа, стандартный возврат уже не сработает.</p>
</section>
<section class="guide-sec" id="rf-dlc"><h2>DLC, внутриигровые покупки и наборы</h2>
<p><strong>DLC</strong> возвращаются в течение 14 дней с покупки, если после покупки дополнения вы провели в основной игре меньше 2 часов, а само DLC не израсходовано, не изменено и не передано. Некоторые сторонние DLC вернуть нельзя — например, если они необратимо прокачивают персонажа. Такие дополнения помечены как невозвратные на странице магазина ещё до покупки.</p>
<p><strong>Внутриигровые покупки</strong> в играх Valve (например, в Counter-Strike 2 и Dota 2) можно вернуть в течение 48 часов, если предмет не использован, не изменён и не передан. В играх других разработчиков возврат внутриигровых покупок работает, только если разработчик его включил, — Steam сообщит об этом при покупке. В остальных случаях такие покупки через Steam не возвращаются.</p>
<p><strong>Наборы</strong> возвращаются целиком, если суммарное время во всех играх набора меньше 2 часов и ничего из набора не передано. Если в набор входит невозвратный предмет или DLC, Steam предупредит об этом при оформлении заказа.</p>
</section>
<section class="guide-sec" id="rf-gifts"><h2>Подарки</h2>
<p>Неактивированный подарок можно вернуть на обычных условиях: 14 дней и 2 часа. Если получатель уже добавил подарок в библиотеку, вернуть его можно на тех же условиях, но запрос должен отправить сам получатель. Деньги в обоих случаях вернутся тому, кто покупал подарок.</p>
</section>
<section class="guide-sec" id="rf-sale"><h2>Купили игру, а она подешевела на распродаже</h2>
<p>Это законный повод для возврата. В разделе о злоупотреблениях Valve прямо пишет, что не считает злоупотреблением вернуть игру, купленную прямо перед распродажей, и тут же купить её по цене со скидкой. Главное — уложиться в 14 дней и 2 часа.</p>
<p>Это особенно актуально перед осенней распродажей Steam, которая идёт {SALE} и стартует 1 октября в 20:00 МСК. Если вы купили игру в конце сентября, а на распродаже она подешевела, отправьте запрос на возврат и купите её снова. Прикинуть, на сколько вечеров хватит игры, поможет таблица <a href="{R}guides/game-length/">времени прохождения</a>, а текущие скидки собраны в разделе <a href="{R}#deals">«Скидки»</a>.</p>
<p>Но не превращайте возврат в бесплатную аренду. Valve предупреждает: если система решит, что вы злоупотребляете возвратами, их могут перестать вам предлагать.</p>
</section>
<section class="guide-sec" id="rf-russia"><h2>Российский аккаунт: куда придут деньги</h2>
<p>На официальной странице Valve нет отдельных правил для России: сроки 14 дней и 2 часа одинаковы для всех регионов. Отличается в основном то, куда вернутся деньги. Ниже — то, что следует из политики Valve. Детали оплаты у российских пользователей часто меняются, поэтому проверяйте свой случай.</p>
<ul>
<li>Если исходный способ оплаты не поддерживает возврат, Valve зачисляет полную сумму на кошелёк Steam. Список способов, которые поддерживают возврат, зависит от страны: его показывает страница {ext(REFUND_METHODS_URL, "способов возврата")} для вашего аккаунта.</li>
<li>С 2022 года российские банковские карты в Steam, как правило, не принимаются, и многие пополняют кошелёк через сторонние сервисы. Если игра куплена со средств кошелька, при возврате деньги вернутся на кошелёк Steam.</li>
<li>Само пополнение через посредника Valve не возвращает: для Steam это покупка вне Steam. Вопросы о комиссии или отмене пополнения — к сервису, через который вы платили.</li>
<li>То же с ключами из сторонних магазинов: вернуть их через Steam нельзя, только у продавца.</li>
<li>Не меняйте регион аккаунта через VPN ради покупки или возврата: пользовательское соглашение Steam запрещает скрывать своё местоположение, и за это могут ограничить аккаунт.</li>
</ul>
<p>Некоторые игры в российском регионе Steam не продаются вовсе. Какие игры с русской озвучкой можно купить с российского аккаунта, видно в подборке <a href="{R}guides/russian-voice/">игр с русской озвучкой</a>. А бесплатные раздачи Epic Games, Steam и GOG с российского аккаунта забираются без карты — актуальный список на странице <a href="{R}free-games/">бесплатных игр</a>.</p>
</section>
<section class="guide-sec" id="rf-denied"><h2>Если в возврате отказали</h2>
<p>Чаще всего отказ связан с тем, что вышли сроки: больше 14 дней с покупки или больше 2 часов в игре. Реже — с VAC-баном в этой игре или с тем, что аккаунт слишком часто возвращает покупки. Ответ поддержки приходит в то же обращение, где можно уточнить детали.</p>
<p>Если игра действительно неисправна — не запускается или ломается на ровном месте, — опишите проблему в запросе подробно. Valve отдельно упоминает, что в некоторых странах у покупателей неисправных игр есть дополнительные права. Если же игра просто не понравилась, а сроки вышли, остаётся дать ей второй шанс позже, например после крупного обновления.</p>
</section>
{faq_html(faq, "rf-faq")}
<p class="sp-note ed-source">Источник: {ext(REFUND_URL, "Steam Refunds — официальная политика возврата Valve")} (обновлена {RF_POLICY_UPDATED}) и {ext(REFUND_METHODS_URL, "список способов возврата")}. Проверено {CHECKED}. Это пересказ правил, а не юридическая консультация: решение по каждому запросу принимает поддержка Steam.</p>
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="{R}#deals">Скидки на игры</a>
<a class="btn btn-ghost btn-sm" href="{R}guides/">Все гайды</a>
</div>
</article>
{aside([("#rf-rules", "Таблица правил", f"{len(RF_RULES)} случаев"), ("#rf-steps", "Пошаговая заявка", ""), ("#rf-sale", "Возврат и распродажа", ""), ("#rf-russia", "Российский аккаунт", ""), ("#rf-faq", "Частые вопросы", "")],
       cross_links("steam-refund") + [(f"{R}tools/system-requirements/", "Системные требования", ""), (f"{R}free-games/", "Бесплатные игры", "")])}"""
    words = word_count(body.split('<aside')[0])
    art = article_ld(site, path, "Как вернуть игру в Steam: пошаговая инструкция и правила возврата", desc, "Steam", words, og_image, publisher,
                     [REFUND_URL, REFUND_METHODS_URL, SALE_URL])
    return path, title, desc, body, [("Главная", ""), ("Гайды", "guides/"), ("Как вернуть игру в Steam", path)], "article", "", [art, faq_ld(faq)]


# ================================================================ 4. local-coop
# (appid, title, catalog id or None, what it is) — the local mode itself comes from STEAM (Steam categories)
LC_GROUPS = [
    ("lc-story", "Сюжетные кооперативные игры на двоих",
     "Игры, которые проходят вдвоём от начала до конца: у каждого своя роль, а многие головоломки без напарника не решить.",
     [(1426210, "It Takes Two", None, "сюжетное приключение только для двоих"),
      (2001120, "Split Fiction", None, "сюжетное приключение только для двоих"),
      (1222700, "A Way Out", None, "побег из тюрьмы, только кооператив"),
      (2153350, "Brothers: A Tale of Two Sons Remake", None, "сказочное приключение"),
      (620, "Portal 2", None, "головоломки, отдельная кооп-кампания"),
      (268910, "Cuphead", None, "сложный run-and-gun с боссами"),
      (1225570, "Unravel Two", None, "спокойный платформер"),
      (242550, "Rayman Legends", None, "платформер"),
      (1436700, "Trine 5: A Clockwork Conspiracy", None, "платформер с головоломками"),
      (1599660, "Sackboy: A Big Adventure", None, "платформер"),
      (252110, "Lovers in a Dangerous Spacetime", None, "управление кораблём вдвоём"),
      (1071870, "Biped", None, "головоломки для двоих"),
      (471810, "Death Squared", None, "головоломки"),
      (1509960, "PICO PARK", None, "головоломки на командную работу"),
      (972660, "Spiritfarer", None, "уютный менеджмент"),
      ]),
    ("lc-party", "Весёлый хаос для компании",
     "Короткие раунды, крики и смех: такие игры хороши на вечер, когда в гостях друзья. Многие поддерживают больше двух игроков.",
     [(728880, "Overcooked! 2", None, "готовка на скорость"),
      (1243830, "Overcooked! All You Can Eat", None, "обе части Overcooked в одной"),
      (996770, "Moving Out", None, "переезд на скорость"),
      (1641700, "Moving Out 2", None, "переезд на скорость"),
      (1599600, "PlateUp!", None, "свой ресторан, роглайк"),
      (1016920, "Unrailed!", None, "строим железную дорогу на ходу"),
      (1004490, "Tools Up!", None, "ремонт квартиры на скорость"),
      (477160, "Human Fall Flat", None, "физические головоломки"),
      (905340, "Heave Ho", None, "лазание вдвоём, держась за руки"),
      (386940, "Ultimate Chicken Horse", None, "строим уровни и мешаем друг другу"),
      (285900, "Gang Beasts", None, "потасовка желейных человечков"),
      ]),
    ("lc-action", "Экшены, RPG и платформеры",
     "Игры подлиннее: прокачка, боссы и лут. В большинстве из них второй игрок может подключиться и выйти в любой момент.",
     [(204360, "Castle Crashers", None, "beat 'em up"),
      (330020, "Children of Morta", None, "экшен-RPG, роглайт"),
      (1313140, "Cult of the Lamb", None, "роглайк и управление культом"),
      (435150, "Divinity: Original Sin 2", None, "большая RPG, разделённый экран"),
      (1672970, "Minecraft Dungeons", None, "экшен-RPG"),
      (471550, "Nine Parchments", None, "экшен про магов"),
      (238370, "Magicka 2", None, "экшен про магов"),
      (311690, "Enter the Gungeon", None, "роглайк-шутер"),
      (985890, "Streets of Rage 4", None, "beat 'em up"),
      (534550, "Guacamelee! 2", None, "метроидвания"),
      (250760, "Shovel Knight: Treasure Trove", None, "платформер"),
      (609110, "Blazing Chrome", None, "run-and-gun"),
      (920210, "LEGO Star Wars: The Skywalker Saga", None, "приключение LEGO"),
      (313690, "LEGO Batman 3: Beyond Gotham", None, "приключение LEGO"),
      (413150, "Stardew Valley", "stardew", "ферма, разделённый экран"),
      ]),
    ("lc-versus", "Против друга: файтинги, спорт и гонки",
     "Если хочется не помогать, а соревноваться. Здесь режим в Steam отмечен как «Игрок против игрока (общий/разделённый экран)».",
     [(252950, "Rocket League", "rocket", "футбол на машинах"),
      (1971870, "Mortal Kombat 1", None, "файтинг"),
      (1364780, "Street Fighter 6", None, "файтинг"),
      (1778820, "TEKKEN 8", None, "файтинг"),
      (2669320, "EA SPORTS FC 25", None, "футбол"),
      (3405690, "EA SPORTS FC 26", None, "футбол"),
      (291550, "Brawlhalla", None, "платформенный файтинг, бесплатно"),
      (251470, "TowerFall Ascension", None, "дуэли лучников"),
      (289070, "Civilization VI", "civ6", "стратегия, ходы по очереди"),
      (2488620, "F1 24", None, "гонки, разделённый экран"),
      ]),
]


def lc_items():
    for anchor, h, intro, items in LC_GROUPS:
        yield anchor, h, intro, [it for it in items if STEAM[it[0]][1]]


def local_coop_page(games_by_id: dict, site: str, og_image: str, publisher: dict):
    path = "guides/local-coop/"
    groups = list(lc_items())
    all_items = [it for _, _, _, items in groups for it in items]
    n = len(all_items)
    ru_voice = [t for a, t, *_ in all_items if STEAM[a][0] == "audio" and t not in RV_NONVERBAL]
    no_ru = [t for a, t, *_ in all_items if STEAM[a][0] == ""]
    sold = sum(1 for a, *_ in all_items if STEAM[a][2] in ("price", "free"))
    title = f"Игры на двоих на одном ПК: {n} {plural(n, 'игра', 'игры', 'игр')} с разделённым экраном"
    desc = (f"Во что поиграть вдвоём на одном компьютере: It Takes Two, Overcooked! 2, Portal 2 и ещё {n - 3}. "
            "Кооператив проверен по Steam, указан русский язык.")
    sections = ""
    for anchor, h, intro, items in groups:
        rows = [f'<tr><th scope="row">{game_link(gid, t, games_by_id)}<span class="sp-note"> · {e(what)}</span></th>'
                f'<td>{e(LOCAL[STEAM[a][1]])}</td><td>{e(VOICE[STEAM[a][0]])}</td><td>{e(STORE[STEAM[a][2]])}</td>'
                f'<td><a class="sp-note" href="{STEAM_URL.format(a)}" target="_blank" rel="noopener">Steam ↗</a></td></tr>' for a, t, gid, what in items]
        sections += (f'<section class="guide-sec" id="{anchor}"><h2>{e(h)}</h2><p>{e(intro)}</p>'
                     + table(["Игра", "Режим на одном экране", "Русский язык", "В российском Steam", "Проверить"], rows) + "</section>")
    faq = [
        ("Во что поиграть вдвоём на одном компьютере?",
         "Для сюжетного вечера подойдут It Takes Two, Split Fiction, A Way Out, Portal 2 и Cuphead. Для весёлой компании — Overcooked! 2, Moving Out, PlateUp! и Human Fall Flat. "
         "Если хочется соревноваться, берите Rocket League, Mortal Kombat 1, Street Fighter 6 или TEKKEN 8. У всех этих игр локальный режим отмечен в Steam."),
        ("Как играть вдвоём на одном ПК в Steam?",
         "Подключите второй геймпад, запустите игру с локальным кооперативом или разделённым экраном и выберите в её меню локальную игру. "
         "Удобнее всего играть на телевизоре через HDMI в режиме Big Picture. Steam Input поддерживает геймпады Xbox, PlayStation и Nintendo Switch Pro."),
        ("Нужны ли две копии игры, чтобы играть вдвоём на одном ПК?",
         "Нет. Для локального кооператива или разделённого экрана достаточно одной копии игры на том аккаунте, с которого она запущена. "
         "Для Remote Play Together по сети игра тоже нужна только тому, кто её запускает."),
        ("Можно ли играть вдвоём с клавиатуры?",
         "Иногда да: в части игр один игрок может играть на клавиатуре, а второй — на геймпаде. Но многие локальные игры рассчитаны на геймпады, поэтому надёжнее купить второй контроллер."),
        ("Что такое Remote Play Together в Steam?",
         "Это функция Steam, которая позволяет играть в локальные мультиплеерные игры с друзьями по интернету. Игру запускает и владеет ею один игрок, "
         "а до четырёх друзей (и больше при быстром соединении) подключаются к нему через Steam."),
        ("Есть ли It Takes Two и Split Fiction на русском?",
         f"По данным Steam, в It Takes Two русский есть в интерфейсе и субтитрах, без озвучки. В Split Fiction русского языка в Steam нет. "
         f"Сюжет It Takes Two в среднем проходят за {hrs(HLTB['ittakestwo'][1])}, Split Fiction — за {hrs(HLTB['splitfiction'][1])} (HowLongToBeat)."),
        ("Какие игры на двоих на одном ПК есть с русской озвучкой?",
         "Из нашей подборки полная русская озвучка по данным Steam есть в " + and_join(ru_voice) +
         ". В большинстве остальных игр русский есть в интерфейсе и субтитрах."),
    ]
    toc = [("lc-diff", "Локальный кооператив и игра по сети"), ("lc-setup", "Что понадобится")] + [(a, h) for a, h, _, _ in groups] + [
        ("lc-remote", "Если друг далеко: Remote Play Together"), ("lc-choose", "Как выбрать игру на двоих"), ("lc-faq", "Частые вопросы")]
    body = f"""<article class="sp-article glass ed-page">
<p class="eyebrow">Гайд · Кооператив · Игры на двоих</p>
<h1 class="sp-h1">Игры на двоих на одном ПК: кооператив и разделённый экран</h1>
<p class="sp-meta">Проверено: {CHECKED} · источник: категории и языки в магазине Steam</p>
<div class="npv-body guide-body">
<p class="guide-lead">Если друг сидит рядом, а не в Discord, нужны игры с локальным режимом: общий или разделённый экран на одном компьютере. В подборке {n} {plural(n, 'такая игра', 'таких игры', 'таких игр')} для PC — от сюжетных It Takes Two и Portal 2 до кухонного хаоса Overcooked! 2 и файтингов. Локальный режим каждой игры сверен с категориями Steam — «Кооператив (общий/разделённый экран)» или «Игрок против игрока (общий/разделённый экран)», — а заодно указаны русский язык и доступность в российском Steam на {CHECKED}.</p>
{toc_html(toc)}
<section class="guide-sec" id="lc-diff"><h2>Локальный кооператив и игра «с другом» по сети: в чём разница</h2>
<p>Когда ищут «игры с другом», чаще всего имеют в виду онлайн: у каждого свой компьютер и своя копия игры. Эта подборка про другое — про игру вдвоём за одним ПК. Оба игрока смотрят на один монитор или телевизор, а управляют с разных геймпадов или с геймпада и клавиатуры.</p>
<p>В Steam за это отвечают три категории на странице игры:</p>
<ul>
<li><strong>«Кооператив (общий/разделённый экран)»</strong> — играете в одной команде на одном компьютере;</li>
<li><strong>«Игрок против игрока (общий/разделённый экран)»</strong> — соревнуетесь друг с другом на одном компьютере;</li>
<li><strong>«Общий/разделённый экран»</strong> — общая метка локального режима без уточнения.</li>
</ul>
<p>Если у игры есть только «Кооператив (по сети)», вдвоём за одним ПК в неё не поиграть. Мы включили в подборку только игры, у которых в Steam есть одна из трёх локальных категорий. Колонка «Режим на одном экране» в таблицах показывает, какая именно.</p>
</section>
<section class="guide-sec" id="lc-setup"><h2>Что понадобится для игры вдвоём на одном ПК</h2>
<ul>
<li><strong>Второй контроллер.</strong> Steam через Steam Input поддерживает геймпады Xbox, PlayStation и Nintendo Switch Pro, так что подойдёт почти любой. Многие локальные игры рассчитаны именно на геймпады.</li>
<li><strong>Клавиатура — не всегда вариант.</strong> В части игр один игрок может играть на клавиатуре, второй — на геймпаде, но так бывает не везде. Если геймпада нет, проверьте раздел об управлении на странице игры.</li>
<li><strong>Большой экран.</strong> Разделённый экран на 24-дюймовом мониторе тесноват. Удобнее подключить ПК к телевизору по HDMI и запустить Steam в режиме Big Picture.</li>
<li><strong>Запас производительности.</strong> При разделённом экране игра рисует картинку для двух камер сразу, так что FPS может просесть. Прикиньте запас в <a href="{R}tools/fps-calculator/">калькуляторе FPS</a>, а если кадров мало — откройте гайд <a href="{R}guides/fps-boost/">как поднять FPS</a>.</li>
</ul>
</section>
{sections}
<section class="guide-sec" id="lc-remote"><h2>Если друг далеко: Remote Play Together</h2>
<p>Если на странице игры в Steam есть метка Remote Play Together (она есть у многих игр из подборки), в неё можно играть и по сети, даже если в самой игре онлайна нет. По {ext(REMOTE_PLAY_URL, "описанию Valve")}, игру запускает и владеет ею один игрок, а до четырёх друзей (и больше при быстром соединении) подключаются через список друзей Steam. Картинка и звук передаются потоком, а каждый управляет своим контроллером. Для такой игры важны стабильный пинг и скорость — проверить их можно в <a href="{R}tools/speed-test/">тесте скорости</a>, а если связь плохая, загляните в гайд про <a href="{R}guides/network-ping/">пинг и сеть</a>.</p>
<p>У It Takes Two и Split Fiction есть и свой способ: бесплатный Friend's Pass. С ним друг может играть по сети с владельцем игры, не покупая её.</p>
</section>
<section class="guide-sec" id="lc-choose"><h2>Как выбрать игру на двоих</h2>
<ol class="guide-steps">
<li><strong>Учтите разницу в опыте.</strong> Cuphead — очень сложная игра, и новичку в ней будет тяжело. Human Fall Flat, Unravel Two или Stardew Valley прощают ошибки и подойдут тем, кто играет редко.</li>
<li><strong>Проверьте язык.</strong> Если напарник не знает английский, смотрите колонку «Русский язык». Полная русская озвучка из нашей подборки есть в {e(and_join(ru_voice))}, а {e(and_join(no_ru))} русского в Steam не имеют совсем.</li>
<li><strong>Подумайте о длине.</strong> Сюжетные игры рассчитаны на несколько вечеров: It Takes Two в среднем проходят за {hrs(HLTB['ittakestwo'][1])}, Split Fiction — за {hrs(HLTB['splitfiction'][1])}, Cuphead — за {hrs(HLTB['cuphead'][1])} (HowLongToBeat). Пати-игры вроде Overcooked! 2 удобнее, когда времени мало: один уровень — несколько минут. Больше цифр — в таблице <a href="{R}guides/game-length/">времени прохождения</a>.</li>
<li><strong>Проверьте, продаётся ли игра в вашем регионе.</strong> В колонке «В российском Steam» видно, можно ли купить игру с российского аккаунта: по нашему снимку на {CHECKED} это верно для {sold} из {n} игр подборки. Если игра не продаётся, не пытайтесь менять регион через VPN — это нарушает правила Steam.</li>
<li><strong>Купили, а не зашло?</strong> У Steam есть возврат: 14 дней с покупки и меньше 2 часов в игре. Как подать заявку, рассказываем в гайде <a href="{R}guides/steam-refund/">как вернуть игру в Steam</a>.</li>
</ol>
<p>А если сидеть рядом не получается, есть онлайн-вариант: в каталоге NEXUS PULSE много игр для компании по сети, например <a href="{R}games/phasmo/">Phasmophobia</a> и <a href="{R}games/lethal/">Lethal Company</a>. Бесплатные игры для компании ищите на странице <a href="{R}free-games/">раздач</a>, а если не можете выбрать, попробуйте <a href="{R}tools/game-picker/">подбор игры под настроение</a> с режимом «с друзьями».</p>
</section>
{faq_html(faq, "lc-faq")}
<p class="sp-note ed-source">Источник: категории («Кооператив (общий/разделённый экран)», «Игрок против игрока (общий/разделённый экран)», «Общий/разделённый экран»), таблица языков и данные региона RU в магазине Steam; время прохождения — HowLongToBeat. Проверено {CHECKED}.</p>
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="{R}games/">Каталог игр</a>
<a class="btn btn-ghost btn-sm" href="{R}guides/">Все гайды</a>
</div>
</article>
{aside([(f"#{a}", h, f"{len(items)} {plural(len(items), 'игра', 'игры', 'игр')}") for a, h, _, items in groups] + [("#lc-remote", "Remote Play Together", ""), ("#lc-faq", "Частые вопросы", "")],
       cross_links("local-coop") + [(f"{R}tools/game-picker/", "Во что поиграть", ""), (f"{R}free-games/", "Бесплатные игры", "")])}"""
    words = word_count(body.split('<aside')[0])
    sources = [STEAM_URL.format(a) for a, *_ in all_items] + [REMOTE_PLAY_URL] + [HLTB_URL.format(HLTB[k][0]) for k in ("ittakestwo", "splitfiction", "cuphead")]
    art = article_ld(site, path, "Игры на двоих на одном ПК: кооператив и разделённый экран", desc, "Кооператив", words, og_image, publisher, sources)
    return path, title, desc, body, [("Главная", ""), ("Гайды", "guides/"), ("Игры на двоих на одном ПК", path)], "article", "", [art, faq_ld(faq)]


# ================================================================ entry point
def build_pages(games_by_id: dict, site: str, og_image: str, publisher: dict) -> list:
    """Page tuples in the same format as the other builders in build_static_pages.py."""
    return [f(games_by_id, site, og_image, publisher) for f in (game_length_page, russian_voice_page, steam_refund_page, local_coop_page)]


def hub_cards(prefix: str) -> list:
    """(href, title, blurb) for hub pages; prefix is the relative path to the site root."""
    return [(f"{prefix}guides/{s}/", n, b) for s, n, b in ARTICLES]
