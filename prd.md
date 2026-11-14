# PRD: Eldorado Seller API Tool

| | |
|---|---|
| **Status** | Draft v0.3 |
| **Date** | 2026-11-14 |
| **Reference** | [ELDORADO_SELLER_API.md](ELDORADO_SELLER_API.md), [api-spec.md](api-spec.md) |

> **Note:** This PRD is based on Eldorado's help article. Docs for the offer, order and account endpoints are not in hand yet. Anything assumed is marked **(Assumption)**. Questions that need an answer are in "Open Questions".
>
> **This file is the project's source of truth.** The tech stack, folder structure, CLI commands and safety rules are final here. If another file disagrees with this one, this file is right and the other file must be updated.

## 1. Problem

Sellers with many offers on Eldorado do a lot of manual work every day: changing prices, updating stock (quantity), marking orders delivered, going online/offline. Doing this one by one on the website takes a lot of time and invites mistakes.

## 2. Goal

Build a tool on the Eldorado Seller API that automates the seller's repetitive tasks.

**Success metrics:**
- One command can update the price of every offer of a game.
- When the token expires, the tool gets a new one by itself; the user does nothing.
- No Client secret or access token ever goes into code, logs, disk or git.

## 3. User

- **Primary:** a verified Eldorado seller (you) with many offers. **Only verified sellers can use the Seller API.**
- **Secondary (later):** members of a team account. **(Assumption: the article does not say whether team members can use the API.)**

## 4. Scope

### 4.0 Focus (2026-11-14)

The user works only with **TopUp offers**, **of any game**. A new TopUp offer uploaded to the account appears on the page by itself; a deleted one disappears, and Save removes its settings too. Currently: CODM, Brawl Stars, Clash of Clans, Clash Royale, Roblox, PUBG Mobile, TikTok, Free Fire, Yalla Ludo, ChatGPT. The main feature is **auto bidding (F16)**. The other features stay built but are not the priority.

TopUp offers fall under Swagger's **Predefined offer** API (`/api/predefinedOffers/...`). **(Assumption:** to be confirmed with the first read-only call.)

### 4.1 MVP (Phase 1)

| # | Feature | Description |
|---|---|---|
| F1 | **Auth / Token manager** ✅ | Read the Client ID and secret from `.env`. Get a token with `POST https://eldorado.gg/api/authentication/seller/token`. The token expires after 15 minutes, so get a new one when 60 seconds are left. If a request is rejected for authentication, get a new token and try **once** more. (**Assumption:** a rejection returns status code 401.) |
| F2 | **Offer list** | Show offers, filter by game or status (active/paused). (**Assumption:** the API has a list operation. The article does not mention listing separately.) |
| F3 | **Offer update** | Update the price, quantity and delivery time of one offer or of every offer of a game. |
| F4 | **Pause / resume** | Pause and resume one or many offers. |
| F5 | **Order list** | Show orders, filter by status. |
| F6 | **Mark delivered** | Mark an order as delivered. |
| F7 | **Online / offline** | Set the seller status online or offline. |
| F8 | **Dry-run mode** | `--dry-run` on every write command. Shows what would change, but sends no write request. |
| F15 | **Audit log** | Record every change (including dry runs) in `logs/audit.jsonl`. |
| F16 | **Auto bidding** | For each TopUp offer, find the lowest Active price of other sellers for the same game and the same package, and set the price **0.01 lower**. If already the lowest, the price **stays as it is** (the API does not give the 2nd price, see 9.1 below). Never go below each offer's **fixed minimum price (floor)**. Runs only on the offers listed in `bidding.toml`. Runs every **5 minutes**. |
| F18 | **New order alert** | `ui`/`app` reads seller orders every 60 seconds (read-only, `GET /api/v1/orders/me/seller/orders`). A new order triggers a banner + sound + tab title on the page, a desktop notification (if allowed) and a beep in the app window. The page has an "Orders waiting for delivery" table (Paid orders, how long they have waited, red after 1 hour). No alert for orders that existed before the app started. Buyer information is not kept and never written to disk. |
| F17 | **Settings page** | `eldorado ui` opens a local web page (`http://127.0.0.1:8765`, on this computer only). It shows each offer's market price, and edits Min, Max and ON/OFF, saving them to `bidding.toml`. **Preview** shows what prices the bot would set, and sends nothing. The page never sends a write to Eldorado. No new dependency (Python `http.server`). |

### 4.2 Phase 2

| # | Feature | Description |
|---|---|---|
| F9 | **Offer create / delete** | Create and delete currency, top-up, item, account and boosting offers. |
| F10 | **CSV bulk upload** | Upload many offers at once from a CSV file. |
| F11 | **Order cancel / fix delivery details** | Cancel orders and correct delivery details. |
| F12 | **Invoice** | Generate an order's invoice. |
| F13 | **Notifications and restrictions** | Read notifications and check account restrictions. |
| F14 | **Scheduler** | Run tasks at set times, e.g. go offline every night at 12. |

### 4.3 Out of Scope

The Eldorado API does not support these, so this tool will not either:
- Withdrawals and balance
- Messages, disputes and feedback
- Account settings, verification and offer limit requests
- Offer images and sales reports

One more thing is out of scope: **the website's internal endpoints** (found through browser dev tools or HAR files) will not be used. Only the official Seller API is used.

## 5. Requirements

### 5.1 Functional
- A valid token must exist before every API call (F1).
- A command that changes offers or orders shows what will change (before and after) before running, and asks for confirmation unless `--yes` is given.
- After a bulk update, show a summary of how many offers succeeded and how many failed.

### 5.2 Security
- The Client ID and secret live only in the `.env` file. `.env` is listed in `.gitignore`.
- The access token lives **in memory only**. It is never written to disk, a database or a log.
- Logs, error messages and the terminal never show a secret or token. Where one would appear, show `***REDACTED***`.
- There is a `.env.example` file with only the field names, no real values.

### 5.3 Reliability (retry rules)

| What happened | What the tool does |
|---|---|
| Rejected for authentication | Get a new token and retry **once**; if it fails again, show an error |
| Too many requests (rate limit, **Assumption:** 429) | Wait, honoring `Retry-After` when present, at most 3 tries |
| Network or 5xx error on a read request | Exponential backoff + jitter, at most 3 tries |
| Timeout, network or 5xx error on a **write** request | **No automatic retry.** Whether the change happened is unknown, so tell the user to check the dashboard |

### 5.4 Safety (live environment)
Eldorado has no test environment. Therefore:
- When changing several offers, run on **1 offer** first (pilot). If the pilot fails, the rest are not run. If the pilot passes, ask for confirmation again for the rest. With `--yes` no confirmation is asked, but the pilot still runs first.
- Every write command has the `--dry-run` flag.
- If a price changes by **more than 50%** (up or down), the command stops, unless `--allow-big-change` is given.
- Prices are kept as `Decimal`, never float.

### 5.5 Credential
- The API does not tell when a credential expires. So `.env` can hold `ELDORADO_CREDENTIAL_EXPIRES=YYYY-MM-DD` (optional). When 7 days or fewer are left, the tool shows a warning.
- To rotate a credential without stopping work: create a new credential on the dashboard, update `.env`, then revoke the old one. (An account can have at most 2 active credentials.)

## 6. Technical Decisions (final)

| Topic | Decision |
|---|---|
| Language | Python 3.11+ |
| CLI | `typer` (tables and colors with `rich`) |
| HTTP client | `httpx`, **sync only** (`httpx.Client`) |
| Models and validation | `pydantic` v2 |
| Config | `pydantic-settings` (reads the `.env` file) |
| Audit log | `logs/audit.jsonl` (one JSON per line) |
| Database | **Not needed in the MVP.** SQLite in Phase 2 if needed |
| Tests | `pytest` + `respx` (every HTTP call mocked, no live calls) |

### 6.1 Folder structure (final)
```
eldorado_Seller_Api/
├── AGENTS.md                   # Rules for AI agents and developers
├── README.md                   # User guide (English)
├── prd.md                      # Product requirements, source of truth
├── ELDORADO_SELLER_API.md      # Notes from the official article
├── api-spec.md                 # API spec (confirmed / assumed / unknown)
├── architecture.md             # Architecture
├── database.md                 # Local data and audit log format
├── requirement-validation.md   # Traceability and test plan
├── pyproject.toml
├── .env.example
├── .gitignore
├── bidding.example.toml        # template; bidding.toml (ignored) holds Min/Max/ON per offer
├── runme.ps1                   # one-click setup + start (Windows)
├── logs/                       # audit.jsonl, bot.lock (ignored by git)
├── src/eldorado/
│   ├── __init__.py
│   ├── __main__.py             # `python -m eldorado`
│   ├── cli/                    # Typer commands
│   │   ├── main.py
│   │   ├── offers.py
│   │   ├── orders.py
│   │   ├── account.py          # status online/offline
│   │   ├── bid.py              # bid run
│   │   ├── ui.py               # ui and app (local page server)
│   │   ├── ui_page.py          # the page HTML/JS
│   │   └── shared.py
│   ├── services/               # Business rules: diff, pilot, 50% guard, audit
│   │   ├── offers.py
│   │   ├── orders.py
│   │   ├── account.py
│   │   ├── bidding.py          # decide() + Bidder (F16)
│   │   ├── bot_runner.py       # bot thread for `eldorado app`
│   │   ├── order_watch.py      # new-order alert (F18), read-only
│   │   └── dashboard.py        # page data, save, preview
│   ├── client/                 # HTTP only
│   │   ├── auth.py             # Token manager
│   │   ├── base.py             # Base client, retry rules, error mapping
│   │   ├── offers.py
│   │   ├── orders.py
│   │   └── account.py
│   ├── models/                 # Pydantic models
│   │   ├── auth.py
│   │   ├── offer.py
│   │   └── order.py
│   └── core/
│       ├── config.py
│       ├── exceptions.py
│       ├── logging.py          # Secret masking
│       ├── audit.py            # audit.jsonl writer
│       ├── bidding_config.py   # bidding.toml load/save
│       └── instance_lock.py    # one live bot at a time
└── tests/
    ├── conftest.py
    ├── factories.py            # Swagger-shaped JSON for mocked responses
    ├── test_auth.py
    ├── test_offers.py
    ├── test_orders.py
    ├── test_account.py
    ├── test_cli.py
    ├── test_dry_run.py
    ├── test_audit.py
    ├── test_resilience.py
    ├── test_safety_regressions.py  # regression tests from the 2026-11-14 audit
    ├── test_security.py
    ├── test_bidding.py
    ├── test_bot_runner.py
    ├── test_order_watch.py
    ├── test_ui.py
    └── test_audit_fixes.py
```

### 6.2 CLI commands (final)

Every write command has `--dry-run` and `--yes`. TopUp offers only.

| Command | Options | Feature | Status |
|---|---|---|---|
| `eldorado auth check` | | F1 (checks the credential by getting a token, changes nothing) | ✅ |
| `eldorado offers list` | `--game GAMEID`, `--status active/paused/closed/offline`, `--limit N` | F2 | ✅ |
| `eldorado offers update` | `--id ID`, `--price X`, `--allow-big-change` | F3 (one offer's price) | ✅ |
| `eldorado offers pause/resume <offer_id>...` | | F4 (with several ids, the first is the pilot) | ✅ |
| `eldorado status online` / `offline` | | F7 | ✅ |
| `eldorado bid run` | `--once`, `--interval SECONDS`, `--config PATH` | F16 | ✅ |
| `eldorado ui` | `--port` (default 8765), `--no-browser` | F17 (settings page only) | ✅ |
| `eldorado app` | `--port`, `--no-browser` | F17 (page + bot in one window, starts **PAUSED**, RUN from the page) | ✅ |
| `eldorado orders deliver <order_id>` | | F6 | dry-run ✅, live disabled |
| `eldorado offers update --game`, `--quantity`, `--delivery-time` | | F3 bulk | ❌ not built (not needed) |
| `eldorado orders list` | | F5 | ❌ not built |

Only one live bot (`app` or `bid run`) can run at a time. `logs/bot.lock` blocks a second bot.

**Example:**
```
eldorado offers list --status active --limit 10
eldorado offers update --id <offer_id> --price 4.99 --dry-run
eldorado bid run --once --dry-run
eldorado app
```

## 7. Milestones

| Phase | Work | Condition |
|---|---|---|
| M0 | Collect the official endpoint docs | Get the API reference from the dashboard or support |
| M1 | Project setup (`pyproject.toml`, `.env.example`, `.gitignore`) + F1 (Auth) | Client ID and secret in hand |
| M2 | F2 - F8, F15 (MVP) | M0 done |
| M3 | Pilot test on one real offer (no-op update with the same price) | M2 done |
| M4 | Phase 2 features | M3 done |

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| No test environment; a wrong request can change live offers | High | Dry run, confirmation, pilot, 50% price guard |
| Endpoint docs not available | High | Check the dashboard in M0; if not found, email support |
| A write request times out and the change happens twice | Medium | Write requests are never retried automatically |
| Secret or token leak | Medium | `.env` + `.gitignore`, token in memory only, masked in logs |
| Credential expires and the tool stops working | Medium | Early warning via `ELDORADO_CREDENTIAL_EXPIRES` |
| Rate limit unknown | Medium | Retry + backoff, delay between bulk requests |

## 9. Open Questions

1. ~~What are the **base URL and endpoint list** for offers, orders and account?~~ **Answer (Swagger, 2026-11-14):** `https://www.eldorado.gg/swagger/seller/index.html`. The full list is in `api-spec.md` section 4. Each offer type has its own API (Currency, Item, Account, Predefined, Boosting, Swap).
2. ~~What is the token request body format?~~ **Answer (dashboard):** JSON `{"clientId", "clientSecret"}`, response `{"accessToken", "expiresIn": 900, "tokenType": "Bearer"}`.
3. ~~Is the `Authorization` header format `Bearer <token>`?~~ **Answer (dashboard):** Yes, `Authorization: Bearer <access_token>`.
3a. ~~What goes in the request body of `PUT /api/orders/me/{orderId}/delivered`?~~ **Answer (Swagger):** This path is not in Swagger. The correct path is `PUT /api/v1/orders/me/{orderId}/deliver`, with no body.
4. What is the **rate limit**, and what are the error status codes?
5. ~~Is there a separate endpoint for bulk updates?~~ **Answer (Swagger):** Yes. Every offer type has bulk price, delivery time, pause and resume by game.
6. Can team account members use the API?
7. **Which offer types** (Currency, Item, Account, TopUp/GiftCard) and which games will you work with? This decides which APIs the MVP needs. Which feature is needed first?
8. Will the tool be CLI only, or is a web dashboard needed later too?
9. ~~Is auto pricing needed?~~ **Answer:** Yes, F16. Competitor prices come from `GET /api/predefinedOffers/game` (a public endpoint in Swagger).
10. ~~Must Swagger's `swagger` header be sent?~~ **Answer (live):** No, every call works without the header.

### 9.1 Auto bidding rules (F16, final)

| Rule | Value |
|---|---|
| Undercut | Fixed `0.01` (can be changed in `bidding.toml`) |
| Target price | `min(other sellers' Active prices) - 0.01`, rounded down to 2 decimals |
| Floor | Every offer needs a `min_price`. If the target is below the floor, price = floor |
| Ceiling | Optional `max_price`. If the target is above it, price = ceiling |
| No competitor | Price is not changed |
| Held at Min, then #1 | The cheaper seller (below Min) has left. With `max_price`, the bot goes to `max_price` for one cycle. The next cycle sees the real next seller on the market and goes 0.01 below it (e.g. 4.50 -> 4.49). Without `max_price` it stays at Min |
| Already #1 | Price is not changed. The market endpoint returns **only one offer** per package (the cheapest), so when you are #1 the 2nd price is not visible. The user wanted "raise the price", but the API makes that impossible (live, 2026-11-14) |
| Package match | `attributes[].id` + `attributes[].value.id`, e.g. `call-of-duty-mobile-cp=80-cp`. Offers with an unknown package are skipped |
| Game | No filter by game. Names: `GAME_NAMES` (59 CODM, 56 Brawl Stars, 18 Clash of Clans, 52 Clash Royale, 70 Roblox, 21 PUBG Mobile, 254 TikTok, 46 Free Fire, 378 Yalla Ludo, 385 ChatGPT); for an unknown game the name comes from the offer's SEO alias |
| Region | The package match also requires the same trade environment (e.g. Free Fire's Region) |
| Own offers | Not counted as competitors |
| Currency | USD offers only. Other currencies are skipped |
| 50% guard | A change of more than 50% at once is skipped, unless the offer has `allow_big_change = true` |
| Pilot | The first change of every cycle is the pilot. If the pilot fails, the rest of that cycle's changes are not made |
| Write outcome unknown | The whole bot stops (no retry after a timeout or 5xx) |
| Audit log cannot be written | Same as an unknown outcome: `eldorado app` pauses itself, `bid run` stops. The bot never keeps running without an audit record, so an unknown write is never sent again |
| Pause mid-cycle | `paused` is re-read before every live write. Once paused, the rest of the cycle's writes are not sent (`not_sent`) |
| Confirm | Confirm once at start, not with `--yes` |
