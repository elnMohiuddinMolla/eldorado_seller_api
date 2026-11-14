"""The single page served by `eldorado ui` / `eldorado app`. `__TOKEN__` is replaced per run."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eldorado Bot</title>
<style>
:root {
  --bg: #f4f6f9; --card: #ffffff; --card2: #f8f9fb; --text: #18202d; --muted: #6b7486; --line: #e3e7ee;
  --accent: #2f6fed; --accent-bg: #e8effd; --ok: #15803d; --ok-bg: #e6f6ec; --warn: #b45309; --warn-bg: #fff4e0;
  --bad: #c0362c; --bad-bg: #fdeceb; --input: #ffffff; --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08);
  --radius: 12px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1218; --card: #171c24; --card2: #1c222c; --text: #e7eaf0; --muted: #96a0b3; --line: #273041;
    --accent: #6d9bff; --accent-bg: #1c2a47; --ok: #4ccb8a; --ok-bg: #14301f; --warn: #f5a54a; --warn-bg: #33250f;
    --bad: #ff7b72; --bad-bg: #3a1a18; --input: #10141b; --shadow: none;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; padding-bottom: 80px; }
button, select, input { font: inherit; color: var(--text); }
button { border: 1px solid var(--line); background: var(--card); border-radius: 9px; padding: 7px 14px; cursor: pointer; }
button:hover { border-color: var(--accent); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
button:disabled { opacity: .5; cursor: default; }
input[type=text] { background: var(--input); border: 1px solid var(--line); border-radius: 7px; padding: 6px 8px; }
input[type=text]:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
input.price { width: 86px; text-align: right; font-variant-numeric: tabular-nums; }
input.bad { border-color: var(--bad); background: var(--bad-bg); }
input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; accent-color: var(--accent); vertical-align: middle; }
code { font-size: 12px; background: var(--card2); padding: 1px 5px; border-radius: 5px; }

header { position: sticky; top: 0; z-index: 5; background: var(--card); border-bottom: 1px solid var(--line);
         box-shadow: var(--shadow); }
.bar { max-width: 1240px; margin: 0 auto; padding: 10px 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.brand { display: flex; align-items: center; gap: 10px; margin-right: auto; }
.logo { width: 30px; height: 30px; border-radius: 8px; background: linear-gradient(135deg, var(--accent), #8a5cf6);
        display: grid; place-items: center; color: #fff; font-weight: 800; }
.brand h1 { font-size: 16px; margin: 0; }
.brand small { color: var(--muted); display: block; font-size: 12px; }
#botSwitch { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 8px 16px; font-weight: 700; }
#botSwitch .dot { width: 10px; height: 10px; border-radius: 50%; background: currentColor; }
#botSwitch.running { background: var(--ok-bg); color: var(--ok); border-color: var(--ok); }
#botSwitch.running .dot { animation: pulse 1.6s infinite; }
#botSwitch.paused { background: var(--bad-bg); color: var(--bad); border-color: var(--bad); }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 currentColor; } 70% { box-shadow: 0 0 0 7px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }

main { max-width: 1240px; margin: 0 auto; padding: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow);
        margin-bottom: 16px; overflow: hidden; }
.cardhead { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--line); }
.cardhead h2 { font-size: 15px; margin: 0; }
.spacer { flex: 1; }
.note { color: var(--muted); font-size: 13px; }
.scroll { overflow-x: auto; }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 16px; }
.stat { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px; box-shadow: var(--shadow); }
.stat .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.stat .v { font-size: 24px; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }
.stat .s { color: var(--muted); font-size: 12px; margin-top: 2px; min-height: 16px; }
.stat.ok .v { color: var(--ok); } .stat.bad .v { color: var(--bad); } .stat.warn .v { color: var(--warn); }

.two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
.tall { max-height: 340px; overflow-y: auto; }
.tall thead th { position: sticky; top: 0; }
@media (max-width: 900px) { .two { grid-template-columns: 1fr; } }

table { width: 100%; border-collapse: collapse; }
th, td { padding: 9px 12px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
th { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); background: var(--card2); }
th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
th.c, td.c { text-align: center; }
tbody tr:hover td { background: var(--card2); }
tr.late td { color: var(--bad); }
.empty { padding: 18px; text-align: center; color: var(--muted); }

.pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.pill.ok { background: var(--ok-bg); color: var(--ok); }
.pill.warn { background: var(--warn-bg); color: var(--warn); }
.pill.bad { background: var(--bad-bg); color: var(--bad); }
.pill.muted { background: var(--card2); color: var(--muted); }
.pill.accent { background: var(--accent-bg); color: var(--accent); }

.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--line); }
#search { width: 220px; max-width: 100%; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border-radius: 999px; padding: 4px 11px; font-size: 13px; background: var(--card2); }
.chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
label.tog { display: inline-flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px; cursor: pointer; }

tr.game td { background: var(--card2); font-weight: 700; cursor: pointer; user-select: none; }
tr.game td .caret { display: inline-block; width: 14px; transition: transform .15s; }
tr.game.closed td .caret { transform: rotate(-90deg); }
tr.dirty td:first-child { box-shadow: inset 3px 0 var(--accent); }
.pkg b { font-weight: 600; }
.pkg .id { color: var(--muted); font-size: 11px; }

#orderBanner { display: none; padding: 14px 16px; border-radius: var(--radius); margin-bottom: 14px; font-size: 16px; font-weight: 700;
               background: var(--ok-bg); color: var(--ok); border: 2px solid var(--ok); cursor: pointer; }
#toast { position: fixed; right: 16px; top: 76px; z-index: 9; max-width: 420px; padding: 12px 14px; border-radius: 10px;
         box-shadow: 0 8px 24px rgba(0,0,0,.18); display: none; font-weight: 500; }
#toast.ok { display: block; background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok); }
#toast.bad { display: block; background: var(--bad-bg); color: var(--bad); border: 1px solid var(--bad); }
#toast.info { display: block; background: var(--card); color: var(--text); border: 1px solid var(--line); }
#saveBar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 6; background: var(--card); border-top: 1px solid var(--line);
           box-shadow: 0 -4px 16px rgba(0,0,0,.12); transform: translateY(110%); transition: transform .2s; }
#saveBar.show { transform: none; }
#saveBar .bar { justify-content: flex-end; }
.settings { display: flex; flex-wrap: wrap; gap: 18px; align-items: center; padding: 12px 14px; }
.settings label { display: inline-flex; gap: 8px; align-items: center; }
.help { padding: 0 14px 12px; color: var(--muted); font-size: 13px; margin: 0; }
.help b { color: var(--text); }
</style>
</head>
<body>
<header>
  <div class="bar">
    <div class="brand"><div class="logo">E</div>
      <div><h1>Eldorado Bot</h1><small>TopUp auto bidding</small></div></div>
    <button id="botSwitch" title="Pause or run the bot for all offers"><span class="dot"></span><span id="botText">Bot ...</span></button>
    <button id="reload" title="Load live prices from Eldorado">&#x21bb; Reload</button>
    <button id="preview" title="Show what the bot would do now. Sends nothing.">Preview</button>
  </div>
</header>

<main>
  <div id="orderBanner" role="alert"></div>

  <section class="stats">
    <div class="stat" id="stBot"><div class="k">Bot</div><div class="v" id="stBotV">-</div><div class="s" id="stBotS"></div></div>
    <div class="stat" id="stOn"><div class="k">Offers ON</div><div class="v" id="stOnV">-</div><div class="s" id="stOnS"></div></div>
    <div class="stat" id="stOrders"><div class="k">Orders waiting</div><div class="v" id="stOrdersV">-</div><div class="s" id="stOrdersS"></div></div>
    <div class="stat" id="stToday"><div class="k">Price changes today</div><div class="v" id="stTodayV">-</div><div class="s" id="stTodayS"></div></div>
  </section>

  <div class="two">
    <section class="card" id="ordersCard">
      <div class="cardhead"><h2>Orders waiting for delivery</h2><span class="spacer"></span>
        <button id="notifyBtn" style="display:none">&#x1f514; Turn on desktop alerts</button></div>
      <div class="scroll"><table>
        <thead><tr><th>Game</th><th>Package</th><th class="num">Qty</th><th class="num">Total</th><th class="num">Waiting</th></tr></thead>
        <tbody id="orderRows"><tr><td colspan="5" class="empty">Checking orders...</td></tr></tbody>
      </table></div>
      <p class="help" id="ordersInfo"></p>
    </section>
    <section class="card">
      <div class="cardhead"><h2>Recent price changes</h2><span class="spacer"></span><span class="note" id="actInfo"></span></div>
      <div class="scroll tall"><table>
        <thead><tr><th>Time</th><th>Offer</th><th class="num">Price</th><th>Result</th></tr></thead>
        <tbody id="actRows"><tr><td colspan="4" class="empty">Loading...</td></tr></tbody>
      </table></div>
    </section>
  </div>

  <section class="card">
    <div class="cardhead"><h2>Bot settings</h2></div>
    <div class="settings">
      <label>Check every <input type="text" inputmode="numeric" id="interval" class="price" style="width:56px"
        title="Minutes between checks, 1 to 1440"> min</label>
      <label>Undercut <input type="text" inputmode="decimal" id="undercut" class="price" style="width:70px"
        title="How much below the cheapest other seller, 0.01 to 1.00"> USD</label>
    </div>
    <p class="help"><b>Min</b> = never sell below. <b>Max</b> = highest price when a cheaper seller disappears and the
      bot looks for the next one. Tick <b>ON</b> to let the bot manage an offer. <b>Big change</b> allows a price change of more than 50% at once.
      The bot uses saved changes at its next check (right away when started with <code>eldorado app</code>).</p>
  </section>

  <section class="card" id="previewCard" style="display:none">
    <div class="cardhead"><h2>Preview</h2><span class="pill accent">nothing sent</span><span class="spacer"></span>
      <button id="closePreview">Close</button></div>
    <div class="scroll"><table>
      <thead><tr><th>Offer</th><th class="num">Now</th><th class="num">Lowest other</th><th class="num">Bot would set</th><th>Action</th><th>Why</th></tr></thead>
      <tbody id="previewRows"></tbody>
    </table></div>
  </section>

  <section class="card">
    <div class="cardhead"><h2>Offers</h2><span class="note" id="offersInfo"></span></div>
    <div class="toolbar">
      <input type="text" id="search" placeholder="Search package or game...">
      <div class="chips" id="chips"></div>
      <span class="spacer"></span>
      <label class="tog"><input type="checkbox" id="onlyOn"> only ON</label>
      <label class="tog"><input type="checkbox" id="onlyBehind"> only where I'm not #1</label>
    </div>
    <div class="scroll"><table>
      <thead><tr><th>Package</th><th>State</th><th class="num">My price</th><th class="num">Lowest</th><th>Position</th>
        <th class="num" title="Never sell below this">Min</th><th class="num" title="Highest price when searching for the next seller">Max</th><th class="c" title="Let the bot manage this offer">ON</th><th class="c" title="Allow a price change of more than 50% at once">Big change</th></tr></thead>
      <tbody id="rows"><tr><td colspan="9" class="empty">Loading from Eldorado...</td></tr></tbody>
    </table></div>
  </section>
</main>

<div id="toast" role="status"></div>
<div id="saveBar"><div class="bar">
  <span id="dirtyText" class="note">Unsaved changes</span>
  <button id="discard">Discard</button>
  <button id="save" class="primary">Save</button>
</div></div>

<script>
const TOKEN = "__TOKEN__";
let data = { rows: [] };
let saved = "";
let gameFilter = "";
let botHere = true;  // false when the bot runs in another window (eldorado ui + bid run)
const collapsed = new Set();
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (s) => (s === "" || s == null) ? null : Number(s);
const money = (s) => s == null ? "-" : Number(s).toFixed(2);

let toastTimer = null;
function toast(kind, text, ms) {
  const t = $("toast"); t.className = kind; t.textContent = text;
  clearTimeout(toastTimer);
  if (ms !== 0) toastTimer = setTimeout(() => { t.className = ""; }, ms || 4500);
}
$("toast").addEventListener("click", () => { $("toast").className = ""; });

async function call(method, url, body) {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json", "X-Token": TOKEN },
                                 body: body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || ("HTTP " + res.status));
  return json;
}

/* ---------- dirty tracking ---------- */
function snapshot() {
  return JSON.stringify({ u: $("undercut").value.trim(), i: $("interval").value.trim(),
    r: data.rows.map((r) => [r.id, r.min_price || "", r.max_price || "", !!r.enabled, !!r.allow_big_change]) });
}
function changedCount() {
  if (!saved) return 0;
  const a = JSON.parse(saved), b = JSON.parse(snapshot());
  let n = (a.u !== b.u) + (a.i !== b.i);
  b.r.forEach((row, i) => { if (JSON.stringify(row) !== JSON.stringify(a.r[i])) n++; });
  return n;
}
function updateSaveBar() {
  const n = changedCount();
  $("saveBar").classList.toggle("show", n > 0);
  $("dirtyText").textContent = n === 1 ? "1 unsaved change" : n + " unsaved changes";
}
const isDirty = () => changedCount() > 0;

/* ---------- validation ---------- */
function validate(row) {
  const min = num(row.min_price), max = num(row.max_price), errs = {};
  if (row.min_price && !(min > 0)) errs.min = "Min must be a number above 0";
  if (row.max_price && !(max > 0)) errs.max = "Max must be a number above 0";
  if (min > 0 && max > 0 && max < min) errs.max = "Max must be at least Min";
  if ((row.enabled || row.max_price) && !row.min_price) errs.min = "Min is required";
  return errs;
}

/* ---------- position badge ---------- */
function position(r) {
  if (r.lowest == null) return '<span class="pill muted">no market</span>';
  if (r.lowest_is_me) {
    if (r.min_price && Number(r.price) <= Number(r.min_price)) return '<span class="pill bad">#1 at Min</span>';
    return '<span class="pill ok">&#x2714; You\'re #1</span>';
  }
  const gap = Number(r.price) - Number(r.lowest);
  if (r.min_price && Number(r.lowest) < Number(r.min_price)) return '<span class="pill bad">rival below your Min</span>';
  if (gap <= 0) return '<span class="pill ok">tied</span>';
  return '<span class="pill warn">+' + gap.toFixed(2) + " above</span>";
}

/* ---------- offers table ---------- */
function matches(r) {
  if (gameFilter && r.game !== gameFilter) return false;
  if ($("onlyOn").checked && !r.enabled) return false;
  if ($("onlyBehind").checked && (r.lowest == null || r.lowest_is_me)) return false;
  const q = $("search").value.trim().toLowerCase();
  return !q || (r.game + " " + r.package + " " + r.id).toLowerCase().includes(q);
}

function renderChips() {
  const games = [...new Set(data.rows.map((r) => r.game))].sort(gameOrder());
  const count = (g) => data.rows.filter((r) => r.game === g && r.enabled).length;
  $("chips").innerHTML = ['<button class="chip' + (gameFilter ? "" : " on") + '" data-g="">All</button>']
    .concat(games.map((g) => '<button class="chip' + (gameFilter === g ? " on" : "") + '" data-g="' + esc(g) + '">' +
      esc(g) + (count(g) ? " &middot; " + count(g) + " ON" : "") + "</button>")).join("");
}

function gameOrder() {
  // Games with offers ON first (most ON first), then the rest by name.
  const on = {};
  data.rows.forEach((r) => { on[r.game] = (on[r.game] || 0) + (r.enabled ? 1 : 0); });
  return (a, b) => (on[b] > 0) - (on[a] > 0) || (on[b] || 0) - (on[a] || 0) || a.localeCompare(b);
}

function render() {
  const cmp = gameOrder();
  const rows = data.rows.map((r, i) => [r, i]).filter(([r]) => matches(r))
    .sort(([a, ia], [b, ib]) => cmp(a.game, b.game) || ia - ib);
  let html = "", last = null;
  rows.forEach(([r, i]) => {
    if (r.game !== last) {
      last = r.game;
      const all = data.rows.filter((x) => x.game === r.game), on = all.filter((x) => x.enabled).length;
      const first = all.filter((x) => x.lowest_is_me).length;
      html += '<tr class="game' + (collapsed.has(r.game) ? " closed" : "") + '" data-game="' + esc(r.game) + '"><td colspan="9">' +
        '<span class="caret">&#x25be;</span> ' + esc(r.game) + ' <span class="note">&nbsp;' + all.length + " offers &middot; " +
        on + " ON &middot; #1 on " + first + "</span></td></tr>";
    }
    if (collapsed.has(r.game)) return;
    const e = validate(r);
    html += '<tr data-i="' + i + '"' + (r._dirty ? ' class="dirty"' : "") + ">" +
      '<td class="pkg"><b>' + esc(r.package) + '</b><div class="id">' + esc(r.id.slice(0, 8)) + "</div></td>" +
      '<td><span class="pill ' + (r.state === "Active" ? "ok" : "muted") + '">' + esc(r.state) + "</span></td>" +
      '<td class="num">' + money(r.price) + "</td>" +
      '<td class="num">' + money(r.lowest) + "</td>" +
      "<td>" + position(r) + "</td>" +
      '<td class="num"><input type="text" inputmode="decimal" class="price' + (e.min ? " bad" : "") + '" data-f="min_price" value="' + esc(r.min_price) + '" title="' + esc(e.min || "Never sell below this") + '" placeholder="-"></td>' +
      '<td class="num"><input type="text" inputmode="decimal" class="price' + (e.max ? " bad" : "") + '" data-f="max_price" value="' + esc(r.max_price) + '" title="' + esc(e.max || "Highest price when searching upward") + '" placeholder="-"></td>' +
      '<td class="c"><input type="checkbox" data-f="enabled" aria-label="ON"' + (r.enabled ? " checked" : "") + "></td>" +
      '<td class="c"><input type="checkbox" data-f="allow_big_change" aria-label="Big change"' + (r.allow_big_change ? " checked" : "") + "></td></tr>";
  });
  $("rows").innerHTML = html || '<tr><td colspan="9" class="empty">No offer matches the filters.</td></tr>';
  updateStatsOffers();
}

$("rows").addEventListener("click", (ev) => {
  const tr = ev.target.closest("tr.game");
  if (!tr) return;
  const g = tr.dataset.game;
  if (collapsed.has(g)) collapsed.delete(g); else collapsed.add(g);
  render();
});
$("rows").addEventListener("input", (ev) => {
  const el = ev.target, tr = el.closest("tr[data-i]");
  if (!tr || !el.dataset.f) return;
  const r = data.rows[Number(tr.dataset.i)];
  r[el.dataset.f] = el.type === "checkbox" ? el.checked : el.value.trim();
  r._dirty = true; tr.classList.add("dirty");
  const e = validate(r);
  tr.querySelectorAll("input.price").forEach((inp) => {
    const k = inp.dataset.f === "min_price" ? "min" : "max";
    inp.classList.toggle("bad", !!e[k]); if (e[k]) inp.title = e[k];
  });
  updateSaveBar(); updateStatsOffers();
});
$("chips").addEventListener("click", (ev) => {
  const b = ev.target.closest(".chip"); if (!b) return;
  gameFilter = b.dataset.g; renderChips(); render();
});
["search", "onlyOn", "onlyBehind"].forEach((id) => $(id).addEventListener("input", render));
$("undercut").addEventListener("input", updateSaveBar);
$("interval").addEventListener("input", () => {
  const m = Number($("interval").value);
  $("interval").classList.toggle("bad", !(Number.isInteger(m) && m >= 1 && m <= 1440));
  updateSaveBar();
});

function updateStatsOffers() {
  const on = data.rows.filter((r) => r.enabled);
  const first = on.filter((r) => r.lowest_is_me).length;
  $("stOnV").textContent = on.length + " / " + data.rows.length;
  $("stOnS").textContent = on.length ? "#1 on " + first + " of " + on.length + " ON offers" : "Tick ON to let the bot manage offers";
}

/* ---------- load / save ---------- */
async function load(fresh) {
  if (isDirty() && !confirm("Discard unsaved changes?")) return;
  if (!data.rows.length) $("rows").innerHTML = '<tr><td colspan="9" class="empty">Loading from Eldorado...</td></tr>';
  $("reload").disabled = true;
  try {
    data = await call("GET", "/api/offers" + (fresh ? "?fresh=1" : ""));
    $("undercut").value = data.undercut;
    $("interval").value = Math.round(data.interval_seconds / 60);
    $("interval").classList.remove("bad");
    if (gameFilter && !data.rows.some((r) => r.game === gameFilter)) gameFilter = "";
    saved = snapshot(); updateSaveBar();
    showBot(); renderChips(); render(); refreshStatus();
    const age = data.data_age_seconds || 0;
    $("offersInfo").textContent = data.rows.length + " offers · " + (age ? "prices are " + age + " s old" : "live prices");
  } catch (e) { toast("bad", "Could not load: " + e.message, 0); }
  finally { $("reload").disabled = false; }
}

async function save() {
  const minutes = Number($("interval").value);
  if (!(Number.isInteger(minutes) && minutes >= 1 && minutes <= 1440)) { toast("bad", "Check every: whole minutes from 1 to 1440."); return; }
  const bad = data.rows.filter((r) => Object.keys(validate(r)).length);
  if (bad.length) { toast("bad", "Fix the red boxes first (" + bad.length + " offer(s))."); return; }
  $("save").disabled = true;
  try {
    const res = await call("POST", "/api/config", { undercut: $("undercut").value.trim(),
                                                    interval_seconds: minutes * 60, rows: data.rows });
    data.interval_seconds = minutes * 60;
    data.rows.forEach((r) => delete r._dirty);
    saved = snapshot(); updateSaveBar(); renderChips(); render();
    toast("ok", "Saved. " + res.enabled + " offer(s) ON, checks every " + minutes + " min. " +
      (botHere ? "The bot uses it right away." : "The bot uses it at its next check."));
    setTimeout(() => { refreshStatus(); refreshActivity(); }, 4000);
  } catch (e) { toast("bad", "Not saved: " + e.message, 0); }
  finally { $("save").disabled = false; }
}
$("save").addEventListener("click", save);
$("discard").addEventListener("click", () => { saved = ""; load(false); });
$("reload").addEventListener("click", () => load(true));
document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); if (isDirty()) save(); } });
window.addEventListener("beforeunload", (e) => { if (isDirty()) { e.preventDefault(); e.returnValue = ""; } });

/* ---------- bot switch and status ---------- */
function showBot() {
  $("botText").textContent = data.paused ? "PAUSED · click to run" : "RUNNING · click to pause";
  $("botSwitch").className = data.paused ? "paused" : "running";
}
$("botSwitch").addEventListener("click", async () => {
  if (isDirty()) { toast("info", "Save or discard your changes first."); return; }
  const want = !data.paused;
  try {
    await call("POST", "/api/config", { paused: want, rows: [] });
    data.paused = want; showBot();
    toast(want ? "info" : "ok", want ? "Bot paused. Nothing is sent from now on." :
      (botHere ? "Bot running. First check starts now." : "Bot running. It starts at its next check."));
    setTimeout(refreshStatus, 3000); setTimeout(refreshActivity, 8000);
  } catch (e) { toast("bad", "Could not switch: " + e.message, 0); }
});

async function refreshStatus() {
  let s;
  try { s = await call("GET", "/api/status"); } catch (e) { $("stBotS").textContent = "status unavailable"; return; }
  const card = $("stBot");
  botHere = s.state !== "none";
  if (s.state === "none") {
    $("stBotV").textContent = data.paused ? "Paused" : "Running";
    $("stBotS").textContent = "bot runs in its own window"; card.className = "stat"; return;
  }
  const names = { running: "Running", paused: "Paused", idle: "No offer ON", error: "Error", starting: "Starting", stopped: "Stopped" };
  $("stBotV").textContent = names[s.state] || s.state;
  card.className = "stat " + ({ running: "ok", paused: "bad", error: "bad", idle: "warn" }[s.state] || "");
  let t = s.last_cycle ? "Last check " + s.last_cycle : "";
  if (s.next_cycle && s.state !== "paused") t += (t ? " · " : "") + "next " + s.next_cycle;
  $("stBotS").textContent = s.state === "error" ? s.message : t;
  if (s.state === "error" && !data.paused) { data.paused = true; showBot(); toast("bad", s.message, 0); }
}
setInterval(refreshStatus, 15000);

/* ---------- activity ---------- */
async function refreshActivity() {
  let a;
  try { a = await call("GET", "/api/activity"); } catch (e) { $("actInfo").textContent = "unavailable"; return; }
  $("stTodayV").textContent = a.changed_today;
  $("stTodayS").textContent = a.items.length ? "last at " + a.items[0].time : "no changes yet";
  const cls = { success: "ok", failed: "bad", unknown: "bad", dry_run: "muted" };
  const names = { success: "Changed", failed: "Failed", unknown: "Unknown, check Eldorado", dry_run: "Dry run" };
  $("actRows").innerHTML = a.items.map((x) => {
    const b = num(x.before), n = num(x.after);
    const arrow = b == null || n == null || b === n ? "" : (n < b ? "↓" : "↑");
    return "<tr><td>" + esc(x.time) + ' <span class="note">' + esc(x.date) + "</span></td><td>" + esc(x.label) +
      '</td><td class="num">' + money(x.before) + " → <b>" + money(x.after) + "</b> " + arrow +
      '</td><td><span class="pill ' + (cls[x.outcome] || "muted") + '">' + esc(names[x.outcome] || x.outcome) + "</span></td></tr>";
  }).join("") || '<tr><td colspan="4" class="empty">No price changes yet.</td></tr>';
  $("actInfo").textContent = "newest first";
}
setInterval(refreshActivity, 30000);

/* ---------- preview ---------- */
$("preview").addEventListener("click", async () => {
  if (isDirty()) { toast("info", "Save first: Preview uses the saved settings."); return; }
  toast("info", "Checking the market...", 0);
  try {
    const res = await call("POST", "/api/preview");
    const cls = { change: "warn", keep: "ok", skip: "muted" };
    $("previewRows").innerHTML = res.decisions.map((d) =>
      "<tr><td>" + esc(d.label) + '</td><td class="num">' + money(d.current) + '</td><td class="num">' + money(d.lowest) +
      '</td><td class="num"><b>' + money(d.target) + '</b></td><td><span class="pill ' + cls[d.action] + '">' + esc({ change: "Change", keep: "Keep", skip: "Skip" }[d.action] || d.action) +
      '</span></td><td class="note">' + esc(d.reason) + "</td></tr>").join("")
      || '<tr><td colspan="6" class="empty">No offer is ON.</td></tr>';
    $("previewCard").style.display = "";
    $("previewCard").scrollIntoView({ block: "start" });
    toast("ok", "Preview ready. Nothing was sent to Eldorado.");
  } catch (e) { toast("bad", "Preview failed: " + e.message, 0); }
});
$("closePreview").addEventListener("click", () => { $("previewCard").style.display = "none"; });

/* ---------- orders (F18) ---------- */
let knownOrders = null, unread = 0;
const baseTitle = document.title;
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25].forEach((t) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.25, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + t + 0.2);
      o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.2);
    });
  } catch (e) {}
}
function waited(min) {
  if (min == null) return "-";
  if (min < 60) return min + " min";
  if (min < 1440) return Math.floor(min / 60) + " h " + (min % 60) + " min";
  return Math.floor(min / 1440) + " d " + Math.floor((min % 1440) / 60) + " h";
}
function alertNew(orders) {
  unread += orders.length;
  document.title = "(" + unread + ") New order - " + baseTitle;
  const text = orders.map((o) => o.game + " " + o.package + " x" + o.quantity + " (" + o.total + " " + o.currency + ")").join(", ");
  const b = $("orderBanner");
  b.textContent = "🔔 NEW ORDER: " + text + "   (click to dismiss)";
  b.style.display = "block";
  window.scrollTo({ top: 0 });
  beep();
  if ("Notification" in window && Notification.permission === "granted") {
    try { new Notification("New Eldorado order", { body: text, requireInteraction: true }); } catch (e) {}
  }
}
$("orderBanner").addEventListener("click", () => { $("orderBanner").style.display = "none"; unread = 0; document.title = baseTitle; });
function showNotifyButton() {
  $("notifyBtn").style.display = ("Notification" in window && Notification.permission === "default") ? "" : "none";
}
$("notifyBtn").addEventListener("click", async () => { try { await Notification.requestPermission(); } catch (e) {} showNotifyButton(); });

async function refreshOrders() {
  let o;
  try { o = await call("GET", "/api/orders"); }
  catch (e) { $("ordersInfo").textContent = "Orders unavailable: " + e.message; return; }
  if (o.enabled === false) { $("ordersCard").style.display = "none"; $("stOrders").style.display = "none"; return; }
  const ids = new Set([...o.pending, ...o.alerts].map((x) => x.id));
  if (knownOrders === null) knownOrders = ids;
  else {
    const fresh = o.alerts.filter((x) => !knownOrders.has(x.id));
    ids.forEach((id) => knownOrders.add(id));
    if (fresh.length) alertNew(fresh);
  }
  const oldest = o.pending.reduce((m, x) => Math.max(m, x.age_minutes || 0), 0);
  $("stOrdersV").textContent = o.pending.length;
  $("stOrders").className = "stat " + (o.pending.length ? (oldest > 60 ? "bad" : "warn") : "ok");
  $("stOrdersS").textContent = o.pending.length ? "oldest waiting " + waited(oldest) : "nothing to deliver";
  $("ordersInfo").textContent = (o.error ? "Last check failed: " + o.error + ". " : "") +
    (o.last_check ? "Checked " + o.last_check + ", every minute. Red = waiting over 1 hour." : "First check running...");
  $("orderRows").innerHTML = o.pending.map((x) =>
    "<tr" + (x.age_minutes > 60 ? ' class="late"' : "") + "><td>" + esc(x.game) + "</td><td>" + esc(x.package) +
    '</td><td class="num">' + esc(x.quantity) + '</td><td class="num">' + esc(x.total) + " " + esc(x.currency) +
    '</td><td class="num">' + esc(waited(x.age_minutes)) + "</td></tr>").join("")
    || '<tr><td colspan="5" class="empty">&#x2714; No order is waiting.</td></tr>';
}

showNotifyButton();
load(false);
refreshOrders(); setInterval(refreshOrders, 20000);
refreshActivity();
</script>
</body>
</html>
"""
