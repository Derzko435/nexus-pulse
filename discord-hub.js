/* NEXUS PULSE — живая карточка Discord-сервера (онлайн из публичного виджета / инвайта).
   Внешний текст экранируется; при любой ошибке карточка остаётся статичной. */
(function () {
  "use strict";
  const GUILD_ID = "1552735502266794204";
  const CACHE_KEY = "np_discord_live_v1";
  const TTL = 5 * 60 * 1000;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  function inviteUrl() {
    const u = (window.NexusPulse && window.NexusPulse.DISCORD_INVITE_URL) || "";
    return /^https:\/\/discord\.gg\/[\w-]+$/.test(u) ? u : "";
  }
  function inviteCode() {
    const m = inviteUrl().match(/discord\.gg\/([\w-]+)$/);
    return m ? m[1] : "";
  }
  function plural(n, one, few, many) {
    const a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b > 1 && b < 5) return few;
    if (b === 1) return one;
    return many;
  }
  async function getJson(url) {
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 6000) : null;
    try {
      const res = await fetch(url, { signal: ctrl ? ctrl.signal : undefined, credentials: "omit" });
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
  function readCache() {
    try {
      const c = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
      return c && Date.now() - c.t < TTL ? c.d : null;
    } catch (_) { return null; }
  }
  function writeCache(d) {
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), d })); } catch (_) { /* private mode */ }
  }

  async function loadStats() {
    const cached = readCache();
    if (cached) return cached;
    const code = inviteCode();
    // widget.json answers 403 while the server widget is off → ask only when the site config says it's on
    const cfg = await getJson("./data/discord_channels.json");
    const widgetOn = !!(cfg && cfg.widgetEnabled === true);
    const [widget, invite] = await Promise.all([
      widgetOn ? getJson(`https://discord.com/api/guilds/${GUILD_ID}/widget.json`) : Promise.resolve(null),
      code ? getJson(`https://discord.com/api/v10/invites/${encodeURIComponent(code)}?with_counts=true`) : Promise.resolve(null),
    ]);
    const g = (invite && invite.guild) || {};
    const d = {
      name: (widget && widget.name) || g.name || "NEXUS PULSE",
      online: Number((widget && widget.presence_count) ?? (invite && invite.approximate_presence_count) ?? NaN),
      members: Number((invite && invite.approximate_member_count) ?? NaN),
      icon: g.id === GUILD_ID && /^[a-f0-9_]+$/i.test(g.icon || "") ? `https://cdn.discordapp.com/icons/${GUILD_ID}/${g.icon}.png?size=128` : "",
      instant: widget && /^https:\/\/discord\.com\/invite\/[\w-]+$/.test(widget.instant_invite || "") ? widget.instant_invite : "",
    };
    if (widget || invite) writeCache(d);
    return d;
  }

  function render(d) {
    if (!d) return;
    const name = $("#dcName");
    if (name) name.textContent = d.name; // textContent — no HTML injection
    const icon = $("#dcIcon");
    if (icon && d.icon) {
      icon.addEventListener("error", () => { icon.src = "assets/nexus-pulse-icon.png"; }, { once: true });
      icon.src = d.icon;
    }
    const online = $("#dcOnline");
    const card = $("#discordLive");
    if (online && Number.isFinite(d.online) && d.online > 0) {
      online.textContent = `${d.online} ${plural(d.online, "игрок", "игрока", "игроков")} в сети`;
      card && card.classList.add("is-live");
    }
    const members = $("#dcMembers");
    // маленький счётчик участников не показываем — только когда он уже внушительный
    if (members && Number.isFinite(d.members) && d.members >= 25) {
      members.textContent = ` · ${d.members} ${plural(d.members, "участник", "участника", "участников")}`;
    }
    $$("[data-dc-online]").forEach((el) => {
      if (Number.isFinite(d.online) && d.online > 0) {
        el.textContent = String(d.online);
        el.title = `${d.online} в сети`;
        el.hidden = false;
      }
    });
  }

  /* Кнопка Telegram-канала — только когда канал указан в data/site_config.json */
  async function telegramButton() {
    const cfg = await getJson("./data/site_config.json");
    const tg = (cfg && cfg.telegram) || {};
    const m = String(tg.channel || "").trim().match(/^@?([A-Za-z][\w]{4,31})$/);
    if (!m || document.querySelector(".tg-cta")) return;
    const url = "https://t.me/" + m[1];
    $$("#discordCta").forEach((cta) => {
      const a = document.createElement("a");
      a.className = "btn btn-ghost tg-cta";
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = "Telegram-канал";
      a.style.marginLeft = ".5rem";
      cta.insertAdjacentElement("afterend", a);
    });
  }

  function init() {
    setTimeout(() => telegramButton().catch(() => null), 1500);
    if (!inviteUrl()) return;
    const run = () => loadStats().then(render).catch(() => null);
    // не мешаем первой отрисовке страницы
    setTimeout(run, 1200);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
