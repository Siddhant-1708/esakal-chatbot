/* ============================================================================
   Ask Esakal — embeddable news Q&A widget
   Single-file vanilla JS IIFE. All CSS injected via <style>.
   Self-initialises on  <div data-ask-esakal></div>.
   Config (set on window before this script loads):
     window.ESAKAL_API_BASE        — backend base URL ('' = same origin, 'mock' = demo)
     window.ESAKAL_SAKAL_PLUS_URL  — subscription landing URL
   All CSS classes are prefixed  ask-esakal-  and element IDs  ae- .
   ========================================================================== */
(function () {
  "use strict";
  if (window.__askEsakalLoaded) return;
  window.__askEsakalLoaded = true;

  /* ---- config --------------------------------------------------------- */
  var API_BASE = (typeof window.ESAKAL_API_BASE === "string") ? window.ESAKAL_API_BASE : "";
  var SAKAL_PLUS_URL = window.ESAKAL_SAKAL_PLUS_URL || "https://www.esakal.com/subscription";
  var FREE_LIMIT = 9999; // disabled during testing
  var IS_MOCK = API_BASE === "mock";

  /* ---- i18n ----------------------------------------------------------- */
  var lang = "mr";

  var I18N = {
    mr: {
      subtitle:    "आजच्या बातम्यांची उत्तरे, मराठीत.",
      tryAsking:   "विचारून पहा",
      placeholder: "आजच्या बातम्यांबद्दल विचारा…",
      askBtn:      "विचारा",
      emptyH:      "आजच्या बातम्या विचारा",
      emptyP:      "मराठीत प्रश्न विचारा आणि एसकाळच्या बातम्यांवर आधारित थेट उत्तर मिळवा — उद्धृत केलेल्या प्रत्येक लेखाच्या लिंकसह.",
      youAsked:    "तुम्ही विचारले",
      sources:     "स्रोत",
      steps:       ["नियोजन", "शोध", "तपासणी", "उत्तर"],
      error:       "माफ करा — काहीतरी चूक झाली. कृपया पुन्हा प्रयत्न करा.",
      attrib:      "उत्तरे <b>एसकाळ</b> च्या बातम्यांवर आधारित.",
      toggleLabel: "EN",
    },
    en: {
      subtitle:    "Answers from today's reporting, in English.",
      tryAsking:   "Try asking",
      placeholder: "Ask anything about today's news…",
      askBtn:      "Ask",
      emptyH:      "Ask about today's news",
      emptyP:      "Type a question and get a concise answer drawn only from Esakal's own reporting — with links to every article cited.",
      youAsked:    "You asked",
      sources:     "Sources",
      steps:       ["Planning", "Retrieving", "Checking", "Answering"],
      error:       "Sorry — something went wrong reaching the newsroom. Please try again.",
      attrib:      "Answers sourced from <b>Esakal</b> reporting.",
      toggleLabel: "मराठी",
    }
  };

  function t(key) { return I18N[lang][key]; }

  /* ---- styles --------------------------------------------------------- */
  var styles = [
  ".ask-esakal-widget *{box-sizing:border-box;}",
  ".ask-esakal-widget{",
  "  --ae-brand:#3c6afb;",
  "  --ae-brand-dark:#2a52d8;",
  "  --ae-brand-deep:#1e3aa6;",
  "  --ae-ink:#0f1729;",
  "  --ae-text:#3b4254;",
  "  --ae-muted:#697086;",
  "  --ae-faint:#9aa2b4;",
  "  --ae-footer:#aeb5c4;",
  "  --ae-hairline:#eceef4;",
  "  --ae-hairline-strong:#dfe3ed;",
  "  --ae-input-border:#cbd2e0;",
  "  --ae-card:#ffffff;",
  "  --ae-chip-bg:#ffffff;",
  "  --ae-surface:#f7f9ff;",
  "  --ae-serif:Georgia,'Times New Roman','Noto Serif',serif;",
  "  max-width:720px;width:100%;margin:0 auto;",
  "  background:var(--ae-card);",
  "  border:1px solid var(--ae-hairline-strong);",
  "  border-radius:16px;",
  "  box-shadow:0 1px 2px rgba(30,41,82,.05),0 10px 34px rgba(30,41,82,.11);",
  "  overflow:hidden;font-family:inherit;color:var(--ae-text);line-height:1.5;",
  "  -webkit-font-smoothing:antialiased;",
  "}",

  /* header */
  ".ask-esakal-header{",
  "  position:relative;",
  "  background:linear-gradient(180deg,#4f7bff 0%,var(--ae-brand) 58%,#2f59ea 100%);",
  "  color:#fff;padding:18px 20px 17px;border-bottom:1px solid rgba(255,255,255,.06);",
  "}",
  ".ask-esakal-header::after{content:'';position:absolute;left:0;right:0;bottom:0;height:1px;background:rgba(255,255,255,.16);}",
  ".ask-esakal-header-top{display:flex;align-items:center;justify-content:space-between;gap:12px;}",
  ".ask-esakal-brand{display:flex;align-items:center;gap:9px;min-width:0;}",
  ".ask-esakal-mark{flex:0 0 auto;width:26px;height:26px;border-radius:7px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;line-height:1;}",
  ".ask-esakal-title{font-size:1.06rem;font-weight:700;letter-spacing:.005em;margin:0;color:#fff;}",
  ".ask-esakal-title .ask-esakal-thin{font-weight:500;opacity:.62;}",
  ".ask-esakal-sub{margin:5px 0 0;font-size:.8rem;color:rgba(255,255,255,.66);letter-spacing:.01em;}",

  /* lang toggle */
  ".ask-esakal-lang-toggle{flex:0 0 auto;appearance:none;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:999px;color:#fff;cursor:pointer;font:inherit;font-size:.75rem;font-weight:700;letter-spacing:.04em;padding:5px 13px;transition:background .15s ease,border-color .15s ease;white-space:nowrap;}",
  ".ask-esakal-lang-toggle:hover{background:rgba(255,255,255,.22);border-color:rgba(255,255,255,.4);}",
  ".ask-esakal-lang-toggle:active{background:rgba(255,255,255,.30);}",

  /* counter pill (kept for CSS completeness) */
  ".ask-esakal-counter{display:none;}",

  /* suggestions */
  ".ask-esakal-suggest-wrap{padding:14px 20px 4px;background:var(--ae-surface);border-bottom:1px solid var(--ae-hairline);}",
  ".ask-esakal-suggest-label{font-size:.66rem;text-transform:uppercase;letter-spacing:.13em;color:var(--ae-faint);font-weight:700;margin:0 0 9px 2px;}",
  ".ask-esakal-chips{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:14px;}",
  ".ask-esakal-chip{appearance:none;border:1px solid var(--ae-hairline-strong);background:var(--ae-chip-bg);color:var(--ae-brand);font:inherit;font-size:.82rem;font-weight:500;padding:8px 14px;border-radius:999px;cursor:pointer;box-shadow:0 1px 1.5px rgba(30,41,82,.05);transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease,background .12s ease;white-space:nowrap;}",
  ".ask-esakal-chip:hover{border-color:var(--ae-brand);background:#fff;box-shadow:0 3px 10px rgba(30,41,82,.12);transform:translateY(-1px);}",
  ".ask-esakal-chip:active{transform:translateY(0);box-shadow:0 1px 2px rgba(30,41,82,.10);}",

  /* conversation */
  ".ask-esakal-convo{max-height:440px;overflow-y:auto;padding:6px 20px 4px;scroll-behavior:smooth;}",
  ".ask-esakal-convo::-webkit-scrollbar{width:9px;}",
  ".ask-esakal-convo::-webkit-scrollbar-thumb{background:#dfe4ec;border-radius:9px;border:2px solid #fff;}",

  /* empty state */
  ".ask-esakal-empty{text-align:center;padding:30px 16px 30px;color:var(--ae-faint);}",
  ".ask-esakal-empty-mark{width:46px;height:46px;border-radius:12px;margin:0 auto 14px;background:linear-gradient(170deg,#eef3ff,#e0e9ff);border:1px solid var(--ae-hairline-strong);display:flex;align-items:center;justify-content:center;color:var(--ae-brand);font-size:20px;}",
  ".ask-esakal-empty-h{font-size:.95rem;font-weight:600;color:var(--ae-text);margin:0 0 4px;}",
  ".ask-esakal-empty-p{font-size:.82rem;color:var(--ae-faint);max-width:340px;margin:0 auto;line-height:1.55;}",

  /* exchange */
  ".ask-esakal-exchange{padding:18px 0;border-bottom:1px solid var(--ae-hairline);}",
  ".ask-esakal-exchange:last-child{border-bottom:0;}",
  ".ask-esakal-kicker{font-size:.64rem;text-transform:uppercase;letter-spacing:.14em;font-weight:700;color:var(--ae-faint);margin:0 0 6px;display:flex;align-items:center;gap:7px;}",
  ".ask-esakal-kicker::after{content:'';flex:1;height:1px;background:var(--ae-hairline);}",
  ".ask-esakal-question{font-size:1.16rem;line-height:1.34;font-weight:600;color:var(--ae-ink);margin:0 0 16px;letter-spacing:-.005em;}",
  ".ask-esakal-answer{font-family:var(--ae-serif);font-size:1.01rem;line-height:1.68;color:var(--ae-ink);margin:0;}",
  ".ask-esakal-answer p{margin:0 0 .7em;}",
  ".ask-esakal-answer p:last-child{margin-bottom:0;}",
  ".ask-esakal-cite{font-family:inherit;font-size:.66em;font-weight:700;line-height:0;vertical-align:super;color:var(--ae-brand);text-decoration:none;padding:0 1px;cursor:pointer;}",
  ".ask-esakal-cite:hover{color:var(--ae-brand-dark);}",

  /* sources */
  ".ask-esakal-sources{margin-top:16px;}",
  ".ask-esakal-sources-label{font-size:.64rem;text-transform:uppercase;letter-spacing:.13em;font-weight:700;color:var(--ae-faint);margin:0 0 9px;}",
  ".ask-esakal-source{display:flex;gap:12px;align-items:flex-start;text-decoration:none;color:inherit;padding:11px 13px;border:1px solid var(--ae-hairline-strong);border-radius:10px;background:#fff;margin-bottom:8px;transition:border-color .12s ease,box-shadow .12s ease,transform .12s ease;}",
  ".ask-esakal-source:last-child{margin-bottom:0;}",
  ".ask-esakal-source:hover{border-color:var(--ae-brand);box-shadow:0 4px 14px rgba(30,41,82,.10);transform:translateY(-1px);}",
  ".ask-esakal-source-num{flex:0 0 auto;width:24px;height:24px;border-radius:6px;margin-top:1px;background:var(--ae-brand);color:#fff;font-size:.72rem;font-weight:700;display:flex;align-items:center;justify-content:center;}",
  ".ask-esakal-source-body{min-width:0;flex:1;}",
  ".ask-esakal-source-head{font-size:.9rem;font-weight:600;color:var(--ae-ink);line-height:1.38;margin:0 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}",
  ".ask-esakal-source-meta{font-size:.72rem;color:var(--ae-muted);display:flex;align-items:center;gap:7px;flex-wrap:wrap;}",
  ".ask-esakal-source-tag{color:var(--ae-brand);font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:.66rem;}",
  ".ask-esakal-source-dot{width:3px;height:3px;border-radius:50%;background:var(--ae-faint);}",
  ".ask-esakal-source-arrow{flex:0 0 auto;color:var(--ae-faint);align-self:center;transition:transform .12s ease,color .12s ease;}",
  ".ask-esakal-source:hover .ask-esakal-source-arrow{color:var(--ae-brand);transform:translateX(2px);}",

  /* thinking stepper */
  ".ask-esakal-thinking{padding:2px 0 0;}",
  ".ask-esakal-steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px;}",
  ".ask-esakal-step{display:flex;align-items:center;gap:11px;padding:7px 0;font-size:.86rem;color:var(--ae-faint);transition:color .25s ease;}",
  ".ask-esakal-step-ico{flex:0 0 auto;width:20px;height:20px;border-radius:50%;border:1.5px solid var(--ae-hairline-strong);background:#fff;display:flex;align-items:center;justify-content:center;position:relative;transition:border-color .25s ease,background .25s ease;}",
  ".ask-esakal-step-ico svg{width:11px;height:11px;opacity:0;transition:opacity .2s ease;}",
  ".ask-esakal-step.is-active{color:var(--ae-brand);font-weight:600;}",
  ".ask-esakal-step.is-active .ask-esakal-step-ico{border-color:var(--ae-brand);}",
  ".ask-esakal-step.is-active .ask-esakal-spinner{position:absolute;width:20px;height:20px;border-radius:50%;border:1.5px solid transparent;border-top-color:var(--ae-brand);border-right-color:var(--ae-brand);animation:ask-esakal-spin .7s linear infinite;}",
  ".ask-esakal-step.is-done{color:var(--ae-text);}",
  ".ask-esakal-step.is-done .ask-esakal-step-ico{background:var(--ae-brand);border-color:var(--ae-brand);}",
  ".ask-esakal-step.is-done .ask-esakal-step-ico svg{opacity:1;color:#fff;}",
  "@keyframes ask-esakal-spin{to{transform:rotate(360deg);}}",
  "@media (prefers-reduced-motion:reduce){.ask-esakal-step.is-active .ask-esakal-spinner{animation:none;}}",

  /* input */
  ".ask-esakal-footer-wrap{border-top:1px solid var(--ae-hairline);background:var(--ae-surface);padding:14px 20px 12px;}",
  ".ask-esakal-inputrow{display:flex;gap:9px;align-items:stretch;}",
  ".ask-esakal-input{flex:1;min-width:0;font:inherit;font-size:.92rem;color:var(--ae-ink);background:#fff;border:1px solid var(--ae-input-border);border-radius:10px;padding:12px 14px;outline:none;transition:border-color .12s ease,box-shadow .12s ease;}",
  ".ask-esakal-input::placeholder{color:var(--ae-faint);}",
  ".ask-esakal-input:focus{border-color:var(--ae-brand);box-shadow:0 0 0 3px rgba(60,106,251,.12);}",
  ".ask-esakal-send{flex:0 0 auto;display:flex;align-items:center;gap:7px;font:inherit;font-size:.9rem;font-weight:600;color:#fff;cursor:pointer;background:var(--ae-brand);border:1px solid var(--ae-brand-dark);border-radius:10px;padding:0 16px;transition:background .12s ease,transform .08s ease;}",
  ".ask-esakal-send:hover{background:var(--ae-brand-dark);}",
  ".ask-esakal-send:active{transform:translateY(1px);}",
  ".ask-esakal-send svg{width:15px;height:15px;}",
  ".ask-esakal-input:disabled,.ask-esakal-send:disabled{opacity:.5;cursor:not-allowed;pointer-events:none;}",

  /* nudge */
  ".ask-esakal-nudge{display:none;margin:11px 0 1px;font-size:.76rem;color:var(--ae-muted);align-items:center;gap:7px;}",
  ".ask-esakal-nudge.is-show{display:flex;}",
  ".ask-esakal-nudge-pill{flex:0 0 auto;background:#eef3ff;color:var(--ae-brand);font-weight:700;border-radius:999px;padding:2px 8px;font-size:.7rem;border:1px solid #d7e2ff;}",
  ".ask-esakal-nudge a{color:var(--ae-brand);font-weight:600;text-decoration:none;border-bottom:1px solid rgba(60,106,251,.3);}",
  ".ask-esakal-nudge a:hover{color:var(--ae-brand-dark);}",

  /* upsell */
  ".ask-esakal-upsell{position:relative;overflow:hidden;background:linear-gradient(150deg,#4f7bff,var(--ae-brand) 50%,var(--ae-brand-deep));color:#fff;border-radius:14px;padding:20px 20px 19px;}",
  ".ask-esakal-upsell::before{content:'';position:absolute;top:-40px;right:-30px;width:150px;height:150px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.22),transparent 68%);pointer-events:none;}",
  ".ask-esakal-upsell-badge{display:inline-flex;align-items:center;gap:6px;font-size:.64rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#dbe6ff;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:4px 10px;margin-bottom:11px;}",
  ".ask-esakal-upsell-h{font-size:1.08rem;font-weight:700;margin:0 0 5px;color:#fff;letter-spacing:-.005em;}",
  ".ask-esakal-upsell-p{font-size:.84rem;line-height:1.5;color:rgba(255,255,255,.74);margin:0 0 15px;max-width:430px;}",
  ".ask-esakal-upsell-cta{display:inline-flex;align-items:center;gap:8px;text-decoration:none;background:#fff;color:var(--ae-brand-dark);font-weight:700;font-size:.88rem;border-radius:8px;padding:11px 17px;box-shadow:0 6px 18px rgba(0,0,0,.22);transition:transform .12s ease,box-shadow .12s ease;}",
  ".ask-esakal-upsell-cta:hover{transform:translateY(-1px);box-shadow:0 9px 24px rgba(0,0,0,.28);}",
  ".ask-esakal-upsell-cta svg{width:14px;height:14px;}",
  ".ask-esakal-upsell-note{display:block;margin-top:11px;font-size:.72rem;color:rgba(255,255,255,.5);}",

  /* attribution */
  ".ask-esakal-attrib{text-align:center;font-size:.7rem;color:var(--ae-footer);letter-spacing:.02em;padding:11px 20px 14px;border-top:1px solid var(--ae-hairline);background:#fff;}",
  ".ask-esakal-attrib b{color:var(--ae-muted);font-weight:600;}",

  /* mobile */
  "@media (max-width:560px){",
  "  .ask-esakal-widget{border-radius:0;border-left:0;border-right:0;box-shadow:none;max-width:100%;}",
  "  .ask-esakal-header{padding:15px 16px 14px;}",
  "  .ask-esakal-sub{display:none;}",
  "  .ask-esakal-suggest-wrap{padding:13px 0 0 16px;}",
  "  .ask-esakal-chips{flex-wrap:nowrap;overflow-x:auto;padding:0 16px 14px 0;scrollbar-width:none;-webkit-overflow-scrolling:touch;}",
  "  .ask-esakal-chips::-webkit-scrollbar{display:none;}",
  "  .ask-esakal-convo{padding:6px 16px 4px;max-height:none;}",
  "  .ask-esakal-question{font-size:1.08rem;}",
  "  .ask-esakal-footer-wrap{padding:12px 16px 11px;}",
  "  .ask-esakal-send-label{display:none;}",
  "  .ask-esakal-send{padding:0 14px;}",
  "}"
  ].join("\n");

  /* ---- icons ---------------------------------------------------------- */
  var ICON_CHECK = '<svg viewBox="0 0 12 12" fill="none"><path d="M2.5 6.2l2.2 2.2 4.8-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 16 16" fill="none"><path d="M2 8h10M8 4l4 4-4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_ARROW = '<svg viewBox="0 0 14 14" fill="none"><path d="M3 7h7M7 3.5L10.5 7 7 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_EXTLINK = '<svg viewBox="0 0 14 14" fill="none"><path d="M5 3h6v6M11 3L5.5 8.5M9 8.5V11H3V5h2.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  /* ---- fallback suggestions ------------------------------------------- */
  var FALLBACK_SUGGESTIONS = [
    "आज महाराष्ट्रात काय घडले?",
    "पुण्यातील ताज्या बातम्या काय आहेत?",
    "राज्य सरकारने या आठवड्यात काय जाहीर केले?",
    "महाराष्ट्रातील राजकीय घडामोडी काय आहेत?"
  ];

  /* ---- mock data -------------------------------------------------------- */
  var MOCK_REPLY = {
    answer: "Maharashtra's political landscape stayed turbulent through the week. The ruling coalition cleared a revised cabinet portfolio allocation after three days of negotiations, with the finance and urban-development ministries drawing the sharpest contention[1]. Opposition leaders announced a state-wide agitation over delayed farm-loan waivers, setting up a confrontation ahead of the monsoon session[2]. Analysts note the realignment could reshape seat-sharing well before the civic polls due later this year[3].",
    sources: [
      { n: 1, title: "Cabinet portfolios reshuffled after marathon coalition talks", section: "Politics", date: "9 Jun 2026", url: "https://www.esakal.com" },
      { n: 2, title: "Opposition calls state-wide stir over pending farm-loan waivers", section: "Maharashtra", date: "8 Jun 2026", url: "https://www.esakal.com" },
      { n: 3, title: "Civic polls: how the new alignment changes the seat math", section: "Analysis", date: "7 Jun 2026", url: "https://www.esakal.com" }
    ]
  };

  /* ---- date / count helpers ------------------------------------------- */
  function todayIST() {
    return new Date().toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata" });
  }
  function getCount() {
    var date = localStorage.getItem("esakal_chat_date");
    if (date !== todayIST()) return 0;
    return parseInt(localStorage.getItem("esakal_chat_count") || "0", 10) || 0;
  }
  function bumpCount() {
    var c = getCount() + 1;
    localStorage.setItem("esakal_chat_count", String(c));
    localStorage.setItem("esakal_chat_date", todayIST());
    return c;
  }

  /* ---- escape --------------------------------------------------------- */
  function esc(s) {
    return String(s || "").replace(/[&<>"]/g, function (m) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[m];
    });
  }

  /* ---- fetch from real backend ---------------------------------------- */
  function fetchFromBackend(q, history) {
    var base = API_BASE.replace(/\/$/, "");
    return fetch(base + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, source: "esakal", history: history || [], lang: lang })
    })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (resp) {
      var sources = (resp.sources || []).map(function (s) {
        return { n: s.number, title: s.headline, section: "Esakal", date: s.published_at || "", url: s.url };
      });
      return { answer: resp.answer || "No answer available.", sources: sources };
    });
  }

  /* ---- load suggestions ------------------------------------------------ */
  function loadSuggestions(chips, onSelect) {
    if (IS_MOCK) { renderChips(chips, FALLBACK_SUGGESTIONS, onSelect); return; }
    fetch(API_BASE.replace(/\/$/, "") + "/suggestions?lang=" + lang)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderChips(chips, data.suggestions || FALLBACK_SUGGESTIONS, onSelect); })
      .catch(function () { renderChips(chips, FALLBACK_SUGGESTIONS, onSelect); });
  }

  function renderChips(chips, suggestions, onSelect) {
    chips.innerHTML = "";
    suggestions.forEach(function (q) {
      var b = document.createElement("button");
      b.className = "ask-esakal-chip";
      b.type = "button";
      b.textContent = q;
      b.addEventListener("click", function () { onSelect(q); });
      chips.appendChild(b);
    });
  }

  /* ==================================================================== */
  function buildWidget(mount) {
    if (!document.getElementById("ask-esakal-styles")) {
      var st = document.createElement("style");
      st.id = "ask-esakal-styles";
      st.textContent = styles;
      document.head.appendChild(st);
    }

    var root = document.createElement("div");
    root.className = "ask-esakal-widget";
    root.innerHTML =
      buildHeader() +
      '<div class="ask-esakal-suggest-wrap"><p class="ask-esakal-suggest-label" id="ae-try-label">' + t("tryAsking") + '</p><div class="ask-esakal-chips" id="ae-chips"></div></div>' +
      '<div class="ask-esakal-convo" id="ae-convo">' + buildEmpty() + '</div>' +
      '<div id="ae-foot"></div>' +
      '<div class="ask-esakal-attrib" id="ae-attrib">' + t("attrib") + '</div>';

    mount.innerHTML = "";
    mount.appendChild(root);

    var chips = root.querySelector("#ae-chips");
    var convo = root.querySelector("#ae-convo");
    var foot  = root.querySelector("#ae-foot");
    var history = [];
    var busy = false;

    loadSuggestions(chips, submitQ);
    renderFooter();


    function syncCounter() {
      var pill = root.querySelector("#ae-counter");
      if (!pill) return;
      var used = Math.min(getCount(), FREE_LIMIT);
      var left = Math.max(FREE_LIMIT - used, 0);
      var dots = "";
      for (var i = 0; i < FREE_LIMIT; i++) {
        dots += '<span class="ask-esakal-dot' + (i < used ? " is-used" : "") + '"></span>';
      }
      pill.innerHTML = '<span class="ask-esakal-dots">' + dots + '</span><span class="ask-esakal-counter-label">' + left + ' left</span>';
    }

    function renderFooter() {
      var left = Math.max(FREE_LIMIT - getCount(), 0);

      if (left <= 0) {
        foot.innerHTML =
          '<div class="ask-esakal-footer-wrap">' +
          '<div class="ask-esakal-upsell">' +
          '<span class="ask-esakal-upsell-badge">&#10022; Sakal Plus</span>' +
          '<h4 class="ask-esakal-upsell-h">You\'ve used today\'s ' + FREE_LIMIT + ' free questions.</h4>' +
          '<p class="ask-esakal-upsell-p">Get unlimited answers from Esakal\'s newsroom, every day — plus ad-free reading and the e-paper.</p>' +
          '<a class="ask-esakal-upsell-cta" href="' + esc(SAKAL_PLUS_URL) + '" target="_blank" rel="noopener">Join Sakal Plus ' + ICON_ARROW + '</a>' +
          '<span class="ask-esakal-upsell-note">Your free questions reset tomorrow.</span>' +
          '</div></div>';
        return;
      }

      foot.innerHTML =
        '<div class="ask-esakal-footer-wrap">' +
        '<div class="ask-esakal-inputrow">' +
        '<input class="ask-esakal-input" id="ae-input" type="text" placeholder="' + t("placeholder") + '" autocomplete="off" />' +
        '<button class="ask-esakal-send" id="ae-send" type="button"><span class="ask-esakal-send-label">' + t("askBtn") + '</span>' + ICON_SEND + '</button>' +
        '</div>' +
        '<div class="ask-esakal-nudge' + (left <= 2 ? " is-show" : "") + '">' +
        '<span class="ask-esakal-nudge-pill">' + left + ' left</span>' +
        '<span>question' + (left === 1 ? "" : "s") + ' remaining today · <a href="' + esc(SAKAL_PLUS_URL) + '" target="_blank" rel="noopener">Join Sakal Plus</a> for unlimited.</span>' +
        '</div></div>';

      var input = foot.querySelector("#ae-input");
      var send  = foot.querySelector("#ae-send");
      send.addEventListener("click", function () { var v = input.value.trim(); if (v) submitQ(v); });
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") { var v = input.value.trim(); if (v) submitQ(v); } });
    }

    function submitQ(q) {
      if (busy) return;
      if (getCount() >= FREE_LIMIT) { renderFooter(); return; }
      busy = true;

      var inp = foot.querySelector("#ae-input");
      if (inp) inp.value = "";

      var empty = convo.querySelector(".ask-esakal-empty");
      if (empty) empty.remove();

      var ex = document.createElement("div");
      ex.className = "ask-esakal-exchange";
      ex.innerHTML =
        '<p class="ask-esakal-kicker">' + t("youAsked") + '</p>' +
        '<p class="ask-esakal-question">' + esc(q) + '</p>' +
        '<div class="ask-esakal-answer-slot">' + buildThinking() + '</div>';
      convo.appendChild(ex);
      convo.scrollTop = convo.scrollHeight;

      var slot = ex.querySelector(".ask-esakal-answer-slot");

      animateSteps(slot, function () {
        var p = IS_MOCK
          ? new Promise(function (res) { setTimeout(function () { res(MOCK_REPLY); }, 300); })
          : fetchFromBackend(q, history);

        p.then(function (data) {
          slot.innerHTML = buildAnswer(data);
          convo.scrollTop = convo.scrollHeight;
          history.push({ role: "user", content: q });
          history.push({ role: "assistant", content: data.answer });
          if (history.length > 20) history = history.slice(-20);
          bumpCount();
          busy = false;
          renderFooter();
        }).catch(function () {
          slot.innerHTML = '<p class="ask-esakal-answer">' + t("error") + '</p>';
          busy = false;
          renderFooter();
        });
      });
    }

    function animateSteps(slot, onDone) {
      var steps = slot.querySelectorAll(".ask-esakal-step");
      var idx = 0;
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion:reduce)").matches;
      var ms = reduce ? 80 : 520;

      function activate() {
        steps.forEach(function (s, k) {
          s.classList.toggle("is-active", k === idx);
          if (k < idx) s.classList.add("is-done");
        });
        convo.scrollTop = convo.scrollHeight;
      }
      activate();

      function tick() {
        idx++;
        if (idx < steps.length) { activate(); setTimeout(tick, ms); }
        else {
          steps.forEach(function (s) { s.classList.remove("is-active"); s.classList.add("is-done"); });
          onDone();
        }
      }
      setTimeout(tick, ms);
    }
  }

  /* ---- HTML builders -------------------------------------------------- */
  function buildHeader() {
    return '<div class="ask-esakal-header"><div class="ask-esakal-header-top">' +
      '<div class="ask-esakal-brand">' +
      '<span class="ask-esakal-mark">&#10022;</span>' +
      '<div><h3 class="ask-esakal-title">Ask <span class="ask-esakal-thin">Esakal</span></h3>' +
      '<p class="ask-esakal-sub" id="ae-subtitle">' + t("subtitle") + '</p></div>' +
      '</div>' +
      '</div></div>';
  }

  function buildEmpty() {
    return '<div class="ask-esakal-empty">' +
      '<div class="ask-esakal-empty-mark">&#10022;</div>' +
      '<p class="ask-esakal-empty-h" id="ae-empty-h">' + t("emptyH") + '</p>' +
      '<p class="ask-esakal-empty-p" id="ae-empty-p">' + t("emptyP") + '</p>' +
      '</div>';
  }

  function buildThinking() {
    var labels = t("steps");
    var lis = labels.map(function (l) {
      return '<li class="ask-esakal-step"><span class="ask-esakal-step-ico"><span class="ask-esakal-spinner"></span>' + ICON_CHECK + '</span><span>' + l + '</span></li>';
    }).join("");
    return '<div class="ask-esakal-thinking"><ul class="ask-esakal-steps">' + lis + '</ul></div>';
  }

  function buildAnswer(data) {
    var ans = esc(data.answer).replace(/\[(\d+)\]/g, function (_, n) {
      return '<a class="ask-esakal-cite" href="#ae-src-' + n + '">[' + n + ']</a>';
    });
    var paras = ans.split(/\n{2,}/).map(function (p) { return "<p>" + p + "</p>"; }).join("");

    var cards = (data.sources || []).map(function (s) {
      return '<a class="ask-esakal-source" id="ae-src-' + s.n + '" href="' + esc(s.url) + '" target="_blank" rel="noopener">' +
        '<span class="ask-esakal-source-num">' + s.n + '</span>' +
        '<span class="ask-esakal-source-body">' +
        '<span class="ask-esakal-source-head">' + esc(s.title) + '</span>' +
        '<span class="ask-esakal-source-meta">' +
        '<span class="ask-esakal-source-tag">' + esc(s.section || "Esakal") + '</span>' +
        '<span class="ask-esakal-source-dot"></span>' +
        '<span>' + esc(s.date || "") + '</span>' +
        '<span class="ask-esakal-source-dot"></span>' +
        '<span>esakal.com</span>' +
        '</span></span>' +
        '<span class="ask-esakal-source-arrow">' + ICON_EXTLINK + '</span>' +
        '</a>';
    }).join("");

    return '<div class="ask-esakal-answer">' + paras + '</div>' +
      (cards ? '<div class="ask-esakal-sources"><p class="ask-esakal-sources-label">' + t("sources") + '</p>' + cards + '</div>' : "");
  }

  /* ---- init ------------------------------------------------------------ */
  function init() {
    document.querySelectorAll("[data-ask-esakal]").forEach(function (m) {
      if (m.__askEsakalInit) return;
      m.__askEsakalInit = true;
      buildWidget(m);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  window.AskEsakal = { init: init };
})();
