/* NEXUS PULSE — ежедневный контент: новости, календарь, патчи, новинки, каталог с картинками,
   матчи и трансляции, видео, подробные гайды. Весь внешний текст экранируется перед вставкой. */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const TZ = "Europe/Moscow";
  const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const PAGE_HOST = location.hostname || "derzko435.github.io";

  /* ---------------- helpers ---------------- */
  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function safeUrl(u) {
    const s = String(u || "").trim();
    return /^https:\/\/[^\s"'<>]+$/i.test(s) ? s : "";
  }
  async function getJson(name) {
    const res = await fetch("./data/" + name, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }
  function mskParts(d) {
    const f = new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
    const o = {};
    f.formatToParts(d).forEach((p) => { o[p.type] = p.value; });
    return { y: +o.year, m: +o.month, d: +o.day, hh: o.hour === "24" ? "00" : o.hour, mm: o.minute };
  }
  function dayKey(p) { return p.y * 10000 + p.m * 100 + p.d; }
  function todayKey() { return dayKey(mskParts(new Date())); }
  function isoDayKey(iso) {
    const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? (+m[1]) * 10000 + (+m[2]) * 100 + (+m[3]) : 0;
  }
  function fmtDay(iso, withYear) {
    const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return "";
    const nowY = mskParts(new Date()).y;
    return `${+m[3]} ${MONTHS[+m[2] - 1]}${withYear || +m[1] !== nowY ? " " + m[1] : ""}`;
  }
  function relDay(iso) {
    const k = isoDayKey(iso);
    const t = todayKey();
    if (!k) return "";
    const toDate = (x) => new Date(Math.floor(x / 10000), Math.floor((x % 10000) / 100) - 1, x % 100);
    const diff = Math.round((toDate(k) - toDate(t)) / 86400000);
    if (diff === 0) return "сегодня";
    if (diff === -1) return "вчера";
    if (diff === 1) return "завтра";
    return "";
  }
  function fmtDateTime(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const p = mskParts(d);
    const iso2 = `${p.y}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
    return `${relDay(iso2) || fmtDay(iso2)}, ${p.hh}:${p.mm} МСК`;
  }
  function fmtNewsDate(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const p = mskParts(d);
    const iso2 = `${p.y}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
    const r = relDay(iso2);
    return `${r || fmtDay(iso2)}, ${p.hh}:${p.mm}`;
  }
  function fmtUpdated(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const p = mskParts(d);
    return `Обновлено: ${p.d} ${MONTHS[p.m - 1]}, ${p.hh}:${p.mm} МСК`;
  }
  function imgUrl(src) {
    const s = String(src || "").trim();
    return /^\.\/assets\/[\w\/.-]+\.(png|jpe?g|webp|svg)$/i.test(s) ? s : safeUrl(s);
  }
  function img(src, alt, cls, extra) {
    const u = imgUrl(src);
    if (!u) return "";
    return `<img class="${cls || ""}" src="${esc(u)}" alt="${esc(alt || "")}" loading="lazy" decoding="async" data-np-img ${extra || ""}>`;
  }
  // Неудачная картинка → убираем её, остаётся аккуратная заглушка-градиент
  document.addEventListener("error", (e) => {
    const el = e.target;
    if (el && el.tagName === "IMG" && el.hasAttribute("data-np-img")) {
      const box = el.parentElement;
      el.remove();
      if (box) box.classList.add("img-fallback");
    }
  }, true);
  document.addEventListener("load", (e) => {
    const el = e.target;
    if (el && el.tagName === "IMG" && el.hasAttribute("data-np-img") && el.parentElement) el.parentElement.classList.add("img-loaded");
  }, true);

  function blocksHtml(blocks) {
    let html = "";
    let inList = false;
    (blocks || []).forEach((b) => {
      if (!b || typeof b.x !== "string") return;
      if (b.t === "li") {
        if (!inList) { html += "<ul>"; inList = true; }
        html += `<li${b.d ? ' class="sub"' : ""}>${esc(b.x)}</li>`;
        return;
      }
      if (inList) { html += "</ul>"; inList = false; }
      html += b.t === "h" ? `<h4>${esc(b.x)}</h4>` : `<p>${esc(b.x)}</p>`;
    });
    if (inList) html += "</ul>";
    return html;
  }

  /* ---------------- viewer modal ---------------- */
  let viewer, viewerContent, lastFocus = null, savedScroll = 0;
  function ensureViewer() {
    if (viewer) return;
    viewer = document.createElement("div");
    viewer.className = "npv";
    viewer.id = "npViewer";
    viewer.hidden = true;
    viewer.innerHTML = `
      <div class="npv-backdrop" data-npv-close></div>
      <div class="npv-dialog glass" role="dialog" aria-modal="true" aria-labelledby="npvTitle">
        <button type="button" class="npv-close" data-npv-close aria-label="Закрыть">×</button>
        <div class="npv-content"></div>
      </div>`;
    document.body.appendChild(viewer);
    viewerContent = $(".npv-content", viewer);
    viewer.addEventListener("click", (e) => {
      if (e.target.closest("[data-npv-close]")) closeViewer();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && viewer && !viewer.hidden) closeViewer();
      if (e.key === "Tab" && viewer && !viewer.hidden) trapFocus(e);
    });
  }
  function trapFocus(e) {
    const f = $$('a[href], button:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])', viewer).filter((x) => x.offsetParent !== null);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function openViewer(html, opts) {
    ensureViewer();
    lastFocus = document.activeElement;
    viewerContent.innerHTML = html;
    const dlg = $(".npv-dialog", viewer);
    dlg.classList.toggle("npv-wide", !!(opts && opts.wide));
    dlg.scrollTop = 0;
    viewer.hidden = false;
    savedScroll = window.scrollY;
    document.documentElement.classList.add("npv-lock");
    document.body.classList.add("npv-lock");
    requestAnimationFrame(() => $(".npv-close", viewer)?.focus({ preventScroll: true }));
  }
  function closeViewer() {
    if (!viewer || viewer.hidden) return;
    viewer.hidden = true;
    viewerContent.innerHTML = ""; // останавливает видео
    document.documentElement.classList.remove("npv-lock");
    document.body.classList.remove("npv-lock");
    if (Math.abs(window.scrollY - savedScroll) > 2) window.scrollTo(0, savedScroll);
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus({ preventScroll: true });
  }
  function actions(list) {
    return `<div class="npv-actions">${list.filter(Boolean).join("")}<button type="button" class="btn btn-ghost btn-sm" data-npv-close>Закрыть</button></div>`;
  }
  function discordLink(label) {
    const u = String((window.NexusPulse && window.NexusPulse.DISCORD_INVITE_URL) || "");
    return /^https:\/\/discord\.gg\/[\w-]+$/.test(u)
      ? `<a class="btn btn-discord btn-sm" href="${esc(u)}" target="_blank" rel="noopener noreferrer">💬 ${esc(label)}</a>` : "";
  }
  function extLink(url, label) {
    const u = safeUrl(url);
    return u ? `<a class="btn btn-primary btn-sm" href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : "";
  }

  /* ---------------- embeds ---------------- */
  function embedSrc(st) {
    if (!st) return "";
    if (st.type === "twitch" && /^[a-z0-9_]{2,40}$/i.test(st.channel || "")) {
      const parents = Array.from(new Set([PAGE_HOST, "derzko435.github.io"])).map((h) => "&parent=" + encodeURIComponent(h)).join("");
      return `https://player.twitch.tv/?channel=${encodeURIComponent(st.channel)}${parents}&autoplay=true&muted=false`;
    }
    if (st.type === "youtube" && /^[A-Za-z0-9_-]{11}$/.test(st.id || "")) {
      return `https://www.youtube-nocookie.com/embed/${st.id}?autoplay=1&rel=0&modestbranding=1&playsinline=1`;
    }
    if (st.type === "kick" && /^[a-z0-9_]{2,40}$/i.test(st.channel || "")) {
      return `https://player.kick.com/${encodeURIComponent(st.channel)}?autoplay=true`;
    }
    return "";
  }
  function iframeHtml(st, title) {
    const src = embedSrc(st);
    if (!src) return "";
    return `<div class="np-player"><iframe src="${esc(src)}" title="${esc(title || "Трансляция")}" allow="autoplay; fullscreen; picture-in-picture; encrypted-media; keyboard-map" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
  }
  function streamLabel(st) {
    const lang = st.lang === "ru" ? " · RU" : st.lang === "en" ? " · EN" : st.lang ? " · " + st.lang.toUpperCase() : "";
    const kind = st.type === "twitch" ? "Twitch" : st.type === "youtube" ? "YouTube" : "Kick";
    return `${kind}${st.type === "youtube" ? "" : ": " + (st.label || st.channel)}${lang}`;
  }

  /* ---------------- 1. News ---------------- */
  let NEWS = [];
  let newsShown = 12;
  function renderNews() {
    const grid = $("#newsGrid");
    if (!grid) return;
    if (!NEWS.length) { grid.innerHTML = ""; $("#newsMore") && ($("#newsMore").hidden = true); return; }
    grid.innerHTML = NEWS.slice(0, newsShown).map((n) => `
      <article class="news-card glass np-clickable" tabindex="0" role="button" data-news-id="${esc(n.id)}" aria-label="Открыть новость: ${esc(n.title)}">
        <div class="card-cover news-cover">${img(n.image, "", "cover-img")}<span class="news-source">${esc(n.source)}</span></div>
        <div class="card-body">
          <div class="news-date">${esc(fmtNewsDate(n.date))}</div>
          <h3>${esc(n.title)}</h3>
          <p>${esc(n.summary)}</p>
          <span class="card-open">Читать полностью →</span>
        </div>
      </article>`).join("");
    const more = $("#newsMore");
    if (more) more.hidden = newsShown >= NEWS.length;
  }
  function openNews(id) {
    const n = NEWS.find((x) => x.id === id);
    if (!n) {
      getJson("share_index.json").then((d) => {
        const a = ((d && d.news) || []).find((x) => x.id === id);
        if (a) openArchivedNews(a);
      }).catch(() => {});
      return;
    }
    openViewer(`
      ${imgUrl(n.image) ? `<div class="npv-hero">${img(n.image, n.title, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">${esc(n.source)} · ${esc(fmtNewsDate(n.date))} МСК</p>
      <h3 id="npvTitle">${esc(n.title)}</h3>
      <div class="npv-body">${blocksHtml(n.body)}</div>
      <p class="npv-source">Источник: ${esc(n.source)}. Полная версия материала — на сайте издания.</p>
      ${actions([extLink(n.url, "Читать в источнике"), shareBtn("news", n.id, n.title), discordLink("Обсудить в Discord")])}`, { wide: true });
  }
  // Кнопка «Поделиться»: ссылка на страницу-превью /s/news/<id>.html (красивая карточка в мессенджерах)
  function shareBtn(kind, id, title) {
    if (!/^[\w-]{1,64}$/.test(String(id || ""))) return "";
    return `<button type="button" class="btn btn-ghost btn-sm" data-np-share="${esc(kind)}" data-id="${esc(id)}" data-title="${esc(title || "")}">↗ Поделиться</button>`;
  }
  // Новость, которой уже нет в ленте (ссылка из мессенджера): показываем сохранённую карточку
  function openArchivedNews(a) {
    openViewer(`
      ${imgUrl(a.image) ? `<div class="npv-hero">${img(a.image, a.title, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">${esc(a.source || "")}${a.date ? " · " + esc(fmtNewsDate(a.date)) + " МСК" : ""}</p>
      <h3 id="npvTitle">${esc(a.title)}</h3>
      <div class="npv-body"><p>${esc(a.summary || "")}</p></div>
      <p class="npv-source">Источник: ${esc(a.source || "")}. Полная версия материала — на сайте издания.</p>
      ${actions([extLink(a.url, "Читать в источнике"), shareBtn("news", a.id, a.title)])}`, { wide: true });
  }

  /* ---------------- 2. Releases / patches ---------------- */
  let RELEASES = [], PATCHES = [], releasesAll = false, releasePlat = "all";
  const PLAT_BADGE = { PC: "ПК", PlayStation: "PS", Xbox: "Xbox", Switch: "Switch" };
  function relKey(r) { return String(r.appid || r.id || ""); }
  function relMatches(r, plat) {
    if (plat === "all") return true;
    if (plat === "Epic") return (r.stores || []).includes("Epic");
    return (r.platforms || ["PC"]).includes(plat);
  }
  function platBadges(r) {
    const pl = (r.platforms || ["PC"]).filter((p) => PLAT_BADGE[p]);
    const b = pl.map((p) => `<span class="plat-badge plat-${esc(p.toLowerCase())}">${esc(PLAT_BADGE[p])}</span>`);
    if ((r.stores || []).includes("Epic")) b.push('<span class="plat-badge plat-epic">Epic</span>');
    return b.length ? `<span class="plat-badges">${b.join("")}</span>` : "";
  }
  function renderReleases() {
    const ul = $("#releasesList");
    if (!ul) return;
    const t = todayKey();
    const upcoming = RELEASES.filter((r) => isoDayKey(r.date) >= t);
    const list = upcoming.filter((r) => relMatches(r, releasePlat));
    const shown = releasesAll ? list : list.slice(0, 8);
    ul.innerHTML = shown.map((r) => `
      <li class="cal-rich np-clickable" tabindex="0" role="button" data-release="${esc(relKey(r))}" aria-label="Подробнее: ${esc(r.title)}">
        <div class="cal-thumb">${img(r.image, "", "cover-img")}</div>
        <div class="cal-body">
          <div class="cal-when"><span class="cal-date-chip">${esc(fmtDay(r.date))}</span>${relDay(r.date) ? `<span class="cal-label">${esc(relDay(r.date))}</span>` : ""}</div>
          <strong>${esc(r.title)}</strong>
          ${platBadges(r)}
          <p class="cal-note">${esc((r.genres || []).join(" · "))}${r.price ? ` · ${esc(r.price)}` : ""}</p>
        </div>
      </li>`).join("") || `<li class="cal-empty">${upcoming.length ? "Для этой платформы ближайших релизов пока нет." : "Скоро здесь появятся ближайшие релизы."}</li>`;
    const more = $("#releasesMore");
    if (more) {
      more.hidden = list.length <= 8;
      more.textContent = releasesAll ? "Свернуть" : `Показать все релизы (${list.length})`;
    }
  }
  function storeLinks(r) {
    const L = r.links || {};
    const out = [];
    if (L.steam) out.push(extLink(L.steam, "Страница в Steam"));
    if (L.epic) out.push(extLink(L.epic, "Epic Games Store"));
    if (!out.length && L.wiki) out.push(extLink(L.wiki, "Об игре"));
    if (!out.length && r.url) out.push(extLink(r.url, "Страница в Steam"));
    return out;
  }
  function openRelease(appid) {
    const r = RELEASES.find((x) => relKey(x) === String(appid)) || NEWGAMES.find((x) => relKey(x) === String(appid));
    if (!r) return;
    const isNew = NEWGAMES.includes(r);
    const plats = (r.platforms || ["PC"]).map((p) => (p === "PC" ? "ПК" : p));
    openViewer(`
      ${imgUrl(r.image) ? `<div class="npv-hero npv-hero-wide">${img(r.image, r.title, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">${isNew ? "Новинка" : "Релиз"} · ${esc(fmtDay(r.date, true))}</p>
      <h3 id="npvTitle">${esc(r.title)}</h3>
      <div class="npv-body">
        <p>${esc(r.desc)}</p>
        <ul class="npv-facts">
          <li><b>Дата выхода:</b> ${esc(fmtDay(r.date, true))}</li>
          ${(r.genres || []).length ? `<li><b>Жанр:</b> ${esc(r.genres.join(", "))}</li>` : ""}
          ${r.developer ? `<li><b>Разработчик:</b> ${esc(r.developer)}</li>` : ""}
          <li><b>Платформы:</b> ${esc(plats.join(", "))}</li>
          ${(r.stores || []).length ? `<li><b>Магазины на ПК:</b> ${esc(r.stores.join(", "))}</li>` : ""}
          ${r.price ? `<li><b>Цена в Steam:</b> ${esc(r.price)}</li>` : ""}
          ${r.reviews ? `<li><b>Отзывов в Steam:</b> ${esc(Number(r.reviews).toLocaleString("ru-RU"))}</li>` : ""}
        </ul>
        ${window.NPPriceHistory && r.links && r.links.steam ? window.NPPriceHistory.block(String(r.appid)) : ""}
      </div>
      ${actions(storeLinks(r))}`);
  }
  const CATALOG_IDS = { cs2: "cs2", dota2: "dota2", apex: "apex", r6: "r6", ow2: "ow2", destiny2: "destiny2", poe2: "poe2", valorant: "valorant", lol: "lol" };
  function renderPatches() {
    const ul = $("#patchesList");
    if (!ul) return;
    ul.innerHTML = PATCHES.slice(0, 10).map((p) => `
      <li class="cal-rich np-clickable" tabindex="0" role="button" data-patch="${esc(p.id)}" aria-label="Описание обновления: ${esc(p.game)}">
        <div class="cal-thumb">${img(patchThumb(p), "", "cover-img")}</div>
        <div class="cal-body">
          <div class="cal-when"><span class="cal-date-chip">${esc(fmtDay(p.date))}</span>${relDay(p.date) ? `<span class="cal-label">${esc(relDay(p.date))}</span>` : ""}</div>
          <strong>${esc(p.game)}</strong>
          <p class="cal-note">${esc(p.title)}</p>
        </div>
      </li>`).join("") || `<li class="cal-empty">Скоро здесь появятся свежие обновления.</li>`;
  }
  function patchThumb(p) {
    const c = CATALOG && CATALOG.games && CATALOG.games[p.catalogId || CATALOG_IDS[p.id] || ""];
    return (c && c.img && !c.fit) ? c.img : p.image;
  }
  function openPatch(id) {
    const p = PATCHES.find((x) => x.id === id);
    if (!p) return;
    openViewer(`
      ${imgUrl(p.image) ? `<div class="npv-hero npv-hero-wide">${img(p.image, p.game, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">Обновление · ${esc(p.game)} · ${esc(fmtDay(p.date, true))}</p>
      <h3 id="npvTitle">${esc(p.title)}</h3>
      ${p.lang === "en" ? `<p class="npv-note">Официальное описание изменений от разработчиков (на английском языке).</p>` : ""}
      ${p.translated ? `<p class="npv-note">Официальное описание изменений в автоматическом переводе на русский. Оригинал — по кнопке ниже.</p>` : ""}
      <div class="npv-body npv-notes">${blocksHtml(p.body)}</div>
      ${actions([extLink(p.url, "Открыть оригинал")])}`, { wide: true });
  }

  /* ---------------- 3. New games ---------------- */
  let NEWGAMES = [];
  function renderNewGames(updatedAt) {
    const grid = $("#newGamesGrid");
    if (!grid) return;
    grid.innerHTML = NEWGAMES.map((g) => `
      <article class="new-game-card np-clickable" tabindex="0" role="button" data-release="${esc(relKey(g))}" aria-label="Подробнее: ${esc(g.title)}">
        <div class="card-cover new-cover">${img(g.image, "", "cover-img")}<span class="new-game-tag">${esc(g.price === "Бесплатно" ? "бесплатно" : "новинка")}</span></div>
        <div class="card-body">
          <h3>${esc(g.title)}</h3>
          <p class="new-game-genre">${esc((g.genres || []).join(" · "))}</p>
          ${platBadges(g)}
          <p class="new-game-blurb">${esc(g.desc)}</p>
          <div class="new-game-meta">
            <span class="new-game-price">${esc(g.price || "")}</span>
            <span class="new-game-date">${esc(fmtDay(g.date))}</span>
          </div>
        </div>
      </article>`).join("");
    const up = $("#newGamesUpdated");
    if (up && updatedAt) {
      up.dataset.date = String(updatedAt).slice(0, 10);
      up.textContent = "Обновлено: " + fmtDay(updatedAt, true);
    }
  }

  /* ---------------- 4. Catalog pictures ---------------- */
  let CATALOG = null;
  function decorateCatalog() {
    if (!CATALOG || !CATALOG.games) return;
    $$("#gamesGrid .game-card").forEach((card) => {
      const id = card.dataset.id;
      const info = CATALOG.games[id];
      if (!info) return;
      const cover = $(".card-cover", card);
      if (cover && !cover.dataset.npImg && imgUrl(info.img)) {
        cover.dataset.npImg = "1";
        cover.classList.add("has-media");
        if (info.fit === "contain") cover.classList.add("media-contain");
        cover.insertAdjacentHTML("afterbegin", img(info.img, "", "cover-img"));
      }
      const body = $(".card-body", card);
      if (body && !body.dataset.npDesc) {
        body.dataset.npDesc = "1";
        if (info.desc) {
          const p = document.createElement("p");
          p.className = "card-desc-long";
          p.textContent = info.desc;
          const short = $(".card-desc", body);
          (short || body.lastElementChild).insertAdjacentElement("afterend", p);
        }
        const more = document.createElement("button");
        more.type = "button";
        more.className = "card-more";
        more.dataset.gameMore = id;
        more.textContent = "Подробнее об игре";
        body.appendChild(more);
      }
    });
  }
  function openGame(id) {
    const NP = window.NexusPulse;
    const g = NP && NP.GAMES ? NP.GAMES.find((x) => x.id === id) : null;
    if (!g) return;
    const info = (CATALOG && CATALOG.games && CATALOG.games[id]) || {};
    const genres = (info.genres || []).join(", ");
    openViewer(`
      ${imgUrl(info.img) ? `<div class="npv-hero npv-hero-wide${info.fit === "contain" ? " media-contain" : ""}">${img(info.img, g.title, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">Каталог · ${esc(g.genre)}</p>
      <h3 id="npvTitle">${esc(g.title)}</h3>
      <div class="npv-body">
        <p><strong>${esc(g.desc)}</strong></p>
        ${info.desc ? `<p>${esc(info.desc)}</p>` : ""}
        <ul class="npv-facts">
          <li><b>Рейтинг редакции:</b> ★ ${esc(Number(g.rating).toFixed(1))}</li>
          <li><b>Платформы:</b> ${esc((g.platforms || []).join(", "))}</li>
          ${genres ? `<li><b>Жанры:</b> ${esc(genres)}</li>` : ""}
          ${info.release ? `<li><b>Дата выхода:</b> ${esc(info.release)}</li>` : ""}
        </ul>
        ${window.NPPriceHistory && info.appid ? window.NPPriceHistory.block(String(info.appid)) : ""}
      </div>
      ${actions([extLink(info.url, info.appid ? "Страница в Steam" : "Официальный сайт")])}`);
  }

  /* ---------------- 5. Esports ---------------- */
  const OFFICIAL_CHANNELS = [
    { channel: "eslcs", label: "ESL Counter-Strike", game: "CS2" },
    { channel: "blastpremier", label: "BLAST", game: "CS2 · Dota 2" },
    { channel: "pgl", label: "PGL", game: "CS2" },
    { channel: "pgl_dota2", label: "PGL Dota 2", game: "Dota 2" },
    { channel: "esl_dota2", label: "ESL Dota 2", game: "Dota 2" },
    { channel: "valorant", label: "VALORANT", game: "Valorant" },
    { channel: "riotgames", label: "Riot Games", game: "LoL" },
    { channel: "lck", label: "LCK", game: "LoL" },
    { channel: "lec", label: "LEC", game: "LoL" },
  ].map((c) => Object.assign({ type: "twitch", lang: "en", official: true }, c));
  let MATCHES = [], TOURS = [], matchFilter = "all";
  let pendingStream = OFFICIAL_CHANNELS[0];

  function renderWatchChips() {
    const host = $("#watchChannels");
    if (!host) return;
    host.innerHTML = OFFICIAL_CHANNELS.map((c, i) => `
      <button type="button" class="chip watch-chip${i === 0 ? " active" : ""}" data-watch-channel="${esc(c.channel)}">
        <span class="watch-chip-name">${esc(c.label)}</span><span class="watch-chip-game">${esc(c.game)}</span>
      </button>`).join("");
    setWatchNow(pendingStream, null, false);
  }
  function setWatchNow(st, match, playing) {
    const now = $("#watchNow");
    if (!now) return;
    const what = match ? `${match.teamA} — ${match.teamB} · ${match.event}` : (st.label || st.channel);
    now.textContent = (playing ? "Сейчас: " : "Выбрано: ") + what + " · " + streamLabel(st);
  }
  function playStream(st, match, scroll) {
    const box = $("#watchPlayer");
    if (!box || !embedSrc(st)) return;
    pendingStream = st;
    box.innerHTML = iframeHtml(st, match ? `${match.teamA} — ${match.teamB}` : st.label);
    box.classList.add("is-playing");
    setWatchNow(st, match, true);
    $$("#watchChannels .watch-chip").forEach((c) => c.classList.toggle("active", st.type === "twitch" && c.dataset.watchChannel === st.channel));
    if (scroll) $("#watchBlock")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function matchState(m, now) {
    const st = new Date(m.startsAt).getTime();
    if (m.status === "finished") return "finished";
    if (!Number.isFinite(st)) return "hide";
    if (st > now) return "upcoming";
    if (now - st < 4 * 3600 * 1000) return "live";
    return "hide"; // результат неизвестен — не показываем устаревшее
  }
  function teamHtml(name, logo, side) {
    const initials = String(name || "?").replace(/[^A-Za-zА-Яа-я0-9 ]/g, "").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
    return `<div class="mt-team mt-${side}"><span class="mt-logo">${img(logo, "", "mt-logo-img")}<i>${esc(initials)}</i></span><span class="mt-name">${esc(name)}</span></div>`;
  }
  function matchCard(m, state) {
    const idx = MATCHES.indexOf(m);
    const hasScore = state !== "upcoming" && m.scoreA != null && m.scoreB != null;
    const streams = (m.streams || []).filter((s) => embedSrc(s));
    const statusText = state === "live" ? "В эфире" : state === "upcoming" ? fmtDateTime(m.startsAt) : "Завершён · " + fmtDateTime(m.startsAt);
    return `
      <article class="match-card glass status-${state}">
        <div class="match-top"><span class="match-game-badge g-${esc(m.gameKey)}">${esc(m.game)}</span><span class="match-event">${esc(m.event)}</span></div>
        <div class="match-teams2">
          ${teamHtml(m.teamA, m.logoA, "a")}
          <div class="mt-score">${hasScore ? `${esc(m.scoreA)}<span>:</span>${esc(m.scoreB)}` : "vs"}${m.bo ? `<small>Bo${esc(m.bo)}</small>` : ""}</div>
          ${teamHtml(m.teamB, m.logoB, "b")}
        </div>
        <div class="match-status">${state === "live" ? '<span class="live-dot"></span>' : ""}${esc(statusText)}</div>
        <div class="match-actions">
          ${streams.length ? `<button type="button" class="btn btn-primary btn-sm" data-watch-match="${idx}" data-stream="0">${state === "finished" ? "Смотреть запись" : "Смотреть"}</button>` : ""}
          ${streams.slice(1, 3).map((s, i) => `<button type="button" class="chip chip-sm" data-watch-match="${idx}" data-stream="${i + 1}">${esc(streamLabel(s))}</button>`).join("")}
          ${safeUrl(m.url) ? `<a class="match-more" href="${esc(m.url)}" target="_blank" rel="noopener noreferrer">Подробнее ↗</a>` : ""}
        </div>
      </article>`;
  }
  function renderMatches() {
    const host = $("#matchesLive");
    if (!host) return;
    const now = Date.now();
    const list = MATCHES.filter((m) => matchFilter === "all" || m.gameKey === matchFilter);
    const groups = { live: [], upcoming: [], finished: [] };
    list.forEach((m) => { const s = matchState(m, now); if (groups[s]) groups[s].push(m); });
    groups.upcoming.sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));
    groups.finished.sort((a, b) => new Date(b.startsAt) - new Date(a.startsAt));
    const block = (title, arr, state, max) => arr.length ? `
      <div class="match-group"><h4 class="match-group-title">${title}</h4>
        <div class="matches-grid">${arr.slice(0, max).map((m) => matchCard(m, state)).join("")}</div></div>` : "";
    const html = block("Сейчас в эфире", groups.live, "live", 8) + block("Ближайшие матчи", groups.upcoming, "upcoming", 12) + block("Последние результаты", groups.finished, "finished", 8);
    host.innerHTML = html || `<p class="empty-state">Матчей по выбранной игре пока нет — загляни позже или включи официальный канал выше.</p>`;
  }
  function renderTournaments() {
    const ul = $("#tournamentsList");
    if (!ul) return;
    ul.innerHTML = TOURS.slice(0, 10).map((t) => {
      const prize = Number(t.prize) > 0 ? "$" + Number(t.prize).toLocaleString("en-US") : (t.status === "current" ? "идёт" : "скоро");
      const range = t.start === t.end ? fmtDay(t.start) : `${fmtDay(t.start)} — ${fmtDay(t.end)}`;
      const name = safeUrl(t.url) ? `<a href="${esc(t.url)}" target="_blank" rel="noopener noreferrer">${esc(t.name)}</a>` : esc(t.name);
      return `<li class="${t.status === "current" ? "t-current" : ""}">
        <span class="t-date">${esc(range)}</span>
        <div><div class="t-name">${name}</div><div class="t-game">${esc(t.game)}${t.status === "current" ? " · идёт сейчас" : ""}</div></div>
        <span class="t-prize">${esc(prize)}</span></li>`;
    }).join("");
  }

  /* ---------------- 6. Videos & streams ---------------- */
  let VIDEOS = [], videoCat = "all", videosShown = 12;
  const STREAM_CHANNELS = OFFICIAL_CHANNELS;
  function videoCard(v) {
    return `
      <article class="video-card np-clickable" tabindex="0" role="button" data-video="${esc(v.id)}" aria-label="Смотреть: ${esc(v.title)}">
        <div class="video-thumb">${img(`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`, "", "cover-img")}<span class="video-play" aria-hidden="true">▶</span>
          <span class="video-cat">${esc({ games: "Игры", esports: "Киберспорт", ai: "ИИ и технологии" }[v.category] || "")}</span></div>
        <div class="video-body">
          <h3>${esc(v.title)}</h3>
          <p class="video-meta">${esc(v.channel)} · ${esc(fmtNewsDate(v.date))}${v.views ? ` · ${esc(Number(v.views).toLocaleString("ru-RU"))} просмотров` : ""}</p>
        </div>
      </article>`;
  }
  function streamCard(c) {
    return `
      <article class="video-card stream-card np-clickable" tabindex="0" role="button" data-stream-channel="${esc(c.channel)}" aria-label="Смотреть канал ${esc(c.label)}">
        <div class="video-thumb stream-thumb"><span class="stream-mono">${esc(c.label.split(" ").map((w) => w[0]).join("").slice(0, 3))}</span><span class="video-play" aria-hidden="true">▶</span><span class="video-cat">Twitch</span></div>
        <div class="video-body"><h3>${esc(c.label)}</h3><p class="video-meta">Официальный канал · ${esc(c.game)}</p></div>
      </article>`;
  }
  function renderVideos() {
    const grid = $("#videoGrid");
    if (!grid) return;
    const more = $("#videosMore");
    if (videoCat === "streams") {
      grid.innerHTML = STREAM_CHANNELS.map(streamCard).join("");
      if (more) more.hidden = true;
      return;
    }
    const list = VIDEOS.filter((v) => videoCat === "all" || (videoCat === "ru" ? v.lang === "ru" : v.category === videoCat));
    grid.innerHTML = list.slice(0, videosShown).map(videoCard).join("") || `<p class="empty-state">Скоро здесь появятся новые видео.</p>`;
    if (more) more.hidden = videosShown >= list.length;
  }
  function openVideo(id) {
    const v = VIDEOS.find((x) => x.id === id);
    if (!v) return;
    openViewer(`
      ${iframeHtml({ type: "youtube", id: v.id }, v.title)}
      <p class="npv-kicker">${esc(v.channel)} · ${esc(fmtNewsDate(v.date))}</p>
      <h3 id="npvTitle">${esc(v.title)}</h3>
      ${v.desc ? `<div class="npv-body"><p>${esc(v.desc)}</p></div>` : ""}
      ${actions([extLink("https://www.youtube.com/watch?v=" + v.id, "Открыть на YouTube")])}`, { wide: true });
  }
  function openStreamChannel(ch) {
    const c = STREAM_CHANNELS.find((x) => x.channel === ch);
    if (!c) return;
    openViewer(`
      ${iframeHtml(c, c.label)}
      <p class="npv-kicker">Официальный канал · ${esc(c.game)}</p>
      <h3 id="npvTitle">${esc(c.label)}</h3>
      <div class="npv-body"><p>Если сейчас эфира нет, в плеере будут последние записи трансляций.</p></div>
      ${actions([extLink("https://www.twitch.tv/" + c.channel, "Открыть на Twitch")])}`, { wide: true });
  }

  /* ---------------- 7. Guides ---------------- */
  function guideList() { return Array.isArray(window.NP_GUIDES) ? window.NP_GUIDES : []; }
  function renderGuides() {
    const el = $("#guidesGrid");
    const list = guideList();
    if (!el || !list.length) return;
    el.innerHTML = list.map((g) => {
      const info = g.game && CATALOG && CATALOG.games ? CATALOG.games[g.game] : null;
      const cover = info && imgUrl(info.img) && !info.fit ? `<div class="guide-cover">${img(info.img, "", "cover-img")}</div>` : "";
      return `
      <button type="button" class="guide-card glass${cover ? " has-cover" : ""}" data-np-guide="${esc(g.id)}" aria-label="Открыть гайд: ${esc(g.title)}">
        ${cover}
        <span class="guide-tag">${esc(g.tag)}</span>
        <h3>${esc(g.title)}</h3>
        <p class="guide-preview">${esc(g.lead)}</p>
        <div class="guide-meta">⏱ ${esc(g.time)} · ${esc(g.level || "")}</div>
        <span class="guide-open">Открыть гайд →</span>
      </button>`;
    }).join("");
  }
  function sectionHtml(sec) {
    let inner = "";
    if (sec.steps) inner = `<ol class="guide-steps">${sec.steps.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
    else if (sec.list) inner = `<ul>${sec.list.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    else if (sec.settings) inner = `<div class="guide-table" role="table">${sec.settings.map((r) => `
        <div class="gt-row" role="row"><div class="gt-name" role="cell">${esc(r[0])}</div><div class="gt-val" role="cell">${esc(r[1])}</div><div class="gt-why" role="cell">${esc(r[2] || "")}</div></div>`).join("")}</div>`;
    else if (sec.text) inner = `<p>${esc(sec.text)}</p>`;
    return `<section class="guide-sec"><h4>${esc(sec.h)}</h4>${inner}</section>`;
  }
  function openGuideById(id) {
    const g = guideList().find((x) => x.id === id);
    if (!g) return;
    const info = g.game && CATALOG && CATALOG.games ? CATALOG.games[g.game] : null;
    const toc = (g.sections || []).map((s, i) => `<li><a href="#g-sec-${i}" data-guide-jump="${i}">${esc(s.h)}</a></li>`).join("");
    openViewer(`
      ${info && imgUrl(info.img) && !info.fit ? `<div class="npv-hero npv-hero-wide">${img(info.img, g.title, "npv-hero-img")}</div>` : ""}
      <p class="npv-kicker">Гайд · ${esc(g.tag)} · ⏱ ${esc(g.time)} · ${esc(g.level || "")}</p>
      <h3 id="npvTitle">${esc(g.title)}</h3>
      <div class="npv-body guide-body">
        <p class="guide-lead">${esc(g.lead)}</p>
        ${toc ? `<nav class="guide-toc" aria-label="Содержание"><p>Содержание</p><ol>${toc}${g.tips ? `<li><a href="#g-tips" data-guide-jump="tips">Советы новичку</a></li>` : ""}${g.mistakes ? `<li><a href="#g-mist" data-guide-jump="mist">Частые ошибки</a></li>` : ""}</ol></nav>` : ""}
        ${(g.sections || []).map((s, i) => sectionHtml(s).replace("<section class=\"guide-sec\">", `<section class="guide-sec" id="g-sec-${i}">`)).join("")}
        ${g.tips ? `<section class="guide-sec guide-tips" id="g-tips"><h4>💡 Советы новичку</h4><ul>${g.tips.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
        ${g.mistakes ? `<section class="guide-sec guide-mistakes" id="g-mist"><h4>⚠️ Частые ошибки</h4><ul>${g.mistakes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
      </div>
      <div class="npv-actions"><button type="button" class="btn btn-primary btn-sm" data-guide-copy="${esc(g.id)}">Скопировать ссылку на гайд</button><button type="button" class="btn btn-ghost btn-sm" data-npv-close>Понятно</button></div>`, { wide: true });
  }

  /* ---------------- events ---------------- */
  function activate(e) {
    const t = e.target;
    let el;
    if ((el = t.closest("[data-news-id]"))) return openNews(el.dataset.newsId), true;
    if ((el = t.closest("[data-release]"))) return openRelease(el.dataset.release), true;
    if ((el = t.closest("[data-patch]"))) return openPatch(el.dataset.patch), true;
    if ((el = t.closest("[data-video]"))) return openVideo(el.dataset.video), true;
    if ((el = t.closest("[data-stream-channel]"))) return openStreamChannel(el.dataset.streamChannel), true;
    if ((el = t.closest("[data-np-guide]"))) return openGuideById(el.dataset.npGuide), true;
    if ((el = t.closest("[data-game-more]"))) return openGame(el.dataset.gameMore), true;
    return false;
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("a[href]") && !e.target.closest("[data-guide-jump]")) return;
    const jump = e.target.closest("[data-guide-jump]");
    if (jump) {
      e.preventDefault();
      const k = jump.dataset.guideJump;
      const target = $(k === "tips" ? "#g-tips" : k === "mist" ? "#g-mist" : "#g-sec-" + k, viewer || document);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const copy = e.target.closest("[data-guide-copy]");
    if (copy) {
      const url = location.origin + location.pathname + "#guide=" + encodeURIComponent(copy.dataset.guideCopy);
      const done = () => { copy.textContent = "Ссылка скопирована ✓"; };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, done); else done();
      return;
    }
    const cover = e.target.closest(".game-card .card-cover.has-media");
    if (cover && !e.target.closest("button")) {
      const card = cover.closest(".game-card");
      if (card) return openGame(card.dataset.id);
    }
    const wc = e.target.closest("[data-watch-channel]");
    if (wc) {
      const c = OFFICIAL_CHANNELS.find((x) => x.channel === wc.dataset.watchChannel);
      if (c) playStream(c, null, false);
      return;
    }
    if (e.target.closest("#watchPoster")) { playStream(pendingStream, null, false); return; }
    const wm = e.target.closest("[data-watch-match]");
    if (wm) {
      const m = MATCHES[Number(wm.dataset.watchMatch)];
      const streams = m ? (m.streams || []).filter((s) => embedSrc(s)) : [];
      const st = streams[Number(wm.dataset.stream) || 0];
      if (st) playStream(st, m, true);
      return;
    }
    const mf = e.target.closest("[data-mgame]");
    if (mf) {
      matchFilter = mf.dataset.mgame;
      $$("#matchFilters .chip").forEach((c) => c.classList.toggle("active", c === mf));
      renderMatches();
      return;
    }
    const vt = e.target.closest("[data-vcat]");
    if (vt) {
      videoCat = vt.dataset.vcat;
      videosShown = 12;
      $$("#videoTabs .chip").forEach((c) => c.classList.toggle("active", c === vt));
      renderVideos();
      return;
    }
    if (e.target.closest("#newsMore")) { newsShown += 12; renderNews(); return; }
    if (e.target.closest("#videosMore")) { videosShown += 12; renderVideos(); return; }
    if (e.target.closest("#releasesMore")) { releasesAll = !releasesAll; renderReleases(); return; }
    const rp = e.target.closest("[data-rplat]");
    if (rp) {
      releasePlat = rp.dataset.rplat;
      $$("#releaseFilters [data-rplat]").forEach((c) => { const on = c === rp; c.classList.toggle("active", on); c.setAttribute("aria-pressed", String(on)); });
      renderReleases();
      return;
    }
    activate(e);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const el = e.target.closest?.(".np-clickable");
    if (el && el === e.target) { e.preventDefault(); activate({ target: el }); }
  });

  /* ---------------- load ---------------- */
  function setUpdated(sel, iso) { const el = $(sel); if (el && iso) el.textContent = fmtUpdated(iso); }
  async function loadAll() {
    const jobs = {
      catalog: getJson("catalog.json").then((d) => { CATALOG = d; decorateCatalog(); renderGuides(); renderPatches(); }),
      news: getJson("news.json").then((d) => { NEWS = (d.items || []).filter((n) => n && n.id && n.title); renderNews(); setUpdated("#newsUpdated", d.updatedAt); }),
      releases: getJson("releases.json").then((d) => { RELEASES = d.items || []; renderReleases(); }),
      patches: getJson("patches.json").then((d) => { PATCHES = d.items || []; renderPatches(); }),
      newGames: getJson("new_games.json").then((d) => { NEWGAMES = d.items || []; renderNewGames(d.updatedAt); }),
      matches: getJson("matches.json").then((d) => {
        MATCHES = Array.isArray(d.matches) ? d.matches.filter((m) => m && m.teamA && m.startsAt) : [];
        TOURS = Array.isArray(d.tournaments) ? d.tournaments : [];
        renderMatches(); renderTournaments(); setUpdated("#matchesUpdated", d.updatedAt);
      }),
      videos: getJson("videos.json").then((d) => { VIDEOS = d.items || []; renderVideos(); setUpdated("#videosUpdated", d.updatedAt); }),
    };
    await Promise.all(Object.values(jobs).map((p) => p.catch(() => null)));
  }

  // deep links from Discord posts: #news=<id>, #video=<id>, #patch=<id>, #release=<appid>
  // share pages: index.html?news=<id> (also ?video= ?patch= ?release=)
  function deepLink() {
    const m = location.hash.match(/^#(news|video|patch|release)=([\w-]{1,64})$/);
    if (m) return [m[1], m[2]];
    const q = new URLSearchParams(location.search);
    for (const k of ["news", "video", "patch", "release"]) {
      const v = q.get(k);
      if (v && /^[\w-]{1,64}$/.test(v)) return [k, v];
    }
    return null;
  }
  function openFromHash() {
    const m = deepLink();
    if (!m) return;
    const [kind, id] = m;
    const sec = { news: "#news", video: "#videos", patch: "#calendar", release: "#calendar" }[kind];
    $(sec)?.scrollIntoView();
    setTimeout(() => {
      if (kind === "news") openNews(id);
      else if (kind === "video") openVideo(id);
      else if (kind === "patch") openPatch(id);
      else openRelease(id);
    }, 250);
  }

  function init() {
    renderGuides();
    const sg = $("#statGuides");
    if (sg && guideList().length) sg.textContent = guideList().length + "+";
    renderWatchChips();
    renderVideos();
    const grid = $("#gamesGrid");
    if (grid) new MutationObserver(() => decorateCatalog()).observe(grid, { childList: true });
    loadAll().then(openFromHash);
    window.addEventListener("hashchange", openFromHash);
    // статусы матчей зависят от текущего времени — пересчитываем раз в минуту
    setInterval(renderMatches, 60000);
    const m = location.hash.match(/^#guide=([\w-]+)/);
    if (m) setTimeout(() => { $("#guides")?.scrollIntoView(); openGuideById(m[1]); }, 400);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
