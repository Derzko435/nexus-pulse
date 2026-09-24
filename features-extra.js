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
    alerts: "nexus_pulse_price_alerts",
    webhook: "nexus_pulse_discord_webhook",
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
    const alerts = getAlerts();
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
        const bell = document.createElement("button");
        bell.type = "button";
        bell.className = "alert-bell" + (hasAlertForTitle(alerts, g.title) ? " active" : "");
        bell.dataset.alertTitle = g.title;
        bell.dataset.alertId = "game-" + g.id;
        bell.title = "Ценовой алерт";
        bell.setAttribute("aria-label", "Алерт на скидку");
        bell.textContent = "🔔";
        cover.appendChild(bell);
      }
    });
  }

  /* ============================================================
   * 6) Price alerts
   * ============================================================ */
  function getAlerts() {
    return lsGet(KEYS.alerts, []);
  }
  function setAlerts(list) {
    lsSet(KEYS.alerts, list);
  }
  function hasAlertForTitle(list, title) {
    const t = (title || "").toLowerCase();
    return list.some((a) => (a.gameTitle || "").toLowerCase() === t || a.dealId === title);
  }

  function toggleAlert(opts) {
    const list = getAlerts();
    const title = opts.gameTitle || "";
    const dealId = opts.dealId || "";
    const idx = list.findIndex(
      (a) =>
        (dealId && a.dealId === dealId) ||
        (title && (a.gameTitle || "").toLowerCase() === title.toLowerCase())
    );
    if (idx >= 0) {
      list.splice(idx, 1);
      setAlerts(list);
      toast("Алерт снят: " + (title || dealId));
      return false;
    }
    list.push({
      gameTitle: title,
      dealId: dealId || undefined,
      targetPct: opts.targetPct != null ? Number(opts.targetPct) : 50,
      created: new Date().toISOString(),
    });
    setAlerts(list);
    toast("Алерт сохранён: " + (title || dealId) + " (−" + (opts.targetPct || 50) + "%+)");
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
    return true;
  }

  function wireAlertClicks() {
    document.addEventListener("click", (e) => {
      const bell = e.target.closest(".alert-bell");
      if (!bell) return;
      e.preventDefault();
      e.stopPropagation();
      const active = toggleAlert({
        gameTitle: bell.dataset.alertTitle,
        dealId: bell.dataset.alertId,
        targetPct: bell.dataset.targetPct ? Number(bell.dataset.targetPct) : 50,
      });
      bell.classList.toggle("active", active);
    });
  }

  function decorateDealCards() {
    const alerts = getAlerts();
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
      const bell = document.createElement("button");
      bell.type = "button";
      bell.className = "alert-bell" + (hasAlertForTitle(alerts, d.title) || alerts.some((a) => a.dealId === d.id) ? " active" : "");
      bell.dataset.alertTitle = d.title;
      bell.dataset.alertId = d.id;
      bell.dataset.targetPct = String(Math.max(10, Number(d.pct) || 50));
      bell.title = "Алерт на скидку";
      bell.textContent = "🔔";
      cover.appendChild(bell);
    });
  }

  function checkAlertsAgainstDeals(payload) {
    const deals = (payload && payload.deals) || [];
    const alerts = getAlerts();
    if (!alerts.length || !deals.length) return;
    const fired = [];
    alerts.forEach((a) => {
      const target = a.targetPct != null ? Number(a.targetPct) : 50;
      const match = deals.find((d) => {
        const titleOk =
          a.gameTitle &&
          d.title &&
          (d.title.toLowerCase().includes(a.gameTitle.toLowerCase()) ||
            a.gameTitle.toLowerCase().includes(d.title.toLowerCase()));
        const idOk = a.dealId && d.id === a.dealId;
        return (titleOk || idOk) && Number(d.pct) >= target;
      });
      if (match) {
        fired.push({ alert: a, deal: match });
      }
    });
    if (!fired.length) return;

    const panel = $("#alertFiredList");
    const head = $("#alertFiredHead");
    if (head) head.hidden = false;
    if (panel) {
      panel.hidden = false;
      panel.innerHTML = fired
        .map(
          (f) =>
            `<li><strong>${f.deal.title}</strong> −${f.deal.pct}% · ${f.deal.store || ""}
            <a href="${f.deal.url || "#"}" target="_blank" rel="noopener">открыть</a></li>`
        )
        .join("");
    }

    fired.forEach((f) => {
      const msg = `🔥 ${f.deal.title}: −${f.deal.pct}% на ${f.deal.store || "скидке"}`;
      toast(msg, 6000);
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try {
          new Notification("NEXUS PULSE · алерт", { body: msg });
        } catch { /* ignore */ }
      }
    });

    const copyBtn = $("#alertCopyDiscord");
    if (copyBtn) {
      copyBtn.onclick = () => {
        const text = fired
          .map((f) => `🔥 **${f.deal.title}** −${f.deal.pct}% (${f.deal.store || ""})\n${f.deal.url || ""}`)
          .join("\n\n");
        navigator.clipboard?.writeText(text).then(
          () => toast("Скопировано — вставь в Discord #анонсы (live-посты также идут с бота на боксе)"),
          () => toast("Не удалось скопировать")
        );
      };
    }

    maybePostWebhook(fired);
  }

  async function maybePostWebhook(fired) {
    const url = (localStorage.getItem(KEYS.webhook) || "").trim();
    if (!url || !fired.length) return;
    const embeds = fired.slice(0, 5).map((f) => ({
      title: f.deal.title,
      description: `Скидка −${f.deal.pct}% · ${f.deal.store || ""}\n[Открыть](${f.deal.url || "#"})`,
      color: 0x00f5ff,
    }));
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: "NEXUS PULSE · сработали алерты", embeds }),
      });
      toast("Webhook: попытка отправки (может блокироваться CORS)");
    } catch {
      toast("Webhook не дошёл (CORS). Лучше локальный бот + «Скопировать».");
    }
  }

  function wireAlertSettings() {
    const input = $("#discordWebhookInput");
    const save = $("#discordWebhookSave");
    if (input) input.value = localStorage.getItem(KEYS.webhook) || "";
    save?.addEventListener("click", () => {
      const v = (input?.value || "").trim();
      if (v) localStorage.setItem(KEYS.webhook, v);
      else localStorage.removeItem(KEYS.webhook);
      toast(v ? "Webhook сохранён только в этом браузере" : "Webhook очищен");
    });
    $("#notifyPermBtn")?.addEventListener("click", async () => {
      if (!("Notification" in window)) {
        toast("Notification API недоступен");
        return;
      }
      const p = await Notification.requestPermission();
      toast("Разрешение уведомлений: " + p);
    });
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
    const labels = { ok: "Потянет", min: "На минимуме", no: "Не потянет" };
    return { status, label: labels[status], fps };
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
    } else {
      if ($("#pcCpu")) $("#pcCpu").value = "r5_7600";
      if ($("#pcGpu")) $("#pcGpu").value = "rtx4060";
      if ($("#pcRam")) $("#pcRam").value = "16";
      if ($("#pcStorage")) $("#pcStorage").value = "ssd_1t";
    }
  }

  function renderBuildCompat(NP) {
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
    const block = (title, arr, cls) => `
      <div class="compat-group ${cls}">
        <h4>${title} <small>(${arr.length})</small></h4>
        <ul>${arr
          .slice(0, 40)
          .map(
            (r) => `<li>
            <button type="button" class="linkish" data-prefill-fps="${r.game.id}" data-fps-gpu="${PARTS.gpu.find((p) => p.id === build.gpu)?.fpsKey || "mid"}">${r.game.title}</button>
            <span class="compat-fps">~${r.fps} FPS</span>
          </li>`
          )
          .join("")}${arr.length > 40 ? `<li class="muted">…и ещё ${arr.length - 40}</li>` : ""}</ul>
      </div>`;
    host.innerHTML =
      block("Потянет", groups.ok, "compat-ok") +
      block("На минимуме", groups.min, "compat-min") +
      block("Не потянет", groups.no, "compat-no");
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
        savedAt: new Date().toISOString(),
      };
      lsSet(KEYS.build, build);
      toast("Сборка сохранена в браузере");
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
    const ctx = canvas.getContext("2d");
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

    // emblem (geometric)
    drawEmblem(ctx, w, h, style, c1, c2, rnd);

    // soft glow behind initials
    glowCircle(w / 2, h / 2, 58, c1, 0.35);
    ctx.fillStyle = "rgba(0,0,0,.4)";
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, 48, 0, Math.PI * 2);
    ctx.fill();

    const initials = (nick || "NP")
      .replace(/[^a-zA-Zа-яА-Я0-9]/g, "")
      .slice(0, 2)
      .toUpperCase() || "NP";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "bold 44px Orbitron, Manrope, sans-serif";
    ctx.letterSpacing = "0.08em";
    ctx.shadowColor = "rgba(0,0,0,.65)";
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    ctx.fillStyle = "#fff";
    // slight letter spacing via two chars
    if (initials.length === 2) {
      ctx.fillText(initials[0], w / 2 - 14, h / 2 + 2);
      ctx.fillText(initials[1], w / 2 + 14, h / 2 + 2);
    } else {
      ctx.fillText(initials, w / 2, h / 2 + 2);
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
  const PING_TARGETS = [
    { id: "cloudflare", name: "Cloudflare", url: "https://speed.cloudflare.com/__down?bytes=0", kind: "fetch" },
    { id: "steam", name: "Steam CDN", url: "https://cdn.cloudflare.steamstatic.com/steam/apps/730/header.jpg", kind: "img" },
    { id: "riot", name: "Riot (approx)", url: "https://authenticate.riotgames.com/favicon.ico", kind: "img" },
    { id: "epic", name: "Epic", url: "https://static-assets-prod.unrealengine.com/account-portal/static/favicon.ico", kind: "img" },
    { id: "blizzard", name: "Blizzard", url: "https://www.blizzard.com/favicon.ico", kind: "img" },
    { id: "google", name: "Google (ref)", url: "https://www.google.com/favicon.ico", kind: "img" },
  ];

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

  function wirePingMap() {
    $("#pingRefreshBtn")?.addEventListener("click", () => {
      runPingMap();
    });
    // delay slightly so speed test globals may exist
    setTimeout(runPingMap, 400);
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

  async function resolveVanity(vanity) {
    // Best-effort via allorigins + community XML redirect is hard; try profile XML path
    const url = `https://steamcommunity.com/id/${encodeURIComponent(vanity)}/?xml=1`;
    const proxied = `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`;
    const res = await fetch(proxied, { cache: "no-store" });
    if (!res.ok) throw new Error("vanity HTTP " + res.status);
    const text = await res.text();
    const m = text.match(/<steamID64>(\d+)<\/steamID64>/i);
    if (!m) throw new Error("steamID64 not found");
    return m[1];
  }

  async function fetchSteamGamesXml(steamid64) {
    const url = `https://steamcommunity.com/profiles/${steamid64}/games?tab=all&xml=1`;
    const proxied = `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`;
    const res = await fetch(proxied, { cache: "no-store" });
    if (!res.ok) throw new Error("games HTTP " + res.status);
    const text = await res.text();
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
      if (status) status.textContent = "Загрузка через публичный прокси…";
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
          status.textContent = `Steam: найдено ${titles.length} игр, совпало с каталогом: ${matched.size}. Профиль должен быть публичным.`;
        toast("Импорт Steam: +" + matched.size + " из каталога");
      } catch (err) {
        console.warn(err);
        if (status)
          status.textContent =
            "Импорт не удался (" + (err.message || err) + "). Отметь игры вручную ниже — браузер/CORS/прокси часто блокируют.";
        toast("Steam import недоступен — используй ручной список");
      }
    });

    $("#epicNameSave")?.addEventListener("click", () => {
      const n = ($("#epicNameInput")?.value || "").trim();
      lsSet(KEYS.epicName, n);
      toast(n ? "Epic display name сохранён локально" : "Очищено");
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

  function renderFreebies(payload) {
    const grid = $("#freebiesGrid");
    const updated = $("#freebiesUpdated");
    if (updated) updated.textContent = "Обновлено: " + (payload.updatedAt || "—");
    if (!grid) return;
    const items = payload.items || [];
    grid.innerHTML = items
      .map((it) => {
        const forever = it.until && it.until.startsWith("2099");
        return `<article class="freebie-card glass">
          <div class="freebie-store">${it.store || ""}</div>
          <h3>${it.title}</h3>
          <p class="freebie-until">${forever ? "Постоянно F2P / витрина" : "До " + it.until}</p>
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
  const LFG_DEMO = [
    { game: "CS2", rank: "DMG", prime: "20:00–23:00 МСК", mic: true, note: "Ищу 5-ку на премьер, без тильта", nick: "RazerFox" },
    { game: "Valorant", rank: "Gold 2", prime: "18:00–21:00 МСК", mic: true, note: "Дуо на анрейт / дедлок мейн", nick: "NeonKat" },
    { game: "Dota 2", rank: "Archon", prime: "выходные", mic: false, note: "Саппорт 4/5, можно без микро", nick: "VoidRunner" },
    { game: "Lethal Company", rank: "casual", prime: "вечером", mic: true, note: "Моды ок, квота или смерть", nick: "PulseBot" },
  ];

  function renderLfg() {
    const self = lsGet(KEYS.lfgSelf, null);
    const feed = $("#lfgFeed");
    if (!feed) return;
    const cards = self ? [Object.assign({ nick: "Ты", _self: true }, self), ...LFG_DEMO] : LFG_DEMO;
    feed.innerHTML = cards
      .map(
        (c) => `<article class="lfg-card glass ${c._self ? "lfg-self" : ""}">
        <div class="lfg-top"><strong>${c.nick || "Игрок"}</strong> · ${c.game}</div>
        <div class="lfg-meta">Ранг: ${c.rank || "—"} · Прайм: ${c.prime || "—"} · Мик: ${c.mic ? "да" : "нет"}</div>
        <p>${c.note || ""}</p>
      </article>`
      )
      .join("");
  }

  function wireLfg() {
    const self = lsGet(KEYS.lfgSelf, null);
    if (self) {
      if ($("#lfgGame")) $("#lfgGame").value = self.game || "";
      if ($("#lfgRank")) $("#lfgRank").value = self.rank || "";
      if ($("#lfgPrime")) $("#lfgPrime").value = self.prime || "";
      if ($("#lfgMic")) $("#lfgMic").checked = !!self.mic;
      if ($("#lfgNote")) $("#lfgNote").value = self.note || "";
    }
    renderLfg();
    $("#lfgSaveBtn")?.addEventListener("click", () => {
      const nickEl = $("#nickOutput");
      const card = {
        game: $("#lfgGame")?.value || "CS2",
        rank: $("#lfgRank")?.value || "",
        prime: $("#lfgPrime")?.value || "",
        mic: !!$("#lfgMic")?.checked,
        note: $("#lfgNote")?.value || "",
        nick: (nickEl && nickEl.textContent && nickEl.textContent !== "—") ? nickEl.textContent : "Player",
        ts: Date.now(),
      };
      lsSet(KEYS.lfgSelf, card);
      lsSet(KEYS.lfgPending, card);
      renderLfg();
      toast("Карточка LFG сохранена · серверный пост бота — через updater на боксе");
    });
    $("#lfgDiscordBtn")?.addEventListener("click", () => {
      const nickEl = $("#nickOutput");
      const card = Object.assign(
        {
          game: $("#lfgGame")?.value || "CS2",
          rank: $("#lfgRank")?.value || "",
          prime: $("#lfgPrime")?.value || "",
          mic: !!$("#lfgMic")?.checked,
          note: $("#lfgNote")?.value || "",
          nick: (nickEl && nickEl.textContent && nickEl.textContent !== "—") ? nickEl.textContent : "Player",
          ts: Date.now(),
        },
        lsGet(KEYS.lfgSelf, null) || {}
      );
      // refresh fields from form (form wins)
      card.game = $("#lfgGame")?.value || card.game;
      card.rank = $("#lfgRank")?.value || card.rank;
      card.prime = $("#lfgPrime")?.value || card.prime;
      card.mic = !!$("#lfgMic")?.checked;
      card.note = $("#lfgNote")?.value || card.note;
      card.ts = Date.now();
      lsSet(KEYS.lfgSelf, card);
      lsSet(KEYS.lfgPending, card);
      const text = `LFG · ${card.game} · ${card.rank || "?"} · ${card.prime || "?"} · mic:${card.mic ? "yes" : "no"}\n${card.note || ""}\n#поиск-тимы`;
      navigator.clipboard?.writeText(text).then(
        () => toast("Скопировано — открываю Discord"),
        () => toast("Открываю Discord (буфер недоступен)")
      );
      renderLfg();
      const url = window.NexusPulse?.DISCORD_INVITE_URL || "https://discord.gg/c7UHcM2UR";
      window.open(url, "_blank", "noopener,noreferrer");
    });
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
    });
    $("#backlogList")?.addEventListener("click", (e) => {
      if (!e.target.closest("[data-bl-del]")) return;
      const row = e.target.closest("[data-bl]");
      setBacklog(getBacklog().filter((r) => r.id !== row.dataset.bl));
      renderBacklog(NP);
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
      <p class="streams-note">Стримы по игре дня${title && title !== "—" ? `: <strong>${title}</strong>` : ""}. Twitch Helix требует ключ — здесь глубокие ссылки поиска (без live API).</p>
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
    const note = $("#matchesNote");
    if (note) note.textContent = payload.note || "Данные из data/matches.json (обновляется скриптом).";
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
    };

    if (typeof NP.renderDeals === "function") {
      const origDeals = NP.renderDeals.bind(NP);
      NP.renderDeals = function (payload) {
        origDeals(payload);
        decorateDealCards();
        checkAlertsAgainstDeals(payload);
      };
    }

    // If deals already rendered, decorate now
    setTimeout(() => {
      decorateDealCards();
      try {
        const raw = $("#dealsGrid")?.dataset.deals;
        if (raw) checkAlertsAgainstDeals({ deals: JSON.parse(raw) });
      } catch { /* ignore */ }
    }, 800);
  }

  /* ---------- Init ---------- */
  waitForNexus((NP) => {
    enrichGames(NP.GAMES);
    NP.extraFilter = extraFilter;
    NP.getOwned = getOwned;
    patchRenderHooks(NP);
    wireExtraFilters(NP);
    wireAlertClicks();
    wireAlertSettings();
    wirePcBuilder(NP);
    wireNickGen();
    wirePingMap();
    wireSteamImport(NP);
    loadFreebies();
    wireLfg();
    wireChecklist();
    wireBacklog(NP);
    watchGotd();
    loadMatches();
    NP.renderGames();
    if (NP.updateHeroStats) {
      const tools = $("#statTools");
      if (tools) tools.textContent = "12";
    }
    console.info("[NEXUS PULSE] features-extra ready");
  });
})();
