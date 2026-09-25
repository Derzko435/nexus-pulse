/* NEXUS PULSE — header navigation: dropdowns, mobile menu, current section, quick search */
(function () {
  "use strict";

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  const header = $(".site-header");
  const panel = $("#navPanel");
  const toggle = $("#navToggle");
  const groups = $$(".nav-group");
  if (!header || !panel) return;

  const mqDesktop = window.matchMedia("(min-width: 900px)");
  const mqHover = window.matchMedia("(hover: hover) and (pointer: fine)");
  const isDesktop = () => mqDesktop.matches;

  /* ---------- Dropdowns / accordion ---------- */
  function triggerOf(g) { return g.querySelector("button.nav-trigger"); }
  function itemsOf(g) { return $$(".nav-dd a", g); }

  function setOpen(g, open) {
    const b = triggerOf(g);
    if (!b) return;
    g.classList.toggle("open", open);
    b.setAttribute("aria-expanded", String(open));
    if (!open) delete g.dataset.hover;
  }
  function closeAll(except) {
    groups.forEach((g) => { if (g !== except) setOpen(g, false); });
  }

  groups.forEach((g) => {
    const b = triggerOf(g);
    if (!b) return;
    let hideTimer = 0;

    b.addEventListener("click", (e) => {
      e.preventDefault();
      const wasOpen = g.classList.contains("open");
      // opened by hover a moment ago → a click should keep it open, not close it
      if (wasOpen && g.dataset.hover === "1") { delete g.dataset.hover; return; }
      closeAll(g);
      setOpen(g, !wasOpen);
    });

    g.addEventListener("mouseenter", () => {
      if (!isDesktop() || !mqHover.matches) return;
      clearTimeout(hideTimer);
      if (!g.classList.contains("open")) {
        closeAll(g);
        setOpen(g, true);
        g.dataset.hover = "1";
      }
    });
    g.addEventListener("mouseleave", () => {
      if (!isDesktop() || !mqHover.matches) return;
      hideTimer = setTimeout(() => setOpen(g, false), 220);
    });

    g.addEventListener("keydown", (e) => {
      const items = itemsOf(g);
      const idx = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!g.classList.contains("open")) { closeAll(g); setOpen(g, true); }
        (items[idx + 1] || items[0])?.focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!g.classList.contains("open")) { closeAll(g); setOpen(g, true); }
        (idx > 0 ? items[idx - 1] : items[items.length - 1])?.focus();
      } else if (e.key === "Home" && idx >= 0) {
        e.preventDefault(); items[0]?.focus();
      } else if (e.key === "End" && idx >= 0) {
        e.preventDefault(); items[items.length - 1]?.focus();
      } else if (e.key === "Escape" && g.classList.contains("open")) {
        e.preventDefault();
        e.stopPropagation();
        setOpen(g, false);
        b.focus();
      }
    });

    g.addEventListener("focusout", (e) => {
      if (isDesktop() && !g.contains(e.relatedTarget)) setOpen(g, false);
    });
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".nav-group") && isDesktop()) closeAll();
  });

  /* ---------- Mobile panel ---------- */
  function setPanel(open) {
    header.classList.toggle("nav-open", open);
    document.documentElement.classList.toggle("nav-lock", open);
    toggle?.setAttribute("aria-expanded", String(open));
    toggle?.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    if (open) {
      // раскрываем раздел, в котором сейчас находишься
      const cur = groups.find((g) => g.classList.contains("is-current") && triggerOf(g));
      closeAll(cur);
      if (cur) setOpen(cur, true);
    }
  }
  toggle?.addEventListener("click", (e) => {
    e.stopPropagation();
    setPanel(!header.classList.contains("nav-open"));
  });
  mqDesktop.addEventListener?.("change", () => { setPanel(false); closeAll(); });

  // any navigation click closes menus
  panel.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a) return;
    closeAll();
    setPanel(false);
    a.blur();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (searchOpen()) return; // search handles its own Escape
    if (groups.some((g) => g.classList.contains("open"))) closeAll();
    if (header.classList.contains("nav-open")) { setPanel(false); toggle?.focus(); }
  });

  /* ---------- Current section highlight ---------- */
  const sectionGroup = new Map(); // section id → { group, link }
  const linkEls = $$("a.nav-item, a.nav-direct", panel);
  // 1) direct matches first (link points to the section itself)
  linkEls.forEach((a) => {
    const id = (a.getAttribute("href") || "").slice(1);
    const el = id && document.getElementById(id);
    if (el && el.tagName === "SECTION" && !sectionGroup.has(id)) {
      sectionGroup.set(id, { group: a.closest(".nav-group"), link: a });
    }
  });
  // 2) links to blocks inside sections (tools, game of the day…)
  linkEls.forEach((a) => {
    const id = (a.getAttribute("href") || "").slice(1);
    const sec = id && document.getElementById(id)?.closest("section[id]");
    if (sec && !sectionGroup.has(sec.id)) sectionGroup.set(sec.id, { group: a.closest(".nav-group"), link: null });
  });

  function markCurrent(sectionId) {
    const hit = sectionGroup.get(sectionId);
    groups.forEach((g) => g.classList.toggle("is-current", !!hit && hit.group === g));
    linkEls.forEach((a) => {
      const on = !!hit && hit.link === a;
      a.classList.toggle("is-current", on);
      if (on) a.setAttribute("aria-current", "location"); else a.removeAttribute("aria-current");
    });
  }

  const visible = new Set();
  let io = null;
  function setupObserver() {
    io?.disconnect();
    visible.clear();
    const h = header.getBoundingClientRect().height || 72;
    io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) visible.add(en.target); else visible.delete(en.target); });
      let best = null;
      let bestTop = -Infinity;
      visible.forEach((el) => {
        const top = el.getBoundingClientRect().top;
        if (top > bestTop) { bestTop = top; best = el; }
      });
      markCurrent(best ? best.id : "");
    }, { rootMargin: `-${Math.round(h + 8)}px 0px -55% 0px`, threshold: 0 });
    $$("main section[id]").forEach((s) => io.observe(s));
  }
  if ("IntersectionObserver" in window) {
    setupObserver();
    let rt = 0;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(setupObserver, 250); });
  }

  /* ---------- Quick search (Ctrl+K or /) ---------- */
  let dlg = null;
  let results = [];
  let activeIdx = 0;
  function searchOpen() { return !!dlg && !dlg.hidden; }

  const norm = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").replace(/[^a-zа-я0-9]+/gi, " ").trim();
  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function buildIndex() {
    const idx = [];
    linkEls.forEach((a) => {
      const label = a.querySelector(".nav-item-label")?.textContent || a.textContent;
      const hint = a.querySelector(".nav-hint")?.textContent || "";
      const icon = a.querySelector(".nav-ico")?.textContent || "➜";
      const group = a.closest(".nav-group")?.querySelector(".nav-trigger span")?.textContent || "";
      idx.push({ kind: "Раздел", icon, title: label.trim(), hint, group, href: a.getAttribute("href") });
    });
    idx.push({ kind: "Раздел", icon: "💬", title: "Discord-сервер", hint: "Комьюнити NEXUS PULSE", href: "#community" });
    const NP = window.NexusPulse;
    (NP && NP.GAMES || []).forEach((g) => {
      idx.push({ kind: "Игра", icon: "🎮", title: g.title, hint: g.genre, game: g.title });
    });
    (Array.isArray(window.NP_GUIDES) ? window.NP_GUIDES : []).forEach((g) => {
      idx.push({ kind: "Гайд", icon: "📘", title: g.title, hint: g.tag || "Гайд", guide: g.id });
    });
    return idx;
  }

  function score(item, q) {
    const t = norm(item.title);
    const h = norm(item.hint);
    if (!q) return item.kind === "Раздел" ? 1 : 0;
    if (t.startsWith(q)) return 100 - t.length / 100;
    if (t.split(" ").some((w) => w.startsWith(q))) return 80;
    if (t.includes(q)) return 60;
    if (h.includes(q)) return 30;
    if (item.group && norm(item.group).startsWith(q)) return 20;
    return 0;
  }

  function renderResults() {
    const q = norm($("#npSearchInput", dlg).value);
    const index = buildIndex();
    results = index.map((it) => ({ it, s: score(it, q) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 9)
      .map((x) => x.it);
    activeIdx = 0;
    const list = $("#npSearchList", dlg);
    list.innerHTML = results.length
      ? results.map((r, i) => `
        <li><button type="button" class="nps-item${i === 0 ? " active" : ""}" data-i="${i}">
          <span class="nps-ico" aria-hidden="true">${esc(r.icon)}</span>
          <span class="nps-text"><b>${esc(r.title)}</b><small>${esc(r.hint)}</small></span>
          <span class="nps-kind">${esc(r.kind)}</span>
        </button></li>`).join("")
      : `<li class="nps-empty">Ничего не нашлось — попробуй другое слово</li>`;
  }

  function setActive(i) {
    const btns = $$(".nps-item", dlg);
    if (!btns.length) return;
    activeIdx = (i + btns.length) % btns.length;
    btns.forEach((b, k) => b.classList.toggle("active", k === activeIdx));
    btns[activeIdx].scrollIntoView({ block: "nearest" });
  }

  function go(r) {
    if (!r) return;
    closeSearch();
    closeAll();
    setPanel(false);
    if (r.href) {
      const el = document.querySelector(r.href);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", r.href);
      }
    } else if (r.game) {
      const input = $("#gameSearch");
      if (input) {
        input.value = r.game;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      $("#games")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (r.guide) {
      const card = document.querySelector(`[data-np-guide="${CSS.escape(r.guide)}"]`);
      if (card) card.click();
      else $("#guides")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function ensureDialog() {
    if (dlg) return dlg;
    dlg = document.createElement("div");
    dlg.className = "np-search";
    dlg.hidden = true;
    dlg.innerHTML = `
      <div class="nps-backdrop" data-close></div>
      <div class="nps-box glass" role="dialog" aria-modal="true" aria-label="Быстрый поиск">
        <div class="nps-field">
          <span aria-hidden="true">🔍</span>
          <input type="search" id="npSearchInput" placeholder="Найти раздел, игру или гайд…" autocomplete="off" />
          <kbd>Esc</kbd>
        </div>
        <ul class="nps-list" id="npSearchList"></ul>
      </div>`;
    document.body.appendChild(dlg);
    const input = $("#npSearchInput", dlg);
    input.addEventListener("input", renderResults);
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIdx + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIdx - 1); }
      else if (e.key === "Enter") { e.preventDefault(); go(results[activeIdx]); }
      else if (e.key === "Escape") { e.preventDefault(); closeSearch(); }
    });
    dlg.addEventListener("click", (e) => {
      if (e.target.closest("[data-close]")) return closeSearch();
      const b = e.target.closest(".nps-item");
      if (b) go(results[Number(b.dataset.i)]);
    });
    return dlg;
  }

  let lastFocus = null;
  function openSearch() {
    ensureDialog();
    lastFocus = document.activeElement;
    dlg.hidden = false;
    document.documentElement.classList.add("nav-lock");
    const input = $("#npSearchInput", dlg);
    input.value = "";
    renderResults();
    setTimeout(() => input.focus(), 0);
    if (window.npGoal) window.npGoal("search_open");
  }
  function closeSearch() {
    if (!dlg || dlg.hidden) return;
    dlg.hidden = true;
    if (!header.classList.contains("nav-open")) document.documentElement.classList.remove("nav-lock");
    if (lastFocus && lastFocus.focus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }

  $("#navSearchBtn")?.addEventListener("click", (e) => { e.stopPropagation(); openSearch(); });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K" || e.key === "л" || e.key === "Л")) {
      e.preventDefault();
      searchOpen() ? closeSearch() : openSearch();
    } else if (e.key === "/" && !typing && !searchOpen()) {
      e.preventDefault();
      openSearch();
    }
  });
})();
