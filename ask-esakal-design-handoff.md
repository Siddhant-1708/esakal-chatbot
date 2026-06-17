# Ask Esakal Widget — UI Design Handoff

## What This Is

A self-contained chat widget embedded on **esakal.com**'s homepage. Users ask English questions about today's news and get answers sourced exclusively from Esakal's own articles, with links back to those articles.

The widget is a single vanilla JS file (`widget/ask-esakal.js`) — an IIFE with all CSS injected via a `<style>` tag. No framework. No build step. It must work inside Quintype Bold's CMS theme.

**Live demo:** `http://localhost:8000` (run `python main.py` to start)

---

## Current State (what it looks like now)

### Normal state (questions remaining)
- Navy header with ✦ Ask Esakal title
- 4 suggestion chips in a row
- Empty conversation area
- Input + Ask button
- "Answers sourced from Esakal reporting." footer

### Limit hit state
- Same header + chips
- Blue upsell box: "You've used today's 5 free questions. Join Sakal Plus for unlimited access."
- **[Join Sakal Plus →]** button (navy, rounded)
- Input + Ask button both greyed out / disabled

### Active conversation state
- User question shown in bold
- "Thinking" state: italic grey text e.g. "Retrieving articles: Found 6 articles for: Maharashtra"
- Answer text with inline [1] [2] citations
- Source links below answer (navy, underlined, open in new tab)

### Nudge state (1–2 questions remaining)
- Small grey text below send button: "1 question remaining today. Join Sakal Plus for unlimited access."

---

## Current CSS Tokens

| Token | Value | Used for |
|---|---|---|
| Primary | `#1B3A6B` | Header bg, chips border/hover, buttons, links |
| Primary dark | `#0f2547` | Link hover |
| Background | `#fff` | Widget card |
| Page bg | `#f4f6f9` | Demo page body |
| Upsell bg | `#f0f4ff` | Limit message box |
| Border | `#e8ecf0` | Section dividers |
| Input border | `#c5cdd8` | Input field |
| Text primary | `#222` | Answer text |
| Text secondary | `#333` | User question |
| Text muted | `#666` | Thinking/status text |
| Text faint | `#888` | Nudge text |
| Text footer | `#aaa` | Footer attribution |
| Border radius | `12px` widget, `8px` inputs/buttons, `20px` chips, `6px` upsell CTA |
| Box shadow | `0 4px 24px rgba(0,0,0,0.12)` |

---

## Current Layout Structure

```
┌─────────────────────────────────────────────┐
│  [HEADER]  #1B3A6B bg                       │
│  ✦ Ask Esakal  (bold, 1.1rem)               │
│  Ask anything about today's news.  (0.85rem)│
├─────────────────────────────────────────────┤
│  [SUGGESTIONS]  flex-wrap, gap 8px          │
│  [chip] [chip] [chip] [chip]                │
├─────────────────────────────────────────────┤
│  [CONVERSATION]  max-height 420px, scroll   │
│                                             │
│  User: [bold question text]                 │
│  Assistant: [answer or thinking...]         │
│    [1] Article headline  ← source link      │
│    [2] Article headline                     │
│                                             │
├─────────────────────────────────────────────┤
│  [LIMIT BLOCK]  shown only when 0 left      │
│  ┌─────────────────────────────────────────┐│
│  │ You've used today's 5 free questions... ││
│  │         [Join Sakal Plus →]             ││
│  └─────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│  [INPUT ROW]                                │
│  [______ Type your question... ______][Ask] │
├─────────────────────────────────────────────┤
│  [NUDGE]  shown at 1-2 questions left       │
│  "1 question remaining today. Join Sakal+"  │
├─────────────────────────────────────────────┤
│  Answers sourced from Esakal reporting.     │
└─────────────────────────────────────────────┘
```

Max width: `720px`, centered, on a `#f4f6f9` page background.

---

## What Needs Improving

### 1. Visual polish
- The widget looks functional but plain. Make it feel premium — like a serious Indian news brand, not a generic chatbot.
- The header could use a subtle gradient or texture instead of flat navy.
- Suggested question chips could feel more tactile — slight shadow, better hover animation.
- The "Ask" button could have a send/arrow icon instead of just text.

### 2. Conversation rendering
- User and assistant messages are just stacked divs. Consider chat-bubble styling, or a clean newspaper-editorial layout.
- The "thinking" state is plain italic text. Could be an animated progress indicator showing each pipeline step: Planning → Retrieving → Checking → Answering.
- Source links look like raw anchor tags. Could be proper citation cards with a newspaper icon and publish date.

### 3. Freemium upsell
- The limit block is functional but blunt. Could be a gradient fade over the last answer with an overlay CTA.
- The nudge text ("1 question remaining") is easy to miss. Consider a pill counter in the header or near the input.

### 4. Mobile (360px)
- Currently just removes border-radius at 420px — needs a real mobile layout pass.
- Chips should scroll horizontally on mobile rather than wrapping to 3 rows.

### 5. Empty state
- When the widget first loads, the conversation area is blank. Could show a small illustration, a "powered by Esakal" badge, or recent article highlights.

---

## Implementation Constraints (must follow these)

- **Single file IIFE** — all styles stay inside the JS as a template literal injected into `<style>`. No external CSS files.
- **No framework, no build step** — vanilla JS only. Modern Chrome/Safari/Edge only.
- **CSS class prefix** — all classes must start with `ask-esakal-` to avoid conflicts with the host page.
- **ID prefix** — all element IDs use `ae-` prefix (e.g. `ae-input`, `ae-send`).
- **Configurable via globals** — `window.ESAKAL_API_BASE` and `window.ESAKAL_SAKAL_PLUS_URL` can be set by the host page before the script loads.
- **Must work as embed** — `<div data-ask-esakal></div>` + `<script src="ask-esakal.js">` anywhere on a page self-initialises the widget.
- **Max widget width:** `720px` — lives in an editorial content column.
- **No heavy animations** — the host page (esakal.com) is performance-sensitive.
- **Do not load external fonts** — use `inherit` from the host page (Noto Sans / system sans-serif).

---

## Files to Edit

| File | What it contains |
|---|---|
| `widget/ask-esakal.js` | Everything — the IIFE, the `styles` template literal string, the HTML template inside `buildWidget()`, and all JS logic. Edit the `styles` const and the HTML string. |
| `widget/demo.html` | Test page. Edit for page-level styles or to simulate different host page contexts. |

Backend files (`main.py`, `app/`, `schemas.py`) do not need to change for UI work.

---

## How to Test Changes

1. Edit `widget/ask-esakal.js`
2. Hard-refresh `localhost:8000` (Ctrl+Shift+R) — no build step
3. Test the limit state (console):
   ```js
   localStorage.setItem('esakal_chat_count', '5');
   localStorage.setItem('esakal_chat_date', new Date().toLocaleDateString('en-IN', {timeZone:'Asia/Kolkata'}));
   location.reload();
   ```
4. Test the nudge state (1 question left):
   ```js
   localStorage.setItem('esakal_chat_count', '4');
   localStorage.setItem('esakal_chat_date', new Date().toLocaleDateString('en-IN', {timeZone:'Asia/Kolkata'}));
   location.reload();
   ```
5. Reset to fresh:
   ```js
   localStorage.removeItem('esakal_chat_count');
   localStorage.removeItem('esakal_chat_date');
   location.reload();
   ```

---

## Brand Reference

- **Primary colour:** `#1B3A6B` (Esakal navy — do not change, it's the brand colour)
- **Font:** inherit from host page — do not load external fonts
- **Tone:** serious, trustworthy Indian news brand — not a Silicon Valley chatbot. Think The Hindu or Times of India, not ChatGPT.
- **Live site reference:** https://www.esakal.com (look at their Prime Deals / subscription pages for visual tone)
