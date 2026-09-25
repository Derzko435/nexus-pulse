/* NEXUS PULSE — настройки сайта (data/site_config.json), Яндекс Метрика и цели,
   кнопки «Поделиться», поиск по ссылке ?q=… */
(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);

  /* ---------- Цели Метрики: копим до загрузки счётчика ---------- */
  let metrikaId = null;
  let metrikaOff = false;
  const queue = [];
  function npGoal(name, params) {
    if (!name) return;
    if (metrikaId && typeof window.ym === "function") {
      try { window.ym(metrikaId, "reachGoal", name, params || undefined); } catch { /* ignore */ }
    } else if (!metrikaOff && queue.length < 50) {
      queue.push([name, params]);
    }
  }
  window.npGoal = npGoal;

  function loadMetrika(id) {
    /* Официальный код счётчика Яндекс Метрики */
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (let j = 0; j < document.scripts.length; j++) { if (document.scripts[j].src === r) return; }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0]; k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js?id=" + id, "ym");
    window.ym(id, "init", { ssr: true, clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: false });
    metrikaId = id;
    queue.splice(0).forEach(([n, p]) => npGoal(n, p));
  }

  fetch("./data/site_config.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}))
    .then((cfg) => {
      const id = String((cfg && cfg.yandexMetrikaId) || "").trim();
      if (/^\d{5,12}$/.test(id)) loadMetrika(Number(id));
      else { metrikaOff = true; queue.length = 0; } // счётчик не настроен — ничего не загружаем
    });

  /* ---------- Цели: ключевые действия ---------- */
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[href]");
    if (a && /^https:\/\/(www\.)?(discord\.gg|discord\.com\/invite)\//i.test(a.href)) npGoal("discord_join");
    if (e.target.closest && e.target.closest("#installBtn")) npGoal("pwa_install_click");
    if (e.target.closest && e.target.closest("[data-guide-copy]")) npGoal("share", { what: "guide" });
  }, true);
  window.addEventListener("appinstalled", () => npGoal("pwa_install"));

  /* ---------- «Поделиться» ---------- */
  function siteBase() {
    return (location.origin + location.pathname.replace(/[^/]*$/, "")).replace(/\/?$/, "/");
  }
  function toast(msg) {
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
    setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 300); }, 4200);
  }
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch { /* fall through */ }
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch { return false; }
  }
  const mobile = () => (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");

  document.addEventListener("click", async (e) => {
    const b = e.target.closest && e.target.closest("[data-np-share]");
    if (!b) return;
    e.preventDefault();
    const kind = b.dataset.npShare;
    const id = b.dataset.id || "";
    if (kind !== "news" || !/^[\w-]{1,64}$/.test(id)) return;
    const url = siteBase() + "s/news/" + id + ".html";
    const title = b.dataset.title || "NEXUS PULSE";
    npGoal("share", { what: kind });
    if (typeof navigator.share === "function" && mobile()) {
      try { await navigator.share({ title, url }); return; } catch (err) { if (err && err.name === "AbortError") return; }
    }
    if (await copy(url)) {
      b.textContent = "✓ Ссылка скопирована";
      toast("Ссылка скопирована — отправь её другу");
    } else {
      window.prompt("Скопируй ссылку:", url);
    }
  });

  /* ---------- Поиск по ссылке: ?q=… (для поисковиков) ---------- */
  function searchFromQuery() {
    const q = new URLSearchParams(location.search).get("q");
    if (!q || q.length > 80) return;
    const btn = $("#navSearchBtn");
    if (!btn) return;
    btn.click();
    setTimeout(() => {
      const input = $("#npSearchInput");
      if (!input) return;
      input.value = q;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }, 60);
  }
  if (document.readyState === "complete") setTimeout(searchFromQuery, 400);
  else window.addEventListener("load", () => setTimeout(searchFromQuery, 400));
})();
