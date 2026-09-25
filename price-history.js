/* NEXUS PULSE — история цен Steam (data/price_history.json): мини-графики в «Отслеживаю цены»
   и в карточке игры. Лёгкий inline SVG без библиотек. */
(function () {
  "use strict";
  const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  let DATA = null;
  let loading = null;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const rub = (n) => Number(n).toLocaleString("ru-RU") + " ₽";
  const dayMs = 86400000;
  const toTime = (d) => Date.parse(d + "T12:00:00+03:00");
  function fmt(d) {
    const m = String(d || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${+m[3]} ${MONTHS[+m[2] - 1]}` : "";
  }
  function todayIso() {
    const p = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
    return p;
  }

  function load() {
    if (loading) return loading;
    loading = fetch("./data/price_history.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        DATA = d && d.items ? d : { items: {} };
        document.dispatchEvent(new CustomEvent("np:price-history"));
        fillPending();
        return DATA;
      })
      .catch(() => { DATA = { items: {} }; return DATA; });
    return loading;
  }

  function series(appid) {
    const pts = DATA && DATA.items && DATA.items[String(appid)];
    return Array.isArray(pts) && pts.length ? pts : null;
  }

  /** Сводка: текущая, минимальная, максимальная цена и с какого дня отслеживаем */
  function stats(appid, currentPrice) {
    const pts = series(appid);
    if (!pts) return null;
    const prices = pts.map((p) => p[1]);
    const cur = Number.isFinite(Number(currentPrice)) && currentPrice != null ? Number(currentPrice) : prices[prices.length - 1];
    let lowIdx = 0;
    prices.forEach((v, i) => { if (v <= prices[lowIdx]) lowIdx = i; });
    const low = Math.min(prices[lowIdx], cur);
    return {
      pts, cur, low, high: Math.max(...prices, cur),
      lowDate: cur < prices[lowIdx] ? todayIso() : pts[lowIdx][0],
      since: pts[0][0], changes: pts.length - 1,
    };
  }

  /** SVG-график «ступеньками»: цена держится до следующего изменения, линия тянется до сегодня */
  function svg(appid, w, h, big) {
    const pts = series(appid);
    if (!pts) return "";
    const t0 = toTime(pts[0][0]);
    const t1 = Math.max(toTime(todayIso()), t0 + dayMs);
    const prices = pts.map((p) => p[1]);
    const lo = Math.min(...prices), hi = Math.max(...prices);
    const pad = big ? 6 : 3;
    const X = (t) => pad + ((t - t0) / (t1 - t0)) * (w - pad * 2);
    const Y = (v) => (hi === lo ? h / 2 : pad + (1 - (v - lo) / (hi - lo)) * (h - pad * 2));
    let d = `M${X(t0).toFixed(1)},${Y(prices[0]).toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) {
      const x = X(toTime(pts[i][0])).toFixed(1);
      d += ` H${x} V${Y(pts[i][1]).toFixed(1)}`;
    }
    d += ` H${X(t1).toFixed(1)}`;
    const area = `${d} V${h} H${X(t0).toFixed(1)} Z`;
    const lowPts = pts.filter((p) => p[1] === lo);
    const dots = lowPts.map((p) => `<circle cx="${X(toTime(p[0])).toFixed(1)}" cy="${Y(lo).toFixed(1)}" r="${big ? 3 : 2}" class="ph-low-dot"/>`).join("");
    const gid = "phg" + String(appid).replace(/\D/g, "") + (big ? "b" : "s");
    const label = `История цены: от ${rub(lo)} до ${rub(hi)} с ${fmt(pts[0][0])}`;
    return `<svg class="ph-svg${big ? " ph-svg-big" : ""}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" preserveAspectRatio="none" role="img" aria-label="${esc(label)}">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".28"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
      <path d="${area}" fill="url(#${gid})" stroke="none"/>
      <path d="${d}" fill="none" stroke="currentColor" stroke-width="${big ? 2 : 1.6}" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
      ${dots}</svg>`;
  }

  /** Строка списка «Отслеживаю цены»: мини-график + минимум */
  function row(appid, currentPrice) {
    if (!DATA) { load(); return ""; }
    const s = stats(appid, currentPrice);
    if (!s) return "";
    const atLow = s.cur <= s.low;
    const txt = s.changes === 0 && s.cur === s.low
      ? `Цена не менялась с ${fmt(s.since)}`
      : atLow ? `🏷 Минимальная цена с ${fmt(s.since)}` : `Минимум ${rub(s.low)} · ${fmt(s.lowDate)}`;
    return `<span class="ph-row${atLow && s.changes ? " ph-at-low" : ""}" title="${esc("Отслеживаем с " + fmt(s.since))}">${svg(appid, 92, 24, false)}<span class="ph-row-txt">${esc(txt)}</span></span>`;
  }

  /** Блок для карточки игры */
  function block(appid, currentPrice) {
    if (!DATA) {
      load();
      return `<div class="ph-block ph-pending" data-ph-appid="${esc(appid)}" hidden></div>`;
    }
    const s = stats(appid, currentPrice);
    if (!s) return "";
    const diff = s.cur - s.low;
    const verdict = s.changes === 0
      ? `Цена не менялась с ${fmt(s.since)}`
      : diff <= 0 ? "Сейчас самая низкая цена за время наблюдения" : `Сейчас дороже минимума на ${rub(diff)}`;
    return `<div class="ph-block" data-ph-appid="${esc(appid)}">
      <div class="ph-head"><b>История цены в Steam</b><span>с ${esc(fmt(s.since))}</span></div>
      ${svg(appid, 520, 84, true)}
      <div class="ph-stats">
        <span><small>Сейчас</small><b>${esc(rub(s.cur))}</b></span>
        <span><small>Минимум</small><b class="ph-low">${esc(rub(s.low))}</b><small>${esc(fmt(s.lowDate))}</small></span>
        <span><small>Максимум</small><b>${esc(rub(s.high))}</b></span>
      </div>
      <p class="ph-verdict${diff <= 0 && s.changes ? " ph-good" : ""}">${esc(verdict)}</p>
    </div>`;
  }

  function fillPending() {
    document.querySelectorAll(".ph-pending[data-ph-appid]").forEach((el) => {
      const html = block(el.dataset.phAppid);
      if (html) el.outerHTML = html; else el.remove();
    });
  }

  window.NPPriceHistory = { load, row, block, stats, svg };
  load();
})();
