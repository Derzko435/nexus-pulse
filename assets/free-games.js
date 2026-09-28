/* NEXUS PULSE — free-games/: keeps the prerendered tables honest between rebuilds.
 * Rows carry data-start / data-end (ISO, MSK). A giveaway whose end has passed is hidden;
 * an upcoming one whose start has passed moves to the «now» table. No network, no data changes:
 * the static HTML stays the source for search engines, the page itself is rebuilt after every data refresh. */
(function () {
  "use strict";
  function t(v) { var d = v ? Date.parse(v) : NaN; return isNaN(d) ? null : d; }
  function tick() {
    var now = Date.now();
    var nowBody = document.querySelector("#fgNowTable tbody");
    var soonBody = document.querySelector("#fgSoonTable tbody");
    var rows = document.querySelectorAll(".fg-page tr[data-end], .fg-page tr[data-start]");
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i], end = t(r.getAttribute("data-end")), start = t(r.getAttribute("data-start"));
      if (end !== null && end <= now) { r.hidden = true; continue; }
      if (soonBody && nowBody && r.parentNode === soonBody && start !== null && start <= now) {
        // «now» table has no start column: drop it and turn the link into a claim button
        var cells = r.children;
        if (cells.length === 6) {
          r.removeChild(cells[2]);
          var a = r.querySelector("a");
          if (a) { a.className = "btn btn-primary btn-sm"; a.textContent = "Забрать"; }
        }
        nowBody.appendChild(r);
      }
    }
    if (soonBody) {
      var left = 0;
      for (var k = 0; k < soonBody.children.length; k++) if (!soonBody.children[k].hidden) left++;
      var soonWrap = soonBody.closest(".sp-table-wrap");
      if (soonWrap) soonWrap.hidden = left === 0;
    }
    var empty = document.getElementById("fgNowEmpty");
    if (empty && nowBody) {
      var visible = 0;
      for (var j = 0; j < nowBody.children.length; j++) if (!nowBody.children[j].hidden) visible++;
      empty.hidden = visible > 0;
      var wrap = nowBody.closest(".sp-table-wrap");
      if (wrap) wrap.hidden = visible === 0;
    }
  }
  tick();
  setInterval(tick, 60000);
})();
