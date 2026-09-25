#!/usr/bin/env python3
"""Link previews + SEO files for the static site (no network, reads data/*.json only).

Writes:
  s/news/<id>.html   — share pages with per-news Open Graph / Twitter tags; people are sent on to
                       index.html?news=<id> (the site opens that news in its viewer)
  s/build.html       — share page for PC builds (query string is passed through to the builder)
  data/share_index.json — compact archive of shared news (the site can still show an old news
                       card after it has left the feed); capped, oldest removed together with pages
  sitemap.xml, robots.txt
  index.html         — only the block between <!-- np:verify:start --> and <!-- np:verify:end -->:
                       Yandex / Google / Bing verification meta tags from data/site_config.json
                       (empty values → no tags)
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from np_common import DATA, MSK, ROOT, log, read_json

CONFIG = read_json(DATA / "site_config.json", {}) or {}
SITE = (CONFIG.get("siteUrl") or "https://derzko435.github.io/nexus-pulse/").rstrip("/") + "/"
SHARE_DIR = ROOT / "s"
NEWS_DIR = SHARE_DIR / "news"
INDEX_FILE = DATA / "share_index.json"
MAX_NEWS_PAGES = 200
KEEP_DAYS = 45
ID_RE = re.compile(r"^[\w-]{1,64}$")
OG_IMAGE = SITE + "assets/og-image.png"
OG_BUILD = SITE + "assets/og-build.png"


def e(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — NEXUS PULSE</title>
<meta name="description" content="{desc}">
<meta name="robots" content="noindex, follow">
<meta name="theme-color" content="#00f5ff">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="NEXUS PULSE">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
{image_extra}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
{extra}<link rel="icon" type="image/png" href="{rel}assets/icons/icon-192.png">
<style>
html,body{{margin:0;height:100%;background:#07090f;color:#e8eefc;font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{min-height:100%;display:grid;place-items:center;text-align:center;padding:24px;box-sizing:border-box}}
a{{color:#00f5ff}} .t{{max-width:640px}} img{{width:64px;height:64px;border-radius:14px}}
</style>
<script>location.replace({target_js} + location.hash);</script>
</head>
<body>
<main><div class="t">
<img src="{rel}assets/icons/icon-192.png" alt="NEXUS PULSE">
<h1 style="font-size:1.25rem">{title}</h1>
<p>{desc}</p>
<p><a href="{target}">Открыть на NEXUS PULSE →</a></p>
</div></main>
</body>
</html>
"""


def own_image_meta(w: int = 1200, h: int = 630) -> str:
    return f'<meta property="og:image:width" content="{w}">\n<meta property="og:image:height" content="{h}">\n'


def news_page(n: dict) -> str:
    nid = n["id"]
    target = f"../../?news={nid}"
    image = n.get("image") if str(n.get("image") or "").startswith("https://") else ""
    title = clip(n.get("title"), 140)
    desc = clip(n.get("summary") or f"Новость от {n.get('source') or 'игровых изданий'} на NEXUS PULSE", 250)
    extra = ""
    if n.get("date"):
        extra += f'<meta property="article:published_time" content="{e(n["date"])}">\n'
    if n.get("source"):
        extra += f'<meta property="article:author" content="{e(n["source"])}">\n'
    return PAGE.format(
        title=e(title), desc=e(desc), og_type="article", url=e(f"{SITE}s/news/{nid}.html"),
        image=e(image or OG_IMAGE), image_extra="" if image else own_image_meta(), extra=extra,
        rel="../../", target=e(target), target_js=json.dumps(target),
    )


def build_page() -> str:
    title = "Моя сборка ПК — что она потянет?"
    desc = "Процессор, видеокарта и память: смотри, в какие игры можно играть на этой сборке и с каким FPS."
    target = "../"
    return PAGE.format(
        title=e(title), desc=e(desc), og_type="website", url=e(f"{SITE}s/build.html"),
        image=e(OG_BUILD), image_extra=own_image_meta(), extra="", rel="../", target=e(target + "?share=1#tools"),
        # the builder reads cpu/gpu/ram/res from the query string
        target_js='"../" + (location.search || "?share=1") + "#tools"',
    ).replace('location.replace("../" + (location.search || "?share=1") + "#tools" + location.hash);',
              'location.replace("../" + (location.search || "?share=1") + "#tools");')


def share_pages() -> int:
    now = datetime.now(MSK)
    idx = read_json(INDEX_FILE, {}) or {}
    archive = {a["id"]: a for a in idx.get("news") or [] if isinstance(a, dict) and ID_RE.match(str(a.get("id") or ""))}
    for n in (read_json(DATA / "news.json", {}) or {}).get("items") or []:
        if not isinstance(n, dict) or not ID_RE.match(str(n.get("id") or "")) or not n.get("title"):
            continue
        archive[n["id"]] = {
            "id": n["id"], "title": clip(n["title"], 180), "summary": clip(n.get("summary"), 300),
            "image": n.get("image") if str(n.get("image") or "").startswith("https://") else "",
            "url": n.get("url") if str(n.get("url") or "").startswith("https://") else "",
            "source": n.get("source") or "", "date": n.get("date") or "",
        }
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    items = sorted(archive.values(), key=lambda a: a.get("date") or "", reverse=True)
    items = [a for a in items if (a.get("date") or "9") >= cutoff][:MAX_NEWS_PAGES]
    keep = {a["id"] for a in items}
    changed = 0
    for a in items:
        changed += write_if_changed(NEWS_DIR / f"{a['id']}.html", news_page(a))
    removed = 0
    if NEWS_DIR.exists():
        for f in NEWS_DIR.glob("*.html"):
            if f.stem not in keep:
                f.unlink()
                removed += 1
    changed += write_if_changed(SHARE_DIR / "build.html", build_page())
    old_items = idx.get("news") or []
    if old_items != items:
        INDEX_FILE.write_text(json.dumps({"updatedAt": now.replace(microsecond=0).isoformat(), "news": items},
                                         ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"[share] {len(items)} news pages ({changed} written, {removed} removed)")
    return changed + removed


def latest_update() -> str:
    best = ""
    for name in ("news.json", "releases.json", "patches.json", "matches.json", "videos.json", "deals.json"):
        u = str((read_json(DATA / name, {}) or {}).get("updatedAt") or "")
        best = max(best, u)
    return (best or datetime.now(MSK).isoformat())[:10]


def seo_files() -> None:
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{e(SITE)}</loc>
    <lastmod>{latest_update()}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    robots = f"""User-agent: *
Allow: /
Disallow: /scripts/

Sitemap: {SITE}sitemap.xml
"""
    a = write_if_changed(ROOT / "sitemap.xml", sitemap)
    b = write_if_changed(ROOT / "robots.txt", robots)
    log(f"[seo] sitemap {'updated' if a else 'same'}, robots {'updated' if b else 'same'}")


VERIFY_RE = re.compile(r"(<!-- np:verify:start -->)(.*?)(<!-- np:verify:end -->)", re.S)
CODE_RE = re.compile(r"^[\w\-=+/.:]{4,200}$")


def verification_tags() -> None:
    idx = ROOT / "index.html"
    src = idx.read_text(encoding="utf-8")
    if not VERIFY_RE.search(src):
        log("[verify] markers not found in index.html — skipped")
        return
    tags = []
    for key, name in (("yandexVerification", "yandex-verification"), ("googleVerification", "google-site-verification"),
                      ("bingVerification", "msvalidate.01")):
        val = str(CONFIG.get(key) or "").strip()
        m = re.search(r'content="([^"]+)"', val)  # the whole <meta …> tag may be pasted — take the code
        if m:
            val = m.group(1)
        if val and CODE_RE.match(val):
            tags.append(f'<meta name="{name}" content="{e(val)}" />')
        elif val:
            log(f"[verify] {key}: value looks wrong, skipped")
    inner = ("\n  " + "\n  ".join(tags) + "\n  ") if tags else ""
    out = VERIFY_RE.sub(lambda m: m.group(1) + inner + m.group(3), src)
    if out != src:
        idx.write_text(out, encoding="utf-8")
        log(f"[verify] index.html updated ({len(tags)} tags)")
    else:
        log(f"[verify] index.html unchanged ({len(tags)} tags)")


def main() -> int:
    share_pages()
    seo_files()
    verification_tags()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
