#!/usr/bin/env python3
"""Shared helpers for NEXUS PULSE daily content scripts.

Rules:
- Never invent data. If a source fails, the previous file is kept.
- Text is stored as plain strings / simple blocks; the site escapes it on render.
"""
from __future__ import annotations

import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MSK = timezone(timedelta(hours=3), name="MSK")

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 NexusPulse/1.0 (+https://derzko435.github.io/nexus-pulse/)"
)


def log(*a: Any) -> None:
    print(*a, file=sys.stderr, flush=True)


def now_msk_iso() -> str:
    return datetime.now(MSK).replace(microsecond=0).isoformat()


def fetch_bytes(url: str, headers: dict | None = None, timeout: int = 30, retries: int = 2) -> bytes:
    h = {
        "User-Agent": BROWSER_UA,
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "*/*",
    }
    if headers:
        h.update(headers)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if enc == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                return raw
        except urllib.error.HTTPError as e:  # 4xx are not worth retrying (except 429)
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                break
            if e.code == 429:
                time.sleep(25 * (attempt + 1))
                continue
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")


def fetch_text(url: str, **kw: Any) -> str:
    raw = fetch_bytes(url, **kw)
    return raw.decode("utf-8", "replace")


def fetch_json(url: str, **kw: Any) -> Any:
    return json.loads(fetch_text(url, **kw))


WS_RE = re.compile(r"[ \t\r\f\v\u00a0\u200b]+")


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"<[^>]+>", " ", s)
    s = WS_RE.sub(" ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def clip(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    if sp > n * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,.;:—-") + "…"


def safe_url(u: str | None) -> str:
    """Only allow absolute http(s) URLs."""
    if not u:
        return ""
    u = html.unescape(str(u)).strip()
    if u.startswith("//"):
        u = "https:" + u
    if not re.match(r"^https?://[^\s\"'<>]+$", u):
        return ""
    return u.replace("http://", "https://", 1) if u.startswith("http://") else u


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def write_json_if_good(path: Path, payload: dict, items_key: str, min_items: int) -> bool:
    """Write payload only if it has enough items. Keeps last good data otherwise.

    Returns True if the file was written.
    """
    items = payload.get(items_key) or []
    if len(items) < min_items:
        log(f"[keep] {path.name}: only {len(items)} {items_key} (< {min_items}); keeping previous file")
        return False
    old = read_json(path, {}) or {}
    # avoid churn: if content (minus timestamps) is identical, keep the old file untouched
    def strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in ("updatedAt", "checkedAt")}
    if old and strip(old) == strip(payload):
        log(f"[same] {path.name}: no content changes")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    log(f"[write] {path.name}: {len(items)} {items_key}")
    return True


# ---------------------------------------------------------------- blocks
JUNK_RE = re.compile(
    r"(подпис(ыв|ат)|читайте также|читать также|реклама|telegram|телеграм|vk\.com|"
    r"источник фото|фото:|изображение:|cookie|javascript|поделиться|комментари[йи]\s*$|"
    r"^\s*теги|^\s*оцените|присоединяйтесь|наш канал|дзен)",
    re.I,
)


def _direct_text(el: Any) -> str:
    """Text of an element without its nested lists (for <li> with sub-lists)."""
    parts = []
    for c in el.contents:
        name = getattr(c, "name", None)
        if name in ("ul", "ol"):
            continue
        parts.append(c.get_text(" ", strip=True) if name else str(c))
    return " ".join(parts)


def blocks_from_soup(container: Any, max_blocks: int = 40, max_chars: int = 6000) -> list[dict]:
    """Convert a bs4 container into safe text blocks: h / p / li (li may carry depth d=1)."""
    out: list[dict] = []
    total = 0
    for el in container.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        if el.name == "p" and el.find_parent("li") is not None:
            continue  # its text is part of the <li>
        if el.name == "p" and el.find_parent("blockquote") is not None:
            continue
        raw = _direct_text(el) if el.name == "li" else el.get_text(" ", strip=True)
        text = clean_text(raw)
        if not text or len(text) < 2:
            continue
        if el.name in ("p", "blockquote") and len(text) < 25:
            continue
        if JUNK_RE.search(text) and len(text) < 160:
            continue
        kind = "h" if el.name in ("h1", "h2", "h3", "h4") else ("li" if el.name == "li" else "p")
        if kind == "h" and len(text) > 140:
            kind = "p"
        if out and out[-1]["x"] == text:
            continue
        block = {"t": kind, "x": clip(text, 1200)}
        if kind == "li" and el.find_parent("li") is not None:
            block["d"] = 1
        out.append(block)
        total += len(text)
        if len(out) >= max_blocks or total >= max_chars:
            break
    while out and out[-1]["t"] == "h":
        out.pop()
    return out


def best_text_container(soup: Any) -> Any:
    """Pick the element with the most paragraph text (a tiny readability)."""
    for bad in soup(["script", "style", "noscript", "iframe", "form", "nav", "aside", "footer", "header", "svg", "button"]):
        bad.decompose()
    best, best_score = None, 0
    for cand in soup.find_all(["article", "div", "section", "main"]):
        ps = cand.find_all("p", recursive=False)
        if not ps:
            # allow one wrapper level
            ps = [p for child in cand.find_all(recursive=False) for p in child.find_all("p", recursive=False)]
        score = sum(len(p.get_text(" ", strip=True)) for p in ps)
        if score > best_score:
            best, best_score = cand, score
    return best if best_score >= 200 else None


def paragraphs_to_blocks(text: str, max_chars: int = 6000) -> list[dict]:
    text = clean_text(text)
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if len(parts) <= 1 and len(text) > 600:
        # split long single paragraph by sentences into ~400-char chunks
        sents = re.split(r"(?<=[.!?…])\s+", text)
        parts, cur = [], ""
        for s in sents:
            if len(cur) + len(s) > 420 and cur:
                parts.append(cur.strip())
                cur = ""
            cur += " " + s
        if cur.strip():
            parts.append(cur.strip())
    out, total = [], 0
    for p in parts:
        if JUNK_RE.search(p) and len(p) < 160:
            continue
        out.append({"t": "p", "x": clip(p, 1200)})
        total += len(p)
        if total >= max_chars:
            break
    return out


def og_image(soup: Any) -> str:
    for attrs in ({"property": "og:image"}, {"name": "og:image"}, {"name": "twitter:image"}, {"property": "twitter:image"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            u = safe_url(tag["content"])
            if u:
                return u
    return ""


def iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, MSK).replace(microsecond=0).isoformat()
