/* ==========================================================================
   ok-lzr // 100 PROGRAMS · 进度展示页

   数据：window.DECK_DATA     由 tools/build.py 从 data/ 生成
   进度：优先读 progress.json，读不到就用内置的 window.DECK_PROGRESS
        在页面上勾的先存在浏览器本地，点「导出 progress.json」再覆盖进仓库

   这个页面的定位是「给别人看我的进度」，所以这里不放任务卡的思路和提示，
   只放：做到哪了、什么时候做的、每个项目是干什么的。
   ========================================================================== */

(function () {
  "use strict";

  var DATA = window.DECK_DATA || { meta: { stages: [] }, projects: [] };
  var PROJECTS = DATA.projects || [];
  var STAGES = (DATA.meta && DATA.meta.stages) || [];
  var NOTE = "每关做没做完 + 完成时间。levels 里第 1 个是第 1 关；times 跟它一一对应，没做完就是空字符串。";
  var STORE_KEY = "deck100.local";
  var FEED_MAX = 12;

  var state = {
    progress: {},
    repoUpdated: "",
    repoSource: "",
    dirty: false,
    filter: { stage: "all", status: "all", q: "" },
    pendingDetail: null,
  };

  /* ------------------------------ 小工具 ------------------------------ */

  function $(sel) { return document.querySelector(sel); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function levels(p) { return p.status === "ready" && p.levels ? p.levels : []; }

  function rawEntry(pid, n) {
    var e = state.progress[pid], lv = [], tm = [];
    if (Array.isArray(e)) { lv = e.map(Boolean); }
    else if (e && typeof e === "object") {
      lv = (e.levels || []).map(Boolean);
      tm = (e.times || []).map(String);
    }
    while (lv.length < n) lv.push(false);
    while (tm.length < n) tm.push("");
    lv = lv.slice(0, n); tm = tm.slice(0, n);
    for (var i = 0; i < n; i++) { if (!lv[i]) tm[i] = ""; }
    return { levels: lv, times: tm };
  }
  function arrFor(p) { return rawEntry(p.id, levels(p).length).levels; }
  function timesFor(p) { return rawEntry(p.id, levels(p).length).times; }
  function doneIn(p) { return arrFor(p).filter(Boolean).length; }
  function isDone(p) { var n = levels(p).length; return n > 0 && doneIn(p) === n; }
  function isDoing(p) { var d = doneIn(p); return d > 0 && d < levels(p).length; }

  function stars(d) {
    var full = Math.floor(d), half = d - full >= 0.5;
    return "★".repeat(full) + (half ? "½" : "") + "☆".repeat(Math.max(0, 5 - full - (half ? 1 : 0)));
  }
  function nowCN() {
    var d = new Date();
    var utc = d.getTime() + d.getTimezoneOffset() * 60000;
    return new Date(utc + 8 * 3600000);
  }
  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function stamp(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }
  function toast(msg) {
    var t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove("show"); }, 2600);
  }

  /* ------------------------------ 时钟 ------------------------------ */

  function tickClock() {
    var d = nowCN();
    $("#clock").textContent = pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    var week = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
    $("#clock-date").textContent = d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " 星期" + week + " UTC+8";
  }

  /* --------------------------- 进度的读写 --------------------------- */

  function readLocal() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function writeLocal() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ updated: state.repoUpdated, progress: state.progress }));
    } catch (e) { /* 隐私模式下写不了，忽略 */ }
  }
  function clearLocal() { try { localStorage.removeItem(STORE_KEY); } catch (e) {} }

  function normalize(obj) {
    var out = {};
    if (obj && obj.progress) {
      Object.keys(obj.progress).forEach(function (k) {
        var e = obj.progress[k], lv = [], tm = [];
        if (Array.isArray(e)) { lv = e.map(Boolean); }
        else if (e && typeof e === "object") {
          lv = (e.levels || []).map(Boolean);
          tm = (e.times || []).map(String);
        }
        out[k] = { levels: lv, times: tm };
      });
    }
    return out;
  }

  function loadProgress() {
    var fallback = { version: 2, updated: "（内置副本）", progress: window.DECK_PROGRESS || {} };
    var done = function (repo) {
      state.repoUpdated = repo.updated || "";
      state.repoSource = repo.__source || "";
      var local = readLocal();
      var baseline = normalize(repo);
      if (local && normalize(local).progress) {
        var sameBase = (local.updated || "") === (state.repoUpdated || "");
        var localProg = normalize(local);
        if (sameBase) {
          state.progress = localProg;
          state.dirty = JSON.stringify(localProg) !== JSON.stringify(baseline);
        } else {
          state.progress = baseline;
          state.dirty = false;
          writeLocal();
          toast("progress.json 有新版本，已按文件为准刷新");
        }
      } else {
        state.progress = baseline;
        state.dirty = false;
      }
      renderAll();
      if (state.pendingDetail) {
        var pid = state.pendingDetail;
        state.pendingDetail = null;
        openDetail(pid);
      }
    };

    fetch("progress.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (j) { j.__source = "progress.json"; done(j); })
      .catch(function () {
        var f = fallback;
        f.__source = "内置副本（直接双击打开时读不到 progress.json）";
        done(f);
      });
  }

  function exportObject() {
    var o = {};
    PROJECTS.forEach(function (p) {
      if (levels(p).length) {
        var e = rawEntry(p.id, levels(p).length);
        o[p.id] = { levels: e.levels, times: e.times };
      }
    });
    return { version: 2, updated: stamp(nowCN()), note: NOTE, progress: o };
  }

  /* ------------------------------ 统计 ------------------------------ */

  function allEvents() {
    var evs = [];
    PROJECTS.forEach(function (p) {
      var ls = levels(p);
      if (!ls.length) return;
      var e = rawEntry(p.id, ls.length);
      e.times.forEach(function (t, i) {
        if (e.levels[i] && t) {
          evs.push({ at: t, pid: p.id, title: p.title, n: i + 1, name: ls[i].name });
        }
      });
    });
    evs.sort(function (a, b) { return a.at < b.at ? 1 : (a.at > b.at ? -1 : 0); });
    return evs;
  }

  function stats() {
    var written = PROJECTS.filter(function (p) { return levels(p).length > 0; });
    var totalLevels = 0, doneLevels = 0, doneProjects = 0;
    written.forEach(function (p) {
      totalLevels += levels(p).length;
      doneLevels += doneIn(p);
      if (isDone(p)) doneProjects++;
    });

    /* 连续过关 = 从「当前卡住的那一关」往前数，中间没断的那一段。
       （不是从最后一关往前数——那样只要后面还有没做的项目就永远是 0） */
    var flat = [];
    written.forEach(function (p) {
      arrFor(p).forEach(function (ok) { flat.push(ok); });
    });
    var firstUndone = flat.indexOf(false);
    var upto = firstUndone === -1 ? flat.length : firstUndone;
    var streak = 0;
    for (var b = upto - 1; b >= 0; b--) {
      if (flat[b]) streak++;
      else break;
    }

    var next = null;
    for (var k = 0; k < PROJECTS.length; k++) {
      var p = PROJECTS[k];
      if (!levels(p).length) continue;
      var idx = arrFor(p).indexOf(false);
      if (idx >= 0) { next = { project: p, levelIndex: idx }; break; }
    }

    var evs = allEvents();
    var month = stamp(nowCN()).slice(0, 7);
    var thisMonth = evs.filter(function (e) { return e.at.slice(0, 7) === month; }).length;

    var currentStage = next ? next.project.stage : (written.length ? written[written.length - 1].stage : (STAGES[0] || {}).id);
    return {
      totalLevels: totalLevels, doneLevels: doneLevels, doneProjects: doneProjects,
      written: written.length, next: next, currentStage: currentStage,
      streak: streak, events: evs, thisMonth: thisMonth
    };
  }

  /* --------------------------- 01 总览 --------------------------- */

  function renderOverview() {
    var s = stats();
    var pct = s.totalLevels ? Math.round(s.doneLevels / s.totalLevels * 100) : 0;
    var pPct = s.written ? Math.round(s.doneProjects / s.written * 100) : 0;
    var C1 = 2 * Math.PI * 86, C2 = 2 * Math.PI * 70;

    $("#ring-main").setAttribute("stroke-dasharray", (C1 * pct / 100) + " " + C1);
    $("#ring-project").setAttribute("stroke-dasharray", (C2 * pPct / 100) + " " + C2);
    $("#ring-percent").textContent = pct + "%";
    $("#ring-detail").textContent = s.doneLevels + " / " + s.totalLevels + " 关";

    $("#kpi-levels").textContent = s.doneLevels;
    $("#kpi-levels-total").textContent = "/ " + s.totalLevels;
    $("#kpi-projects").textContent = s.doneProjects;
    $("#kpi-projects-total").textContent = "/ " + s.written;
    $("#kpi-streak").textContent = s.streak;

    var last = s.events[0];
    $("#kpi-last").textContent = last ? last.at.slice(5) : "—";
    $("#kpi-last-note").textContent = last
      ? ("完成了 " + last.pid + " 第 " + last.n + " 关")
      : "还没有打卡记录";

    var stage = STAGES.filter(function (x) { return x.id === s.currentStage; })[0] || STAGES[0];
    var sub;
    if (!s.doneLevels) {
      sub = "还没开始打卡。第一个目标是 001 温度转换器 的第 1 关。";
    } else if (s.next) {
      sub = "已完成 " + s.doneLevels + " / " + s.totalLevels + " 关 · 本月完成 " + s.thisMonth + " 关 · 现在在 "
        + (stage ? stage.name + "（" + stage.range + "）" : "")
        + " · 下一个目标：" + s.next.project.id + " 第 " + (s.next.levelIndex + 1) + " 关 · "
        + levels(s.next.project)[s.next.levelIndex].name;
    } else {
      sub = "已写好任务卡的项目全部做完了，共 " + s.doneLevels + " 关。下一批任务卡写完就继续。";
    }
    $("#hero-sub").textContent = sub;

    var feed = $("#feed");
    feed.innerHTML = "";
    if (!s.events.length) {
      feed.appendChild(el("div", "empty", "还没有动态。做掉第一关，这里就会亮起第一条记录。"));
    } else {
      s.events.slice(0, FEED_MAX).forEach(function (e) {
        var row = el("div", "tl-row");
        row.appendChild(el("span", "tl-time", e.at));
        var txt = el("span", "tl-text");
        txt.innerHTML = "完成了 <b>" + esc(e.pid) + "</b> 第 " + e.n + " 关 · " + esc(e.name)
          + "　<span class='tl-proj'>" + esc(e.title) + "</span>";
        row.appendChild(txt);
        feed.appendChild(row);
      });
      if (s.events.length > FEED_MAX) {
        feed.appendChild(el("div", "tl-more", "…还有 " + (s.events.length - FEED_MAX) + " 条更早的记录"));
      }
    }
  }

  /* --------------------------- 02 阶段 --------------------------- */

  function renderRoadmap() {
    var wrap = $("#stage-cards");
    wrap.innerHTML = "";
    STAGES.forEach(function (st) {
      var inStage = PROJECTS.filter(function (p) { return p.stage === st.id; });
      var written = inStage.filter(function (p) { return levels(p).length > 0; });
      var total = 0, done = 0, doneP = 0;
      inStage.forEach(function (p) {
        total += levels(p).length; done += doneIn(p);
        if (isDone(p)) doneP++;
      });
      var pct = total ? Math.round(done / total * 100) : 0;

      var card = el("div", "panel stage-card");
      var top = el("div", "sc-top");
      top.appendChild(el("div", "sc-name", st.name));
      top.appendChild(el("div", "sc-range", st.range));
      card.appendChild(top);
      card.appendChild(el("div", "sc-line", st.oneLine));
      var bar = el("div", "bar");
      var fill = el("i");
      fill.style.width = pct + "%";
      bar.appendChild(fill);
      card.appendChild(bar);
      var stat = el("div", "sc-stat");
      stat.appendChild(el("span", null, written.length ? done + " / " + total + " 关" : "任务卡待编写"));
      stat.appendChild(el("span", null, doneP + " / " + inStage.length + " 项目"));
      card.appendChild(stat);
      card.appendChild(el("div", "sc-out", "产出：" + st.outcome));
      wrap.appendChild(card);
    });
  }

  /* -------------------------- 03 项目库 -------------------------- */

  function statusOf(p) {
    if (!levels(p).length) return "planned";
    if (isDone(p)) return "done";
    if (isDoing(p)) return "doing";
    return "ready";
  }
  var STATUS_TEXT = { ready: "还没开始", doing: "进行中", done: "已完成", planned: "待编写" };

  function renderFilters() {
    var box = $("#filter-stage");
    box.innerHTML = "";
    var all = el("button", "chip" + (state.filter.stage === "all" ? " active" : ""), "全部阶段");
    all.addEventListener("click", function () { state.filter.stage = "all"; renderFilters(); renderLibrary(); });
    box.appendChild(all);
    STAGES.forEach(function (st) {
      var b = el("button", "chip" + (state.filter.stage === st.id ? " active" : ""), st.range + " " + st.name);
      b.addEventListener("click", function () { state.filter.stage = st.id; renderFilters(); renderLibrary(); });
      box.appendChild(b);
    });
  }

  function visibleProjects() {
    var q = state.filter.q.trim().toLowerCase();
    return PROJECTS.filter(function (p) {
      if (state.filter.stage !== "all" && p.stage !== state.filter.stage) return false;
      if (state.filter.status !== "all" && statusOf(p) !== state.filter.status) return false;
      if (q) {
        var hay = (p.id + " " + p.title + " " + (p.summary || "")).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
  }

  function renderLibrary() {
    var grid = $("#project-grid");
    grid.innerHTML = "";
    var list = visibleProjects();
    $("#lib-count").textContent = "显示 " + list.length + " / " + PROJECTS.length + " 个";
    if (!list.length) {
      grid.appendChild(el("div", "empty", "没有匹配的项目，换个关键词或清掉筛选。"));
      return;
    }
    list.forEach(function (p) {
      var st = statusOf(p);
      var n = levels(p).length;
      var card = el("div", "pcard" + (st === "done" ? " done" : "") + (st === "planned" ? " locked" : ""));
      var head = el("div", "pcard-head");
      head.appendChild(el("span", "pcard-id", p.id));
      head.appendChild(el("span", "pcard-title", p.title));
      head.appendChild(el("span", "pcard-stars", stars(p.difficulty)));
      card.appendChild(head);
      card.appendChild(el("div", "pcard-sum", p.summary || ""));
      var foot = el("div", "pcard-foot");
      var pips = el("div", "pips");
      if (n) {
        arrFor(p).forEach(function (on) {
          pips.appendChild(el("i", on ? "on" : ""));
        });
      } else {
        pips.appendChild(el("span", "count", "任务卡待编写"));
      }
      foot.appendChild(pips);
      foot.appendChild(el("span", "tag " + st, STATUS_TEXT[st]));
      card.appendChild(foot);
      card.addEventListener("click", function () { openDetail(p.id); });
      grid.appendChild(card);
    });
  }

  /* -------------------------- 项目详情 -------------------------- */

  function openDetail(pid, focusLevel) {
    var p = PROJECTS.filter(function (x) { return x.id === pid; })[0];
    if (!p) return;
    closeDetail();
    setHash(pid);

    var back = el("div", "detail-backdrop");
    back.id = "detail-backdrop";
    var d = el("div", "detail");

    var close = el("button", "detail-close", "✕");
    close.addEventListener("click", closeDetail);
    d.appendChild(close);

    var h = el("h2");
    h.innerHTML = '<span class="d-id">' + esc(p.id) + "</span>" + esc(p.title);
    d.appendChild(h);

    var meta = el("div", "d-meta");
    meta.innerHTML = "难度 <b>" + esc(stars(p.difficulty)) + " " + esc(String(p.difficulty)) + " / 5</b>　·　"
      + esc((p.stageRange || "") + " · " + (p.stageName || ""))
      + (levels(p).length ? "　·　" + levels(p).length + " 关　·　" + esc(p.hoursLine || "") : "");
    d.appendChild(meta);

    d.appendChild(el("div", "d-sum", p.summary || ""));

    if (!levels(p).length) {
      var nb = el("div", "d-block");
      nb.appendChild(el("div", "d-lab", "STATUS"));
      nb.appendChild(el("p", null, "这个项目还没写任务卡，在路线上的位置是：" + (p.stageRange || "") + " · " + (p.stageName || "") + "。"));
      d.appendChild(nb);
      back.appendChild(d);
      document.body.appendChild(back);
      back.addEventListener("click", function (e) { if (e.target === back) closeDetail(); });
      document.addEventListener("keydown", escClose);
      return;
    }

    var head = el("div", "d-progress");
    var dn = doneIn(p);
    head.innerHTML = "进度 <b>" + dn + " / " + levels(p).length + "</b> 关"
      + (dn === levels(p).length ? "　·　已完成 ✅" : "");
    d.appendChild(head);

    var list = el("div", "level-list");
    var ls = levels(p), tm = timesFor(p);
    ls.forEach(function (lv, i) {
      var ok = arrFor(p)[i];
      var box = el("div", "level" + (ok ? " done" : ""));

      var row = el("div", "level-head");
      var tick = el("div", "tick" + (ok ? " on" : ""));
      tick.title = ok ? "点一下取消勾选" : "做完了，勾一下";
      tick.addEventListener("click", function (e) {
        e.stopPropagation();
        toggle(p, i);
        box.classList.toggle("done", arrFor(p)[i]);
        tick.classList.toggle("on", arrFor(p)[i]);
        var tspan = row.querySelector(".lv-time");
        tspan.textContent = timesFor(p)[i] ? ("完成于 " + timesFor(p)[i]) : (lv.time || "");
        var pbar = d.querySelector(".d-progress b");
        if (pbar) pbar.textContent = doneIn(p) + " / " + ls.length;
        afterProgressChange();
      });
      row.appendChild(tick);
      row.appendChild(el("span", "lv-n", "#" + lv.n));
      row.appendChild(el("span", "lv-name", lv.name));
      row.appendChild(el("span", "lv-time", tm[i] ? ("完成于 " + tm[i]) : (lv.time || "")));
      box.appendChild(row);
      list.appendChild(box);
    });
    d.appendChild(list);
    d.appendChild(el("p", "dim-p", "任务卡（这一关要做出什么效果、要用到哪些语法、自检清单）在仓库里 " + p.dir + "/README.md，不放在网站上。"));

    back.appendChild(d);
    document.body.appendChild(back);
    back.addEventListener("click", function (e) { if (e.target === back) closeDetail(); });
    document.addEventListener("keydown", escClose);
    document.body.style.overflow = "hidden";
  }

  function escClose(e) { if (e.key === "Escape") closeDetail(); }

  /* 让每个项目都能被链接分享：#p=001 直接打开 001 的详情 */
  function setHash(pid) {
    try { history.replaceState(null, "", "#p=" + pid); }
    catch (e) { location.hash = "p=" + pid; }
  }
  function clearHash() {
    if (location.hash.indexOf("#p=") !== 0) return;
    try { history.replaceState(null, "", location.pathname + location.search + "#library"); }
    catch (e) { location.hash = "library"; }
  }
  function hashTarget() {
    var m = /^#p=(\d{1,3})$/.exec(location.hash);
    return m ? m[1].padStart(3, "0") : null;
  }

  function closeDetail() {
    var b = $("#detail-backdrop");
    if (b) b.remove();
    document.removeEventListener("keydown", escClose);
    document.body.style.overflow = "";
    clearHash();
  }

  /* -------------------------- 勾选与同步 -------------------------- */

  function toggle(p, i) {
    var n = levels(p).length;
    var e = rawEntry(p.id, n);
    e.levels[i] = !e.levels[i];
    e.times[i] = e.levels[i] ? stamp(nowCN()) : "";
    state.progress[p.id] = e;
    state.dirty = true;
    writeLocal();
    var allDone = e.levels.filter(Boolean).length === n;
    toast(allDone
      ? (p.id + " " + p.title + " 全部做完了 🎉")
      : (p.id + " 第 " + (i + 1) + " 关" + (e.levels[i] ? "完成 ✅" : "已取消")));
  }

  function afterProgressChange() {
    renderOverview();
    renderRoadmap();
    renderLibrary();
    renderSync();
  }

  function renderSync() {
    var s = stats();
    var lines = [];
    lines.push("仓库文件   " + (state.repoUpdated || "未知") + (state.repoSource ? "　（来源：" + state.repoSource + "）" : ""));
    lines.push("本地改动   " + (state.dirty ? "有未导出的勾选（先存在浏览器里，刷新不会丢）" : "与文件一致"));
    lines.push("总进度     " + s.doneLevels + " / " + s.totalLevels + " 关　·　完成项目 " + s.doneProjects + " / " + s.written + "　·　本月 " + s.thisMonth + " 关");
    $("#sync-status").textContent = lines.join("\n");
  }

  function doExport() {
    var obj = exportObject();
    var blob = new Blob([JSON.stringify(obj, null, 2) + "\n"], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "progress.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
    state.dirty = false;
    state.repoUpdated = obj.updated;
    writeLocal();
    renderSync();
    toast("已导出 progress.json，覆盖进仓库的 web/progress.json 再 push");
  }

  function doCopy() {
    var text = JSON.stringify(exportObject(), null, 2) + "\n";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { toast("已复制 progress.json 的内容"); },
        function () { toast("复制失败，改用「导出」按钮吧"); }
      );
    } else {
      toast("这个浏览器不支持自动复制，用「导出」按钮");
    }
  }

  function doImport(file) {
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var j = JSON.parse(fr.result);
        state.progress = normalize(j);
        state.repoUpdated = j.updated || "";
        state.repoSource = "手动导入";
        state.dirty = false;
        writeLocal();
        afterProgressChange();
        toast("已导入：" + file.name);
      } catch (e) {
        toast("这个文件不是合法的 JSON，导入失败");
      }
    };
    fr.readAsText(file, "utf-8");
  }

  /* ------------------------------ 导航 ------------------------------ */

  function initNav() {
    var links = Array.prototype.slice.call(document.querySelectorAll(".nav a"));
    var sections = links.map(function (a) { return document.querySelector(a.getAttribute("href")); });
    function onScroll() {
      var y = window.scrollY + 200, idx = 0;
      sections.forEach(function (sec, i) { if (sec && sec.offsetTop <= y) idx = i; });
      links.forEach(function (a, i) { a.classList.toggle("active", i === idx); });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ------------------------------ 启动 ------------------------------ */

  function renderAll() {
    renderOverview();
    renderRoadmap();
    renderFilters();
    renderLibrary();
    renderSync();
  }

  function init() {
    tickClock();
    setInterval(tickClock, 1000);
    initNav();

    $("#search").addEventListener("input", function (e) {
      state.filter.q = e.target.value;
      renderLibrary();
    });
    document.querySelectorAll("#filter-status .chip").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filter-status .chip").forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        state.filter.status = b.getAttribute("data-status");
        renderLibrary();
      });
    });
    $("#btn-export").addEventListener("click", doExport);
    $("#btn-copy").addEventListener("click", doCopy);
    $("#file-import").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) doImport(e.target.files[0]);
      e.target.value = "";
    });
    $("#btn-reset").addEventListener("click", function () {
      clearLocal();
      state.dirty = false;
      toast("已清空浏览器里的改动，重新读取文件");
      loadProgress();
    });

    state.pendingDetail = hashTarget();
    window.addEventListener("hashchange", function () {
      var t = hashTarget();
      if (t) openDetail(t);
      else closeDetail();
    });

    loadProgress();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
