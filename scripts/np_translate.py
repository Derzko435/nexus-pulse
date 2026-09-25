#!/usr/bin/env python3
"""Free, keyless English → Russian machine translation with a persistent cache.

Providers (tried in order, no API keys needed):
  1. Google translate "dict-chrome-ex" endpoint — batch (many strings per request, 1:1 order kept)
  2. Google translate "gtx" endpoint — one string per request
  3. deep-translator GoogleTranslator (if the package is installed)
If every provider fails the original text is returned unchanged, so a failure never breaks
the pipeline and never shows half-translated junk.

Cache: data/translations.json  {"v": 1, "items": {sha1(src)[:16]: [ru, "YYYY-MM-DD"]}}
Entries unused for CACHE_DAYS are pruned on save, so reruns never translate the same text twice.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from np_common import DATA, MSK, log, read_json

CACHE_FILE = DATA / "translations.json"
CACHE_DAYS = 45
MAX_BATCH_CHARS = 4200
MAX_BATCH_ITEMS = 90
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CYR_RE = re.compile(r"[А-Яа-яЁё]")
LAT_RE = re.compile(r"[A-Za-z]")

# Names that machine translation tends to "translate" literally — kept as-is.
KEEP_NAMES = [
    "Counter-Strike 2", "Counter-Strike", "Dota 2", "PUBG: Battlegrounds", "PUBG", "Apex Legends",
    "Rainbow Six Siege", "Overwatch 2", "Overwatch", "Rust", "Destiny 2", "Warframe", "Path of Exile 2",
    "Path of Exile", "Helldivers 2", "Marvel Rivals", "Valorant", "League of Legends", "Steam", "Epic Games",
    "Battle Pass", "Deadlock", "Fortnite", "Minecraft",
]


def _h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


class Translator:
    def __init__(self) -> None:
        raw = read_json(CACHE_FILE, {}) or {}
        self.cache: dict = raw.get("items") or {}
        self.today = datetime.now(MSK).date().isoformat()
        self.dirty = False
        self.provider_ok = True  # flips to False after repeated failures → stop hammering
        self.fails = 0
        self.stats = {"cached": 0, "translated": 0, "failed": 0}

    # ---------------------------------------------------------- helpers
    @staticmethod
    def needs(s: str) -> bool:
        """Only English-looking text is translated (Russian or empty text is left alone)."""
        if not s or not s.strip():
            return False
        lat = len(LAT_RE.findall(s))
        cyr = len(CYR_RE.findall(s))
        return lat >= 3 and cyr < lat * 0.3

    def _protect(self, s: str) -> tuple[str, list[str]]:
        found: list[str] = []
        for name in KEEP_NAMES:
            if name in s:
                found.append(name)
        # protect longest first; tokens are short ASCII words Google keeps untouched
        out = s
        keep = []
        for name in sorted(set(found), key=len, reverse=True):
            tok = f"NPX{len(keep)}Q"
            if name in out:
                out = re.sub(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", tok, out)
                keep.append(name)
        return out, keep

    @staticmethod
    def _restore(s: str, keep: list[str]) -> str:
        for i, name in enumerate(keep):
            s = re.sub(rf"NPX\s*{i}\s*Q", name, s, flags=re.I)
        return s

    # ---------------------------------------------------------- providers
    def _batch_chrome_ex(self, items: list[str]) -> list[str] | None:
        data = urllib.parse.urlencode([("q", x) for x in items]).encode()
        req = urllib.request.Request(
            "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=ru",
            data=data, headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"})
        with urllib.request.urlopen(req, timeout=40) as r:
            res = json.loads(r.read().decode("utf-8"))
        if isinstance(res, str):
            res = [res]
        out = []
        for x in res:
            if isinstance(x, list):  # some variants answer [text, lang]
                x = x[0]
            out.append(str(x))
        return out if len(out) == len(items) else None

    @staticmethod
    def _single_gtx(s: str) -> str | None:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t"
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"q": s}).encode(), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
        return "".join(seg[0] for seg in res[0] if seg and seg[0]) or None

    @staticmethod
    def _single_deep(s: str) -> str | None:
        try:
            from deep_translator import GoogleTranslator  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        return GoogleTranslator(source="en", target="ru").translate(s)

    def _translate_many(self, texts: list[str]) -> list[str | None]:
        """Translate unique uncached strings. Returns None for failures."""
        results: list[str | None] = [None] * len(texts)
        # 1) batches
        i = 0
        while i < len(texts) and self.provider_ok:
            batch, size = [], 0
            while i + len(batch) < len(texts) and len(batch) < MAX_BATCH_ITEMS:
                nxt = texts[i + len(batch)]
                if batch and size + len(nxt) > MAX_BATCH_CHARS:
                    break
                batch.append(nxt)
                size += len(nxt)
            prot = [self._protect(x) for x in batch]
            try:
                res = self._batch_chrome_ex([p[0] for p in prot])
            except Exception as e:  # noqa: BLE001
                log(f"[translate] batch provider failed: {e}")
                res = None
            if res:
                for k, (txt, keep) in enumerate(prot):
                    results[i + k] = self._restore(res[k], keep)
                self.fails = 0
            else:
                self.fails += 1
                if self.fails >= 3:
                    log("[translate] batch provider unavailable, switching to single-string providers")
                    break
            i += len(batch)
            time.sleep(0.4)
        # 2) singles for whatever is still missing
        single_fails = 0
        for k, src in enumerate(texts):
            if results[k] is not None or single_fails >= 4:
                continue
            txt, keep = self._protect(src)
            for fn in (self._single_gtx, self._single_deep):
                try:
                    r = fn(txt)
                except Exception as e:  # noqa: BLE001
                    log(f"[translate] {fn.__name__} failed: {str(e)[:120]}")
                    r = None
                if r:
                    results[k] = self._restore(r, keep)
                    break
                time.sleep(0.6)
            if results[k] is None:
                single_fails += 1
            time.sleep(0.3)
        return results

    # ---------------------------------------------------------- public
    def many(self, texts: list[str]) -> list[str]:
        """Translate a list of strings (order kept). Non-English strings pass through."""
        out = list(texts)
        todo: dict[str, list[int]] = {}
        for idx, s in enumerate(texts):
            if not self.needs(s):
                continue
            h = _h(s)
            hit = self.cache.get(h)
            if hit:
                out[idx] = hit[0]
                if hit[1] != self.today:
                    hit[1] = self.today
                    self.dirty = True
                self.stats["cached"] += 1
            else:
                todo.setdefault(s, []).append(idx)
        if todo:
            srcs = list(todo)
            res = self._translate_many(srcs)
            for s, r in zip(srcs, res):
                if r and CYR_RE.search(r):
                    self.cache[_h(s)] = [r, self.today]
                    self.dirty = True
                    self.stats["translated"] += 1
                    for idx in todo[s]:
                        out[idx] = r
                else:
                    self.stats["failed"] += 1
        return out

    def one(self, s: str) -> str:
        return self.many([s])[0]

    def is_done(self, s: str) -> bool:
        """True if the string does not need translation or is already in the cache."""
        return not self.needs(s) or _h(s) in self.cache

    def save(self) -> None:
        cutoff = (datetime.now(MSK).date() - timedelta(days=CACHE_DAYS)).isoformat()
        before = len(self.cache)
        self.cache = {k: v for k, v in self.cache.items() if isinstance(v, list) and len(v) == 2 and v[1] >= cutoff}
        if not self.dirty and before == len(self.cache):
            log(f"[translate] cache unchanged ({len(self.cache)} entries) {self.stats}")
            return
        CACHE_FILE.write_text(json.dumps({"v": 1, "items": self.cache}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        log(f"[translate] cache saved: {len(self.cache)} entries {self.stats}")
