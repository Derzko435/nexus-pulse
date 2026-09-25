/* NEXUS PULSE — extended features (client-side) */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function waitForNexus(cb, tries) {
    if (window.NexusPulse) return cb(window.NexusPulse);
    if ((tries || 0) > 80) {
      console.warn("[NEXUS PULSE] NexusPulse bridge missing");
      return;
    }
    setTimeout(() => waitForNexus(cb, (tries || 0) + 1), 25);
  }

  /* ---------- Keys ---------- */
  const KEYS = {
    build: "nexus_pulse_pc_build",
    owned: "nexus_pulse_owned_games",
    epicOwned: "nexus_pulse_epic_owned",
    epicName: "nexus_pulse_epic_name",
    alerts: "nexus_pulse_price_alerts", // старый формат — переносится в watch
    watch: "nexus_pulse_watchlist",
    lfgSelf: "nexus_pulse_lfg_self",
    lfgPending: "nexus_pulse_lfg_pending_post",
    checklist: "nexus_pulse_checklist",
    backlog: "nexus_pulse_backlog",
    hideOwned: "nexus_pulse_hide_owned",
  };

  function lsGet(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v == null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  }
  function lsSet(key, val) {
    try {
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) {
      console.warn("[NEXUS PULSE] localStorage:", e);
    }
  }

  function toast(msg, ms) {
    let host = $("#npToasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "npToasts";
      host.className = "np-toasts";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "np-toast glass";
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.classList.add("show"), 10);
    setTimeout(() => {
      el.classList.remove("show");
      setTimeout(() => el.remove(), 300);
    }, ms || 4200);
  }

  /* ============================================================
   * 5) Game tag enrichment + catalog filters
   * ============================================================ */
  const F2P = new Set([
    "cs2", "valorant", "dota2", "lol", "rocket", "fortnite", "apex", "ow2",
    "destiny2", "poe2", "gw2", "lostark", "newworld", "throne", "warframe",
  ]);
  const SUB = new Set(["ffxiv", "wow", "eso"]);
  const P2W = new Set(["diablo4", "lostark", "throne", "newworld"]);
  const DECK_VERIFIED = new Set([
    "hollow", "hades", "celeste", "stardew", "balatro", "vampire", "outerwilds",
    "ultrakill", "hades2", "cs2", "valorant", "doom", "re4", "phasmo", "lethal",
    "rimworld", "civ6", "ets2",
  ]);
  const DECK_PLAYABLE = new Set([
    "elden", "bg3", "witcher3", "skyrim", "persona5", "gtav", "r6", "apex",
    "ow2", "halo", "xcom2", "ck3", "stellaris", "reVillage", "forza5", "dirt",
    "nfs", "snowrunner", "sekiro", "hogwarts", "gw2", "deadspace", "outlast",
  ]);
  const DECK_UNSUPPORTED = new Set([
    "cp2077", "rdr2", "wukong", "msfs", "cities", "mhwilds", "alanwake2",
    "totalwar", "spiderman2", "codmw",
  ]);
  const CROSSPLAY = new Set([
    "fortnite", "rocket", "apex", "ow2", "codmw", "destiny2", "minecraft",
    "gtav", "r6", "halo", "forza5", "f1_24", "diablo4", "mhwilds", "newworld",
    "throne", "eso", "phasmo", "outlast", "deadspace", "lethal", "stardew",
    "balatro", "vampire", "hades", "hogwarts", "acvalhalla",
  ]);
  const MULTIPLAYER_ONLY = new Set([
    "cs2", "valorant", "dota2", "lol", "rocket", "r6", "fortnite", "apex",
    "ow2", "codmw", "destiny2", "wow", "gw2", "eso", "lostark", "newworld",
    "throne", "ffxiv", "phasmo", "outlast", "lethal",
  ]);

  function enrichGames(games) {
    if (!games) return;
    games.forEach((g) => {
      if (g.monetization && g.deck != null && g.crossplay != null && g.singleplayer != null) return;
      let monetization = "buy";
      if (F2P.has(g.id)) monetization = "f2p";
      if (SUB.has(g.id)) monetization = "subscription";
      if (P2W.has(g.id)) monetization = "p2w";
      let deck = "unknown";
      if (DECK_VERIFIED.has(g.id)) deck = "verified";
      else if (DECK_PLAYABLE.has(g.id)) deck = "playable";
      else if (DECK_UNSUPPORTED.has(g.id)) deck = "unsupported";
      else if (g.genre === "инди") deck = "verified";
      else if (g.platforms && g.platforms.includes("PC") && g.demand <= 0.7) deck = "playable";
      const crossplay = CROSSPLAY.has(g.id);
      const singleplayer = !MULTIPLAYER_ONLY.has(g.id);
      Object.assign(g, {
        monetization: g.monetization || monetization,
        deck: g.deck || deck,
        crossplay: g.crossplay != null ? g.crossplay : crossplay,
        singleplayer: g.singleplayer != null ? g.singleplayer : singleplayer,
      });
    });
  }

  const extraState = {
    monetization: "all",
    deck: "all",
    crossplay: "all",
    singleplayer: "all",
    hideOwned: false,
  };

  function getOwned() {
    return new Set(lsGet(KEYS.owned, []));
  }
  function setOwned(ids) {
    lsSet(KEYS.owned, [...ids]);
  }

  function extraFilter(g) {
    if (extraState.monetization !== "all" && g.monetization !== extraState.monetization) return false;
    if (extraState.deck !== "all" && g.deck !== extraState.deck) return false;
    if (extraState.crossplay === "yes" && !g.crossplay) return false;
    if (extraState.crossplay === "no" && g.crossplay) return false;
    if (extraState.singleplayer === "yes" && !g.singleplayer) return false;
    if (extraState.singleplayer === "no" && g.singleplayer) return false;
    if (extraState.hideOwned && getOwned().has(g.id)) return false;
    return true;
  }

  function wireExtraFilters(NP) {
    const savedHide = lsGet(KEYS.hideOwned, false);
    extraState.hideOwned = !!savedHide;
    const hideChk = $("#hideOwnedChk");
    if (hideChk) hideChk.checked = extraState.hideOwned;

    $("#extraFilters")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip[data-xfilter]");
      if (!btn) return;
      const group = btn.dataset.xgroup;
      $$(`#extraFilters .chip[data-xgroup="${group}"]`).forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const val = btn.dataset.xfilter;
      if (group === "monetization") extraState.monetization = val;
      if (group === "deck") extraState.deck = val;
      if (group === "crossplay") extraState.crossplay = val;
      if (group === "singleplayer") extraState.singleplayer = val;
      NP.renderGames();
    });

    hideChk?.addEventListener("change", () => {
      extraState.hideOwned = hideChk.checked;
      lsSet(KEYS.hideOwned, extraState.hideOwned);
      NP.renderGames();
    });
  }

  function decorateGameCards(NP) {
    const owned = getOwned();
    $$("#gamesGrid .game-card").forEach((card) => {
      const id = card.dataset.id;
      const g = NP.GAMES.find((x) => x.id === id);
      if (!g) return;
      const cover = card.querySelector(".card-cover");
      const body = card.querySelector(".card-body");
      if (owned.has(id) && cover && !cover.querySelector(".owned-badge")) {
        const b = document.createElement("span");
        b.className = "owned-badge";
        b.textContent = "В библиотеке";
        cover.appendChild(b);
      }
      if (body && !body.querySelector(".tag-pills")) {
        const pills = document.createElement("div");
        pills.className = "tag-pills";
        const mono = { f2p: "F2P", buy: "Купить", subscription: "Подписка", p2w: "P2W" };
        const deck = { verified: "Deck ✓", playable: "Deck ~", unsupported: "Deck ✕", unknown: "Deck ?" };
        pills.innerHTML = `
          <span class="tag-pill">${mono[g.monetization] || g.monetization}</span>
          <span class="tag-pill">${deck[g.deck] || g.deck}</span>
          ${g.crossplay ? '<span class="tag-pill">Crossplay</span>' : ""}
          ${g.singleplayer ? '<span class="tag-pill">Solo</span>' : '<span class="tag-pill">Multi</span>'}`;
        body.appendChild(pills);
      }
      if (cover && !cover.querySelector(".alert-bell")) {
        const appid = catalogAppId(g.id);
        cover.appendChild(makeBell({ watchTitle: g.title, watchGame: g.id, steamAppId: appid }));
      }
    });
  }

  /* ============================================================
   * 6) «Отслеживаю цены» — список желаемого с целевой ценой
   * ============================================================ */
  const WATCH_NOTIFIED = "nexus_pulse_watch_notified";
  const WATCH_ASKED = "nexus_pulse_watch_notify_asked";
  const watchState = { deals: [], prices: {}, catalog: {}, pricesLoaded: false, dealsLoaded: false };

  function normTitle(s) {
    return String(s || "").toLowerCase().replace(/ё/g, "е").replace(/[™®©]/g, "").replace(/[^a-z0-9а-я]+/gi, " ").trim();
  }
  function rub(n) {
    const v = Number(n);
    return Number.isFinite(v) ? v.toLocaleString("ru-RU") + " ₽" : "—";
  }
  function escHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function watchKey(it) {
    return it.gameId ? "g:" + it.gameId : it.steamAppId ? "s:" + it.steamAppId : "t:" + normTitle(it.title);
  }

  function getWatch() {
    const list = lsGet(KEYS.watch, null);
    if (Array.isArray(list)) return list;
    // перенос старых «алертов» в новый список
    const old = lsGet(KEYS.alerts, []);
    const migrated = [];
    (Array.isArray(old) ? old : []).forEach((a) => {
      const id = String(a.dealId || "");
      const it = { title: a.gameTitle || id, added: a.created || new Date().toISOString() };
      if (id.startsWith("game-")) it.gameId = id.slice(5);
      else if (/^steam-\d+$/.test(id)) { it.dealId = id; it.steamAppId = id.slice(6); }
      if (it.title && !migrated.some((m) => watchKey(m) === watchKey(it))) migrated.push(it);
    });
    lsSet(KEYS.watch, migrated);
    try { localStorage.removeItem(KEYS.alerts); } catch { /* ignore */ }
    return migrated;
  }
  function setWatch(list) {
    lsSet(KEYS.watch, list);
  }
  function findWatch(list, probe) {
    const k = watchKey(probe);
    const t = normTitle(probe.title);
    return list.findIndex((it) =>
      watchKey(it) === k ||
      (probe.steamAppId && it.steamAppId && String(it.steamAppId) === String(probe.steamAppId)) ||
      (probe.gameId && it.gameId === probe.gameId) ||
      (t && normTitle(it.title) === t));
  }

  function catalogAppId(gameId) {
    const c = watchState.catalog[gameId];
    return c && c.appid ? String(c.appid) : "";
  }

  /** Текущая цена и скидка для игры из списка */
  function watchStatus(it) {
    const NP = window.NexusPulse;
    const g = it.gameId && NP ? NP.GAMES.find((x) => x.id === it.gameId) : null;
    const appid = String(it.steamAppId || catalogAppId(it.gameId) || "");
    const t = normTitle(it.title || (g && g.title));
    const deal = watchState.deals.find((d) =>
      (it.dealId && d.id === it.dealId) ||
      (appid && d.steamAppId && String(d.steamAppId) === appid) ||
      (t && normTitle(d.title) === t)) || null;
    const steam = it.gameId ? watchState.prices[it.gameId] : null;
    let price = null, old = null, pct = 0, store = "";
    if (deal) {
      price = Number(deal.neu ?? deal.new ?? deal.price);
      old = Number(deal.old);
      pct = Number(deal.pct) || 0;
      store = deal.store || "";
    } else if (steam && Number.isFinite(Number(steam.final))) {
      price = Number(steam.final);
      old = Number(steam.initial);
      pct = Number(steam.pct) || 0;
      store = "Steam";
    }
    if (!Number.isFinite(price)) price = null;
    if (!Number.isFinite(old) || old <= (price || 0)) old = null;
    const target = Number(it.target) > 0 ? Number(it.target) : null;
    const discounted = pct > 0 && price != null;
    const hitTarget = target != null && price != null && price <= target;
    const cat = it.gameId ? watchState.catalog[it.gameId] : null;
    const url = (deal && deal.url) || it.url || (cat && cat.url) ||
      (appid ? `https://store.steampowered.com/app/${appid}/` : `https://store.steampowered.com/search/?term=${encodeURIComponent(it.title || "")}`);
    const img = it.image || (cat && (cat.capsule || cat.img)) ||
      (appid ? `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/capsule_231x87.jpg` : "");
    return { deal, price, old, pct, store, target, discounted, hitTarget, matched: discounted || hitTarget, url, img, regular: it.regular || null };
  }

  function priceHtml(st) {
    if (st.price == null) {
      return st.regular
        ? `<span class="wl-price-none">Скидки нет · обычно ${rub(st.regular)}</span>`
        : `<span class="wl-price-none">Скидки пока нет — ждём</span>`;
    }
    return `<span class="wl-price-now">${rub(st.price)}</span>` +
      (st.old ? `<span class="wl-price-old">${rub(st.old)}</span>` : "") +
      (st.pct > 0 ? `<span class="wl-pct">−${st.pct}%</span>` : "") +
      (st.store ? `<span class="wl-store">${escHtml(st.store)}</span>` : "");
  }
  function badgeHtml(st) {
    if (st.hitTarget) return `<span class="wl-flag wl-flag-hit">🎯 Цена достигнута</span>`;
    if (st.discounted) return `<span class="wl-flag">🔥 Скидка сейчас</span>`;
    if (st.target && st.price != null) return `<span class="wl-flag wl-flag-wait">ещё ${rub(st.price - st.target)} до цели</span>`;
    return "";
  }

  function paintRow(li, it) {
    const st = watchStatus(it);
    li.classList.toggle("is-match", st.matched);
    li.classList.toggle("is-hit", st.hitTarget);
    const p = li.querySelector(".wl-price");
    if (p) p.innerHTML = priceHtml(st);
    const f = li.querySelector(".wl-flag-slot");
    if (f) f.innerHTML = badgeHtml(st);
    return st;
  }

  function updateWatchCounters() {
    const list = getWatch();
    const matched = list.filter((it) => watchStatus(it).matched).length;
    $$("[data-watch-count]").forEach((el) => {
      el.textContent = String(matched);
      el.hidden = matched === 0;
      el.title = matched ? `Выгодных цен в твоём списке: ${matched}` : "";
    });
    const c = $("#wlCount");
    if (c) {
      c.hidden = !list.length;
      c.textContent = matched ? `${matched} из ${list.length} по выгодной цене` : `${list.length}`;
      c.classList.toggle("has-match", matched > 0);
    }
  }

  function renderWatchlist() {
    const ul = $("#wlList");
    const empty = $("#wlEmpty");
    if (!ul) return;
    const list = getWatch();
    if (empty) empty.hidden = list.length > 0;
    // выгодные — наверх
    const rows = list.map((it) => ({ it, st: watchStatus(it) }))
      .sort((a, b) => (Number(b.st.matched) - Number(a.st.matched)));
    ul.innerHTML = rows.map(({ it, st }) => {
      const k = watchKey(it);
      const initials = escHtml(String(it.title || "?").trim().slice(0, 2).toUpperCase());
      return `
      <li class="wl-row" data-key="${escHtml(k)}">
        <a class="wl-cover" href="${escHtml(st.url)}" target="_blank" rel="noopener noreferrer" tabindex="-1" aria-hidden="true">
          <span class="wl-initials">${initials}</span>
          ${st.img ? `<img src="${escHtml(st.img)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
        </a>
        <div class="wl-main">
          <a class="wl-title" href="${escHtml(st.url)}" target="_blank" rel="noopener noreferrer">${escHtml(it.title)}</a>
          <div class="wl-price"></div>
          <div class="wl-flag-slot"></div>
        </div>
        <label class="wl-target">
          <span>Хочу за</span>
          <span class="wl-target-box"><input type="number" inputmode="numeric" min="0" step="1" placeholder="—" value="${it.target ? Number(it.target) : ""}" aria-label="Желаемая цена для ${escHtml(it.title)}"><i>₽</i></span>
        </label>
        <div class="wl-btns">
          <a class="btn btn-ghost btn-sm wl-store-btn" href="${escHtml(st.url)}" target="_blank" rel="noopener noreferrer">В магазин</a>
          <button type="button" class="wl-remove" aria-label="Убрать ${escHtml(it.title)} из списка" title="Убрать из списка">✕</button>
        </div>
      </li>`;
    }).join("");
    $$(".wl-row", ul).forEach((li) => {
      const it = list.find((x) => watchKey(x) === li.dataset.key);
      if (it) paintRow(li, it);
    });
    updateWatchCounters();
    syncBells();
    syncNotifyBtn();
  }

  function syncBells() {
    const list = getWatch();
    $$(".alert-bell").forEach((b) => {
      const on = findWatch(list, {
        title: b.dataset.watchTitle, gameId: b.dataset.watchGame, steamAppId: b.dataset.steamAppId,
      }) >= 0;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
      b.title = on ? "Убрать из «Отслеживаю цены»" : "Следить за ценой";
    });
  }

  function markNotified(it) {
    const st = watchStatus(it);
    const n = lsGet(WATCH_NOTIFIED, {});
    if (st.matched) n[watchKey(it)] = `${st.price}|${st.pct}|${st.target || ""}`;
    else delete n[watchKey(it)];
    lsSet(WATCH_NOTIFIED, n);
  }

  function toggleWatch(probe) {
    const list = getWatch();
    const idx = findWatch(list, probe);
    if (idx >= 0) {
      const [removed] = list.splice(idx, 1);
      setWatch(list);
      const n = lsGet(WATCH_NOTIFIED, {});
      delete n[watchKey(removed)];
      lsSet(WATCH_NOTIFIED, n);
      toast("Убрано из «Отслеживаю цены»: " + (removed.title || ""));
      renderWatchlist();
      return false;
    }
    const it = { title: probe.title, added: new Date().toISOString() };
    if (probe.gameId) it.gameId = probe.gameId;
    if (probe.steamAppId) it.steamAppId = String(probe.steamAppId);
    if (probe.dealId) it.dealId = probe.dealId;
    if (probe.image) it.image = probe.image;
    if (probe.url) it.url = probe.url;
    if (Number(probe.regular) > 0) it.regular = Number(probe.regular);
    list.push(it);
    setWatch(list);
    markNotified(it); // уже идущую скидку не дублируем уведомлением
    toast("🔔 Добавлено в «Отслеживаю цены»: " + it.title);
    renderWatchlist();
    // один раз предлагаем включить уведомления — сразу после осознанного действия
    if (typeof Notification !== "undefined" && Notification.permission === "default" && !localStorage.getItem(WATCH_ASKED)) {
      try { localStorage.setItem(WATCH_ASKED, "1"); } catch { /* ignore */ }
      Notification.requestPermission().then(syncNotifyBtn).catch(() => {});
    }
    return true;
  }

  function wireAlertClicks() {
    document.addEventListener("click", (e) => {
      const bell = e.target.closest(".alert-bell");
      if (!bell) return;
      e.preventDefault();
      e.stopPropagation();
      toggleWatch({
        title: bell.dataset.watchTitle,
        gameId: bell.dataset.watchGame,
        dealId: bell.dataset.watchDeal,
        steamAppId: bell.dataset.steamAppId,
        image: bell.dataset.watchImage,
        url: bell.dataset.watchUrl,
        regular: bell.dataset.watchRegular,
      });
    });
  }

  function makeBell(data) {
    const bell = document.createElement("button");
    bell.type = "button";
    bell.className = "alert-bell";
    Object.entries(data).forEach(([k, v]) => { if (v != null && v !== "") bell.dataset[k] = String(v); });
    bell.setAttribute("aria-label", "Следить за ценой: " + (data.watchTitle || ""));
    bell.textContent = "🔔";
    return bell;
  }

  function decorateDealCards() {
    let list = [];
    try {
      list = JSON.parse($("#dealsGrid")?.dataset.deals || "[]");
    } catch {
      list = [];
    }
    $$("#dealsGrid .deal-card").forEach((card, i) => {
      const d = list[i];
      if (!d) return;
      const cover = card.querySelector(".card-cover");
      if (!cover || cover.querySelector(".alert-bell")) return;
      if (d.steamAppId) card.dataset.steamAppId = d.steamAppId;
      if (d.image) card.dataset.dealImage = d.image;
      const appid = d.steamAppId || (String(d.id || "").match(/(\d{3,})/) || [])[1] || "";
      cover.appendChild(makeBell({
        watchTitle: d.title,
        watchDeal: d.id,
        steamAppId: appid,
        watchImage: d.image || (appid ? `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/capsule_231x87.jpg` : ""),
        watchUrl: d.url || "",
        watchRegular: d.old || "",
      }));
    });
    syncBells();
  }

  /* ---- уведомления ---- */
  function syncNotifyBtn() {
    const btn = $("#wlNotifyBtn");
    if (!btn) return;
    const supported = typeof Notification !== "undefined";
    btn.hidden = !supported || Notification.permission === "granted" || !getWatch().length;
  }

  async function showNotice(title, body) {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const opts = { body, icon: "assets/icons/icon-192.png", badge: "assets/icons/icon-192.png", tag: "np-watch-" + normTitle(title).slice(0, 40) };
    try {
      const reg = navigator.serviceWorker && (await navigator.serviceWorker.getRegistration());
      if (reg && reg.showNotification) return void reg.showNotification(title, opts);
    } catch { /* fall through */ }
    try { new Notification(title, opts); } catch { /* ignore */ }
  }

  /** Сообщаем один раз о каждом новом совпадении (скидка или целевая цена) */
  function notifyWatchMatches() {
    if (!watchState.dealsLoaded) return;
    const list = getWatch();
    if (!list.length) return;
    const n = lsGet(WATCH_NOTIFIED, {});
    const fresh = [];
    list.forEach((it) => {
      const st = watchStatus(it);
      const k = watchKey(it);
      if (!st.matched) {
        delete n[k]; // скидка закончилась — о следующей снова сообщим
        return;
      }
      const sig = `${st.price}|${st.pct}|${st.target || ""}`;
      if (n[k] === sig) return;
      n[k] = sig;
      fresh.push({ it, st });
    });
    lsSet(WATCH_NOTIFIED, n);
    fresh.slice(0, 4).forEach(({ it, st }) => {
      const what = st.hitTarget ? `цена ${rub(st.price)} — как ты хотел` : `скидка −${st.pct}%, сейчас ${rub(st.price)}`;
      toast(`🔔 ${it.title}: ${what}`, 7000);
      showNotice(`🔔 ${it.title}`, `${st.hitTarget ? "Цена достигнута" : "Скидка"}: ${rub(st.price)}${st.pct ? ` (−${st.pct}%)` : ""}${st.store ? " · " + st.store : ""}`);
    });
  }

  function refreshWatch() {
    renderWatchlist();
    notifyWatchMatches();
  }

  function setWatchDeals(payload) {
    const deals = (payload && payload.deals) || [];
    watchState.deals = Array.isArray(deals) ? deals : [];
    watchState.dealsLoaded = true;
    // запоминаем обычную цену, чтобы показать её, когда скидка закончится
    const list = getWatch();
    let changed = false;
    list.forEach((it) => {
      const st = watchStatus(it);
      if (st.deal && Number(st.deal.old) > 0 && it.regular !== Number(st.deal.old)) { it.regular = Number(st.deal.old); changed = true; }
    });
    if (changed) setWatch(list);
    refreshWatch();
  }

  async function loadWatchSources() {
    const get = (f) => fetch("./data/" + f, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    const [prices, catalog] = await Promise.all([get("prices.json"), get("catalog.json")]);
    watchState.prices = (prices && prices.prices) || {};
    watchState.pricesLoaded = !!prices;
    watchState.catalog = (catalog && catalog.games) || {};
    refreshWatch();
  }

  function wireWatchlist() {
    try { localStorage.removeItem("nexus_pulse_discord_webhook"); } catch { /* ignore */ }
    const ul = $("#wlList");
    ul?.addEventListener("click", (e) => {
      const rm = e.target.closest(".wl-remove");
      if (!rm) return;
      const li = rm.closest(".wl-row");
      const list = getWatch();
      const it = list.find((x) => watchKey(x) === li?.dataset.key);
      if (it) toggleWatch({ title: it.title, gameId: it.gameId, steamAppId: it.steamAppId, dealId: it.dealId });
    });
    ul?.addEventListener("input", (e) => {
      const inp = e.target.closest(".wl-target input");
      if (!inp) return;
      const li = inp.closest(".wl-row");
      const list = getWatch();
      const it = list.find((x) => watchKey(x) === li?.dataset.key);
      if (!it) return;
      const v = Math.round(Number(inp.value));
      if (v > 0) it.target = v; else delete it.target;
      setWatch(list);
      paintRow(li, it);
      updateWatchCounters();
    });
    ul?.addEventListener("change", (e) => {
      if (e.target.closest(".wl-target input")) notifyWatchMatches();
    });
    $("#wlNotifyBtn")?.addEventListener("click", async () => {
      if (typeof Notification === "undefined") {
        toast("Этот браузер не умеет показывать уведомления");
        return;
      }
      if (Notification.permission === "denied") {
        toast("Уведомления запрещены в настройках браузера — разреши их для этого сайта (значок 🔒 слева от адреса)", 7000);
        return;
      }
      const p = await Notification.requestPermission();
      if (p === "granted") {
        toast("Готово! Сообщим, когда цена упадёт");
        showNotice("NEXUS PULSE", "Уведомления о скидках включены 🔔");
      } else {
        toast("Уведомления не включены");
      }
      syncNotifyBtn();
    });
    renderWatchlist();
    loadWatchSources();
    // данные о скидках обновляются в течение дня — проверяем раз в 30 минут, пока вкладка открыта
    setInterval(async () => {
      try {
        const res = await fetch("./data/deals.json", { cache: "no-store" });
        if (res.ok) setWatchDeals(await res.json());
      } catch { /* offline */ }
      loadWatchSources();
    }, 30 * 60 * 1000);
  }

  /* ============================================================
   * 1) PC build calculator
   * ============================================================ */
  const PARTS = {
    cpu: [
      { id: "r5_5500", name: "Ryzen 5 5500", tier: 1, score: 58 },
      { id: "i5_12400f", name: "Intel i5-12400F", tier: 2, score: 72 },
      { id: "r5_7600", name: "Ryzen 5 7600", tier: 3, score: 86 },
      { id: "i7_14700k", name: "Intel i7-14700K", tier: 4, score: 96 },
      { id: "r9_7950x", name: "Ryzen 9 7950X", tier: 5, score: 100 },
    ],
    gpu: [
      { id: "gtx1650", name: "GTX 1650", tier: 1, score: 35, fpsKey: "budget" },
      { id: "rtx3060", name: "RTX 3060 12GB", tier: 2, score: 58, fpsKey: "mid" },
      { id: "rtx4060", name: "RTX 4060", tier: 3, score: 70, fpsKey: "mid" },
      { id: "rtx4070", name: "RTX 4070", tier: 4, score: 88, fpsKey: "high" },
      { id: "rtx4080", name: "RTX 4080 / 7900 XT", tier: 5, score: 100, fpsKey: "ultra" },
    ],
    ram: [
      { id: "8", name: "8 GB", gb: 8, score: 40 },
      { id: "16", name: "16 GB", gb: 16, score: 75 },
      { id: "32", name: "32 GB", gb: 32, score: 95 },
      { id: "64", name: "64 GB", gb: 64, score: 100 },
    ],
    storage: [
      { id: "hdd", name: "HDD 1 TB", score: 40, ssd: false },
      { id: "ssd_512", name: "SSD 512 GB", score: 70, ssd: true },
      { id: "ssd_1t", name: "NVMe 1 TB", score: 90, ssd: true },
      { id: "ssd_2t", name: "NVMe 2 TB", score: 100, ssd: true },
    ],
  };

  // Heuristic parse of SPECS GPU/CPU strings → tier 1..5
  function parseGpuTier(str) {
    const s = (str || "").toLowerCase();
    if (/4090|4080|7900|3080|3090|6800\s*xt|7800/.test(s)) return 5;
    if (/4070|3070|3080|6700|6800|2080|2070/.test(s)) return 4;
    if (/4060|3060|1660|2060|5700|6600|rx\s*580|1060\s*6/.test(s)) return 3;
    if (/1050|1650|550|560|970|980|470|480|r9\s*280|770|780/.test(s)) return 2;
    if (/hd\s*3000|720|intel hd|gt\s*7/.test(s)) return 1;
    return 3;
  }
  function parseCpuTier(str) {
    const s = (str || "").toLowerCase();
    if (/i9|ryzen\s*9|14700|13700|7950|7900/.test(s)) return 5;
    if (/i7|ryzen\s*7|7600|12700|8700|3600x/.test(s)) return 4;
    if (/i5|ryzen\s*5|12400|5600|3600|8400|3300/.test(s)) return 3;
    if (/i3|ryzen\s*3|fx-83|4690|3570|2500/.test(s)) return 2;
    return 2;
  }
  function parseRamGb(str) {
    const m = String(str || "").match(/(\d+)\s*gb/i);
    return m ? Number(m[1]) : 8;
  }

  function scoreBuild(build) {
    const cpu = PARTS.cpu.find((p) => p.id === build.cpu);
    const gpu = PARTS.gpu.find((p) => p.id === build.gpu);
    const ram = PARTS.ram.find((p) => p.id === build.ram);
    const storage = PARTS.storage.find((p) => p.id === build.storage);
    if (!cpu || !gpu || !ram || !storage) return 0;
    return Math.round(cpu.score * 0.28 + gpu.score * 0.48 + ram.score * 0.14 + storage.score * 0.1);
  }

  function compatForGame(NP, game, build) {
    const cpu = PARTS.cpu.find((p) => p.id === build.cpu);
    const gpu = PARTS.gpu.find((p) => p.id === build.gpu);
    const ram = PARTS.ram.find((p) => p.id === build.ram);
    const storage = PARTS.storage.find((p) => p.id === build.storage);
    if (!cpu || !gpu || !ram) return { status: "no", label: "Не потянет", fps: 0 };

    const spec = NP.SPECS[game.id];
    let status = "ok";
    if (spec) {
      const minGpu = parseGpuTier((spec.min || []).find((x) => /^GPU/i.test(x)));
      const recGpu = parseGpuTier((spec.rec || []).find((x) => /^GPU/i.test(x)));
      const minCpu = parseCpuTier((spec.min || []).find((x) => /^CPU/i.test(x)));
      const recCpu = parseCpuTier((spec.rec || []).find((x) => /^CPU/i.test(x)));
      const minRam = parseRamGb((spec.min || []).find((x) => /^RAM/i.test(x)));
      const recRam = parseRamGb((spec.rec || []).find((x) => /^RAM/i.test(x)));
      const gpuOkRec = gpu.tier >= recGpu && cpu.tier >= recCpu && ram.gb >= recRam;
      const gpuOkMin = gpu.tier >= minGpu && cpu.tier >= minCpu && ram.gb >= minRam;
      if (gpuOkRec) status = "ok";
      else if (gpuOkMin) status = "min";
      else status = "no";
    } else {
      // heuristic from demand
      const need = game.demand || 1;
      const power = (gpu.score / 100) * 0.7 + (cpu.score / 100) * 0.2 + (ram.score / 100) * 0.1;
      if (power >= need * 0.85) status = "ok";
      else if (power >= need * 0.55) status = "min";
      else status = "no";
    }

    const fpsKey = gpu.fpsKey || "mid";
    const cpuKey = cpu.tier >= 4 ? "high" : cpu.tier >= 3 ? "mid" : "budget";
    const fps = NP.estimateFps(game.id, fpsKey, cpuKey);
    const power = (gpu.score / 100) * 0.7 + (cpu.score / 100) * 0.2 + (ram.score / 100) * 0.1;
    const need = game.demand || 1;
    let badge = "Потянет";
    let badgeClass = "compat-badge-ok";
    if (status === "ok") {
      if (power >= need * 1.15 || (gpu.tier >= 4 && fps >= 90)) {
        badge = "На ультрах";
        badgeClass = "compat-badge-ultra";
      } else if (power >= need * 0.95 || fps >= 70) {
        badge = "Потянет на высоких";
        badgeClass = "compat-badge-high";
      } else {
        badge = "Потянет";
        badgeClass = "compat-badge-ok";
      }
    } else if (status === "min") {
      badge = "Впритык";
      badgeClass = "compat-badge-tight";
    } else {
      badge = "Слабо";
      badgeClass = "compat-badge-weak";
    }
    const labels = { ok: "Потянет", min: "На минимуме", no: "Не потянет" };
    return { status, label: labels[status], fps, badge, badgeClass, power };
  }

  function fillPartSelects() {
    const map = [
      ["#pcCpu", PARTS.cpu],
      ["#pcGpu", PARTS.gpu],
      ["#pcRam", PARTS.ram],
      ["#pcStorage", PARTS.storage],
    ];
    map.forEach(([sel, list]) => {
      const el = $(sel);
      if (!el) return;
      el.innerHTML = list.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
    });
    const saved = lsGet(KEYS.build, null);
    if (saved) {
      if ($("#pcCpu") && saved.cpu) $("#pcCpu").value = saved.cpu;
      if ($("#pcGpu") && saved.gpu) $("#pcGpu").value = saved.gpu;
      if ($("#pcRam") && saved.ram) $("#pcRam").value = saved.ram;
      if ($("#pcStorage") && saved.storage) $("#pcStorage").value = saved.storage;
      if ($("#pcRes") && saved.res) $("#pcRes").value = saved.res;
    } else {
      if ($("#pcCpu")) $("#pcCpu").value = "r5_7600";
      if ($("#pcGpu")) $("#pcGpu").value = "rtx4060";
      if ($("#pcRam")) $("#pcRam").value = "16";
      if ($("#pcStorage")) $("#pcStorage").value = "ssd_1t";
    }
  }

  function getFocusGameId() {
    try { return sessionStorage.getItem("nexus_pulse_focus_game") || ""; } catch { return ""; }
  }
  function setFocusGameId(id) {
    try {
      if (id) sessionStorage.setItem("nexus_pulse_focus_game", id);
      else sessionStorage.removeItem("nexus_pulse_focus_game");
    } catch { /* ignore */ }
  }
  function neededGpuTierForGame(NP, game) {
    const spec = NP.SPECS && NP.SPECS[game.id];
    if (spec) {
      const rec = parseGpuTier((spec.rec || []).find((x) => /^GPU/i.test(x)));
      const min = parseGpuTier((spec.min || []).find((x) => /^GPU/i.test(x)));
      return Math.max(rec || 0, min || 0, 1);
    }
    const need = game.demand || 1;
    if (need >= 0.95) return 5;
    if (need >= 0.8) return 4;
    if (need >= 0.6) return 3;
    if (need >= 0.4) return 2;
    return 1;
  }
  function suggestNextGpu(currentId, needTier) {
    const sorted = PARTS.gpu.slice().sort((a, b) => a.tier - b.tier);
    const cur = PARTS.gpu.find((p) => p.id === currentId);
    const curTier = cur ? cur.tier : 0;
    if (curTier >= needTier) return null;
    return sorted.find((p) => p.tier > curTier) || sorted.find((p) => p.tier >= needTier) || null;
  }

  function renderBuildCompat(NP, opts) {
    opts = opts || {};
    const build = {
      cpu: $("#pcCpu")?.value,
      gpu: $("#pcGpu")?.value,
      ram: $("#pcRam")?.value,
      storage: $("#pcStorage")?.value,
    };
    const score = scoreBuild(build);
    const scoreEl = $("#pcBuildScore");
    if (scoreEl) scoreEl.textContent = String(score);

    const results = NP.GAMES.map((g) => {
      const c = compatForGame(NP, g, build);
      return { game: g, ...c };
    });
    const groups = {
      ok: results.filter((r) => r.status === "ok"),
      min: results.filter((r) => r.status === "min"),
      no: results.filter((r) => r.status === "no"),
    };
    const host = $("#pcCompatList");
    if (!host) return;

    const shared = readSharedBuild();
    const fromShare =
      !!opts.fromShare ||
      !!(shared &&
        (!shared.cpu || shared.cpu === build.cpu) &&
        (!shared.gpu || shared.gpu === build.gpu) &&
        (!shared.ram || shared.ram === build.ram));
    const focusId = opts.focusGame || getFocusGameId();
    const focusGame = focusId ? NP.GAMES.find((g) => g.id === focusId) : null;

    let tipHtml = "";
    if (focusGame) {
      const needTier = neededGpuTierForGame(NP, focusGame);
      const next = suggestNextGpu(build.gpu, needTier);
      const curGpu = PARTS.gpu.find((p) => p.id === build.gpu);
      if (next && (!curGpu || curGpu.tier < needTier)) {
        tipHtml = `<p class="upgrade-gpu-tip">Для <strong>${focusGame.title}</strong>: попробуй GPU уровнем выше → <button type="button" class="linkish" data-set-gpu="${next.id}">${next.name}</button></p>`;
      } else if (focusGame) {
        tipHtml = `<p class="upgrade-gpu-tip">Фокус: <strong>${focusGame.title}</strong> — смотри строку в списках ниже.</p>`;
      }
    }

    const banner = fromShare
      ? `<div class="share-friend-banner" id="shareFriendBanner">Сборка по ссылке · вот что потянет этот ПК · скор <strong>${score}</strong>/100</div>`
      : "";

    const block = (title, arr, cls) => `
      <div class="compat-group ${cls}">
        <h4>${title} <small>(${arr.length})</small></h4>
        <ul>${arr
          .slice(0, 40)
          .map((r) => {
            const hi = focusId && r.game.id === focusId ? " compat-row-focus" : "";
            return `<li class="${hi.trim()}" data-compat-game="${r.game.id}">
            <button type="button" class="linkish" data-prefill-fps="${r.game.id}" data-fps-gpu="${PARTS.gpu.find((p) => p.id === build.gpu)?.fpsKey || "mid"}">${r.game.title}</button>
            <span class="compat-fps">~${r.fps} FPS</span>
          </li>`;
          })
          .join("")}${arr.length > 40 ? `<li class="muted">…и ещё ${arr.length - 40}</li>` : ""}</ul>
      </div>`;
    host.innerHTML =
      banner +
      tipHtml +
      block("Потянет", groups.ok, "compat-ok") +
      block("На минимуме", groups.min, "compat-min") +
      block("Не потянет", groups.no, "compat-no");

    if (opts.focusGame) {
      try {
        host.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } catch { /* ignore */ }
    }
  }

  /* ---------- Share build via GET params ---------- */
  const RES_VALUES = ["1080", "1440", "2160"];
  // Build loaded from a friend's link: used for catalog badges without overwriting the user's saved build
  let shareBuildOverride = null;

  function currentBuild() {
    return {
      cpu: $("#pcCpu")?.value || "",
      gpu: $("#pcGpu")?.value || "",
      ram: $("#pcRam")?.value || "",
      storage: $("#pcStorage")?.value || "",
      res: $("#pcRes")?.value || "",
    };
  }

  function buildShareUrl(build) {
    const b = build || currentBuild();
    const q = new URLSearchParams();
    if (b.cpu) q.set("cpu", b.cpu);
    if (b.gpu) q.set("gpu", b.gpu);
    if (b.ram) q.set("ram", b.ram);
    if (b.res) q.set("res", b.res);
    q.set("share", "1");
    const base = (location.origin + location.pathname.replace(/index\.html$/i, "")).replace(/\/?$/, "/");
    return base + "?" + q.toString() + "#tools";
  }

  function readSharedBuild() {
    const params = new URLSearchParams(location.search);
    const pick = (list, v) => (v && list.some((p) => p.id === v) ? v : "");
    const shared = {
      cpu: pick(PARTS.cpu, params.get("cpu")),
      gpu: pick(PARTS.gpu, params.get("gpu")),
      ram: pick(PARTS.ram, params.get("ram")),
      res: RES_VALUES.includes(params.get("res") || "") ? params.get("res") : "",
    };
    return shared.cpu || shared.gpu || shared.ram ? shared : null;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(() => true, () => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  }
  function legacyCopy(text) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return !!ok;
    } catch {
      return false;
    }
  }

  function isMobileDevice() {
    return (
      (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) ||
      /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "")
    );
  }

  async function shareBuild() {
    const b = currentBuild();
    const url = buildShareUrl(b);
    const cpuP = PARTS.cpu.find((p) => p.id === b.cpu);
    const gpuP = PARTS.gpu.find((p) => p.id === b.gpu);
    const ramP = PARTS.ram.find((p) => p.id === b.ram);
    const score = scoreBuild(b);
    const text = `Моя сборка: ${[cpuP?.name, gpuP?.name, ramP?.name].filter(Boolean).join(" · ")} — скор ${score}/100. Смотри, что она потянет:`;
    if (typeof navigator.share === "function" && isMobileDevice()) {
      try {
        await navigator.share({ title: "NEXUS PULSE · сборка ПК", text, url });
        return;
      } catch (e) {
        if (e && e.name === "AbortError") return; // user closed the share sheet
      }
    }
    const ok = await copyText(url);
    if (ok) toast("Ссылка на сборку скопирована — кинь её другу");
    else window.prompt("Скопируй ссылку на сборку:", url);
  }

  function wirePcBuilder(NP) {
    fillPartSelects();
    const run = () => renderBuildCompat(NP);
    ["#pcCpu", "#pcGpu", "#pcRam", "#pcStorage"].forEach((sel) => {
      $(sel)?.addEventListener("change", run);
    });
    $("#pcBuildSave")?.addEventListener("click", () => {
      const build = {
        cpu: $("#pcCpu")?.value,
        gpu: $("#pcGpu")?.value,
        ram: $("#pcRam")?.value,
        storage: $("#pcStorage")?.value,
        res: $("#pcRes")?.value || undefined,
        savedAt: new Date().toISOString(),
      };
      lsSet(KEYS.build, build);
      shareBuildOverride = null;
      toast("Сборка сохранена");
      if (window.NexusPulse) injectCompatBadges(window.NexusPulse);
    });
    $("#pcBuildShare")?.addEventListener("click", () => shareBuild());
    $("#pcCompatList")?.addEventListener("click", (e) => {
      const setGpu = e.target.closest("[data-set-gpu]");
      if (!setGpu) return;
      if ($("#pcGpu")) $("#pcGpu").value = setGpu.dataset.setGpu;
      renderBuildCompat(NP, { focusGame: getFocusGameId() });
      toast("GPU обновлён: " + (PARTS.gpu.find((p) => p.id === setGpu.dataset.setGpu)?.name || setGpu.dataset.setGpu));
    });
    $("#pcBuildCalc")?.addEventListener("click", run);
    $("#pcCompatList")?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-prefill-fps]");
      if (!btn) return;
      const id = btn.dataset.prefillFps;
      const fpsGame = $("#fpsGame");
      const fpsGpu = $("#fpsGpu");
      const fpsCpu = $("#fpsCpu");
      if (fpsGame) fpsGame.value = id;
      if (fpsGpu && btn.dataset.fpsGpu) fpsGpu.value = btn.dataset.fpsGpu;
      const cpu = PARTS.cpu.find((p) => p.id === $("#pcCpu")?.value);
      if (fpsCpu && cpu) {
        fpsCpu.value = cpu.tier >= 4 ? "high" : cpu.tier >= 3 ? "mid" : "budget";
      }
      $("#fpsCalcBtn")?.click();
      document.getElementById("tools")?.scrollIntoView({ behavior: "smooth", block: "start" });
      toast("FPS-калькулятор заполнен: " + (NP.GAMES.find((g) => g.id === id)?.title || id));
    });
    run();
  }

  /* ============================================================
   * 2) Nickname + avatar generator
   * ============================================================ */
const NICK_BANKS = {
    cyberpunk: {
      pre: ["Neo","Chrome","Null","Volt","Glitch","Cyber","Nova","Hex","Pulse","Zero","Neon","Byte","Circuit","Phantom","Static","Vapor","Pixel","Shadow","Drift","Blade","Synth","Grid","Echo","Razor"],
      mid: ["","byte","wire","net","core","hack","shade","drift","flux","node"],
      suf: ["Runner","Fox","Ghost","Kat","Ronin","Punk","Protocol","X","404","Wave","Shift","Link","Ops","Core","Spark","Noir","Edge","Prime","Unit","Wire"],
    },
    fantasy: {
      pre: ["Ash","Storm","Moon","Iron","Shadow","Ember","Frost","Thorn","Silver","Dawn","Rune","Wolf","Drake","Oak","Crystal","Night","Sky","Flame","Stone","Mist","Arcane","Wild","Bright","Hollow"],
      mid: ["","blade","song","born","heart","bane","walker","forge","wind"],
      suf: ["Warden","Mage","Knight","Seer","Drake","Rune","Vale","IX","Sage","Blade","Guard","Born","Fang","Spark","Crest","Keeper","Vow","Hunt","Shade","Forge"],
    },
    shooter: {
      pre: ["Aim","Frag","Clutch","Rush","Snap","Ace","Tilt","Ping","Smoke","Flash","Bolt","Scope","Blitz","Strike","Recoil","Trigger","Peak","Swift","Silent","Rapid","Sharp","Blast","Zero","Viper"],
      mid: ["","shot","peek","strafe","flick","tap","spray"],
      suf: ["God","King","One","Ops","TTV","Pro","HQ","Aim","Star","Shot","Lock","Fire","Drop","Zone","Elite","Ace","Rush","Peek","Snap","Line"],
    },
    cozy: {
      pre: ["Soft","Tea","Sunny","Berry","Cloud","Pebble","Mochi","Maple","Cozy","Honey","Cocoa","Daisy","Warm","Gentle","Peach","Mint","Cotton","Bloom","Lazy","Sugar","Amber","Olive","Cream","Petal"],
      mid: ["","bloom","nest","glow","leaf","brew","soft"],
      suf: ["Cat","Fox","Bean","Farm","Tea","Bun","Star","Paws","Nest","Glow","Joy","Hug","Kit","Bloom","Dove","Moss","Pine","Dawn","Sip","Home"],
    },
    space: {
      pre: ["Orion","Nova","Astro","Lunar","Cosmo","Quark","Solar","Nebula","Orbit","Ion","Stellar","Comet","Pulsar","Zenith","Aether","Void","Galaxy","Meteor","Photon","Helio","Aurora","Titan","Orbit","Sigma"],
      mid: ["","star","void","warp","pulse","ray","orbit"],
      suf: ["Pilot","Drifter","X","Prime","One","Station","42","Craft","Wing","Trail","Nova","Core","Jump","Path","Light","Scan","Dock","Flux","Arc","Sky"],
    },
    pro: {
      pre: ["Ace","Clutch","Prime","Elite","Rapid","Clean","Sharp","Focus","True","Swift","Peak","Solid","Crisp","Hyper","Meta","Rank","Ladder","Final","Crown","Pulse","Nova","Storm","Blitz","Viper"],
      mid: ["","shot","play","aim","frag","combo"],
      suf: ["Aim","Play","Star","One","Pro","GG","Ops","Line","Form","Mode","Core","Edge","Rise","Lock","Flow","Spark","Zone","Wave","Shot","Ace"],
    },
  };

  const OFFENSIVE = /\b(nazi|hitler|rape|slave|killall|suicide|nigg|fag|retard|pedo|sex|porn|slut|whore|kys)\b/i;

  function seedRng(str) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return () => {
      h ^= h << 13; h >>>= 0;
      h ^= h >>> 17; h >>>= 0;
      h ^= h << 5; h >>>= 0;
      return (h >>> 0) / 4294967296;
    };
  }

  function leetSwap(s, rnd) {
    const map = { e: "3", a: "4", i: "1", o: "0", E: "3", A: "4", I: "1", O: "0" };
    let out = "";
    let swapped = 0;
    for (const ch of s) {
      if (map[ch] && rnd() < 0.45 && swapped < 2) {
        out += map[ch];
        swapped++;
      } else out += ch;
    }
    return out;
  }

  function genNick(style) {
    const b = NICK_BANKS[style] || NICK_BANKS.cyberpunk;
    const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
    const midRaw = pick(b.mid);
    const mid = midRaw ? midRaw.charAt(0).toUpperCase() + midRaw.slice(1) : "";
    let base = pick(b.pre) + mid + pick(b.suf);
    // trim if too long before pattern wrap
    if (base.length > 14) base = pick(b.pre) + pick(b.suf);

    const patterns = [
      () => base,
      () => "xX" + base.slice(0, 12) + "Xx",
      () => base.slice(0, 12) + "_TTV",
      () => base.slice(0, 14) + "GG",
      () => "i" + base.slice(0, 15),
      () => "The" + base.slice(0, 13),
      () => base.slice(0, 14) + "TV",
      () => (pick(b.pre) + "." + pick(b.suf)).toLowerCase().slice(0, 18),
      () => base.slice(0, 15) + "z",
      () => leetSwap(base.slice(0, 16), Math.random),
      () => base.slice(0, 14) + String(7 + Math.floor(Math.random() * 20)).padStart(2, "0"), // 07–26
      () => base.slice(0, 12) + "_" + String(10 + Math.floor(Math.random() * 90)),
    ];
    // weighted toward readable plain / TTV / year / The / i
    const weights = [22, 6, 10, 8, 8, 8, 6, 7, 5, 8, 10, 6];
    let r = Math.random() * weights.reduce((a, c) => a + c, 0);
    let idx = 0;
    for (let i = 0; i < weights.length; i++) {
      r -= weights[i];
      if (r <= 0) { idx = i; break; }
    }
    let nick = patterns[idx]();
    // rare global leet (~15%) if not already leet pattern
    if (idx !== 9 && Math.random() < 0.15) nick = leetSwap(nick, Math.random);
    nick = nick.replace(/[^a-zA-Z0-9._]/g, "").slice(0, 20);
    if (!nick || OFFENSIVE.test(nick)) nick = pick(b.pre) + pick(b.suf);
    return nick.slice(0, 20);
  }

  function drawAvatar(canvas, nick, style) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const w = canvas.width;
    const h = canvas.height;
    const rnd = seedRng(String(nick || "NP") + "|" + String(style || "cyberpunk"));
    const palettes = {
      cyberpunk: ["#050d1a", "#00f5ff", "#ff2bd6", "#7c3aed", "#0ea5e9"],
      fantasy: ["#12081c", "#8b5cff", "#ffc857", "#c084fc", "#f472b6"],
      shooter: ["#0a120c", "#3dff9a", "#ff4d6d", "#22c55e", "#fbbf24"],
      cozy: ["#15120c", "#ffc857", "#86efac", "#fdba74", "#f9a8d4"],
      space: ["#050510", "#00f5ff", "#8b5cff", "#38bdf8", "#a78bfa"],
      pro: ["#0b0f14", "#f59e0b", "#e2e8f0", "#38bdf8", "#22c55e"],
    };
    const pal = palettes[style] || palettes.cyberpunk;
    const [bg, c1, c2, c3, c4] = pal;
    const templates = ["radial", "stripes", "lowpoly", "circuit", "starfield", "hex", "vignette", "blobs"];
    const tmpl = templates[Math.floor(rnd() * templates.length)];

    // base fill
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    function glowCircle(x, y, r, color, a) {
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, color);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.globalAlpha = a;
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      ctx.globalAlpha = 1;
    }

    if (tmpl === "radial") {
      glowCircle(w * 0.35, h * 0.35, w * 0.7, c1, 0.55);
      glowCircle(w * 0.75, h * 0.7, w * 0.55, c2, 0.45);
      glowCircle(w * 0.5, h * 0.5, w * 0.4, c3, 0.25);
    } else if (tmpl === "stripes") {
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, bg);
      g.addColorStop(0.5, c1);
      g.addColorStop(1, c2);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.rotate(-0.55);
      for (let i = -6; i < 8; i++) {
        ctx.fillStyle = i % 2 ? c3 : c4;
        ctx.globalAlpha = 0.22;
        ctx.fillRect(-w, i * 28 - 10, w * 2, 14);
      }
      ctx.restore();
      ctx.globalAlpha = 1;
    } else if (tmpl === "lowpoly") {
      for (let i = 0; i < 14; i++) {
        const cols = [c1, c2, c3, c4];
        ctx.beginPath();
        const x0 = rnd() * w, y0 = rnd() * h;
        ctx.moveTo(x0, y0);
        ctx.lineTo(rnd() * w, rnd() * h);
        ctx.lineTo(rnd() * w, rnd() * h);
        ctx.closePath();
        ctx.fillStyle = cols[i % cols.length];
        ctx.globalAlpha = 0.18 + rnd() * 0.25;
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      glowCircle(w / 2, h / 2, w * 0.45, c1, 0.3);
    } else if (tmpl === "circuit") {
      glowCircle(w * 0.2, h * 0.2, w * 0.5, c1, 0.35);
      ctx.strokeStyle = c1;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.55;
      for (let i = 0; i < 10; i++) {
        let x = rnd() * w, y = rnd() * h;
        ctx.beginPath();
        ctx.moveTo(x, y);
        for (let s = 0; s < 4; s++) {
          if (rnd() > 0.5) x += (rnd() - 0.3) * 80;
          else y += (rnd() - 0.3) * 80;
          ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = c2;
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    } else if (tmpl === "starfield") {
      glowCircle(w * 0.6, h * 0.4, w * 0.6, c3, 0.4);
      for (let i = 0; i < 80; i++) {
        const x = rnd() * w, y = rnd() * h, r = rnd() * 1.8 + 0.3;
        ctx.fillStyle = rnd() > 0.7 ? c1 : "#fff";
        ctx.globalAlpha = 0.35 + rnd() * 0.6;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    } else if (tmpl === "hex") {
      glowCircle(w / 2, h / 2, w * 0.55, c1, 0.35);
      const size = 18 + rnd() * 8;
      ctx.strokeStyle = c1;
      ctx.lineWidth = 1.2;
      for (let row = -1; row < h / (size * 1.5) + 1; row++) {
        for (let col = -1; col < w / (size * 1.75) + 1; col++) {
          const cx = col * size * 1.75 + (row % 2 ? size * 0.875 : 0);
          const cy = row * size * 1.5;
          ctx.globalAlpha = 0.15 + ((col + row) % 5) * 0.05;
          ctx.beginPath();
          for (let k = 0; k < 6; k++) {
            const a = (Math.PI / 3) * k + Math.PI / 6;
            const px = cx + size * Math.cos(a);
            const py = cy + size * Math.sin(a);
            if (k === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.closePath();
          ctx.stroke();
          if ((col + row) % 4 === 0) {
            ctx.fillStyle = c2;
            ctx.globalAlpha = 0.12;
            ctx.fill();
          }
        }
      }
      ctx.globalAlpha = 1;
    } else if (tmpl === "vignette") {
      const g = ctx.createRadialGradient(w / 2, h / 2, w * 0.15, w / 2, h / 2, w * 0.72);
      g.addColorStop(0, c1);
      g.addColorStop(0.45, c3);
      g.addColorStop(1, bg);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = c2;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, w * 0.42, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    } else {
      // soft blob mesh
      for (let i = 0; i < 8; i++) {
        glowCircle(rnd() * w, rnd() * h, 40 + rnd() * 70, [c1, c2, c3, c4][i % 4], 0.35);
      }
    }

    // grain
    const img = ctx.getImageData(0, 0, w, h);
    const data = img.data;
    for (let i = 0; i < data.length; i += 4) {
      const n = (rnd() - 0.5) * 18;
      data[i] = Math.max(0, Math.min(255, data[i] + n));
      data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + n));
      data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + n));
    }
    ctx.putImageData(img, 0, 0);

    // small avatars (LFG) get bigger initials and no corner emblem so they stay readable at 48–56px
    const compact = canvas.classList.contains("lfg-avatar");
    const k = w / 256;

    // emblem (geometric)
    if (!compact) drawEmblem(ctx, w, h, style, c1, c2, rnd);

    // soft glow behind initials
    glowCircle(w / 2, h / 2, (compact ? 120 : 58) * k, c1, 0.35);
    ctx.fillStyle = compact ? "rgba(0,0,0,.45)" : "rgba(0,0,0,.4)";
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, (compact ? 96 : 48) * k, 0, Math.PI * 2);
    ctx.fill();

    const initials = (nick || "NP")
      .replace(/[^a-zA-Zа-яА-Я0-9]/g, "")
      .slice(0, 2)
      .toUpperCase() || "NP";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `bold ${Math.round((compact ? 92 : 44) * k)}px Orbitron, Manrope, sans-serif`;
    ctx.letterSpacing = "0.08em";
    ctx.shadowColor = "rgba(0,0,0,.65)";
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    ctx.fillStyle = "#fff";
    // slight letter spacing via two chars
    const dx = (compact ? 30 : 14) * k;
    if (initials.length === 2) {
      ctx.fillText(initials[0], w / 2 - dx, h / 2 + 2 * k);
      ctx.fillText(initials[1], w / 2 + dx, h / 2 + 2 * k);
    } else {
      ctx.fillText(initials, w / 2, h / 2 + 2 * k);
    }
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
  }

  function drawEmblem(ctx, w, h, style, c1, c2, rnd) {
    ctx.save();
    ctx.translate(w * 0.78, h * 0.22);
    const s = 22;
    ctx.globalAlpha = 0.85;
    ctx.strokeStyle = c1;
    ctx.fillStyle = c2;
    ctx.lineWidth = 2;
    const kind = style || "cyberpunk";
    if (kind === "cyberpunk") {
      // hexagon
      ctx.beginPath();
      for (let k = 0; k < 6; k++) {
        const a = (Math.PI / 3) * k + Math.PI / 6;
        const px = s * Math.cos(a), py = s * Math.sin(a);
        if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.globalAlpha = 0.25; ctx.fill();
      ctx.globalAlpha = 0.9; ctx.stroke();
    } else if (kind === "fantasy") {
      // sword
      ctx.beginPath();
      ctx.moveTo(0, -s); ctx.lineTo(4, -s + 8); ctx.lineTo(4, 8); ctx.lineTo(-4, 8); ctx.lineTo(-4, -s + 8);
      ctx.closePath();
      ctx.globalAlpha = 0.35; ctx.fill();
      ctx.globalAlpha = 0.95; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-10, 6); ctx.lineTo(10, 6); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, 8); ctx.lineTo(0, 16); ctx.stroke();
    } else if (kind === "shooter") {
      // crosshair
      ctx.beginPath(); ctx.arc(0, 0, s * 0.7, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-s, 0); ctx.lineTo(-4, 0); ctx.moveTo(4, 0); ctx.lineTo(s, 0);
      ctx.moveTo(0, -s); ctx.lineTo(0, -4); ctx.moveTo(0, 4); ctx.lineTo(0, s); ctx.stroke();
    } else if (kind === "cozy") {
      // leaf
      ctx.beginPath();
      ctx.moveTo(0, -s);
      ctx.quadraticCurveTo(s, 0, 0, s);
      ctx.quadraticCurveTo(-s, 0, 0, -s);
      ctx.closePath();
      ctx.globalAlpha = 0.3; ctx.fill();
      ctx.globalAlpha = 0.95; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, -s + 4); ctx.lineTo(0, s - 4); ctx.stroke();
    } else if (kind === "space") {
      // planet + ring
      ctx.beginPath(); ctx.arc(0, 0, s * 0.55, 0, Math.PI * 2);
      ctx.globalAlpha = 0.3; ctx.fill();
      ctx.globalAlpha = 0.95; ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(0, 0, s, s * 0.35, -0.4, 0, Math.PI * 2);
      ctx.stroke();
    } else {
      // trophy / cup (pro)
      ctx.beginPath();
      ctx.moveTo(-10, -12); ctx.lineTo(10, -12); ctx.lineTo(8, 4); ctx.quadraticCurveTo(0, 12, -8, 4);
      ctx.closePath();
      ctx.globalAlpha = 0.35; ctx.fill();
      ctx.globalAlpha = 0.95; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, 10); ctx.lineTo(0, 16); ctx.moveTo(-8, 16); ctx.lineTo(8, 16); ctx.stroke();
      ctx.beginPath(); ctx.arc(-12, -6, 5, -1.2, 1.2); ctx.stroke();
      ctx.beginPath(); ctx.arc(12, -6, 5, Math.PI - 1.2, Math.PI + 1.2); ctx.stroke();
    }
    ctx.restore();
  }

  function wireNickGen() {
    let style = "cyberpunk";
    $("#nickStyleChips")?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-nick-style]");
      if (!btn) return;
      $$("#nickStyleChips .chip").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      style = btn.dataset.nickStyle;
    });
    const out = $("#nickOutput");
    const canvas = $("#nickAvatar");
    $("#nickGenBtn")?.addEventListener("click", () => {
      const nick = genNick(style);
      if (out) out.textContent = nick;
      drawAvatar(canvas, nick, style);
    });
    $("#nickCopyBtn")?.addEventListener("click", () => {
      const n = out?.textContent || "";
      if (!n || n === "—") return toast("Сначала сгенерируй ник");
      navigator.clipboard?.writeText(n).then(() => toast("Ник скопирован"), () => toast("Не удалось скопировать"));
    });
    $("#nickDlBtn")?.addEventListener("click", () => {
      if (!canvas) return;
      const a = document.createElement("a");
      a.download = "nexus-pulse-avatar.png";
      a.href = canvas.toDataURL("image/png");
      a.click();
    });
    // initial
    const nick = genNick(style);
    if (out) out.textContent = nick;
    drawAvatar(canvas, nick, style);
  }

  /* ============================================================
   * 3) Ping map
   * ============================================================ */
  const PING_TARGETS_FALLBACK = [
    { id: "cloudflare", name: "Cloudflare", url: "https://www.cloudflare.com/favicon.ico", kind: "img" },
    { id: "steam", name: "Steam CDN", url: "https://cdn.cloudflare.steamstatic.com/steam/apps/730/header.jpg", kind: "img" },
    { id: "riot", name: "Riot", url: "https://authenticate.riotgames.com/favicon.ico", kind: "img" },
    { id: "epic", name: "Epic", url: "https://static-assets-prod.unrealengine.com/account-portal/static/favicon.ico", kind: "img" },
    { id: "blizzard", name: "Blizzard", url: "https://www.blizzard.com/favicon.ico", kind: "img" },
    { id: "google", name: "Google (ref)", url: "https://www.google.com/favicon.ico", kind: "img" },
  ];
  let PING_TARGETS = PING_TARGETS_FALLBACK.slice();
  let steamCatalogSnapshot = null;

  function pingColor(ms) {
    if (ms == null || !Number.isFinite(ms)) return "ping-err";
    if (ms < 50) return "ping-ok";
    if (ms < 100) return "ping-mid";
    return "ping-bad";
  }

  function measureImg(url) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      const img = new Image();
      const done = (ok) => resolve(ok ? performance.now() - t0 : null);
      img.onload = () => done(true);
      img.onerror = () => done(true); // opaque / blocked still may fire; treat as timed
      img.src = url + (url.includes("?") ? "&" : "?") + "_np=" + Date.now() + Math.random();
      setTimeout(() => done(false), 4000);
    });
  }

  async function measureFetch(url) {
    const t0 = performance.now();
    try {
      await fetch(url + (url.includes("?") ? "&" : "?") + "_np=" + Date.now(), {
        cache: "no-store",
        mode: "cors",
      });
      return performance.now() - t0;
    } catch {
      try {
        await fetch(url, { cache: "no-store", mode: "no-cors" });
        return performance.now() - t0;
      } catch {
        return null;
      }
    }
  }

  async function runPingMap() {
    const list = $("#pingMapList");
    if (!list) return;
    list.innerHTML = PING_TARGETS.map(
      (t) => `<li data-ping="${t.id}"><span class="ping-name">${t.name}</span>
        <span class="ping-bar"><i style="width:10%"></i></span>
        <span class="ping-ms">…</span></li>`
    ).join("");
    for (const t of PING_TARGETS) {
      let samples = [];
      for (let i = 0; i < 3; i++) {
        const ms = t.kind === "fetch" ? await measureFetch(t.url) : await measureImg(t.url);
        if (ms != null) samples.push(ms);
      }
      let ms = samples.length
        ? samples.sort((a, b) => a - b)[Math.floor(samples.length / 2)]
        : null;
      // fallback: last Cloudflare speed latency
      if (ms == null && t.id === "cloudflare" && window.NexusPulse?.lastLatency != null) {
        ms = window.NexusPulse.lastLatency;
      }
      const li = list.querySelector(`[data-ping="${t.id}"]`);
      if (!li) continue;
      const msEl = li.querySelector(".ping-ms");
      const bar = li.querySelector(".ping-bar i");
      const cls = pingColor(ms);
      li.className = cls;
      if (msEl) msEl.textContent = ms != null ? Math.round(ms) + " ms" : "ошибка";
      if (bar && ms != null) {
        const pct = Math.max(8, Math.min(100, 100 - ms / 2));
        bar.style.width = pct + "%";
      }
    }
  }

  async function loadPingTargets() {
    try {
      const res = await fetch("./data/ping_targets.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (Array.isArray(data.targets) && data.targets.length) {
        PING_TARGETS = data.targets.map((t) => ({
          id: t.id,
          name: t.name,
          url: t.url,
          kind: t.kind || "img",
        }));
      }
    } catch (e) {
      console.warn("[ping_targets]", e);
      PING_TARGETS = PING_TARGETS_FALLBACK.slice();
    }
  }

  async function loadSteamCatalogSnapshot() {
    try {
      const res = await fetch("./data/steam_catalog_snapshot.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      steamCatalogSnapshot = await res.json();
    } catch (e) {
      console.warn("[steam_catalog]", e);
      steamCatalogSnapshot = null;
    }
  }

  function wirePingMap() {
    $("#pingRefreshBtn")?.addEventListener("click", () => {
      runPingMap();
    });
    loadPingTargets().then(() => setTimeout(runPingMap, 200));
  }

  /* ============================================================
   * 4) Steam / Epic library
   * ============================================================ */
  function normalizeTitle(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[^a-z0-9а-яё]+/gi, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function matchCatalogGames(NP, titles) {
    const owned = new Set();
    const norms = titles.map(normalizeTitle).filter(Boolean);
    NP.GAMES.forEach((g) => {
      const gt = normalizeTitle(g.title);
      if (norms.some((t) => t.includes(gt) || gt.includes(t) || t.split(" ")[0] === gt.split(" ")[0])) {
        owned.add(g.id);
      }
    });
    return owned;
  }

  const STEAM_PROXY_FALLBACK = "https://api.allorigins.win/raw?url=";

  async function fetchTextDirectThenProxy(url) {
    try {
      const res = await fetch(url, { cache: "no-store", mode: "cors" });
      if (res.ok) return await res.text();
    } catch { /* CORS / network — try single fallback proxy */ }
    const proxied = STEAM_PROXY_FALLBACK + encodeURIComponent(url);
    const res2 = await fetch(proxied, { cache: "no-store" });
    if (!res2.ok) throw new Error("HTTP " + res2.status + " (direct+proxy)");
    return await res2.text();
  }

  async function resolveVanity(vanity) {
    const url = `https://steamcommunity.com/id/${encodeURIComponent(vanity)}/?xml=1`;
    const text = await fetchTextDirectThenProxy(url);
    const m = text.match(/<steamID64>(\d+)<\/steamID64>/i);
    if (!m) throw new Error("steamID64 not found");
    return m[1];
  }

  async function fetchSteamGamesXml(steamid64) {
    const url = `https://steamcommunity.com/profiles/${steamid64}/games?tab=all&xml=1`;
    const text = await fetchTextDirectThenProxy(url);
    if (/privacy|Private|не доступен|This profile is private/i.test(text) && !/<game>/i.test(text)) {
      throw new Error("Профиль или список игр закрыт");
    }
    const names = [...text.matchAll(/<name><!\[CDATA\[(.*?)\]\]><\/name>/g)].map((m) => m[1]);
    if (!names.length) {
      const alt = [...text.matchAll(/<name>([^<]+)<\/name>/g)].map((m) => m[1]);
      return alt;
    }
    return names;
  }

  function renderOwnedChecklist(NP) {
    const host = $("#steamManualList");
    if (!host) return;
    const owned = getOwned();
    const q = ($("#steamManualSearch")?.value || "").toLowerCase();
    host.innerHTML = NP.GAMES.filter((g) => !q || g.title.toLowerCase().includes(q))
      .map(
        (g) => `<label class="owned-check"><input type="checkbox" data-own-id="${g.id}" ${owned.has(g.id) ? "checked" : ""}/> ${g.title}</label>`
      )
      .join("");
  }

  function wireSteamImport(NP) {
    renderOwnedChecklist(NP);
    $("#steamManualSearch")?.addEventListener("input", () => renderOwnedChecklist(NP));
    $("#steamManualList")?.addEventListener("change", (e) => {
      const inp = e.target.closest("[data-own-id]");
      if (!inp) return;
      const set = getOwned();
      if (inp.checked) set.add(inp.dataset.ownId);
      else set.delete(inp.dataset.ownId);
      setOwned(set);
      NP.renderGames();
      toast("Библиотека обновлена (" + set.size + ")");
    });

    $("#steamImportBtn")?.addEventListener("click", async () => {
      const raw = ($("#steamIdInput")?.value || "").trim();
      const status = $("#steamImportStatus");
      if (!raw) {
        if (status) status.textContent = "Введи SteamID64 или vanity.";
        return;
      }
      if (status) status.textContent = "Загружаем библиотеку Steam…";
      try {
        let id = raw;
        if (!/^\d{15,20}$/.test(raw)) {
          if (raw.includes("steamcommunity.com/id/")) {
            id = raw.split("/id/")[1].split(/[/?#]/)[0];
            id = await resolveVanity(id);
          } else if (raw.includes("steamcommunity.com/profiles/")) {
            id = raw.split("/profiles/")[1].split(/[/?#]/)[0];
          } else {
            id = await resolveVanity(raw);
          }
        }
        const titles = await fetchSteamGamesXml(id);
        const matched = matchCatalogGames(NP, titles);
        const prev = getOwned();
        matched.forEach((x) => prev.add(x));
        setOwned(prev);
        renderOwnedChecklist(NP);
        NP.renderGames();
        if (status)
          status.textContent = `Steam: найдено ${titles.length} игр, из них в каталоге: ${matched.size}.`;
        toast("Импорт Steam: +" + matched.size + " из каталога");
      } catch (err) {
        console.warn(err);
        if (status)
          status.textContent =
            "Не удалось загрузить библиотеку. Проверь, что профиль Steam открыт, или отметь игры вручную ниже.";
        toast("Импорт Steam не удался — отметь игры вручную");
      }
    });

    $("#epicNameSave")?.addEventListener("click", () => {
      const n = ($("#epicNameInput")?.value || "").trim();
      lsSet(KEYS.epicName, n);
      toast(n ? "Ник Epic сохранён" : "Ник Epic удалён");
    });
    const en = lsGet(KEYS.epicName, "");
    if ($("#epicNameInput") && en) $("#epicNameInput").value = en;
  }

  /* ============================================================
   * 7) Freebies calendar
   * ============================================================ */
  const FREEBIES_FALLBACK = {
    updatedAt: "2026-09-24T21:00:00+03:00",
    items: [
      {
        id: "fb1",
        store: "Epic Games",
        title: "Control Ultimate Edition",
        until: "2026-10-02",
        claimUrl: "https://store.epicgames.com/ru/free-games",
      },
    ],
  };

  function formatStampRu(iso) {
    const d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return "—";
    return d.toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  }
  function formatDayRu(iso) {
    const d = iso ? new Date(iso + (String(iso).length === 10 ? "T12:00:00" : "")) : null;
    if (!d || isNaN(d)) return iso || "";
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  }

  function renderFreebies(payload) {
    const grid = $("#freebiesGrid");
    const updated = $("#freebiesUpdated");
    if (updated) updated.textContent = "Обновлено: " + formatStampRu(payload.updatedAt);
    if (!grid) return;
    const items = payload.items || [];
    grid.innerHTML = items
      .map((it) => {
        const forever = it.until && it.until.startsWith("2099");
        return `<article class="freebie-card glass">
          <div class="freebie-store">${it.store || ""}</div>
          <h3>${it.title}</h3>
          <p class="freebie-until">${forever ? "Бесплатно всегда" : "До " + formatDayRu(it.until)}</p>
          ${it.note ? `<p class="freebie-note">${it.note}</p>` : ""}
          <a class="btn btn-primary btn-sm" href="${it.claimUrl}" target="_blank" rel="noopener">Забрать</a>
        </article>`;
      })
      .join("");
  }

  async function loadFreebies() {
    try {
      const res = await fetch("./data/freebies.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      renderFreebies(await res.json());
    } catch (e) {
      console.warn("[freebies]", e);
      renderFreebies(FREEBIES_FALLBACK);
    }
  }

  /* ============================================================
   * 8) LFG mini-tinder
   * ============================================================ */
  function lfgStyleForGame(game) {
    const g = String(game || "").toLowerCase();
    if (/cs2|valorant|apex|cod|r6|overwatch|ow2/.test(g)) return "shooter";
    if (/dota|lol|wow|ffxiv|eso|destiny/.test(g)) return "fantasy";
    return "cyberpunk";
  }

  function escHtml(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function readLfgNick() {
    const input = $("#lfgNick");
    const v = (input?.value || "").trim();
    if (v) return v.slice(0, 20);
    const nickEl = $("#nickOutput");
    if (nickEl && nickEl.textContent && nickEl.textContent !== "—") return nickEl.textContent.trim();
    return "Player";
  }

  /** Current (possibly unsaved) values of the LFG form. */
  function readLfgForm() {
    return {
      game: $("#lfgGame")?.value || "CS2",
      rank: $("#lfgRank")?.value || "",
      prime: $("#lfgPrime")?.value || "",
      mic: !!$("#lfgMic")?.checked,
      note: $("#lfgNote")?.value || "",
      nick: ($("#lfgNick")?.value || "").trim().slice(0, 20),
    };
  }

  function lfgFormDiffersFromSaved(form, saved) {
    if (!saved) return true;
    return ["game", "rank", "prime", "note", "nick"].some((k) => (form[k] || "") !== (saved[k] || "")) || !!form.mic !== !!saved.mic;
  }

  /** Draws the avatar preview next to the nick field (same nick + style as the feed card). */
  function refreshLfgNickAvatar(nick, game) {
    const canvas = $("#lfgNickAvatar");
    if (!canvas) return;
    canvas.hidden = false;
    const n = (nick || "").trim();
    canvas.classList.toggle("is-empty", !n);
    drawAvatar(canvas, n || "NP", lfgStyleForGame(game || $("#lfgGame")?.value));
    canvas.setAttribute("aria-label", n ? "Аватар " + n : "Аватар карточки");
  }

  let _lfgLiveCache = null;
  let _lfgLiveLoading = false;

  async function fetchLfgSnapshot() {
    if (_lfgLiveLoading) return _lfgLiveCache;
    _lfgLiveLoading = true;
    try {
      const res = await fetch("./data/lfg_snapshot.json?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      _lfgLiveCache = await res.json();
    } catch (e) {
      console.warn("[lfg snapshot]", e);
      if (!_lfgLiveCache) _lfgLiveCache = { items: [] };
    } finally {
      _lfgLiveLoading = false;
    }
    return _lfgLiveCache;
  }

  function renderLfgCards(liveItems) {
    const saved = lsGet(KEYS.lfgSelf, null);
    const form = readLfgForm();
    const feed = $("#lfgFeed");
    if (!feed) return;
    const rankInfo = computeNexusRank();
    const hint = $("#lfgSelfRankHint");
    if (hint) {
      hint.textContent = saved ? ("· ранг: " + rankInfo.label) : "";
    }
    const live = Array.isArray(liveItems) ? liveItems : [];
    const cards = [];
    // Self card = live preview of the form (falls back to saved card)
    const selfNick = form.nick || (saved && saved.nick) || "";
    if (selfNick || saved) {
      const base = form.nick ? form : Object.assign({}, saved || {}, { game: form.game });
      cards.push(
        Object.assign({}, base, {
          nick: selfNick || "Ты",
          _self: true,
          _draft: lfgFormDiffersFromSaved(form, saved),
          _rankLabel: saved ? rankInfo.label : "",
        })
      );
    }
    live.forEach((it) => {
      cards.push({
        nick: it.nick || "Игрок",
        game: it.game || "—",
        rank: it.rank || "",
        prime: it.prime || "",
        mic: !!it.mic,
        note: it.note || it.content || "",
        _live: true,
        url: it.url || "",
      });
    });
    const emptyHtml = live.length
      ? ""
      : `<p class="empty-state small lfg-empty">${cards.length ? "Пока здесь только ты — нажми «Написать в Discord», чтобы тебя увидели." : "В ленте пока пусто — заполни карточку и нажми «Написать в Discord»."}</p>`;
    feed.innerHTML =
      cards
        .map((c, i) => {
          const selfTag = c._self
            ? `<span class="lfg-rank-inline">Твоя карточка${c._draft ? " · не сохранена" : ""}${c._rankLabel ? " · ранг: " + escHtml(c._rankLabel) : ""}</span>`
            : "";
          return `<article class="lfg-card glass ${c._self ? "lfg-self" : ""} ${c._live ? "lfg-live" : ""}"${c._self ? ' id="lfgSelfCard"' : ""}>
        <div class="lfg-top">
          <canvas class="lfg-avatar" width="256" height="256" data-lfg-av="${i}" aria-hidden="true"></canvas>
          <div class="lfg-top-text"><strong class="lfg-card-nick">${escHtml(c.nick || "Игрок")}</strong> · ${escHtml(c.game || "—")}
            ${c._live ? '<span class="lfg-discord-pill" title="Из Discord">Discord</span>' : ""}
            ${selfTag}
          </div>
        </div>
        <div class="lfg-meta">Ранг: ${escHtml(c.rank || "—")} · Прайм: ${escHtml(c.prime || "—")} · Мик: ${c.mic ? "да" : "нет"}</div>
        ${c.note ? `<p>${escHtml(c.note)}</p>` : ""}
      </article>`;
        })
        .join("") + emptyHtml;
    $$("#lfgFeed .lfg-avatar").forEach((canvas) => {
      const i = Number(canvas.dataset.lfgAv);
      const c = cards[i];
      if (!c) return;
      drawAvatar(canvas, c.nick || "Player", lfgStyleForGame(c.game));
    });
  }

  function renderLfg() {
    renderLfgCards((_lfgLiveCache && _lfgLiveCache.items) || []);
    fetchLfgSnapshot().then((snap) => {
      renderLfgCards((snap && snap.items) || []);
    });
  }

  /** Live preview: avatar next to the nick + self card in the feed, without saving. */
  function updateLfgPreview() {
    const form = readLfgForm();
    const saved = lsGet(KEYS.lfgSelf, null);
    refreshLfgNickAvatar(form.nick || (saved && saved.nick) || "", form.game);
    renderLfgCards((_lfgLiveCache && _lfgLiveCache.items) || []);
  }

  function wireLfg() {
    const self = lsGet(KEYS.lfgSelf, null);
    if (self) {
      if ($("#lfgGame")) $("#lfgGame").value = self.game || "CS2";
      if ($("#lfgRank")) $("#lfgRank").value = self.rank || "";
      if ($("#lfgPrime")) $("#lfgPrime").value = self.prime || "";
      if ($("#lfgMic")) $("#lfgMic").checked = !!self.mic;
      if ($("#lfgNote")) $("#lfgNote").value = self.note || "";
      if ($("#lfgNick") && self.nick) $("#lfgNick").value = self.nick;
    }
    refreshLfgNickAvatar((self && self.nick) || "", (self && self.game) || $("#lfgGame")?.value);
    renderLfg();
    // redraw once web fonts are ready so initials use Orbitron in both preview and feed
    try { document.fonts?.ready.then(() => updateLfgPreview()); } catch { /* ignore */ }
    $("#lfgNickDice")?.addEventListener("click", () => {
      const style = lfgStyleForGame($("#lfgGame")?.value);
      const nick = genNick(style);
      if ($("#lfgNick")) $("#lfgNick").value = nick;
      updateLfgPreview();
    });
    ["#lfgNick", "#lfgRank", "#lfgPrime", "#lfgNote"].forEach((sel) => {
      $(sel)?.addEventListener("input", updateLfgPreview);
    });
    ["#lfgGame", "#lfgMic"].forEach((sel) => {
      $(sel)?.addEventListener("change", updateLfgPreview);
    });
    $("#lfgSaveBtn")?.addEventListener("click", () => {
      const card = Object.assign(readLfgForm(), { nick: readLfgNick(), ts: Date.now() });
      if ($("#lfgNick")) $("#lfgNick").value = card.nick;
      lsSet(KEYS.lfgSelf, card);
      lsSet(KEYS.lfgPending, card);
      refreshLfgNickAvatar(card.nick, card.game);
      renderLfg();
      updateNexusRankUI();
      toast("Карточка сохранена");
    });
    $("#lfgDiscordBtn")?.addEventListener("click", () => {
      const card = Object.assign(readLfgForm(), { nick: readLfgNick(), ts: Date.now() });
      if ($("#lfgNick")) $("#lfgNick").value = card.nick;
      lsSet(KEYS.lfgSelf, card);
      lsSet(KEYS.lfgPending, card);
      const text = `LFG · ${card.nick} · ${card.game} · ${card.rank || "?"} · ${card.prime || "?"} · mic:${card.mic ? "yes" : "no"}\n${card.note || ""}\n#поиск-тимы`;
      copyText(text).then((ok) =>
        toast(ok ? "Текст скопирован — вставь его в #поиск-тимы" : "Открываю #поиск-тимы")
      );
      refreshLfgNickAvatar(card.nick, card.game);
      renderLfg();
      updateNexusRankUI();
      const deep = "https://discord.com/channels/1552735502266794204/1552736838555402431";
      window.open(deep, "_blank", "noopener,noreferrer");
    });
  }

  /* ============================================================
   * NEXUS profile ranks (fun)
   * ============================================================ */
  function computeNexusRank() {
    const doneSet = new Set(lsGet(KEYS.checklist, []));
    const checklistPct = CHECKLIST_ITEMS.length
      ? Math.round((doneSet.size / CHECKLIST_ITEMS.length) * 100)
      : 0;
    const backlog = lsGet(KEYS.backlog, []);
    const backlogDonePct = backlog.length
      ? Math.round((backlog.filter((r) => r.status === "done").length / backlog.length) * 100)
      : 0;
    const score = Math.round(0.6 * checklistPct + 0.4 * backlogDonePct);
    let label;
    if (score >= 100) label = "NEXUS GOD 👑";
    else if (score >= 70) label = "Имба-сессионщик 🔥";
    else if (score >= 30) label = "Трайхард-киберкотлет ⚡";
    else if (score >= 1) label = "Уверенный подпивас 🍺";
    else label = "Tilt-пропердол 🧼";
    return { score, checklistPct, backlogDonePct, label };
  }

  function updateNexusRankUI() {
    const info = computeNexusRank();
    const badge = $("#nexusRankBadge");
    if (badge) {
      badge.textContent = info.label;
      badge.title = `Ранг NEXUS · score ${info.score} (чеклист ${info.checklistPct}% · бэклог done ${info.backlogDonePct}%)`;
    }
    const hint = $("#lfgSelfRankHint");
    if (hint && lsGet(KEYS.lfgSelf, null)) {
      hint.textContent = "· ранг: " + info.label;
    }
  }

  /* ============================================================
   * 9) Checklists + backlog
   * ============================================================ */
  const CHECKLIST_ITEMS = [
    { id: "c1", text: "Обновить GPU-драйверы (Clean Install)" },
    { id: "c2", text: "Включить XMP/EXPO для RAM в BIOS" },
    { id: "c3", text: "Кабель Ethernet вместо Wi‑Fi для ранкида" },
    { id: "c4", text: "Отключить ускорение мыши в Windows" },
    { id: "c5", text: "Game Mode + Hardware GPU Scheduling" },
    { id: "c6", text: "Лимит FPS = Hz монитора (+1) через RTSS/драйвер" },
    { id: "c7", text: "Закрыть лишний Chrome / оверлеи" },
    { id: "c8", text: "Настроить Discord: push-to-talk, без оверлея" },
    { id: "c9", text: "Сейвы / облако: проверить Steam Cloud" },
    { id: "c10", text: "Анти-тилт правило: стоп после −2 ранга" },
  ];

  function renderChecklist() {
    const done = new Set(lsGet(KEYS.checklist, []));
    const host = $("#beginnerChecklist");
    if (!host) return;
    host.innerHTML = CHECKLIST_ITEMS.map(
      (it) => `<label class="check-row"><input type="checkbox" data-check="${it.id}" ${done.has(it.id) ? "checked" : ""}/> <span>${it.text}</span></label>`
    ).join("");
    const pct = Math.round((done.size / CHECKLIST_ITEMS.length) * 100);
    const p = $("#checklistProgress");
    if (p) p.textContent = pct + "%";
    updateNexusRankUI();
  }

  function wireChecklist() {
    renderChecklist();
    $("#beginnerChecklist")?.addEventListener("change", (e) => {
      const inp = e.target.closest("[data-check]");
      if (!inp) return;
      const set = new Set(lsGet(KEYS.checklist, []));
      if (inp.checked) set.add(inp.dataset.check);
      else set.delete(inp.dataset.check);
      lsSet(KEYS.checklist, [...set]);
      renderChecklist();
    });
  }

  function getBacklog() {
    return lsGet(KEYS.backlog, []);
  }
  function setBacklog(list) {
    lsSet(KEYS.backlog, list);
  }

  function renderBacklog(NP) {
    const host = $("#backlogList");
    const sel = $("#backlogGameSelect");
    if (sel && !sel.dataset.filled) {
      sel.innerHTML = NP.GAMES.map((g) => `<option value="${g.id}">${g.title}</option>`).join("");
      sel.dataset.filled = "1";
    }
    if (!host) return;
    const list = getBacklog();
    if (!list.length) {
      host.innerHTML = '<p class="empty-state small">Пока пусто — добавь игру из каталога.</p>';
      return;
    }
    const statusLabel = { backlog: "Бэклог", playing: "Играю", done: "Пройдено", dropped: "Дроп" };
    host.innerHTML = list
      .map((row) => {
        const g = NP.GAMES.find((x) => x.id === row.id);
        return `<div class="backlog-row glass" data-bl="${row.id}">
          <strong>${g ? g.title : row.id}</strong>
          <select data-bl-status>
            ${["backlog", "playing", "done", "dropped"]
              .map((s) => `<option value="${s}" ${row.status === s ? "selected" : ""}>${statusLabel[s]}</option>`)
              .join("")}
          </select>
          <label class="bl-prog">Прогресс <input type="range" min="0" max="100" value="${row.progress || 0}" data-bl-prog/> <span>${row.progress || 0}%</span></label>
          <button type="button" class="btn btn-ghost btn-sm" data-bl-del>✕</button>
        </div>`;
      })
      .join("");
    updateNexusRankUI();
  }

  function wireBacklog(NP) {
    renderBacklog(NP);
    $("#backlogAddBtn")?.addEventListener("click", () => {
      const id = $("#backlogGameSelect")?.value;
      if (!id) return;
      const list = getBacklog();
      if (list.some((r) => r.id === id)) return toast("Уже в бэклоге");
      list.push({ id, status: "backlog", progress: 0 });
      setBacklog(list);
      renderBacklog(NP);
      updateNexusRankUI();
    });
    $("#backlogList")?.addEventListener("input", (e) => {
      const row = e.target.closest("[data-bl]");
      if (!row) return;
      const id = row.dataset.bl;
      const list = getBacklog();
      const item = list.find((r) => r.id === id);
      if (!item) return;
      if (e.target.matches("[data-bl-prog]")) {
        item.progress = Number(e.target.value);
        const span = row.querySelector(".bl-prog span");
        if (span) span.textContent = item.progress + "%";
      }
      if (e.target.matches("[data-bl-status]")) item.status = e.target.value;
      setBacklog(list);
      updateNexusRankUI();
    });
    $("#backlogList")?.addEventListener("click", (e) => {
      if (!e.target.closest("[data-bl-del]")) return;
      const row = e.target.closest("[data-bl]");
      setBacklog(getBacklog().filter((r) => r.id !== row.dataset.bl));
      renderBacklog(NP);
      updateNexusRankUI();
    });
  }

  /* ============================================================
   * 10) Streams of the day
   * ============================================================ */
  const CURATED_CHANNELS = {
    "Counter-Strike 2": [
      { name: "ESL CS", url: "https://www.twitch.tv/eslcs" },
      { name: "BLAST", url: "https://www.twitch.tv/blastpremier" },
      { name: "HLTV", url: "https://www.twitch.tv/hltv" },
    ],
    CS2: [
      { name: "ESL CS", url: "https://www.twitch.tv/eslcs" },
      { name: "BLAST", url: "https://www.twitch.tv/blastpremier" },
    ],
    "Dota 2": [
      { name: "PGL", url: "https://www.twitch.tv/pglesports" },
      { name: "ESL Dota", url: "https://www.twitch.tv/esldota2" },
    ],
    Valorant: [
      { name: "Valorant", url: "https://www.twitch.tv/valorant" },
      { name: "VCT", url: "https://www.twitch.tv/valorant_americas" },
    ],
    "League of Legends": [{ name: "LCK", url: "https://www.twitch.tv/lck" }],
    default: [
      { name: "Twitch Directory", url: "https://www.twitch.tv/directory" },
      { name: "YouTube Gaming", url: "https://www.youtube.com/gaming" },
    ],
  };

  function renderStreams() {
    const title = ($("#gotdTitle")?.textContent || "").trim();
    const host = $("#streamsOfDay");
    if (!host) return;
    const q = encodeURIComponent(title && title !== "—" ? title : "gaming");
    const channels =
      CURATED_CHANNELS[title] ||
      (title.includes("Counter-Strike") ? CURATED_CHANNELS.CS2 : null) ||
      (title.includes("Dota") ? CURATED_CHANNELS["Dota 2"] : null) ||
      (title.includes("Valorant") ? CURATED_CHANNELS.Valorant : null) ||
      CURATED_CHANNELS.default;
    host.innerHTML = `
      <p class="streams-note">Стримы по игре дня${title && title !== "—" ? `: <strong>${title}</strong>` : ""}</p>
      <div class="streams-actions">
        <a class="btn btn-primary btn-sm" target="_blank" rel="noopener" href="https://www.twitch.tv/search?term=${q}">Стримы Twitch</a>
        <a class="btn btn-ghost btn-sm" target="_blank" rel="noopener" href="https://www.youtube.com/results?search_query=${q}+live">YouTube</a>
      </div>
      <div class="stream-chips">${channels
        .map((c) => `<a class="chip" href="${c.url}" target="_blank" rel="noopener">${c.name}</a>`)
        .join("")}</div>`;
  }

  function watchGotd() {
    const el = $("#gotdTitle");
    if (!el) return;
    const mo = new MutationObserver(() => renderStreams());
    mo.observe(el, { childList: true, characterData: true, subtree: true });
    renderStreams();
  }

  /* ============================================================
   * 11) Esports matches
   * ============================================================ */
  const MATCHES_FALLBACK = {
    updatedAt: "2026-09-24T22:00:00+03:00",
    matches: [],
  };

  function statusLabel(s) {
    if (s === "live") return "LIVE";
    if (s === "upcoming") return "Скоро";
    if (s === "finished") return "Завершён";
    return s || "";
  }

  function renderMatches(payload) {
    const host = $("#matchesLive");
    if (!host) return;
    const list = payload.matches || [];
    host.innerHTML = list
      .map((m) => {
        const liq = m.links?.liquipedia || "#";
        const hltv = m.links?.hltv || "#";
        return `<article class="match-card glass status-${m.status || ""}">
          <div class="match-game">${m.game} · ${m.event || ""}</div>
          <div class="match-teams"><span>${m.teamA}</span><strong>${m.scoreA ?? 0}:${m.scoreB ?? 0}</strong><span>${m.teamB}</span></div>
          <div class="match-status">${statusLabel(m.status)}</div>
          <div class="match-links">
            <a href="${liq}" target="_blank" rel="noopener">Liquipedia</a>
            <a href="${hltv}" target="_blank" rel="noopener">HLTV/stats</a>
          </div>
        </article>`;
      })
      .join("");
  }

  async function loadMatches() {
    try {
      const res = await fetch("./data/matches.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      renderMatches(await res.json());
    } catch (e) {
      console.warn("[matches]", e);
      renderMatches(MATCHES_FALLBACK);
    }
  }

  /* ============================================================
   * Compatibility badges on game cards
   * ============================================================ */
  function injectCompatBadges(NP) {
    const build = shareBuildOverride || lsGet(KEYS.build, null);
    $$("#gamesGrid .game-card .compat-badge").forEach((el) => el.remove());
    $$("#gamesGrid .game-card .upgrade-pc-link").forEach((el) => el.remove());
    if (!build || !build.cpu || !build.gpu) return;
    $$("#gamesGrid .game-card").forEach((card) => {
      const id = card.dataset.id;
      const g = NP.GAMES.find((x) => x.id === id);
      if (!g) return;
      const c = compatForGame(NP, g, build);
      const cover = card.querySelector(".card-cover") || card;
      const b = document.createElement("span");
      b.className = "compat-badge " + (c.badgeClass || "compat-badge-ok");
      b.textContent = c.badge || c.label;
      b.title = shareBuildOverride ? "Совместимость со сборкой по ссылке" : "Совместимость с твоей сборкой";
      cover.appendChild(b);
      const weak = c.status === "no" || c.status === "min" || /Слабо|Впритык|Не потянет/i.test(c.badge || c.label || "");
      if (weak) {
        const a = document.createElement("a");
        a.href = "#tools";
        a.className = "upgrade-pc-link";
        a.dataset.upgradeGame = id;
        a.textContent = "Апгрейднуть ПК";
        a.addEventListener("click", (e) => {
          e.preventDefault();
          setFocusGameId(id);
          document.getElementById("tools")?.scrollIntoView({ behavior: "smooth", block: "start" });
          // prefill FPS + highlight in compat
          const fpsGame = $("#fpsGame");
          if (fpsGame) fpsGame.value = id;
          const gpu = PARTS.gpu.find((p) => p.id === ($("#pcGpu")?.value || build.gpu));
          const fpsGpu = $("#fpsGpu");
          if (fpsGpu && gpu) fpsGpu.value = gpu.fpsKey || "mid";
          $("#fpsCalcBtn")?.click();
          renderBuildCompat(NP, { focusGame: id });
          const row = document.querySelector(`[data-compat-game="${id}"]`);
          row?.scrollIntoView({ behavior: "smooth", block: "nearest" });
          toast("Подбери GPU под " + (g.title || id));
        });
        const body = card.querySelector(".card-body") || card;
        body.appendChild(a);
      }
    });
  }

  /* ============================================================
   * Export / Import nexus_backup.json
   * ============================================================ */
  const BACKUP_PREFIX = "nexus_pulse_";
  const KNOWN_BACKUP_KEYS = [
    KEYS.build, KEYS.owned, KEYS.epicOwned, KEYS.epicName, KEYS.watch,
    KEYS.lfgSelf, KEYS.lfgPending, KEYS.checklist, KEYS.backlog,
    KEYS.hideOwned, "nexus_pulse_wishlist", "nexus_pulse_lang",
  ];

  function collectBackupPayload() {
    const data = {};
    // Prefer known keys + any nexus_pulse_* in localStorage
    const keys = new Set(KNOWN_BACKUP_KEYS);
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(BACKUP_PREFIX)) keys.add(k);
      }
    } catch { /* ignore */ }
    keys.forEach((k) => {
      try {
        const v = localStorage.getItem(k);
        if (v != null) data[k] = v;
      } catch { /* ignore */ }
    });
    return {
      version: 1,
      exportedAt: new Date().toISOString(),
      app: "NEXUS PULSE",
      data,
    };
  }

  function applyBackupPayload(payload, mode) {
    if (!payload || typeof payload !== "object" || !payload.data) {
      throw new Error("файл не похож на резервную копию NEXUS PULSE");
    }
    const entries = Object.entries(payload.data);
    if (mode === "replace") {
      const toRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(BACKUP_PREFIX)) toRemove.push(k);
      }
      toRemove.forEach((k) => localStorage.removeItem(k));
    }
    entries.forEach(([k, v]) => {
      if (!k || !String(k).startsWith(BACKUP_PREFIX)) return;
      localStorage.setItem(k, typeof v === "string" ? v : JSON.stringify(v));
    });
  }

  function wireBackup(NP) {
    $("#backupExportBtn")?.addEventListener("click", () => {
      const payload = collectBackupPayload();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "nexus_backup.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast("Резервная копия сохранена");
    });
    $("#backupImportBtn")?.addEventListener("click", () => {
      $("#backupImportFile")?.click();
    });
    $("#backupImportFile")?.addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      if (!file) return;
      try {
        const text = await file.text();
        const payload = JSON.parse(text);
        if (!confirm("Загрузить данные из резервной копии?")) return;
        const mode = confirm("OK — заменить текущие данные" + "\n" + "Отмена — объединить с текущими");
        applyBackupPayload(payload, mode ? "replace" : "merge");
        // reload UI bits
        try {
          fillPartSelects();
          renderBuildCompat(NP);
          renderOwnedChecklist(NP);
          renderLfg();
          renderChecklist();
          if (typeof wireBacklog === "function") { /* noop */ }
          if (NP.renderWishlist) NP.renderWishlist();
          NP.renderGames();
          injectCompatBadges(NP);
        } catch (err) {
          console.warn(err);
        }
        toast("Данные восстановлены");
      } catch (err) {
        toast("Импорт не удался: " + (err instanceof SyntaxError ? "файл повреждён" : err.message || err));
      }
    });
  }

  function applyBuildFromQuery(NP) {
    const params = new URLSearchParams(location.search);
    const hasParams = params.has("cpu") || params.has("gpu") || params.has("ram");
    const shared = readSharedBuild();
    if (!shared) {
      if (hasParams) toast("Ссылка на сборку повреждена — показываем твою сборку");
      return;
    }
    if (shared.cpu && $("#pcCpu")) $("#pcCpu").value = shared.cpu;
    if (shared.gpu && $("#pcGpu")) $("#pcGpu").value = shared.gpu;
    if (shared.ram && $("#pcRam")) $("#pcRam").value = shared.ram;
    if (shared.res && $("#pcRes")) $("#pcRes").value = shared.res;
    shareBuildOverride = Object.assign(currentBuild(), { fromShare: true });
    renderBuildCompat(NP, { fromShare: true });
    injectCompatBadges(NP);
    if (location.hash !== "#tools") {
      try { history.replaceState(null, "", location.pathname + location.search + "#tools"); } catch { /* ignore */ }
    }
    const compat = document.getElementById("pcBuilder") || document.getElementById("tools");
    if (compat) {
      setTimeout(() => {
        try { compat.scrollIntoView({ behavior: "smooth", block: "start" }); } catch { /* ignore */ }
      }, 300);
    }
    toast("Сборка друга загружена — смотри, что она потянет");
  }

  /* ============================================================
   * Hook renderGames / renderDeals
   * ============================================================ */
  function patchRenderHooks(NP) {
    const origGames = NP.renderGames.bind(NP);
    NP.renderGames = function () {
      // temporarily filter via monkeypatch on GAMES filter — use wrapper
      const all = NP.GAMES;
      const filteredIds = new Set(all.filter(extraFilter).map((g) => g.id));
      // Call original then hide non-matching / or re-filter DOM
      // Better: patch by filtering search — set a flag on NP
      NP._extraFilter = extraFilter;
      origGames();
      // Hide cards that fail extra filter (original only does genre+search)
      $$("#gamesGrid .game-card").forEach((card) => {
        if (!filteredIds.has(card.dataset.id)) card.remove();
      });
      const left = $$("#gamesGrid .game-card").length;
      const empty = $("#gamesEmpty");
      if (empty) empty.hidden = left > 0;
      decorateGameCards(NP);
      injectCompatBadges(NP);
    };

    if (typeof NP.renderDeals === "function") {
      const origDeals = NP.renderDeals.bind(NP);
      NP.renderDeals = function (payload) {
        origDeals(payload);
        decorateDealCards();
        setWatchDeals(payload);
      };
    }

    // If deals already rendered, decorate now
    setTimeout(() => {
      decorateDealCards();
      try {
        const raw = $("#dealsGrid")?.dataset.deals;
        if (raw && !watchState.dealsLoaded) setWatchDeals({ deals: JSON.parse(raw) });
      } catch { /* ignore */ }
    }, 800);
  }

  /* ============================================================
   * PWA install button
   * ============================================================ */
  function isStandaloneApp() {
    try {
      return (
        window.matchMedia("(display-mode: standalone)").matches ||
        window.matchMedia("(display-mode: fullscreen)").matches ||
        window.matchMedia("(display-mode: minimal-ui)").matches ||
        window.navigator.standalone === true
      );
    } catch {
      return false;
    }
  }

  function isIOSDevice() {
    const ua = navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function wireInstall() {
    const btn = $("#installBtn");
    if (!btn) return;
    let deferred = window.__npInstallPrompt || null;
    const ios = isIOSDevice();
    const sync = () => {
      btn.hidden = isStandaloneApp() || !(deferred || ios);
    };
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferred = e;
      window.__npInstallPrompt = e;
      sync();
    });
    window.addEventListener("appinstalled", () => {
      deferred = null;
      window.__npInstallPrompt = null;
      sync();
      toast("NEXUS PULSE установлен");
    });
    try {
      window.matchMedia("(display-mode: standalone)").addEventListener("change", sync);
    } catch { /* old Safari */ }
    btn.addEventListener("click", async () => {
      if (deferred) {
        const evt = deferred;
        deferred = null;
        window.__npInstallPrompt = null;
        try {
          await evt.prompt();
          const choice = await evt.userChoice;
          if (choice && choice.outcome === "dismissed") toast("Установку можно повторить позже");
        } catch (e) {
          console.warn("[NEXUS PULSE] install prompt:", e);
        }
        sync();
        return;
      }
      if (ios) {
        toast("Поделиться → На экран «Домой»", 6000);
      }
    });
    sync();
  }

  wireInstall();

  /* ---------- Init ---------- */
  waitForNexus((NP) => {
    enrichGames(NP.GAMES);
    NP.extraFilter = extraFilter;
    NP.getOwned = getOwned;
    patchRenderHooks(NP);
    wireExtraFilters(NP);
    wireAlertClicks();
    wireWatchlist();
    wirePcBuilder(NP);
    wireNickGen();
    wirePingMap();
    wireSteamImport(NP);
    wireBackup(NP);
    loadSteamCatalogSnapshot();
    loadFreebies();
    wireLfg();
    wireChecklist();
    wireBacklog(NP);
    watchGotd();
    // Матчи, турниры и трансляции рендерит content-hub.js (void loadMatches — оставлено для совместимости)
    void loadMatches;
    applyBuildFromQuery(NP);
    NP.renderGames();
    injectCompatBadges(NP);
    updateNexusRankUI();
    if (NP.updateHeroStats) {
      const tools = $("#statTools");
      if (tools) tools.textContent = "12";
    }
    console.info("[NEXUS PULSE] features-extra ready");
  });
})();
