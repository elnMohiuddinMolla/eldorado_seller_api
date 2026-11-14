"""The single page served by `eldorado ui`. `__TOKEN__` is replaced per run."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bid Settings</title>
<style>
:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #1d2330; --muted: #667085; --line: #e4e7ec;
  --accent: #2f6fed; --ok: #18794e; --ok-bg: #e7f6ee; --warn: #b54708; --warn-bg: #fff4e5;
  --bad: #c0362c; --bad-bg: #fdecea; --input: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --card: #1a1f27; --text: #e6e8ec; --muted: #98a2b3; --line: #2a313c;
    --accent: #6b9bff; --ok: #4cc38a; --ok-bg: #16301f; --warn: #f5a54a; --warn-bg: #33250f;
    --bad: #ff7b72; --bad-bg: #3a1a18; --input: #12151b;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { position: sticky; top: 0; z-index: 2; background: var(--card); border-bottom: 1px solid var(--line);
         padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
h1 { font-size: 17px; margin: 0 12px 0 0; }
main { padding: 16px; max-width: 1200px; margin: 0 auto; }
button, select, input { font: inherit; color: var(--text); }
button { border: 1px solid var(--line); background: var(--card); border-radius: 8px; padding: 7px 14px; cursor: pointer; }
button.running { background: var(--ok-bg); color: var(--ok); border-color: var(--ok); font-weight: 600; }
button.paused { background: var(--bad-bg); color: var(--bad); border-color: var(--bad); font-weight: 600; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
button:disabled { opacity: .5; cursor: default; }
select, input[type=text] { background: var(--input); border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; }
input.price { width: 84px; text-align: right; font-variant-numeric: tabular-nums; }
input.bad { border-color: var(--bad); background: var(--bad-bg); }
.spacer { flex: 1; }
.note { color: var(--muted); font-size: 13px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; margin-bottom: 16px; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); background: var(--card); }
th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
th.c, td.c { text-align: center; }
col.pkg { width: 22%; }
input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; accent-color: var(--accent); vertical-align: middle; }
tr.game td { background: var(--bg); font-weight: 600; }
tr.dirty td:first-child { box-shadow: inset 3px 0 var(--accent); }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; }
.pill.ok { background: var(--ok-bg); color: var(--ok); }
.pill.warn { background: var(--warn-bg); color: var(--warn); }
.pill.bad { background: var(--bad-bg); color: var(--bad); }
.pill.muted { background: var(--bg); color: var(--muted); }
#msg { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; display: none; }
#msg.ok { display: block; background: var(--ok-bg); color: var(--ok); }
#msg.bad { display: block; background: var(--bad-bg); color: var(--bad); }
#msg.info { display: block; background: var(--warn-bg); color: var(--warn); }
.help { margin: 0 0 14px; color: var(--muted); }
.cardhead { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--line); }
#orderBanner { padding: 14px 16px; border-radius: 10px; margin-bottom: 12px; font-size: 16px; font-weight: 600;
               background: var(--ok-bg); color: var(--ok); border: 2px solid var(--ok); cursor: pointer; }
tr.late td { color: var(--bad); }
.help b { color: var(--text); }
</style>
</head>
<body>
<header>
  <h1>Auto bid settings</h1>
  <select id="game" aria-label="Game"><option value="">All games</option></select>
  <label class="note"><input type="checkbox" id="onlyOn"> only ON</label>
  <button id="botSwitch" title="Global switch for the running bot">Bot: ...</button>
  <span id="botStatus" class="note"></span>
  <span class="spacer"></span>
  <span class="note">Check every <input type="text" inputmode="numeric" id="interval" class="price"
    style="width:48px" title="Minutes between bot checks (1 to 1440)"> min</span>
  <span class="note">Undercut <input type="text" id="undercut" class="price" style="width:60px"></span>
  <button id="reload">Reload</button>
  <button id="preview">Preview</button>
  <button id="save" class="primary" disabled>Save</button>
</header>
<main>
  <div id="orderBanner" role="alert" style="display:none"></div>
  <div id="msg"></div>
  <div class="card" id="ordersCard">
    <div class="cardhead"><b>Orders waiting for delivery</b>
      <span id="ordersInfo" class="note"></span>
      <span class="spacer"></span>
      <button id="notifyBtn" style="display:none">Turn on desktop alerts</button>
    </div>
    <div class="scroll"><table>
      <thead><tr><th>Game</th><th>Package</th><th class="num">Qty</th><th class="num">Total</th>
        <th class="num">Waiting</th><th>State</th></tr></thead>
      <tbody id="orderRows"><tr><td colspan="6" class="note">Checking orders...</td></tr></tbody>
    </table></div>
  </div>
  <p class="help"><b>Min</b> = never sell below this. <b>Max</b> = highest price when a cheaper seller
  disappears and the bot looks for the next one. Turn <b>ON</b> to let the bot manage the offer. The <b>Bot</b> button pauses or resumes all offers at once.
  Saving or switching takes effect right away.
  Saving writes <code>bidding.toml</code> only.</p>
  <div class="card scroll"><table>
    <colgroup><col class="pkg"><col><col><col><col><col><col><col></colgroup>
    <thead><tr><th>Package</th><th>State</th><th class="num">My price</th><th class="num">Market lowest</th>
      <th class="num">Min</th><th class="num">Max</th><th class="c">ON</th><th class="c">Big change</th></tr></thead>
    <tbody id="rows"><tr><td colspan="8" class="note">Loading from Eldorado...</td></tr></tbody>
  </table></div>
  <div class="card scroll" id="previewCard" style="display:none"><table>
    <thead><tr><th>Preview (nothing sent)</th><th class="num">Now</th><th class="num">Lowest other</th>
      <th class="num">Bot would set</th><th>Action</th><th>Why</th></tr></thead>
    <tbody id="previewRows"></tbody>
  </table></div>
</main>
<script>
const TOKEN = "__TOKEN__";
let data = { rows: [] };
let dirty = false;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (s) => (s === "" || s == null) ? null : Number(s);

function msg(kind, text) { const m = $("msg"); m.className = kind; m.textContent = text; }

async function call(method, url, body) {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json", "X-Token": TOKEN },
                                 body: body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || ("HTTP " + res.status));
  return json;
}

function showBot() {
  const b = $("botSwitch");
  b.textContent = data.paused ? "Bot: PAUSED (click to run)" : "Bot: RUNNING (click to pause)";
  b.className = data.paused ? "paused" : "running";
}

$("botSwitch").addEventListener("click", async () => {
  if (dirty) { msg("info", "Save your changes first."); return; }
  const want = !data.paused;
  try {
    await call("POST", "/api/config", { paused: want, rows: [] });
    data.paused = want; showBot(); setTimeout(refreshStatus, 3000);
    msg(want ? "info" : "ok", want ? "Bot paused. It sends nothing from its next cycle."
                                   : "Bot running. It works again from its next cycle (within 5 minutes).");
  } catch (e) { msg("bad", "Could not switch: " + e.message); }
});

async function refreshStatus() {
  try {
    const s = await call("GET", "/api/status");
    if (s.state === "none") { $("botStatus").textContent = "(bot runs in its own window)"; return; }
    let t = s.message || s.state;
    if (s.last_cycle) t += "  Last check " + s.last_cycle + ".";
    if (s.next_cycle && s.state !== "paused") t += " Next " + s.next_cycle + ".";
    $("botStatus").textContent = t;
    $("botStatus").style.color = s.state === "error" ? "var(--bad)" : "";
    if (s.state === "error" && !data.paused) { data.paused = true; showBot(); }
  } catch (e) { $("botStatus").textContent = "status unavailable"; }
}
setInterval(refreshStatus, 15000);

function setDirty(v) { dirty = v; $("save").disabled = !v; }

function validate(row) {
  const min = num(row.min_price), max = num(row.max_price);
  const errs = {};
  if (row.min_price && !(min > 0)) errs.min = "Min must be a number above 0";
  if (row.max_price && !(max > 0)) errs.max = "Max must be a number above 0";
  if (min > 0 && max > 0 && max < min) errs.max = "Max must be at least Min";
  if ((row.enabled || row.max_price) && !row.min_price) errs.min = "Min is required";
  return errs;
}

function marketCell(r) {
  if (r.lowest == null) return '<span class="pill muted">none</span>';
  if (r.lowest_is_me) return '<span class="pill ok">you ' + esc(r.lowest) + '</span>';
  return esc(r.lowest);
}

function render() {
  const game = $("game").value, onlyOn = $("onlyOn").checked;
  let html = "", last = null;
  data.rows.forEach((r, i) => {
    if (game && r.game !== game) return;
    if (onlyOn && !r.enabled) return;
    if (r.game !== last) { html += '<tr class="game"><td colspan="8">' + esc(r.game) + "</td></tr>"; last = r.game; }
    const e = validate(r);
    html += '<tr data-i="' + i + '"' + (r._dirty ? ' class="dirty"' : "") + ">" +
      "<td>" + esc(r.package) + '<div class="note">' + esc(r.id.slice(0, 8)) + "</div></td>" +
      '<td><span class="pill ' + (r.state === "Active" ? "ok" : "muted") + '">' + esc(r.state) + "</span></td>" +
      '<td class="num">' + esc(r.price) + "</td>" +
      '<td class="num">' + marketCell(r) + "</td>" +
      '<td class="num"><input type="text" inputmode="decimal" class="price' + (e.min ? " bad" : "") + '" data-f="min_price" value="' + esc(r.min_price) + '" title="' + esc(e.min || "") + '"></td>' +
      '<td class="num"><input type="text" inputmode="decimal" class="price' + (e.max ? " bad" : "") + '" data-f="max_price" value="' + esc(r.max_price) + '" title="' + esc(e.max || "") + '"></td>' +
      '<td class="c"><input type="checkbox" data-f="enabled" aria-label="ON"' + (r.enabled ? " checked" : "") + "></td>" +
      '<td class="c"><input type="checkbox" data-f="allow_big_change" aria-label="Big change"' + (r.allow_big_change ? " checked" : "") + "></td></tr>";
  });
  $("rows").innerHTML = html || '<tr><td colspan="8" class="note">No offers.</td></tr>';
}

$("rows").addEventListener("input", (ev) => {
  const el = ev.target, tr = el.closest("tr[data-i]");
  if (!tr || !el.dataset.f) return;
  const r = data.rows[Number(tr.dataset.i)];
  r[el.dataset.f] = el.type === "checkbox" ? el.checked : el.value.trim();
  r._dirty = true; setDirty(true); tr.classList.add("dirty");
  const e = validate(r);
  tr.querySelectorAll("input.price").forEach((inp) => {
    const k = inp.dataset.f === "min_price" ? "min" : "max";
    inp.classList.toggle("bad", !!e[k]); inp.title = e[k] || "";
  });
});
$("undercut").addEventListener("input", () => setDirty(true));
$("interval").addEventListener("input", () => {
  setDirty(true);
  const m = Number($("interval").value);
  $("interval").classList.toggle("bad", !(Number.isInteger(m) && m >= 1 && m <= 1440));
});
$("game").addEventListener("change", render);
$("onlyOn").addEventListener("change", render);

async function load(fresh) {
  if (dirty && !confirm("Discard unsaved changes?")) return;
  msg("info", "Loading from Eldorado...");
  try {
    data = await call("GET", "/api/offers" + (fresh ? "?fresh=1" : ""));
    $("undercut").value = data.undercut;
    $("interval").value = Math.round(data.interval_seconds / 60);
    $("interval").classList.remove("bad");
    showBot(); refreshStatus();
    const games = [...new Set(data.rows.map((r) => r.game))];
    const sel = $("game"), keep = sel.value;
    sel.innerHTML = '<option value="">All games</option>' + games.map((g) => "<option>" + esc(g) + "</option>").join("");
    sel.value = games.includes(keep) ? keep : "";
    setDirty(false); render();
    const age = data.data_age_seconds || 0;
    msg("ok", "Loaded " + data.rows.length + " offers" +
        (age ? " (prices from " + age + " s ago; click Reload for live prices)." : " (live prices)."));
  } catch (e) { msg("bad", "Could not load: " + e.message); }
}

async function save() {
  const minutes = Number($("interval").value);
  if (!(Number.isInteger(minutes) && minutes >= 1 && minutes <= 1440)) {
    msg("bad", "Check every: write whole minutes from 1 to 1440."); return;
  }
  const bad = data.rows.filter((r) => Object.keys(validate(r)).length);
  if (bad.length) { msg("bad", "Fix the red boxes first (" + bad.length + " offer(s))."); return; }
  $("save").disabled = true;
  try {
    const res = await call("POST", "/api/config", { undercut: $("undercut").value.trim(),
                                                    interval_seconds: minutes * 60, rows: data.rows });
    data.interval_seconds = minutes * 60;
    data.rows.forEach((r) => delete r._dirty);
    setDirty(false); render();
    msg("ok", "Saved. " + res.enabled + " offer(s) ON, bot checks every " + minutes +
        " min. A running bot uses the new values right away.");
  } catch (e) { setDirty(true); msg("bad", "Not saved: " + e.message); }
}

async function preview() {
  if (dirty) { msg("info", "Save first, Preview uses the saved settings."); return; }
  msg("info", "Checking market...");
  try {
    const res = await call("POST", "/api/preview");
    const cls = { change: "warn", keep: "ok", skip: "muted" };
    $("previewRows").innerHTML = res.decisions.map((d) =>
      "<tr><td>" + esc(d.label) + '</td><td class="num">' + esc(d.current ?? "-") + '</td><td class="num">' +
      esc(d.lowest ?? "-") + '</td><td class="num"><b>' + esc(d.target ?? "-") + '</b></td><td><span class="pill ' +
      cls[d.action] + '">' + esc(d.action) + "</span></td><td class=\"note\">" + esc(d.reason) + "</td></tr>").join("")
      || '<tr><td colspan="6" class="note">No offer is ON.</td></tr>';
    $("previewCard").style.display = "";
    msg("ok", "Preview ready. Nothing was sent to Eldorado.");
  } catch (e) { msg("bad", "Preview failed: " + e.message); }
}

// ---------- orders (F18) ----------
let knownOrders = null;          // ids seen by this page; null until the first answer
let unread = 0;
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
  b.textContent = "NEW ORDER: " + text + "  (click to dismiss)";
  b.style.display = "";
  beep();
  if ("Notification" in window && Notification.permission === "granted") {
    try { new Notification("New Eldorado order", { body: text, requireInteraction: true }); } catch (e) {}
  }
}

$("orderBanner").addEventListener("click", () => {
  $("orderBanner").style.display = "none"; unread = 0; document.title = baseTitle;
});

function showNotifyButton() {
  const btn = $("notifyBtn");
  btn.style.display = ("Notification" in window && Notification.permission === "default") ? "" : "none";
}
$("notifyBtn").addEventListener("click", async () => {
  try { await Notification.requestPermission(); } catch (e) {}
  showNotifyButton();
});

async function refreshOrders() {
  let o;
  try { o = await call("GET", "/api/orders"); }
  catch (e) { $("ordersInfo").textContent = "orders unavailable: " + e.message; return; }
  if (o.enabled === false) { $("ordersCard").style.display = "none"; return; }
  const ids = new Set([...o.pending, ...o.alerts].map((x) => x.id));
  if (knownOrders === null) { knownOrders = ids; }
  else {
    const fresh = o.alerts.filter((x) => !knownOrders.has(x.id));
    ids.forEach((id) => knownOrders.add(id));
    if (fresh.length) alertNew(fresh);
  }
  $("ordersInfo").textContent = (o.error ? "last check failed: " + o.error + ". " : "") +
    (o.last_check ? "Checked " + o.last_check + ", every minute." : "First check running...");
  $("orderRows").innerHTML = o.pending.map((x) =>
    "<tr" + (x.age_minutes > 60 ? ' class="late"' : "") + "><td>" + esc(x.game) + "</td><td>" + esc(x.package) +
    '</td><td class="num">' + esc(x.quantity) + '</td><td class="num">' + esc(x.total) + " " + esc(x.currency) +
    '</td><td class="num">' + esc(waited(x.age_minutes)) + '</td><td><span class="pill warn">' + esc(x.state) +
    "</span></td></tr>").join("") || '<tr><td colspan="6" class="note">No order is waiting. </td></tr>';
}
showNotifyButton();
refreshOrders();
setInterval(refreshOrders, 20000);

$("reload").addEventListener("click", () => load(true));
$("save").addEventListener("click", save);
$("preview").addEventListener("click", preview);
window.addEventListener("beforeunload", (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
load();
</script>
</body>
</html>
"""
