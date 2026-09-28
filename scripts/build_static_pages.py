#!/usr/bin/env python3
"""Static (prerendered) pages for search engines. Standard library only, no network.

Reads the same data the SPA uses and writes real HTML pages next to index.html:
  guides/<id>/index.html  — every guide from guides-content.js (window.NP_GUIDES)
  games/<id>/index.html   — every game from app.js (GAMES) + data/catalog.json
  tools/<slug>/index.html — landing pages for the SPA tools (FPS / specs tables from app.js)
  news/<id>/index.html    — news from data/share_index.json (+ excerpt from data/news.json)
  guides/ games/ tools/ news/ index.html — list pages
  free-games/index.html   — giveaways hub from data/freebies.json + data/freebies_archive.json
                            (status now / upcoming / over is computed at build time, MSK)
  data/seo_pages.json     — content hash + lastmod per page (stable sitemap <lastmod>)
  data/news_excerpts.json — short article excerpts kept after a news item leaves news.json, so
                            its page does not change (or thin out) later; pruned with the archive.
                            News pages without an excerpt are "noindex, follow" and not in the sitemap.

Rules: files are written only when their content changes; pages that disappear from the
data are removed (only folders that carry the np:static-page marker are ever deleted).
The SPA (index.html, #guide=…, ?news=…) is untouched — every page links back to it.

Run directly (python scripts/build_static_pages.py) or via build_site_meta.py, which also
puts every page into sitemap.xml.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

from np_common import DATA, MSK, ROOT, log, read_json

CONFIG = read_json(DATA / "site_config.json", {}) or {}
SITE = (CONFIG.get("siteUrl") or "https://derzko435.github.io/nexus-pulse/").rstrip("/") + "/"
OG_IMAGE = SITE + "assets/og-image.png"
LOGO = SITE + "assets/icons/icon-512.png"
MANIFEST = DATA / "seo_pages.json"
NEWS_STORE = DATA / "news_excerpts.json"
MARKER = "<!-- np:static-page -->"
SECTIONS = ("guides", "games", "tools", "news")
ID_RE = re.compile(r"^[A-Za-z0-9][\w-]{0,63}$")


# ---------------------------------------------------------------- JS literal parser
class JSParseError(ValueError):
    pass


class _JS:
    """Parses a JavaScript *data* literal (objects, arrays, strings, numbers, true/false/null).
    Anything else (function calls, spreads, ${} templates) raises JSParseError."""

    def __init__(self, src: str, pos: int):
        self.s, self.i = src, pos

    def err(self, msg: str):
        line = self.s.count("\n", 0, self.i) + 1
        raise JSParseError(f"{msg} at line {line}: {self.s[self.i:self.i + 40]!r}")

    def ws(self):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in " \t\r\n\ufeff":
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = len(s) if j < 0 else j + 1
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                if j < 0:
                    self.err("unterminated comment")
                self.i = j + 2
            else:
                break

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            self.err("unexpected end")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c in "\"'`":
            return self.string()
        m = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?").match(self.s, self.i)
        if m:
            self.i = m.end()
            t = m.group(0)
            return float(t) if any(x in t for x in ".eE") else int(t)
        m = re.compile(r"[A-Za-z_$][\w$]*").match(self.s, self.i)
        if m and m.group(0) in ("true", "false", "null", "undefined"):
            self.i = m.end()
            return {"true": True, "false": False}.get(m.group(0))
        self.err("unsupported value")

    def string(self):
        q = self.s[self.i]
        self.i += 1
        out = []
        s = self.s
        while True:
            if self.i >= len(s):
                self.err("unterminated string")
            c = s[self.i]
            if c == q:
                self.i += 1
                return "".join(out)
            if q == "`" and s.startswith("${", self.i):
                self.err("template expression")
            if c == "\\":
                n = s[self.i + 1]
                self.i += 2
                if n == "u":
                    if s[self.i] == "{":
                        j = s.index("}", self.i)
                        out.append(chr(int(s[self.i + 1:j], 16)))
                        self.i = j + 1
                    else:
                        out.append(chr(int(s[self.i:self.i + 4], 16)))
                        self.i += 4
                elif n == "x":
                    out.append(chr(int(s[self.i:self.i + 2], 16)))
                    self.i += 2
                elif n == "\n":
                    pass
                else:
                    out.append({"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}.get(n, n))
                continue
            if c == "\n" and q != "`":
                self.err("newline in string")
            out.append(c)
            self.i += 1

    def arr(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1
            elif self.s[self.i] != "]":
                self.err("expected , or ]")

    def obj(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                return out
            if c in "\"'":
                key = self.string()
            else:
                m = re.compile(r"[A-Za-z_$][\w$]*|\d+").match(self.s, self.i)
                if not m:
                    self.err("bad key")
                key = m.group(0)
                self.i = m.end()
            self.ws()
            if self.s[self.i] != ":":
                self.err("expected :")
            self.i += 1
            out[key] = self.value()
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1
            elif self.s[self.i] != "}":
                self.err("expected , or }")


def js_literal(path: Path, name: str):
    """Value assigned to `const NAME =` / `window.NAME =` in a JS file."""
    src = path.read_text(encoding="utf-8")
    m = re.search(r"(?:\b(?:const|let|var)\s+|\bwindow\.)" + re.escape(name) + r"\s*=\s*", src)
    if not m:
        raise JSParseError(f"{name} not found in {path.name}")
    return _JS(src, m.end()).value()


# ---------------------------------------------------------------- helpers
def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def clip(s, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def js_round(x: float) -> int:
    return int(math.floor(x + 0.5))


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def ld(obj) -> str:
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + txt.replace("</", "<\\/") + "</script>"


def https(u) -> str:
    u = str(u or "")
    return u if u.startswith("https://") else ""


PLURAL = lambda n, a, b, c: a if n % 10 == 1 and n % 100 != 11 else b if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else c  # noqa: E731

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def ru_date(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    if d.tzinfo:
        d = d.astimezone(MSK)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- data
def load_data():
    games = [g for g in js_literal(ROOT / "app.js", "GAMES") if isinstance(g, dict) and ID_RE.match(str(g.get("id") or "")) and g.get("title")]
    specs = js_literal(ROOT / "app.js", "SPECS")
    try:
        gpu = js_literal(ROOT / "app.js", "GPU_MULT")
        cpu = js_literal(ROOT / "app.js", "CPU_MULT")
        base = js_literal(ROOT / "app.js", "BASE_FPS")
    except JSParseError:
        gpu, cpu, base = {"budget": 0.55, "mid": 1.0, "high": 1.45, "ultra": 1.9}, {"mid": 1.0}, 95
    guides = [g for g in js_literal(ROOT / "guides-content.js", "NP_GUIDES") if isinstance(g, dict) and ID_RE.match(str(g.get("id") or "")) and g.get("title")]
    if len(games) < 10 or len(guides) < 5:
        raise JSParseError(f"too few items parsed (games={len(games)}, guides={len(guides)})")
    catalog = (read_json(DATA / "catalog.json", {}) or {}).get("games") or {}
    fps = {"gpu": gpu, "cpu_mid": float(cpu.get("mid", 1.0)), "base": float(base)}
    return games, specs, fps, guides, catalog


def load_news():
    items = []
    for a in (read_json(DATA / "share_index.json", {}) or {}).get("news") or []:
        if isinstance(a, dict) and ID_RE.match(str(a.get("id") or "")) and a.get("title"):
            items.append(dict(a))
    items.sort(key=lambda a: (a.get("date") or "", a["id"]), reverse=True)
    keep = {a["id"] for a in items}
    old = (read_json(NEWS_STORE, {}) or {}).get("items") or {}
    store = {k: v for k, v in old.items() if k in keep and isinstance(v, list)}
    for n in (read_json(DATA / "news.json", {}) or {}).get("items") or []:
        if isinstance(n, dict) and n.get("id") in keep:
            ex = news_excerpt(n)
            if ex:
                store[n["id"]] = ex
    if store != old:
        NEWS_STORE.write_text(json.dumps({"about": "Generated by scripts/build_static_pages.py: excerpts for news/<id>/ pages. Do not edit.",
                                          "items": dict(sorted(store.items()))}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    for a in items:
        a["excerpt"] = store.get(a["id"]) or []
    return items


# ---------------------------------------------------------------- tools (static copy)
TOOLS = [
    {"slug": "fps-calculator", "anchor": "fpsTool", "icon": "📈", "name": "Калькулятор FPS",
     "title": "Калькулятор FPS в играх онлайн — сколько кадров выдаст твой ПК",
     "lead": "Выбери игру из каталога NEXUS PULSE, уровень видеокарты и процессора — и получи ориентировочный FPS. Ниже — готовая таблица оценок для всех игр каталога.",
     "steps": ["Открой инструмент «Оценка FPS» на главной странице NEXUS PULSE.",
               "Выбери игру из каталога (75 популярных игр).",
               "Укажи уровень видеокарты: бюджетный (GTX 1650 / RX 6500), средний (RTX 4060 / RX 7600), высокий (RTX 4070 Ti / RX 7800 XT) или топовый (RTX 4090 / RX 7900 XTX).",
               "Укажи уровень процессора и нажми «Рассчитать»."],
     "notes": ["Это ориентир, а не бенчмарк: реальный FPS зависит от разрешения, настроек графики, драйверов и конкретной сцены.",
               "Оценка учитывает «тяжесть» игры: требовательные проекты вроде Cyberpunk 2077 получают меньше кадров, чем киберспортивные шутеры.",
               "Если FPS ниже частоты монитора — начни с гайда по повышению FPS: драйверы, режим питания и апскейлеры (DLSS / FSR / XeSS) дают прирост бесплатно."],
     "guides": ["fps-boost", "windows-settings", "cs2-graphics"], "table": "fps"},
    {"slug": "system-requirements", "anchor": "specsTool", "icon": "🧾", "name": "Системные требования игр",
     "title": "Системные требования игр — минимальные и рекомендуемые",
     "lead": "Сравни минимальные и рекомендованные системные требования популярных игр: процессор, видеокарта, оперативная память и место на диске.",
     "steps": ["Открой инструмент «Системные требования» на главной странице.",
               "Выбери игру из списка.",
               "Нажми «Показать требования» — минимальные и рекомендованные параметры появятся рядом для сравнения."],
     "notes": ["Минимальные требования — это запуск на низких настройках, обычно 30+ FPS в 1080p.",
               "Рекомендованные — комфортная игра на средних и высоких настройках.",
               "Для многих современных игр SSD фактически обязателен: с HDD растут загрузки и подгрузка текстур."],
     "guides": ["fps-boost"], "table": "specs"},
    {"slug": "pc-builder", "anchor": "pcBuilder", "icon": "🖥️", "name": "Калькулятор сборки ПК",
     "title": "Калькулятор сборки ПК — какие игры потянет твой компьютер",
     "lead": "Собери ПК из процессора, видеокарты, памяти и накопителя, выбери разрешение — и посмотри, какие игры каталога он потянет и с каким запасом.",
     "steps": ["Открой «Калькулятор PC-сборки» на главной странице.",
               "Выбери CPU, GPU, объём RAM, накопитель и разрешение (1080p, 1440p или 4K).",
               "Нажми «Пересчитать»: появится общий скор сборки и список совместимых игр.",
               "Кликни по игре, чтобы увидеть оценку FPS, и нажми «Поделиться сборкой», чтобы отправить её другу."],
     "notes": ["Сборку можно сохранить в браузере и перенести на другое устройство через резервную копию профиля.",
               "Разрешение сильно влияет на результат: 4K нагружает видеокарту в разы сильнее, чем 1080p."],
     "guides": ["fps-boost"]},
    {"slug": "game-picker", "anchor": "moodPicker", "icon": "🎲", "name": "Подбор игры под настроение",
     "title": "Во что поиграть? Подбор игры под настроение и время",
     "lead": "Не знаешь, во что поиграть сегодня? Выбери настроение, сколько у тебя времени и хочешь ли играть один или с друзьями — получишь три рекомендации из каталога.",
     "steps": ["Открой «Подбор игры под настроение и время» на главной странице.",
               "Выбери настроение: расслабиться, посоревноваться, сюжет и погружение, пощекотать нервы, с друзьями или погриндить.",
               "Укажи, сколько есть времени: 15–30 минут, около часа, 2+ часа или весь вечер.",
               "Выбери режим (соло, мультиплеер или не важно) и нажми «Подобрать игры»."],
     "notes": ["Рекомендации берутся из каталога NEXUS PULSE — у каждой игры есть отдельная страница с описанием и оценкой FPS."],
     "guides": []},
    {"slug": "speed-test", "anchor": "speedTest", "icon": "⚡", "name": "Тест скорости интернета",
     "title": "Тест скорости интернета для игр — скорость и пинг",
     "lead": "Проверь скорость загрузки и пинг прямо в браузере и узнай, подходит ли твоя сеть для онлайн-игр.",
     "steps": ["Открой «Тест скорости» на главной странице.",
               "Закрой торренты и загрузки, которые могут исказить результат.",
               "Нажми «Проверить скорость» и дождись результата: загрузка в Мбит/с, пинг в мс и оценка для онлайна."],
     "notes": ["Для онлайн-игр пинг и его стабильность важнее скорости: даже 20 Мбит/с хватает, если пинг низкий и ровный.",
               "Кабель почти всегда стабильнее Wi-Fi; если играешь по Wi-Fi — используй 5 ГГц."],
     "guides": ["network-ping"]},
    {"slug": "ping-map", "anchor": "pingMapCard", "icon": "📡", "name": "Карта пинга до игровых серверов",
     "title": "Пинг до серверов Steam, Riot, Blizzard и Epic — проверка онлайн",
     "lead": "Замерь время отклика до серверов Steam, Riot Games (Valorant, League of Legends), Blizzard и Epic Games прямо из браузера.",
     "steps": ["Открой «Карту пинга» на главной странице.",
               "Замер запускается автоматически; нажми «Обновить», чтобы повторить его.",
               "Сравни задержку до разных сервисов: высокая задержка до одного сервиса — повод проверить маршрут или выбрать другой регион сервера."],
     "notes": ["Замер из браузера показывает ориентировочную задержку — внутриигровой пинг может немного отличаться."],
     "guides": ["network-ping"]},
    {"slug": "nickname-generator", "anchor": "nickGenCard", "icon": "🏷️", "name": "Генератор ника и аватара",
     "title": "Генератор ников для игр и аватарок — онлайн и бесплатно",
     "lead": "Придумай никнейм для игр в одном из стилей — Cyberpunk, Fantasy, Shooter, Cozy, Space или Pro — и получи к нему аватар, который можно скачать в PNG.",
     "steps": ["Открой «Ник + аватар» на главной странице.",
               "Выбери стиль ника.",
               "Нажми «Сгенерировать» столько раз, сколько нужно, затем «Копировать ник» или «Скачать PNG»."],
     "notes": ["Всё генерируется прямо в браузере — ничего не отправляется на сервер."],
     "guides": []},
    {"slug": "steam-library-import", "anchor": "steamImportCard", "icon": "📚", "name": "Импорт библиотеки Steam и Epic",
     "title": "Импорт библиотеки Steam и Epic Games",
     "lead": "Импортируй игры из публичного профиля Steam или отметь свои игры вручную — сайт подсветит их в каталоге и подборках.",
     "steps": ["Открой «Импорт библиотеки Steam / Epic» на главной странице.",
               "Вставь SteamID64, vanity-ник или ссылку на профиль и нажми «Импортировать Steam» (профиль и список игр должны быть публичными).",
               "Для Epic Games сохрани ник и отметь игры вручную через поиск по каталогу."],
     "notes": ["Библиотека хранится только в твоём браузере."],
     "guides": []},
    {"slug": "profile-backup", "anchor": "profileBackupCard", "icon": "💾", "name": "Резервная копия профиля",
     "title": "Резервная копия профиля NEXUS PULSE — перенос на другое устройство",
     "lead": "Сохрани сборку ПК, библиотеку игр, отслеживаемые цены, карточку LFG, чеклисты и избранное в файл и восстанови их на другом устройстве.",
     "steps": ["Открой «Резервную копию профиля» на главной странице.",
               "Нажми «Экспортировать» — скачается JSON-файл с твоими данными.",
               "На другом устройстве нажми «Импортировать» и выбери этот файл."],
     "notes": ["NEXUS PULSE не хранит персональные данные на сервере — всё лежит в браузере, поэтому резервная копия — единственный способ перенести профиль."],
     "guides": []},
]

GPU_LABELS = [("budget", "Бюджет", "GTX 1650 / RX 6500"), ("mid", "Средний", "RTX 4060 / RX 7600"),
              ("high", "Высокий", "RTX 4070 Ti / RX 7800 XT"), ("ultra", "Топ", "RTX 4090 / RX 7900 XTX")]


def fps_for(game: dict, fps: dict, tier: str) -> int:
    demand = float(game.get("demand") or 1) or 1
    v = js_round(fps["base"] * float(fps["gpu"].get(tier, 1)) * fps["cpu_mid"] / demand)
    return max(25, min(360, v))


# ---------------------------------------------------------------- layout
STATIC_CSS = "assets/static-pages.css"


def metrika_snippet() -> str:
    mid = str(CONFIG.get("yandexMetrikaId") or "").strip()
    if not re.fullmatch(r"\d{5,12}", mid):
        return ""
    return ("<script>(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();"
            "for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return;}"
            "k=e.createElement(t);a=e.getElementsByTagName(t)[0];k.async=1;k.src=r;a.parentNode.insertBefore(k,a)})"
            f"(window,document,\"script\",\"https://mc.yandex.ru/metrika/tag.js?id={mid}\",\"ym\");"
            f"ym({mid},\"init\",{{ssr:true,clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:false}});</script>\n")


def layout(*, path: str, title: str, desc: str, body: str, crumbs: list, og_type: str = "website",
           image: str = "", jsonld: list | None = None, extra_meta: str = "", index: bool = True) -> str:
    depth = path.count("/")
    rel = "../" * depth
    url = SITE + path
    img = https(image) or OG_IMAGE
    crumb_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + p} for i, (name, p) in enumerate(crumbs)]}
    crumb_html = "".join(
        f'<li><a href="{e(rel + p) if p else e(rel)}">{e(name)}</a></li>' if i < len(crumbs) - 1 else f'<li aria-current="page">{e(name)}</li>'
        for i, (name, p) in enumerate(crumbs))
    scripts = "\n".join(ld(x) for x in (jsonld or []) + [crumb_ld])
    nav = [("news/", "Новости"), ("games/", "Игры"), ("guides/", "Гайды"), ("tools/", "Инструменты"), ("free-games/", "Халява")]
    cur = path.split("/")[0] + "/"
    cur_attr = ' aria-current="true"'
    nav_html = "".join(f'<li><a href="{rel}{p}"{cur_attr if p == cur else ""}>{n}</a></li>' for p, n in nav)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta name="robots" content="{"index, follow, max-image-preview:large" if index else "noindex, follow"}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="NEXUS PULSE">
<meta property="og:locale" content="ru_RU">
<meta property="og:url" content="{e(url)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(img)}">
{extra_meta}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(img)}">
{scripts}
<link rel="icon" type="image/png" sizes="192x192" href="{rel}assets/icons/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="{rel}assets/icons/apple-touch-icon.png">
<link rel="manifest" href="{rel}manifest.json">
<meta name="theme-color" content="#00f5ff">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800&amp;family=Manrope:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
<link rel="stylesheet" href="{rel}styles.css">
<link rel="stylesheet" href="{rel}{STATIC_CSS}">
{metrika_snippet()}</head>
<body class="sp-page">
{MARKER}
<div class="bg-grid" aria-hidden="true"></div>
<div class="bg-glow" aria-hidden="true"></div>
<header class="site-header">
<nav class="nav container sp-nav" aria-label="Главная навигация">
<a href="{rel}" class="logo"><span class="logo-mark"><img src="{rel}assets/nexus-pulse-icon.png" alt="NEXUS PULSE" width="36" height="36"></span><span class="logo-text">NEXUS<span>PULSE</span></span></a>
<ul class="sp-menu">{nav_html}</ul>
<a href="{rel}" class="btn btn-primary btn-sm sp-open">Открыть портал</a>
</nav>
</header>
<main class="container sp-main">
<nav class="sp-crumbs" aria-label="Хлебные крошки"><ol>{crumb_html}</ol></nav>
{body}
</main>
<footer class="site-footer">
<div class="container footer-inner">
<div class="footer-brand">
<a href="{rel}" class="logo"><span class="logo-mark"><img src="{rel}assets/nexus-pulse-icon.png" alt="NEXUS PULSE" width="36" height="36" loading="lazy"></span><span class="logo-text">NEXUS<span>PULSE</span></span></a>
<p>Игровой портал для тех, кто играет серьёзно.</p>
</div>
<nav class="footer-nav" aria-label="Навигация в подвале">
<a href="{rel}news/">Новости</a>
<a href="{rel}games/">Каталог игр</a>
<a href="{rel}guides/">Гайды</a>
<a href="{rel}tools/">Инструменты</a>
<a href="{rel}#calendar">Релизы</a>
<a href="{rel}#esports">Киберспорт</a>
<a href="{rel}#deals">Скидки</a>
<a href="{rel}free-games/">Халява</a>
<a href="{rel}#community">Discord</a>
</nav>
</div>
<div class="container footer-bottom">
<p>© 2026 NEXUS PULSE</p>
<p class="privacy">Персональные данные не собираются.</p>
</div>
</footer>
</body>
</html>
"""


def publisher():
    return {"@type": "Organization", "name": "NEXUS PULSE", "url": SITE, "logo": {"@type": "ImageObject", "url": LOGO}}


def links_list(items, cls="sp-links") -> str:
    """items: (href, title, note)"""
    if not items:
        return ""
    note = lambda n: f' <span class="sp-note">{e(n)}</span>' if n else ""  # noqa: E731
    lis = "".join(f'<li><a href="{e(h)}">{e(t)}</a>{note(n)}</li>' for h, t, n in items)
    return f'<ul class="{cls}">{lis}</ul>'


# ---------------------------------------------------------------- guides
def guide_section_html(sec: dict, i: int) -> str:
    inner = ""
    if sec.get("steps"):
        inner = '<ol class="guide-steps">' + "".join(f"<li>{e(x)}</li>" for x in sec["steps"]) + "</ol>"
    elif sec.get("list"):
        inner = "<ul>" + "".join(f"<li>{e(x)}</li>" for x in sec["list"]) + "</ul>"
    elif sec.get("settings"):
        rows = "".join(
            f'<tr><th scope="row">{e(r[0] if len(r) > 0 else "")}</th><td class="gt-val">{e(r[1] if len(r) > 1 else "")}</td><td class="gt-why">{e(r[2] if len(r) > 2 else "")}</td></tr>'
            for r in sec["settings"] if isinstance(r, list))
        inner = f'<div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Параметр</th><th>Значение</th><th>Зачем</th></tr></thead><tbody>{rows}</tbody></table></div>'
    elif sec.get("text"):
        inner = f"<p>{e(sec['text'])}</p>"
    return f'<section class="guide-sec" id="s{i + 1}"><h2>{e(sec.get("h"))}</h2>{inner}</section>'


def guide_text(g: dict) -> str:
    parts = [g.get("lead") or ""]
    for s in g.get("sections") or []:
        parts += [s.get("h") or "", s.get("text") or ""] + list(s.get("steps") or []) + list(s.get("list") or [])
    return " ".join(p for p in parts if p)


def guide_page(g, games_by_id, guides, catalog):
    gid = g["id"]
    path = f"guides/{gid}/"
    game = games_by_id.get(g.get("game") or "")
    info = catalog.get(g.get("game") or "") or {}
    image = https(info.get("img")) if not info.get("fit") else ""
    title = f"{g['title']} — гайд | NEXUS PULSE"
    desc = clip(g.get("lead"), 160)
    secs = g.get("sections") or []
    toc = "".join(f'<li><a href="#s{i + 1}">{e(s.get("h"))}</a></li>' for i, s in enumerate(secs))
    if g.get("tips"):
        toc += '<li><a href="#tips">Советы новичку</a></li>'
    if g.get("mistakes"):
        toc += '<li><a href="#mistakes">Частые ошибки</a></li>'
    related = [x for x in guides if x["id"] != gid and ((g.get("game") and x.get("game") == g.get("game")) or x.get("tag") == g.get("tag"))]
    related += [x for x in guides if x["id"] != gid and x not in related]
    related = related[:6]
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Гайд · {e(g.get("tag"))}</p>
<h1 class="sp-h1">{e(g["title"])}</h1>
<p class="sp-meta">⏱ {e(g.get("time"))}{" · " + e(g.get("level")) if g.get("level") else ""}{f' · игра: <a href="../../games/{e(game["id"])}/">{e(game["title"])}</a>' if game else ""}</p>
{f'<img class="sp-hero" src="{e(image)}" alt="{e(g["title"])}" width="460" height="215" loading="eager" referrerpolicy="no-referrer">' if image else ""}
<div class="npv-body guide-body">
<p class="guide-lead">{e(g.get("lead"))}</p>
{f'<nav class="guide-toc sp-toc" aria-label="Содержание"><p>Содержание</p><ol>{toc}</ol></nav>' if toc else ""}
{"".join(guide_section_html(s, i) for i, s in enumerate(secs))}
{('<section class="guide-sec guide-tips" id="tips"><h2>💡 Советы новичку</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in g["tips"]) + "</ul></section>") if g.get("tips") else ""}
{('<section class="guide-sec guide-mistakes" id="mistakes"><h2>⚠️ Частые ошибки</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in g["mistakes"]) + "</ul></section>") if g.get("mistakes") else ""}
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="../../#guide={e(gid)}">Открыть в портале NEXUS PULSE</a>
<a class="btn btn-ghost btn-sm" href="../">Все гайды</a>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Ещё гайды</h2>
{links_list([(f"../{x['id']}/", x["title"], x.get("tag")) for x in related])}
{f'<h2 class="sp-h2">Игра</h2>' + links_list([(f"../../games/{game['id']}/", game["title"], game.get("genre"))]) if game else ""}
</aside>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": clip(g["title"], 110), "description": desc,
           "inLanguage": "ru", "articleSection": g.get("tag") or "Гайды", "url": SITE + path,
           "mainEntityOfPage": SITE + path, "image": image or OG_IMAGE, "author": publisher(), "publisher": publisher(),
           "wordCount": len(guide_text(g).split())}
    if game:
        art["about"] = {"@type": "VideoGame", "name": game["title"], "url": SITE + f"games/{game['id']}/"}
    return path, title, desc, body, [("Главная", ""), ("Гайды", "guides/"), (g["title"], path)], "article", image, [art]


def guides_index(guides):
    path = "guides/"
    title = "Гайды по играм и настройке ПК — NEXUS PULSE"
    desc = clip(f"{len(guides)} подробных гайдов: как поднять FPS, настройки CS2 и Valorant, пинг и Wi-Fi, ранкед, стратегии и советы новичкам.", 160)
    tags = []
    for g in guides:
        if g.get("tag") not in tags:
            tags.append(g.get("tag"))
    cards = "".join(
        f'<a class="guide-card glass sp-card" href="{e(g["id"])}/"><span class="guide-tag">{e(g.get("tag"))}</span>'
        f'<h2 class="sp-card-h">{e(g["title"])}</h2><p class="guide-preview">{e(clip(g.get("lead"), 180))}</p>'
        f'<span class="guide-meta">⏱ {e(g.get("time"))}{" · " + e(g.get("level")) if g.get("level") else ""}</span></a>' for g in guides)
    body = f"""<section class="sp-list">
<p class="eyebrow">Гайды</p>
<h1 class="sp-h1">Гайды и советы для геймеров</h1>
<p class="section-desc">{e(desc)} Темы: {e(", ".join(t for t in tags if t))}.</p>
<div class="cards-grid sp-grid">{cards}</div>
</section>"""
    lst = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Гайды NEXUS PULSE", "url": SITE + path, "inLanguage": "ru",
           "mainEntity": {"@type": "ItemList", "numberOfItems": len(guides), "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": SITE + f"guides/{g['id']}/", "name": g["title"]} for i, g in enumerate(guides)]}}
    return path, title, desc, body, [("Главная", ""), ("Гайды", path)], "website", "", [lst]


# ---------------------------------------------------------------- games
def game_page(g, games, specs, fps, guides, catalog):
    gid = g["id"]
    path = f"games/{gid}/"
    info = catalog.get(gid) or {}
    image = https(info.get("img"))
    sp = specs.get(gid) if isinstance(specs, dict) else None
    plats = ", ".join(g.get("platforms") or [])
    title = (f"{g['title']}: системные требования, FPS и рейтинг — NEXUS PULSE" if sp
             else f"{g['title']}: описание, рейтинг и оценка FPS — NEXUS PULSE")
    desc = clip(f"{g['title']} — {g.get('genre')}, рейтинг редакции {float(g.get('rating') or 0):.1f}/10. {g.get('desc') or ''} {info.get('desc') or ''}", 160)
    facts = [("Жанр", g.get("genre")), ("Рейтинг редакции", f"★ {float(g.get('rating') or 0):.1f} / 10"), ("Платформы", plats),
             ("Жанры в Steam", ", ".join(info.get("genres") or [])), ("Дата выхода", info.get("release"))]
    facts_html = "".join(f"<li><b>{e(k)}:</b> {e(v)}</li>" for k, v in facts if v)
    fps_rows = "".join(f"<tr><th scope=\"row\">{e(n)} <span class=\"sp-note\">({e(ex)})</span></th><td class=\"gt-val\">≈ {fps_for(g, fps, k)} FPS</td></tr>"
                       for k, n, ex in GPU_LABELS)
    specs_html = ""
    if sp:
        col = lambda h, lst: f'<div class="spec-col"><h3>{e(h)}</h3><ul>' + "".join(f"<li>{e(x)}</li>" for x in lst or []) + "</ul></div>"  # noqa: E731
        specs_html = f'<section class="guide-sec"><h2>Системные требования {e(g["title"])}</h2><div class="specs-compare sp-specs">{col("Минимальные", sp.get("min"))}{col("Рекомендованные", sp.get("rec"))}</div></section>'
    rel_guides = [x for x in guides if x.get("game") == gid]
    similar = [x for x in games if x["id"] != gid and x.get("genre") == g.get("genre")]
    similar.sort(key=lambda x: (-float(x.get("rating") or 0), x["id"]))
    similar = similar[:8]
    steam = https(info.get("url"))
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Каталог · {e(g.get("genre"))}</p>
<h1 class="sp-h1">{e(g["title"])}</h1>
{f'<img class="sp-hero" src="{e(image)}" alt="{e(g["title"])}" width="460" height="215" loading="eager" referrerpolicy="no-referrer">' if image else ""}
<div class="npv-body">
<p><strong>{e(g.get("desc"))}</strong></p>
{f"<p>{e(info['desc'])}</p>" if info.get("desc") else ""}
<ul class="npv-facts">{facts_html}</ul>
<section class="guide-sec"><h2>Сколько FPS будет в {e(g["title"])}</h2>
<p>Ориентировочная оценка NEXUS PULSE для процессора среднего уровня, 1080p. Реальный результат зависит от настроек графики и сцены — точнее посчитает <a href="../../tools/fps-calculator/">калькулятор FPS</a>.</p>
<div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Видеокарта</th><th>FPS</th></tr></thead><tbody>{fps_rows}</tbody></table></div>
</section>
{specs_html}
{('<section class="guide-sec"><h2>Гайды по ' + e(g["title"]) + "</h2>" + links_list([(f"../../guides/{x['id']}/", x["title"], x.get("time")) for x in rel_guides]) + "</section>") if rel_guides else ""}
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="../../#game={e(gid)}">Открыть в каталоге NEXUS PULSE</a>
{f'<a class="btn btn-ghost btn-sm" href="{e(steam)}" target="_blank" rel="noopener noreferrer">{"Страница в Steam" if info.get("appid") else "Официальный сайт"} ↗</a>' if steam else ""}
<a class="btn btn-ghost btn-sm" href="../">Все игры</a>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Похожие игры</h2>
{links_list([(f"../{x['id']}/", x["title"], f"★ {float(x.get('rating') or 0):.1f}") for x in similar])}
<h2 class="sp-h2">Инструменты</h2>
{links_list([("../../tools/fps-calculator/", "Калькулятор FPS", ""), ("../../tools/system-requirements/", "Системные требования", ""), ("../../tools/pc-builder/", "Сборка ПК", "")])}
</aside>"""
    vg = {"@context": "https://schema.org", "@type": "VideoGame", "name": g["title"], "url": SITE + path, "description": desc,
          "genre": [x for x in [g.get("genre")] + list(info.get("genres") or []) if x], "gamePlatform": list(g.get("platforms") or []),
          "inLanguage": "ru", "image": image or OG_IMAGE,
          "review": {"@type": "Review", "author": publisher(),
                     "reviewRating": {"@type": "Rating", "ratingValue": float(g.get("rating") or 0), "bestRating": 10, "worstRating": 1}}}
    if steam:
        vg["sameAs"] = steam
    return path, title, desc, body, [("Главная", ""), ("Игры", "games/"), (g["title"], path)], "website", image, [vg]


def games_index(games, catalog):
    path = "games/"
    title = f"Каталог игр — {len(games)} популярных игр с рейтингом и FPS | NEXUS PULSE"
    desc = clip(f"Каталог NEXUS PULSE: {len(games)} игр — RPG, шутеры, киберспорт, MMO и инди. Рейтинг редакции, платформы, системные требования и оценка FPS.", 160)
    genres = []
    for g in games:
        if g.get("genre") not in genres:
            genres.append(g.get("genre"))
    blocks = []
    for gen in genres:
        items = [g for g in games if g.get("genre") == gen]
        cards = "".join(
            f'<a class="game-card sp-card sp-game" href="{e(g["id"])}/"><div class="card-body"><h3>{e(g["title"])}</h3>'
            f'<div class="card-meta"><span class="rating">★ {float(g.get("rating") or 0):.1f}</span><span>{e(", ".join(g.get("platforms") or []))}</span></div>'
            f'<p class="card-desc">{e(g.get("desc"))}</p></div></a>' for g in items)
        blocks.append(f'<section class="sp-group"><h2 class="sp-h2">{e(gen)} <span class="sp-note">· {len(items)}</span></h2><div class="cards-grid sp-grid">{cards}</div></section>')
    body = f"""<section class="sp-list">
<p class="eyebrow">Каталог</p>
<h1 class="sp-h1">Каталог игр NEXUS PULSE</h1>
<p class="section-desc">{e(desc)}</p>
<p class="section-desc">🎁 <a href="../free-games/">Бесплатные игры сейчас</a>: текущие раздачи Epic Games, Steam и GOG.</p>
{"".join(blocks)}
</section>"""
    lst = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Каталог игр NEXUS PULSE", "url": SITE + path, "inLanguage": "ru",
           "mainEntity": {"@type": "ItemList", "numberOfItems": len(games), "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": SITE + f"games/{g['id']}/", "name": g["title"]} for i, g in enumerate(games)]}}
    return path, title, desc, body, [("Главная", ""), ("Игры", path)], "website", "", [lst]


# ---------------------------------------------------------------- tools
def tool_page(t, games, specs, fps, guides_by_id):
    path = f"tools/{t['slug']}/"
    title = f"{t['title']} | NEXUS PULSE"
    desc = clip(t["lead"], 160)
    table = ""
    if t.get("table") == "fps":
        rows = "".join(
            f'<tr><th scope="row"><a href="../../games/{e(g["id"])}/">{e(g["title"])}</a></th>' + "".join(f"<td>{fps_for(g, fps, k)}</td>" for k, _, _ in GPU_LABELS) + "</tr>"
            for g in games)
        head = "".join(f'<th>{e(n)}<br><span class="sp-note">{e(ex)}</span></th>' for _, n, ex in GPU_LABELS)
        table = f'<section class="guide-sec"><h2>Таблица FPS по играм</h2><p>Ориентировочный FPS в 1080p с процессором среднего уровня.</p><div class="sp-table-wrap"><table class="sp-table sp-table-num"><thead><tr><th>Игра</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></section>'
    elif t.get("table") == "specs":
        by_id = {g["id"]: g for g in games}
        blocks = []
        for gid, sp in (specs or {}).items():
            g = by_id.get(gid)
            if not g or not isinstance(sp, dict):
                continue
            col = lambda h, lst: f'<div class="spec-col"><h4>{e(h)}</h4><ul>' + "".join(f"<li>{e(x)}</li>" for x in lst or []) + "</ul></div>"  # noqa: E731
            blocks.append(f'<section class="sp-spec-game"><h3><a href="../../games/{e(gid)}/">{e(g["title"])}</a></h3><div class="specs-compare sp-specs">{col("Минимальные", sp.get("min"))}{col("Рекомендованные", sp.get("rec"))}</div></section>')
        table = '<section class="guide-sec"><h2>Системные требования популярных игр</h2>' + "".join(blocks) + "</section>"
    rel_guides = [guides_by_id[x] for x in t.get("guides") or [] if x in guides_by_id]
    others = [x for x in TOOLS if x["slug"] != t["slug"]]
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Инструменты · бесплатно · онлайн</p>
<h1 class="sp-h1">{e(t["icon"])} {e(t["name"])}</h1>
<div class="npv-body">
<p class="guide-lead">{e(t["lead"])}</p>
<p><a class="btn btn-primary" href="../../#{e(t["anchor"])}">Открыть инструмент →</a></p>
<section class="guide-sec"><h2>Как пользоваться</h2><ol class="guide-steps">{"".join(f"<li>{e(x)}</li>" for x in t["steps"])}</ol></section>
<section class="guide-sec"><h2>Полезно знать</h2><ul>{"".join(f"<li>{e(x)}</li>" for x in t["notes"])}</ul></section>
{table}
{('<section class="guide-sec"><h2>Гайды по теме</h2>' + links_list([(f"../../guides/{x['id']}/", x["title"], x.get("time")) for x in rel_guides]) + "</section>") if rel_guides else ""}
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="../../#{e(t["anchor"])}">Открыть «{e(t["name"])}»</a>
<a class="btn btn-ghost btn-sm" href="../">Все инструменты</a>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Другие инструменты</h2>
{links_list([(f"../{x['slug']}/", x["name"], "") for x in others])}
</aside>"""
    app = {"@context": "https://schema.org", "@type": "WebApplication", "name": t["name"], "url": SITE + path, "description": desc,
           "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
           "inLanguage": "ru", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
           "publisher": publisher()}
    return path, title, desc, body, [("Главная", ""), ("Инструменты", "tools/"), (t["name"], path)], "website", "", [app]


def tools_index():
    path = "tools/"
    title = "Бесплатные инструменты для геймеров — FPS, требования, пинг | NEXUS PULSE"
    desc = "Калькулятор FPS, системные требования игр, сборка ПК, тест скорости и пинга, подбор игры, генератор ников — бесплатно, прямо в браузере."
    cards = "".join(f'<a class="guide-card glass sp-card" href="{e(t["slug"])}/"><span class="guide-tag">{e(t["icon"])} Инструмент</span>'
                    f'<h2 class="sp-card-h">{e(t["name"])}</h2><p class="guide-preview">{e(clip(t["lead"], 180))}</p></a>' for t in TOOLS)
    body = f"""<section class="sp-list">
<p class="eyebrow">Инструменты</p>
<h1 class="sp-h1">Практические инструменты для геймеров</h1>
<p class="section-desc">{e(desc)}</p>
<p class="section-desc">🎁 <a href="../free-games/">Бесплатные игры сейчас</a>: текущие раздачи Epic Games, Steam и GOG.</p>
<div class="cards-grid sp-grid">{cards}</div>
</section>"""
    lst = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Инструменты NEXUS PULSE", "url": SITE + path, "inLanguage": "ru",
           "mainEntity": {"@type": "ItemList", "numberOfItems": len(TOOLS), "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": SITE + f"tools/{t['slug']}/", "name": t["name"]} for i, t in enumerate(TOOLS)]}}
    return path, title, desc, body, [("Главная", ""), ("Инструменты", path)], "website", "", [lst]


# ---------------------------------------------------------------- news
NEWS_EXCERPT_CHARS = 700
GIVEAWAY_NEWS = re.compile(r"(раздач|халяв|забрать бесплатно|бесплатно (?:забрать|раздают|отдают|получить|раздаст|отдаст))", re.I)


def news_excerpt(n: dict) -> list:
    """First paragraphs of the article (a short quote with attribution, not a full copy)."""
    out, total = [], 0
    for b in n.get("body") or []:
        if not isinstance(b, dict) or b.get("t") != "p":
            continue
        x = re.sub(r"\s+", " ", str(b.get("x") or "")).strip()
        if len(x) < 40:
            continue
        if total + len(x) > NEWS_EXCERPT_CHARS:
            if not out:
                out.append(clip(x, NEWS_EXCERPT_CHARS))
            break
        out.append(x)
        total += len(x)
    return out


def match_games(text: str, games, catalog) -> list:
    t = " " + re.sub(r"[^\w]+", " ", text.lower()) + " "
    hits = []
    for g in games:
        names = {g["title"], (catalog.get(g["id"]) or {}).get("name") or ""}
        for nm in names:
            k = re.sub(r"[^\w]+", " ", nm.lower()).strip()
            if len(k) >= 4 and f" {k} " in t:
                hits.append(g)
                break
    return hits[:4]


def news_page(n, idx, items, games, catalog):
    nid = n["id"]
    path = f"news/{nid}/"
    image = https(n.get("image"))
    title_txt = clip(n["title"], 180)
    title = f"{clip(n['title'], 90)} — новости NEXUS PULSE"
    summary = clip(n.get("summary"), 400)
    desc = clip(summary or f"Новость от {n.get('source') or 'игровых изданий'} на NEXUS PULSE", 160)
    excerpt = n.get("excerpt") or []
    # avoid repeating the summary when it's just the start of the first paragraph
    if excerpt and summary and excerpt[0][:60] == summary.rstrip("…. ")[:60]:
        summary = ""
    newer = items[idx - 1] if idx > 0 else None
    older = items[idx + 1] if idx + 1 < len(items) else None
    hits = match_games(n["title"] + " " + (n.get("summary") or ""), games, catalog)
    src = https(n.get("url"))
    date_txt = ru_date(n.get("date") or "")
    nav_items = []
    if newer:
        nav_items.append((f"../{newer['id']}/", clip(newer["title"], 120), "Следующая новость"))
    if older:
        nav_items.append((f"../{older['id']}/", clip(older["title"], 120), "Предыдущая новость"))
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Новости · {e(n.get("source"))}</p>
<h1 class="sp-h1 sp-h1-news">{e(title_txt)}</h1>
<p class="sp-meta">{f'<time datetime="{e(n.get("date"))}">{e(date_txt)}</time> · ' if date_txt else ""}Источник: {e(n.get("source") or "—")}</p>
{f'<img class="sp-hero" src="{e(image)}" alt="{e(title_txt)}" loading="eager" referrerpolicy="no-referrer">' if image else ""}
<div class="npv-body">
{f"<p><strong>{e(summary)}</strong></p>" if summary else ""}
{"".join(f"<p>{e(p)}</p>" for p in excerpt)}
<p class="npv-source">Источник: {e(n.get("source") or "игровое издание")}. Полная версия материала — на сайте издания{f': <a href="{e(src)}" target="_blank" rel="noopener noreferrer">читать в источнике ↗</a>' if src else "."}</p>
{'<p>🎁 Все текущие раздачи, время окончания по МСК и инструкции — на странице <a href="../../free-games/">«Бесплатные игры и раздачи сегодня»</a>.</p>' if GIVEAWAY_NEWS.search(n["title"]) else ""}
{('<section class="guide-sec"><h2>Игры в новости</h2>' + links_list([(f"../../games/{g['id']}/", g["title"], g.get("genre")) for g in hits]) + "</section>") if hits else ""}
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="../../?news={e(nid)}">Открыть в портале NEXUS PULSE</a>
<a class="btn btn-ghost btn-sm" href="../">Все новости</a>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Ещё новости</h2>
{links_list(nav_items)}
<p><a href="../">Архив новостей →</a></p>
</aside>"""
    art = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": clip(n["title"], 110), "description": desc,
           "inLanguage": "ru", "url": SITE + path, "mainEntityOfPage": SITE + path, "image": [image or OG_IMAGE],
           "author": {"@type": "Organization", "name": n.get("source") or "NEXUS PULSE"}, "publisher": publisher()}
    if n.get("date"):
        art["datePublished"] = n["date"]
        art["dateModified"] = n["date"]
    if src:
        art["isBasedOn"] = src
    extra = ""
    if n.get("date"):
        extra += f'<meta property="article:published_time" content="{e(n["date"])}">\n'
    return path, title, desc, body, [("Главная", ""), ("Новости", "news/"), (clip(n["title"], 60), path)], "article", image, [art], extra, bool(excerpt)


def news_index(items):
    path = "news/"
    title = "Новости игр — архив NEXUS PULSE"
    desc = "Свежие новости игр и киберспорта из российских игровых изданий: релизы, патчи, анонсы и турниры. Обновляется несколько раз в день."
    rows = "".join(
        f'<li><a href="{e(n["id"])}/">{e(clip(n["title"], 180))}</a> <span class="sp-note">{e(n.get("source") or "")}{" · " + e(ru_date(n.get("date") or "")) if n.get("date") else ""}</span></li>'
        for n in items)
    body = f"""<section class="sp-list">
<p class="eyebrow">Новости</p>
<h1 class="sp-h1">Новости игр и киберспорта</h1>
<p class="section-desc">{e(desc)} Самые свежие — в <a href="../#news">ленте на главной</a>.</p>
<ul class="sp-news-list glass">{rows}</ul>
</section>"""
    lst = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Новости игр — NEXUS PULSE", "url": SITE + path, "inLanguage": "ru",
           "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": SITE + f"news/{n['id']}/", "name": clip(n["title"], 110)} for i, n in enumerate(items)]}}
    return path, title, desc, body, [("Главная", ""), ("Новости", path)], "website", "", [lst]


# ---------------------------------------------------------------- free games (free-games/)
FREEBIES_FILE = DATA / "freebies.json"
FREEBIES_ARCHIVE = DATA / "freebies_archive.json"
# curated placeholder rows (not concrete giveaways) — same filter as np_digest.py / discord_feeds.py
CURATED_FREEBIE = re.compile(r"(-always$|^gog-giveaway|^prime-)")
FREE_TO_PLAY = ["cs2", "dota2", "fortnite", "apex", "valorant", "lol", "destiny2", "ow2", "poe2", "lostark", "gw2", "rocket"]
CHECKED_MONTH = "сентябрь 2026"  # «Проверено» for the Russia table — update by hand after a manual re-check
TRACKED_SINCE = "сентября 2026 года"
ARCHIVE_MONTHS = 12
MONTHS_NOM = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
TG_URL = "https://t.me/nexuspulse_news"
EPIC_FREE_URL = "https://store.epicgames.com/ru/free-games"


def now_msk() -> datetime:
    """Current MSK time. NP_NOW (ISO datetime) overrides it — only for tests (giveaway rollover)."""
    forced = os.environ.get("NP_NOW")
    if forced:
        d = datetime.fromisoformat(forced)
        return (d if d.tzinfo else d.replace(tzinfo=MSK)).astimezone(MSK)
    return datetime.now(MSK)


def parse_iso(v) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(MSK) if d.tzinfo else None


def ru_day(d: datetime, year: bool = False) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}" + (f" {d.year}" if year else "")


def ru_dt(d: datetime, year: bool = False) -> str:
    return f"{ru_day(d, year)}, {d:%H:%M}"


def rub(n) -> str:
    try:
        v = int(n)
    except (TypeError, ValueError):
        return ""
    return f"{v:,}".replace(",", "\u00a0") + "\u00a0₽" if v > 0 else ""


def and_join(names: list) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " и " + names[-1] if names else ""


def load_freebies(now: datetime) -> dict:
    """Real giveaways from data/freebies.json (+ archive), with status computed for `now`.
    Curated placeholder rows never become giveaways. Old-format rows (no startsAt/endsAt) still work:
    the end is then a date only and «upcoming» comes from the note."""
    payload = read_json(FREEBIES_FILE, {}) or {}
    arch = [x for x in (read_json(FREEBIES_ARCHIVE, {}) or {}).get("items") or [] if isinstance(x, dict)]
    by_id = {}
    for a in arch:  # newest start per id wins (description / image for the H3 blocks)
        if a.get("id") and (a.get("startsAt") or "") >= (by_id.get(a["id"], {}).get("startsAt") or ""):
            by_id[a["id"]] = a
    now_items, soon, curated = [], [], []
    for it in payload.get("items") or []:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        fid = str(it.get("id") or "")
        if CURATED_FREEBIE.search(fid):
            curated.append(it)
            continue
        g = dict(it)
        g["start"], g["end"] = parse_iso(it.get("startsAt")), parse_iso(it.get("endsAt"))
        g["url"] = https(it.get("claimUrl")) or EPIC_FREE_URL
        a = by_id.get(fid) or {}
        g["description"] = a.get("description") or ""
        g["image"] = https(it.get("image")) or https(a.get("image"))
        if g["end"] and g["end"] <= now:
            continue  # over — only the archive shows it
        if not g["end"]:
            try:
                if datetime.fromisoformat(str(it.get("until"))[:10]).date() < now.date():
                    continue
            except ValueError:
                pass
        if g["start"]:
            upcoming = g["start"] > now
        else:
            upcoming = it.get("status") == "upcoming" or "скоро" in str(it.get("note") or "").lower()
        (soon if upcoming else now_items).append(g)
    key = lambda g: (g["end"] or now.replace(year=2099), g["title"].lower())  # noqa: E731
    now_items.sort(key=key)
    soon.sort(key=lambda g: (g["start"] or now.replace(year=2099), g["title"].lower()))
    past = []
    for a in arch:
        st, en = parse_iso(a.get("startsAt")), parse_iso(a.get("endsAt"))
        if st and st <= now and a.get("title"):
            past.append(dict(a, start=st, end=en))
    past.sort(key=lambda a: (a["start"], a["title"].lower()), reverse=True)
    return {"updated": parse_iso(payload.get("updatedAt")), "source": payload.get("source") or "",
            "now": now_items, "soon": soon, "curated": curated, "archive": past}


def fg_until(g: dict) -> str:
    if g.get("end"):
        return ru_dt(g["end"])
    return ru_day(datetime.fromisoformat(str(g["until"])[:10])) + " (время уточняется)" if g.get("until") else "—"


def fg_time(d: datetime | None, txt: str) -> str:
    return f'<time datetime="{e(d.isoformat())}">{e(txt)}</time>' if d else e(txt)


def fg_attrs(g: dict) -> str:
    out = ""
    if g.get("start"):
        out += f' data-start="{e(g["start"].isoformat())}"'
    if g.get("end"):
        out += f' data-end="{e(g["end"].isoformat())}"'
    return out


def fg_ends_phrase(items: list) -> str:
    """«до 1 октября 2026, 18:00 МСК» when every item ends at the same moment, else per item."""
    ends = {g["end"] for g in items if g.get("end")}
    if len(ends) == 1 and all(g.get("end") for g in items):
        d = next(iter(ends))
        return f"до {ru_dt(d, year=True)} МСК"
    return "; ".join(f"{g['title']} — до {fg_until(g)}" + (" МСК" if g.get("end") else "") for g in items)


def fg_lead(fb: dict) -> tuple[str, str]:
    """(html, plain) answer-first lead."""
    now_items, soon = fb["now"], fb["soon"]
    epic_now = [g for g in now_items if g.get("store") == "Epic Games"]
    parts_html, parts_txt = [], []
    if fb["source"] == "curated-fallback":
        t = ("Данные Epic Games Store временно не обновились, поэтому таблица ниже может быть неполной. "
             "Актуальный список всегда есть на официальной странице бесплатных игр Epic.")
        return (f'<p class="guide-lead fg-lead">{e(t)} <a href="{EPIC_FREE_URL}" target="_blank" rel="noopener">Открыть страницу Epic ↗</a></p>', t)
    if epic_now:
        names = and_join([g["title"] for g in epic_now])
        verb = "раздают" if len(epic_now) > 1 else "раздают игру"
        ends = fg_ends_phrase(epic_now)
        t1 = f"Сейчас в Epic Games Store бесплатно {verb} {names}: забрать {'их' if len(epic_now) > 1 else 'её'} можно {ends}, а полученные игры остаются в библиотеке навсегда."
        h1 = (f"Сейчас в Epic Games Store бесплатно {verb} " + and_join([f"<strong>{e(g['title'])}</strong>" for g in epic_now])
              + f": забрать {'их' if len(epic_now) > 1 else 'её'} можно <strong>{e(ends)}</strong>, а полученные игры остаются в библиотеке навсегда.")
    else:
        nxt = next((g for g in soon if g.get("start")), None)
        t1 = ("Сейчас в Epic Games Store нет активной бесплатной раздачи." +
              (f" Следующая начнётся {ru_dt(nxt['start'], year=True)} МСК." if nxt else " Обычно новая раздача стартует в четверг в 18:00 МСК."))
        h1 = e(t1)
    parts_html.append(h1)
    parts_txt.append(t1)
    epic_soon = [g for g in soon if g.get("store") == "Epic Games"]
    if epic_soon:
        st = {g["start"] for g in epic_soon if g.get("start")}
        when = f"С {ru_dt(next(iter(st)))} МСК" if len(st) == 1 else "Скоро"
        t2 = f"{when} бесплатными станут {and_join([g['title'] for g in epic_soon])}."
        parts_txt.append(t2)
        parts_html.append(f"{e(when)} бесплатными станут " + and_join([f"<strong>{e(g['title'])}</strong>" for g in epic_soon]) + ".")
    if fb["updated"]:
        t3 = f"Обновлено: {ru_dt(fb['updated'], year=True)} МСК."
        parts_txt.append(t3)
        parts_html.append(f'Обновлено: <time datetime="{e(fb["updated"].isoformat())}">{e(ru_dt(fb["updated"], year=True))} МСК</time>.')
    return f'<p class="guide-lead fg-lead">{" ".join(parts_html)}</p>', " ".join(parts_txt)


def fg_desc(fb: dict) -> str:
    epic_now = [g for g in fb["now"] if g.get("store") == "Epic Games"]
    if epic_now and fb["source"] != "curated-fallback":
        names = and_join([g["title"] for g in epic_now[:3]])
        ends = {g["end"] for g in epic_now if g.get("end")}
        when = f" до {ru_dt(next(iter(ends)))} МСК" if len(ends) == 1 else ""
        d = f"Сейчас бесплатно в Epic Games: {names}{when}. Раздачи Steam, GOG и Prime, как забрать из России, архив."
        upd = f" Обновлено {ru_day(fb['updated'])}." if fb["updated"] else ""
        if len(d + upd) <= 170:
            d += upd
        return d if len(d) <= 200 else clip(d, 200)
    return ("Все бесплатные раздачи игр в Epic Games, Steam, GOG и Prime в одном месте: время окончания по МСК, "
            "инструкции и архив. Обновляется каждые 2 часа.")


# Editorial blocks (brief /home/box/seo/brief-free-games.md). Anything that depends on a live account
# (claiming from a Russian account, card at checkout, GOG newsletter, Steam cards…) is worded cautiously.
FG_STORES = [
    ("Как забрать игру в Epic Games Store (в том числе из России)", "epic", [
        "Войдите в аккаунт Epic Games на сайте store.epicgames.com или в лаунчере Epic Games. Если аккаунта нет, зарегистрируйтесь: это бесплатно.",
        "Откройте страницу игры по кнопке «Забрать» в таблице выше. Ссылки ведут прямо в официальный магазин, без посредников.",
        "Нажмите «Получить». Если вместо неё написано «В библиотеке», игра уже на вашем аккаунте.",
        "В окне оформления заказа убедитесь, что итоговая сумма равна 0 ₽, и подтвердите заказ. Обычно для бесплатного заказа платёжные данные не запрашиваются, но окно может отличаться — ориентируйтесь на сумму.",
        "Игра появится в разделе «Библиотека» лаунчера. Скачать её можно в любой момент, в том числе после окончания раздачи.",
    ], "Где потом найти игру: лаунчер Epic Games → «Библиотека». С телефона раздачу можно оформить через браузер, открыв ту же страницу магазина. У Epic есть и отдельные раздачи мобильных игр для Android и iOS; их мы пока не отслеживаем."),
    ("Как забрать бесплатную игру в Steam", "steam", [
        "Войдите в Steam: в клиенте или на сайте store.steampowered.com.",
        "Откройте страницу игры. В блоке покупки навсегда раздаваемая игра обычно отмечена ценой «Бесплатно» и кнопкой «Добавить на аккаунт».",
        "Нажмите «Добавить на аккаунт» — игра появится в библиотеке и останется там после окончания акции.",
        "Если вместо этого видите «Играть», «Бесплатные выходные» или ограничение по времени, это временный доступ, а не раздача: после акции запустить игру без покупки не получится.",
    ], "Где потом найти игру: клиент Steam → «Библиотека». Коллекционные карточки у бесплатно полученных игр не гарантированы: если они важны, проверьте страницу игры до получения."),
    ("Как получить игру в GOG", "gog", [
        "Войдите в аккаунт на GOG.com.",
        "Раздача обычно появляется баннером на главной странице GOG. Нажмите в нём кнопку получения игры.",
        "Проверьте, что игра добавилась в библиотеку GOG (или в GOG Galaxy, если пользуетесь клиентом).",
        "Скачайте игру, когда удобно: GOG продаёт игры без DRM, и раздачи обычно можно скачать как обычный установщик.",
    ], "Где потом найти игру: GOG.com → «Мои игры» или GOG Galaxy. Если после получения вы начали получать письма от магазина, настройки рассылки есть в профиле GOG."),
    ("Prime Gaming теперь Amazon Luna: как забрать игры по подписке Prime", "luna", [
        "Войдите в аккаунт Amazon с активной подпиской Prime.",
        "Откройте раздел Claims на luna.amazon.com/claims — старый адрес gaming.amazon.com теперь перенаправляет туда.",
        "Выберите игру и следуйте инструкции конкретного предложения: часто это код или привязка аккаунта другого магазина.",
        "Активируйте код там, где указано в предложении: в Epic Games Store, GOG, приложении Amazon Games или другом магазине.",
    ], "Где потом найти игру: в библиотеке того магазина, где активирован код. Amazon прямо пишет, что набор предложений зависит от страны, а подписку Prime в России обычным способом не оформить, поэтому для большинства читателей из России этот раздел справочный."),
]

FG_STORE_LINKS = {
    "epic": ("Бесплатные игры Epic Games Store", EPIC_FREE_URL),
    "steam": ("Бесплатные игры в Steam (free-to-play)", "https://store.steampowered.com/genre/Free%20to%20Play/"),
    "gog": ("Бесплатные игры и раздачи GOG", "https://www.gog.com/en/games?priceRange=0,0&discounted=true"),
    "luna": ("Amazon Luna → Claims", "https://luna.amazon.com/claims/home"),
}

FG_OTHER_STORES = [
    ("Steam", "Бессрочные раздачи в Steam бывают несколько раз в год: издатель на короткое время делает платную игру бесплатной, и её можно добавить на аккаунт навсегда. Гораздо чаще Steam проводит бесплатные выходные, когда игру дают только попробовать. Конкретные раздачи Steam мы пока добавляем вручную, поэтому здесь они появятся не сразу.", "steam"),
    ("GOG", "GOG устраивает раздачи реже, чем Epic, но регулярно: обычно это баннер на главной странице магазина, который висит несколько дней. Игры GOG продаются без DRM, так что полученную игру можно хранить как обычный установщик. Отдельные раздачи GOG мы тоже пока отмечаем вручную.", "gog"),
    ("Amazon Luna (бывший Prime Gaming)", "Бренд Prime Gaming Amazon свернул: бесплатные PC-игры для подписчиков Prime теперь выдаются в разделе Claims на Amazon Luna, а сам Amazon называет их Free Games with Prime. Обычно это несколько игр в месяц с кодами для Epic Games Store, GOG или приложения Amazon Games. Нужна активная подписка Prime.", "luna"),
    ("Ubisoft Connect и другие лаунчеры", "Ubisoft, EA и другие издатели иногда раздают игры в собственных лаунчерах. Схема та же: войти в аккаунт на официальном сайте, открыть страницу акции и нажать кнопку получения. Такие акции редкие и короткие, поэтому о них лучше узнавать из новостей.", ""),
]

FG_RUSSIA_ROWS = [
    ("Epic Games Store", "Как правило, да", "Большинство раздач доступны российским аккаунтам. Отдельные игры издатель закрывает для региона — тогда игры нет в разделе раздач или появляется сообщение «Этот продукт недоступен в вашем регионе». Мы запрашиваем данные Epic для региона RU, но проверяйте кнопку «Получить» на своём аккаунте."),
    ("Steam", "Как правило, да", "Раздачи оформляются кнопкой «Добавить на аккаунт». Игры, которые издатель заблокировал для России, в магазине не показываются."),
    ("GOG", "Как правило, да", "Раздача получается кнопкой на баннере. Перед тем как рассчитывать на конкретную игру, проверьте её на своём аккаунте."),
    ("Amazon Luna / Prime", "Практически нет", "Нужна действующая подписка Amazon Prime, а в России её обычным способом не оформить. Набор предложений зависит от страны."),
    ("PS Plus / PlayStation Store", "Нет, с российского аккаунта", "Sony приостановила работу PlayStation Store в России в марте 2022 года. Игры месяца PS Plus — это доступ по подписке, а не раздача."),
    ("Xbox Game Pass", "Не раздача", "Игры из каталога доступны, пока оплачена подписка; после её окончания запустить их без покупки нельзя."),
]

FG_TYPES = [
    ("Раздача (free to keep)", "Получили до конца акции — игра ваша навсегда", "Epic Games Store, Steam («Добавить на аккаунт»), GOG, Amazon Luna"),
    ("Бесплатные выходные, пробный период", "Играть можно несколько дней, потом доступ закрывается. Прогресс обычно сохраняется, если купить игру", "Steam, Ubisoft, Xbox"),
    ("Подписка", "Игры доступны, пока оплачена подписка", "PS Plus, Xbox Game Pass, Ubisoft+"),
    ("Free-to-play", "Игра бесплатна всегда, деньги берут за внутриигровые покупки", "CS2, Dota 2, Fortnite, Warframe"),
]


def fg_faq(fb: dict) -> list:
    epic_now = [g for g in fb["now"] if g.get("store") == "Epic Games"]
    epic_soon = [g for g in fb["soon"] if g.get("store") == "Epic Games"]
    if epic_now:
        a1 = (f"Сейчас в Epic Games Store бесплатно раздают {and_join([g['title'] for g in epic_now])}, забрать можно {fg_ends_phrase(epic_now)}. "
              "После получения игры остаются в библиотеке навсегда, скачивать их сразу не обязательно. Таблица в начале страницы обновляется автоматически.")
    else:
        a1 = ("Прямо сейчас активной бесплатной раздачи в Epic Games Store нет. Новая раздача обычно начинается в четверг в 18:00 МСК; "
              "как только она появится в магазине, она попадёт в таблицу в начале этой страницы.")
    starts = sorted({g["start"] for g in epic_soon if g.get("start")})
    if epic_soon and starts:
        a2 = (f"Следующая раздача в Epic Games начнётся {ru_dt(starts[0], year=True)} МСК: {and_join([g['title'] for g in epic_soon])}. "
              "Обычно Epic меняет бесплатные игры каждый четверг в 18:00 по Москве, но на праздники, особенно в декабре, график бывает другим.")
    else:
        a2 = ("Обычно Epic Games меняет бесплатные игры каждый четверг в 18:00 по Москве и заранее, примерно за неделю, показывает следующую раздачу. "
              "На праздники, особенно в декабре, график бывает другим. Как только анонс появится, он будет в блоке «Скоро бесплатно».")
    return [
        ("Какие игры сейчас бесплатно в Epic Games?", a1),
        ("Когда следующая раздача в Epic Games и во сколько она обновляется?", a2),
        ("Можно ли забрать бесплатную игру в Epic Games из России?",
         "Как правило, да: бесплатные раздачи Epic Games Store обычно можно получить с российского аккаунта обычным способом, без смены региона. "
         "Исключение — игры, которые издатель закрыл для России: их нет в разделе раздач или кнопка получения недоступна. Проверяйте каждую игру на своём аккаунте."),
        ("Что значит «Этот продукт недоступен в вашем регионе» в Epic Games?",
         "Это значит, что издатель закрыл продажу и раздачу игры для страны вашего аккаунта. Легального способа получить такую игру нет: "
         "смена региона и VPN нарушают правила Epic Games и могут закончиться блокировкой аккаунта. Остаётся дождаться следующей раздачи."),
        ("Игры из раздачи остаются навсегда?",
         "Да, если вы нажали «Получить» или «Добавить на аккаунт» до конца акции, игра остаётся на аккаунте и после раздачи. "
         "Скачивать её сразу не обязательно: установить игру можно в любой момент из библиотеки магазина. Это не касается бесплатных выходных и подписок."),
        ("Нужна ли банковская карта, чтобы забрать бесплатную игру?",
         "Обычно нет: в Epic Games Store, Steam и GOG бесплатная игра оформляется заказом на 0 ₽, и платёжные данные для этого, как правило, не запрашиваются. "
         "Магазины могут менять оформление заказа, поэтому ориентируйтесь на итоговую сумму и не вводите данные карты ради бесплатной игры."),
        ("Как забрать бесплатную игру в Steam в России?",
         "Откройте страницу игры в Steam и нажмите «Добавить на аккаунт» — игра появится в библиотеке навсегда. "
         "Раздачи Steam с российского аккаунта, как правило, работают, если игра не заблокирована для России издателем. Кнопка «Играть» означает временный доступ."),
        ("Что такое бесплатные выходные в Steam?",
         "Бесплатные выходные в Steam — это временный доступ: игру можно запускать несколько дней бесплатно, но после акции она не остаётся доступной без покупки. "
         "Навсегда остаются только игры, которые вы добавили на аккаунт кнопкой «Добавить на аккаунт» во время раздачи."),
        ("Как получить раздачу в GOG?",
         "Войдите на GOG.com и нажмите кнопку получения в баннере раздачи на главной странице — игра появится в библиотеке аккаунта. "
         "Скачать её можно на сайте или через GOG Galaxy. Раздачи GOG идут реже, чем в Epic, и обычно длятся несколько дней."),
        ("Куда делся Prime Gaming?",
         "Prime Gaming стал частью Amazon Luna: бесплатные PC-игры для подписчиков Prime теперь выдаются в разделе Claims на luna.amazon.com/claims, "
         "а старый адрес gaming.amazon.com перенаправляет туда. Нужна активная подписка Amazon Prime, набор игр зависит от страны."),
        ("Бесплатные игры PS Plus — это раздача?",
         "Нет, игры месяца PS Plus доступны, только пока действует подписка: если она закончится, запустить их без продления нельзя. "
         "К тому же в марте 2022 года Sony приостановила работу PlayStation Store в России."),
        ("Безопасны ли сайты с раздачей ключей Steam?",
         "Настоящие раздачи проходят только в официальных магазинах, и ключ для них не нужен. Сайты, которые просят войти через Steam на стороннем домене "
         "или «выполнить задания» ради ключа, часто используют это для угона аккаунтов. Проверяйте адрес страницы перед вводом пароля."),
    ]


def fg_now_table(items: list, games, catalog) -> str:
    rows = ""
    for g in items:
        price = rub(g.get("price_rub"))
        rows += (f'<tr{fg_attrs(g)}><th scope="row">{e(g["title"])}</th><td>{e(g.get("store"))}</td>'
                 f'<td>{fg_time(g.get("end"), fg_until(g))}</td><td>{e(price) if price else "—"}</td>'
                 f'<td><a class="btn btn-primary btn-sm" href="{e(g["url"])}" target="_blank" rel="noopener">Забрать</a></td></tr>')
    return (f'<div class="sp-table-wrap"><table class="sp-table fg-table" id="fgNowTable"><thead><tr><th>Игра</th><th>Магазин</th>'
            f'<th>Бесплатно до (МСК)</th><th>Обычная цена</th><th>Забрать</th></tr></thead><tbody>{rows}</tbody></table></div>')


def fg_soon_table(items: list) -> str:
    rows = ""
    for g in items:
        price = rub(g.get("price_rub"))
        st = fg_time(g["start"], ru_dt(g["start"])) if g.get("start") else "скоро"
        rows += (f'<tr{fg_attrs(g)}><th scope="row">{e(g["title"])}</th><td>{e(g.get("store"))}</td><td>{st}</td>'
                 f'<td>{fg_time(g.get("end"), fg_until(g))}</td><td>{e(price) if price else "—"}</td>'
                 f'<td><a href="{e(g["url"])}" target="_blank" rel="noopener">Страница игры ↗</a></td></tr>')
    return (f'<div class="sp-table-wrap"><table class="sp-table fg-table" id="fgSoonTable"><thead><tr><th>Игра</th><th>Магазин</th>'
            f'<th>Начало (МСК)</th><th>Конец (МСК)</th><th>Обычная цена</th><th>Ссылка</th></tr></thead><tbody>{rows}</tbody></table></div>')


def fg_archive(items: list, now: datetime) -> str:
    months = []
    for a in items:
        k = (a["start"].year, a["start"].month)
        if not months or months[-1][0] != k:
            months.append((k, []))
        months[-1][1].append(a)
    out = ""
    for (y, m), lst in months[:ARCHIVE_MONTHS]:
        rows = ""
        for a in lst:
            dates = ru_dt(a["start"]) + (" — " + ru_dt(a["end"]) if a.get("end") else "")
            live = a.get("end") and a["start"] <= now < a["end"]
            price = rub(a.get("price_rub"))
            flag = ' <span class="sp-note">· идёт сейчас</span>' if live else ""
            rows += (f'<tr><th scope="row">{e(a["title"])}{flag}</th>'
                     f'<td>{e(a.get("store"))}</td><td>{e(dates)}</td><td>{e(price) if price else "—"}</td></tr>')
        out += (f'<h3>{MONTHS_NOM[m - 1]} {y}</h3><div class="sp-table-wrap"><table class="sp-table fg-table"><thead><tr><th>Игра</th>'
                f'<th>Магазин</th><th>Даты (МСК)</th><th>Обычная цена</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return out or "<p>Архив пока пуст: первые записи появятся после следующей проверки раздач.</p>"


def giveaway_news(news: list) -> list:
    return [n for n in news if GIVEAWAY_NEWS.search(n.get("title") or "")][:4]


def free_games_page(games, catalog, news):
    path = "free-games/"
    now = now_msk()
    fb = load_freebies(now)
    games_by_id = {g["id"]: g for g in games}
    lead_html, _ = fg_lead(fb)
    title = "Раздачи игр сегодня: бесплатные игры Epic Games, Steam, GOG"
    desc = fg_desc(fb)
    image = next((g["image"] for g in fb["now"] if g.get("image")), "")
    upd_txt = f"{ru_dt(fb['updated'], year=True)} МСК" if fb["updated"] else "—"
    # --- now
    if fb["now"]:
        now_block = fg_now_table(fb["now"], games, catalog)
    elif fb["source"] == "curated-fallback":
        now_block = f'<p class="fg-empty">Данные Epic временно не обновились. Проверьте <a href="{EPIC_FREE_URL}" target="_blank" rel="noopener">страницу бесплатных игр Epic</a>: раздача там может идти, даже если таблица пуста.</p>'
    else:
        nxt = next((g for g in fb["soon"] if g.get("start")), None)
        now_block = ('<p class="fg-empty">Сейчас в Epic нет активной раздачи. ' +
                     (f"Следующая начнётся {e(ru_dt(nxt['start']))} МСК.</p>" if nxt else "Новая обычно начинается по четвергам в 18:00 МСК.</p>"))
    empty_now = '<p class="fg-empty" id="fgNowEmpty" hidden>Раздача, которая была в таблице, закончилась. Страница обновится автоматически в течение пары часов — следите за блоком «Скоро бесплатно».</p>'
    game_blocks = ""
    for g in fb["now"]:
        hit = match_games(g["title"], games, catalog)
        link = f' <a href="../games/{e(hit[0]["id"])}/">Страница игры в каталоге NEXUS PULSE</a>.' if hit else ""
        d = clip(g.get("description"), 320)
        if d or link:
            src = f' <span class="sp-note">(описание из магазина {e(g.get("store"))})</span>' if d else ""
            game_blocks += f'<h3>{e(g["title"])}</h3><p>{e(d)}{src}{link}</p>'
    gnews = giveaway_news(news)
    news_html = ("<p>Новости о раздачах: " + ", ".join(f'<a href="../news/{e(n["id"])}/">{e(clip(n["title"], 90))}</a>' for n in gnews)
                 + '. Все материалы — в <a href="../news/">архиве новостей</a>.</p>') if gnews else '<p>Свежие анонсы раздач — в <a href="../news/">новостях</a>.</p>'
    # --- soon
    soon_block = fg_soon_table(fb["soon"]) if fb["soon"] else "<p>Анонса следующей раздачи Epic пока нет. Обычно он появляется в магазине за неделю до старта.</p>"
    # --- other stores (only real, concrete non-Epic giveaways would be listed; curated rows are hints only)
    other_real = [g for g in fb["now"] + fb["soon"] if g.get("store") != "Epic Games"]
    other_html = ""
    for h, txt, key in FG_OTHER_STORES:
        link = FG_STORE_LINKS.get(key)
        other_html += f'<h3>{e(h)}</h3><p>{e(txt)}' + (f' <a href="{e(link[1])}" target="_blank" rel="noopener">{e(link[0])} ↗</a>' if link else "") + "</p>"
    f2p = [games_by_id[i] for i in FREE_TO_PLAY if i in games_by_id]
    f2p_html = ('<p><strong>Всегда бесплатно (free-to-play):</strong> ' + ", ".join(f'<a href="../games/{e(g["id"])}/">{e(g["title"])}</a>' for g in f2p)
                + ". Эти игры бесплатны постоянно, это не раздачи: скачать их можно в любой момент.</p>") if f2p else ""
    # --- how to
    howto = ""
    for h, key, steps, tail in FG_STORES:
        link = FG_STORE_LINKS.get(key)
        extra = ' Свою библиотеку Steam можно подтянуть на сайт: <a href="../tools/steam-library-import/">импорт библиотеки Steam</a>.' if key == "steam" else ""
        howto += (f'<h3>{e(h)}</h3><ol class="guide-steps">' + "".join(f"<li>{e(s)}</li>" for s in steps) + "</ol>"
                  f'<p>{e(tail)}{extra}' + (f' <a href="{e(link[1])}" target="_blank" rel="noopener">{e(link[0])} ↗</a>' if link else "") + "</p>")
    russia_rows = "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td><td>{e(c)}</td></tr>' for a, b, c in FG_RUSSIA_ROWS)
    types_rows = "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td><td>{e(c)}</td></tr>' for a, b, c in FG_TYPES)
    faq = fg_faq(fb)
    faq_html = "".join(f'<h3>{e(q)}</h3><p>{e(a)}</p>' for q, a in faq)
    toc = [("fg-now", "Что раздают прямо сейчас"), ("fg-soon", "Скоро бесплатно"), ("fg-stores", "Steam, GOG, Amazon Luna, Ubisoft"),
           ("fg-howto", "Как забрать игру"), ("fg-russia", "Раздачи и Россия"), ("fg-types", "Навсегда, выходные или подписка"),
           ("fg-alerts", "Как не пропустить раздачу"), ("fg-archive", "Архив раздач"), ("fg-faq", "Частые вопросы")]
    body = f"""<article class="sp-article glass fg-page">
<p class="eyebrow">Халява · раздачи игр</p>
<h1 class="sp-h1">Бесплатные игры и раздачи сегодня: Epic Games, Steam, GOG и другие</h1>
<div class="npv-body guide-body">
{lead_html}
<p>Данные о раздачах Epic сверяются с магазином автоматически каждые 2 часа. Новые раздачи сразу приходят в наш <a href="../#community">Discord</a> и <a href="{TG_URL}" target="_blank" rel="noopener">Telegram</a>.</p>
<nav class="guide-toc sp-toc" aria-label="Содержание"><p>Содержание</p><ol>{"".join(f'<li><a href="#{a}">{e(b)}</a></li>' for a, b in toc)}</ol></nav>
<section class="guide-sec" id="fg-now"><h2>Что раздают бесплатно прямо сейчас</h2>
{now_block}
{empty_now}
<p>Забрать игру можно бесплатно и навсегда. Скачивать её сразу не нужно: достаточно добавить игру в библиотеку до конца раздачи, а установить — когда будет время.</p>
{game_blocks}
<p>Перед установкой полезно проверить, <a href="../tools/system-requirements/">потянет ли ПК игру — системные требования</a>, и прикинуть, <a href="../tools/fps-calculator/">сколько FPS она выдаст</a>. Если кадров мало, пригодится гайд о том, <a href="../guides/fps-boost/">как поднять FPS бесплатно</a>.</p>
{news_html}
</section>
<section class="guide-sec" id="fg-soon"><h2>Скоро бесплатно: следующая раздача Epic Games</h2>
{soon_block}
<p>Epic обычно объявляет следующую раздачу примерно за неделю, а сама смена бесплатных игр чаще всего происходит по четвергам в 18:00 МСК. Это наблюдение, а не правило: на праздники график бывает другим, а в декабре Epic нередко устраивает ежедневные раздачи «таинственных игр», которые открываются по одной. Время в таблицах указано по Москве и берётся из данных самого магазина.</p>
</section>
<section class="guide-sec" id="fg-stores"><h2>Раздачи в Steam, GOG, Amazon Luna (Prime Gaming) и Ubisoft</h2>
{fg_now_table(other_real, games, catalog) if other_real else "<p>Сейчас мы автоматически отслеживаем только Epic Games Store. По другим магазинам ниже — где искать раздачи и как часто они бывают.</p>"}
{other_html}
{f2p_html}
</section>
<section class="guide-sec" id="fg-howto"><h2>Как забрать бесплатную игру: инструкции по магазинам</h2>
<p>Во всех магазинах схема одинаковая: войти в аккаунт, открыть официальную страницу игры и оформить её за 0 ₽. Ниже шаги для каждого магазина и подсказка, где потом искать игру.</p>
{howto}
</section>
<section class="guide-sec" id="fg-russia"><h2>Раздачи и Россия: что работает, а что нет</h2>
<p>Коротко: бесплатные игры в Epic Games Store, Steam и GOG с российского аккаунта, как правило, получить можно, а подписочные сервисы вроде Prime и PS Plus в России почти не доступны. Подробности по магазинам — в таблице.</p>
<div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Магазин</th><th>Забрать бесплатную игру с российского аккаунта</th><th>Оговорки</th></tr></thead><tbody>{russia_rows}</tbody></table></div>
<p class="sp-note">Проверено: {CHECKED_MONTH}, по открытым источникам. Ситуация может измениться: перед тем как рассчитывать на конкретную игру, проверьте её на своём аккаунте.</p>
<p>Если игра недоступна в вашем регионе, легального способа её получить нет. Смена региона, VPN, прокси и покупка чужих аккаунтов нарушают правила Epic и Steam и могут привести к блокировке аккаунта вместе со всей библиотекой. Надёжнее дождаться следующей раздачи: они выходят каждую неделю.</p>
</section>
<section class="guide-sec" id="fg-types"><h2>Навсегда, бесплатные выходные или подписка: в чём разница</h2>
<p>Слово «бесплатно» в магазинах означает разные вещи. Чтобы не перепутать раздачу с временным доступом, сверьтесь с таблицей.</p>
<div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Тип</th><th>Что это значит</th><th>Где встречается</th></tr></thead><tbody>{types_rows}</tbody></table></div>
<p>Главное отличие раздачи от остальных вариантов — игра остаётся у вас и после окончания акции. «Бесплатные игры PS Plus» и каталог Game Pass — это игры по подписке: пока она оплачена, в них можно играть, а после окончания доступ закрывается.</p>
</section>
<section class="guide-sec" id="fg-alerts"><h2>Как не пропустить следующую раздачу</h2>
<ul>
<li>Включите роль «🔔 Раздачи» в <a href="../#community">нашем Discord</a> — бот напишет, как только появится новая бесплатная игра.</li>
<li>Подпишитесь на <a href="{TG_URL}" target="_blank" rel="noopener">Telegram-канал NEXUS PULSE</a>: раздачи приходят туда вместе с новостями.</li>
<li>Добавьте эту страницу в закладки: адрес не меняется, а таблицы обновляются сами. Заодно загляните в <a href="../#deals">скидки и распродажи</a>.</li>
</ul>
<p>Про безопасность. Настоящие раздачи всегда проходят в официальном магазине: store.epicgames.com, store.steampowered.com, gog.com или luna.amazon.com. Сайты, которые предлагают «раздачу ключей Steam», просят войти через Steam на чужом домене или выполнить задания ради ключа, — частая схема угона аккаунтов. Проверяйте адрес страницы, прежде чем вводить пароль, и не сообщайте никому коды из приложения Steam Guard.</p>
</section>
<section class="guide-sec" id="fg-archive"><h2>Архив раздач: что раздавали раньше</h2>
<p>Здесь все раздачи, которые мы отследили с {TRACKED_SINCE}. Более ранние раздачи в архив не попали: мы записываем только то, что видели сами.</p>
{fg_archive(fb["archive"], now)}
<p>Не знаете, во что поиграть из полученного? Попробуйте <a href="../tools/game-picker/">подбор игры под настроение</a>.</p>
</section>
<section class="guide-sec fg-faq" id="fg-faq"><h2>Частые вопросы</h2>
{faq_html}
</section>
<p class="sp-note fg-source">Данные: API Epic Games Store (регион RU) и ручная проверка редакции. Последнее обновление: {e(upd_txt)}. Смотрите также <a href="../#freebies">раздачи на главной</a>, <a href="../#deals">скидки</a>, <a href="../#calendar">календарь релизов</a> и <a href="../news/">новости</a>.</p>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Коротко</h2>
{links_list([(f"#fg-now", "Сейчас бесплатно", f"{len(fb['now'])} {PLURAL(len(fb['now']), 'игра', 'игры', 'игр')}"), ("#fg-soon", "Скоро бесплатно", f"{len(fb['soon'])} {PLURAL(len(fb['soon']), 'игра', 'игры', 'игр')}"), ("#fg-russia", "Работает ли из России", ""), ("#fg-archive", "Архив раздач", "")])}
<h2 class="sp-h2">Полезное</h2>
{links_list([("../tools/system-requirements/", "Системные требования игр", ""), ("../tools/fps-calculator/", "Калькулятор FPS", ""), ("../guides/fps-boost/", "Как поднять FPS", ""), ("../tools/game-picker/", "Во что поиграть", "")])}
</aside>
<script src="../assets/free-games.js" defer></script>"""
    # --- JSON-LD: only real giveaways (current + upcoming), never curated placeholders
    elems = []
    for i, g in enumerate(fb["now"] + fb["soon"]):
        offer = {"@type": "Offer", "price": "0", "priceCurrency": "RUB", "url": g["url"],
                 "seller": {"@type": "Organization", "name": "Epic Games Store" if g.get("store") == "Epic Games" else g.get("store")}}
        if g.get("start"):
            offer["availabilityStarts"] = g["start"].isoformat()
        if g.get("end"):
            offer["availabilityEnds"] = g["end"].isoformat()
        item = {"@type": "VideoGame", "name": g["title"], "gamePlatform": "PC", "url": g["url"], "offers": offer}
        if g.get("image"):
            item["image"] = g["image"]
        elems.append({"@type": "ListItem", "position": i + 1, "item": item})
    item_list = {"@type": "ItemList", "name": "Бесплатные игры сейчас и скоро", "itemListOrder": "https://schema.org/ItemListOrderAscending",
                 "numberOfItems": len(elems), "itemListElement": elems}
    page = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": SITE + path,
            "inLanguage": "ru", "publisher": publisher(), "mainEntity": item_list}
    if fb["updated"]:
        page["dateModified"] = fb["updated"].isoformat()
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return path, title, desc, body, [("Главная", ""), ("Бесплатные игры", path)], "website", image, [page, faq_ld]


# ---------------------------------------------------------------- build
def today() -> str:
    return datetime.now(MSK).date().isoformat()


def build() -> list:
    """Writes all pages. Returns sitemap entries [{loc, lastmod, changefreq, priority}]."""
    games, specs, fps, guides, catalog = load_data()
    news = load_news()
    games_by_id = {g["id"]: g for g in games}
    guides_by_id = {g["id"]: g for g in guides}

    pages = []  # (path, args tuple, kind)
    pages.append(("page", free_games_page(games, catalog, news), "freebies"))
    pages.append(("page", guides_index(guides), "list"))
    pages += [("page", guide_page(g, games_by_id, guides, catalog), "guide") for g in guides]
    pages.append(("page", games_index(games, catalog), "list"))
    pages += [("page", game_page(g, games, specs, fps, guides, catalog), "game") for g in games]
    pages.append(("page", tools_index(), "list"))
    pages += [("page", tool_page(t, games, specs, fps, guides_by_id), "tool") for t in TOOLS]
    pages.append(("page", news_index(news), "newslist"))
    pages += [("page", news_page(n, i, news, games, catalog), "news") for i, n in enumerate(news)]

    old = (read_json(MANIFEST, {}) or {}).get("pages") or {}
    manifest, entries, written = {}, [], 0
    stamp = today()
    news_dates = {f"news/{n['id']}/": (n.get("date") or "")[:10] for n in news}
    for _, args, kind in pages:
        path, title, desc, body, crumbs, og_type, image, jsonld = args[:8]
        extra = args[8] if len(args) > 8 else ""
        index = args[9] if len(args) > 9 else True
        kw = dict(path=path, title=title, desc=desc, body=body, crumbs=crumbs, og_type=og_type, image=image, jsonld=jsonld, extra_meta=extra, index=index)
        text = layout(**kw)
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        prev = old.get(path) or {}
        created = prev.get("created") or stamp
        lastmod = prev.get("lastmod") if prev.get("hash") == h and prev.get("lastmod") else stamp
        if kind == "news" and news_dates.get(path):
            lastmod = news_dates[path]
        if kind in ("guide",):
            # Article dates come from the manifest: re-render with them (not part of the hash)
            for obj in jsonld:
                obj["datePublished"] = created
                obj["dateModified"] = lastmod
            text = layout(**kw)
        changefreq = {"list": "weekly", "newslist": "hourly", "news": "monthly", "freebies": "daily"}.get(kind, "monthly")
        priority = {"list": "0.8", "newslist": "0.8", "freebies": "0.8", "guide": "0.7", "tool": "0.7", "game": "0.6", "news": "0.5"}[kind]
        manifest[path] = {"hash": h, "created": created, "lastmod": lastmod, "changefreq": changefreq, "priority": priority}
        if not index:
            manifest[path]["noindex"] = True
        written += write_if_changed(ROOT / path / "index.html", text)
        if not index:
            continue  # thin page (no excerpt): reachable, but kept out of the sitemap
        entries.append({"loc": SITE + path, "lastmod": lastmod, "changefreq": changefreq, "priority": priority})

    removed = cleanup(set(manifest))
    if manifest != old:
        MANIFEST.write_text(json.dumps({"about": "Generated by scripts/build_static_pages.py: content hash + lastmod of every static page (sitemap <lastmod>). Do not edit.",
                                        "pages": manifest}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts = {}
    for _, _, kind in pages:
        counts[kind] = counts.get(kind, 0) + 1
    log(f"[static] {len(pages)} pages {counts}, {len(entries)} indexable ({written} written, {removed} removed)")
    return entries


def cleanup(keep: set) -> int:
    removed = 0
    for sec in SECTIONS:
        base = ROOT / sec
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            f = d / "index.html"
            if not d.is_dir() or f"{sec}/{d.name}/" in keep or not f.is_file():
                continue
            if MARKER not in f.read_text(encoding="utf-8", errors="ignore"):
                continue  # not ours — never touch
            f.unlink()
            try:
                d.rmdir()
            except OSError:
                pass
            removed += 1
    return removed


def sitemap_entries_from_manifest() -> list:
    """Fallback when build() fails: keep the pages that are already on disk in the sitemap."""
    out = []
    for path, m in ((read_json(MANIFEST, {}) or {}).get("pages") or {}).items():  # manifest keeps build order
        if (ROOT / path / "index.html").is_file() and not m.get("noindex"):
            out.append({"loc": SITE + path, "lastmod": m.get("lastmod") or today(),
                        "changefreq": m.get("changefreq") or "weekly", "priority": m.get("priority") or "0.5"})
    return out


def main() -> int:
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
