"""Static trust pages: about/, editorial-policy/, contacts/ (used by build_static_pages.py).

Only verifiable facts: what the site does, where every data block comes from (the same sources the
update scripts use), how news are quoted and how to reach the project (the public Discord server and
Telegram channel that the site already links). No invented people, addresses, e-mails or numbers.
"""
from __future__ import annotations

import html

REPO_URL = "https://github.com/Derzko435/nexus-pulse"

# (block, source, how often) — keep in sync with scripts/update_*.py and .github/workflows/*.yml
SOURCES = [
    ("Новости игр", "RSS-ленты StopGame, 3DNews, GoHa.ru, Cybersport.ru и Канобу; у каждой новости указан источник и есть ссылка на оригинал",
     "несколько раз в день"),
    ("Матчи и турниры", "публичная лента матчей bo3.gg (CS2, Dota 2, Valorant, League of Legends; только турниры уровня S и A), трансляции — официальные каналы организаторов",
     "несколько раз в день"),
    ("Календарь релизов", "Steam (российская витрина), Epic Games Store, статьи Википедии о списках игр года (для консолей)", "ежедневно"),
    ("Патчи", "официальные анонсы разработчиков в Steam News и страницы патч-нотов Riot Games (Valorant, League of Legends)", "ежедневно"),
    ("Скидки", "распродажи Steam на российской витрине: только реальные скидки с текущими ценами в рублях", "каждые несколько часов"),
    ("Цены и история цен", "цены Steam (регион RU) для игр каталога", "каждые несколько часов"),
    ("Бесплатные раздачи", "API раздач Epic Games Store, а также Steam, GOG и Prime Gaming (ручная проверка)", "каждые несколько часов"),
    ("Каталог игр", "обложки и краткие описания со страниц игр в Steam или Википедии; описания игр вне Steam написаны редакцией", "ежедневно"),
    ("Видео", "публичные RSS-ленты YouTube-каналов игровых изданий, издателей, киберспортивных организаторов и нескольких технологических каналов", "несколько раз в день"),
]


def _plural(n: int, one: str, few: str, many: str) -> str:
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _links(ctx) -> dict:
    return {"discord": ctx["discord"], "telegram": ctx["telegram"], "site": ctx["site"]}


def _contact_items(ctx) -> list:
    items = []
    if ctx.get("discord"):
        items.append((ctx["discord"], "Discord-сервер NEXUS PULSE", "обсуждения, поиск тиммейтов, вопросы и сообщения об ошибках"))
    if ctx.get("telegram"):
        items.append((ctx["telegram"], "Telegram-канал NEXUS PULSE", "новости, раздачи и скидки"))
    items.append((REPO_URL + "/issues", "GitHub Issues", "сообщить об ошибке на сайте или в данных (нужен аккаунт GitHub)"))
    return items


def _info_nav(rel: str, current: str) -> str:
    pages = [("about/", "О проекте"), ("editorial-policy/", "Редакционная политика и источники"), ("contacts/", "Контакты")]
    lis = "".join(f'<li><a href="{rel}{p}"{" aria-current=\"page\"" if p == current else ""}>{_e(t)}</a></li>' for p, t in pages)
    return f'<aside class="sp-aside glass"><h2 class="sp-h2">О NEXUS PULSE</h2><ul class="sp-links">{lis}</ul></aside>'


def build_pages(ctx) -> list:
    """ctx: site, discord, telegram, counts {games, guides, tools}, org (Organization dict).
    Returns build_static_pages page tuples: (path, title, desc, body, crumbs, og_type, image, jsonld)."""
    site, org = ctx["site"], ctx["org"]
    c = ctx.get("counts") or {}
    rel = "../"
    pages = []

    # ---------------------------------------------------------------- about/
    path = "about/"
    desc = ("NEXUS PULSE — русскоязычный игровой портал: новости игр со ссылками на источники, релизы и патчи, скидки Steam в рублях, "
            "раздачи, гайды и бесплатные инструменты для геймеров.")
    what = [
        ("Новости", "news/", "свежие новости игр и киберспорта из российских изданий — краткий пересказ и ссылка на оригинал"),
        ("Каталог игр", "games/", f"{c.get('games')} {_plural(c.get('games'), 'популярная игра', 'популярные игры', 'популярных игр')}: жанр, платформы, системные требования и оценка FPS" if c.get("games") else "популярные игры: жанр, платформы, системные требования и оценка FPS"),
        ("Гайды", "guides/", f"{c.get('guides')} {_plural(c.get('guides'), 'материал', 'материала', 'материалов')}: настройка ПК и игр, FPS, пинг, советы новичкам и подборки" if c.get("guides") else "настройка ПК и игр, FPS, пинг, советы новичкам и подборки"),
        ("Инструменты", "tools/", "калькулятор FPS, системные требования, сборка ПК, тест скорости и пинга, подбор игры"),
        ("Раздачи игр", "free-games/", "что сейчас бесплатно в Epic Games, Steam, GOG и Prime Gaming и как забрать из России"),
    ]
    body = f"""<article class="sp-article glass">
<p class="eyebrow">О проекте</p>
<h1 class="sp-h1">О проекте NEXUS PULSE</h1>
<div class="npv-body">
<p class="guide-lead">{_e(desc)}</p>
<section class="guide-sec"><h2>Что есть на сайте</h2><ul class="sp-links">{"".join(f'<li><a href="{rel}{p}">{_e(t)}</a> <span class="sp-note">{_e(n)}</span></li>' for t, p, n in what)}</ul></section>
<section class="guide-sec"><h2>Как устроен сайт</h2><ul>
<li>Сайт статический и открытый: код и данные лежат в публичном репозитории <a href="{REPO_URL}" rel="noopener">GitHub</a>, страницы публикуются через GitHub Pages.</li>
<li>Новости, матчи, релизы, патчи, скидки и раздачи обновляются автоматически по расписанию из открытых источников — список источников на странице <a href="{rel}editorial-policy/">«Редакционная политика и источники»</a>.</li>
<li>Если источник недоступен, на сайте остаются последние проверенные данные — пустые или выдуманные значения не публикуются.</li>
<li>Гайды и подборки пишутся и проверяются вручную; в больших подборках указана дата проверки данных.</li>
</ul></section>
<section class="guide-sec"><h2>Персональные данные</h2><p>Сайт не требует регистрации. Избранное, отслеживаемые цены, сборка ПК и другие настройки хранятся только в твоём браузере; перенести их можно через резервную копию профиля. Для обезличенной статистики посещений используется Яндекс Метрика.</p></section>
<section class="guide-sec"><h2>Сообщество и связь</h2><p>Обсуждения и вопросы — в <a href="{_e(ctx.get("discord") or "")}" target="_blank" rel="noopener">Discord-сервере NEXUS PULSE</a>. Все способы связи — на странице <a href="{rel}contacts/">«Контакты»</a>.</p></section>
</div>
</article>
{_info_nav(rel, path)}"""
    about_ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": "О проекте NEXUS PULSE", "url": site + path,
                "inLanguage": "ru", "description": desc, "mainEntity": org}
    pages.append((path, "О проекте NEXUS PULSE — игровой портал", desc, body, [("Главная", ""), ("О проекте", path)], "website", "", [about_ld]))

    # ---------------------------------------------------------------- editorial-policy/
    path = "editorial-policy/"
    desc = "Как NEXUS PULSE работает с новостями, ценами, раздачами и гайдами: источники данных, правила цитирования, проверка фактов и исправление ошибок."
    rows = "".join(f"<tr><th scope=\"row\">{_e(a)}</th><td>{_e(b)}</td><td>{_e(f)}</td></tr>" for a, b, f in SOURCES)
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Редакционная политика</p>
<h1 class="sp-h1">Редакционная политика и источники</h1>
<div class="npv-body">
<p class="guide-lead">{_e(desc)}</p>
<section class="guide-sec"><h2>Главное правило</h2><p>Мы не публикуем выдуманные факты, цены и цифры. Всё, что меняется (новости, цены, даты релизов, матчи, раздачи), берётся из источников ниже; если данных нет — блок не показывается или остаются последние проверенные данные.</p></section>
<section class="guide-sec"><h2>Источники данных</h2><div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Раздел</th><th>Источник</th><th>Обновление</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="guide-sec"><h2>Новости: пересказ со ссылкой</h2><ul>
<li>NEXUS PULSE не пишет собственные новости: это подборка материалов российских игровых изданий.</li>
<li>На странице новости — заголовок, короткое описание и небольшая выдержка из начала материала с указанием издания; полная версия — по ссылке «читать в источнике».</li>
<li>Страницы новостей с выдержкой хранятся около 30 дней, остальные — несколько дней, затем удаляются из архива.</li>
</ul></section>
<section class="guide-sec"><h2>Цены, скидки и раздачи</h2><ul>
<li>Цены — в рублях с российской витрины Steam на момент последнего обновления (время обновления указано на сайте). Перед покупкой проверь цену в магазине: скидки меняются.</li>
<li>Раздачи показываются со временем окончания по Москве; завершённые раздачи уходят в архив.</li>
</ul></section>
<section class="guide-sec"><h2>Гайды, подборки и оценки</h2><ul>
<li>Гайды и подборки пишутся вручную; данные в подборках (время прохождения, озвучка, правила возврата) проверяются по первоисточникам, дата проверки указана в материале.</li>
<li>«Рейтинг редакции» в каталоге — субъективная оценка NEXUS PULSE по шкале от 1 до 10, а не средний балл пользователей или критиков.</li>
<li>Оценка FPS в инструментах — ориентир по формуле, а не результат бенчмарка.</li>
</ul></section>
<section class="guide-sec"><h2>Исправление ошибок</h2><p>Нашёл ошибку в данных или тексте — напиши в <a href="{_e(ctx.get("discord") or "")}" target="_blank" rel="noopener">Discord</a> или создай issue на <a href="{REPO_URL}/issues" rel="noopener">GitHub</a>. Исправления вносятся в данные и публикуются с очередным обновлением сайта.</p></section>
</div>
</article>
{_info_nav(rel, path)}"""
    ed_ld = {"@context": "https://schema.org", "@type": "WebPage", "name": "Редакционная политика и источники NEXUS PULSE", "url": site + path,
             "inLanguage": "ru", "description": desc, "publisher": org}
    pages.append((path, "Редакционная политика и источники — NEXUS PULSE", desc, body,
                  [("Главная", ""), ("Редакционная политика", path)], "website", "", [ed_ld]))

    # ---------------------------------------------------------------- contacts/
    path = "contacts/"
    desc = "Как связаться с NEXUS PULSE: Discord-сервер, Telegram-канал и GitHub для сообщений об ошибках."
    items = _contact_items(ctx)
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Контакты</p>
<h1 class="sp-h1">Контакты NEXUS PULSE</h1>
<div class="npv-body">
<p class="guide-lead">{_e(desc)}</p>
<section class="guide-sec"><h2>Где нас найти</h2><ul class="sp-links">{"".join(f'<li><a href="{_e(u)}" target="_blank" rel="noopener">{_e(t)}</a> <span class="sp-note">{_e(n)}</span></li>' for u, t, n in items)}</ul></section>
<section class="guide-sec"><h2>Быстрее всего</h2><p>Вопросы, идеи и сообщения об ошибках удобнее всего оставлять в <a href="{_e(ctx.get("discord") or "")}" target="_blank" rel="noopener">Discord-сервере</a>. Про то, откуда берутся данные сайта, — на странице <a href="{rel}editorial-policy/">«Редакционная политика и источники»</a>.</p></section>
</div>
</article>
{_info_nav(rel, path)}"""
    contact_ld = {"@context": "https://schema.org", "@type": "ContactPage", "name": "Контакты NEXUS PULSE", "url": site + path,
                  "inLanguage": "ru", "description": desc, "mainEntity": org}
    pages.append((path, "Контакты — NEXUS PULSE", desc, body, [("Главная", ""), ("Контакты", path)], "website", "", [contact_ld]))
    return pages
