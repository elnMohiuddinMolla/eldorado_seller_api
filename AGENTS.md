# AGENTS.md: AI Developer & Agent Guidelines

Rules for any AI coding agent or developer working in the **Eldorado Seller API Tool** repository.

> **Source of truth:** [prd.md](prd.md) defines the tech stack, folder structure, CLI commands and safety rules. If any document disagrees with `prd.md`, follow `prd.md` and update the other document.

---

## 1. Prime Directive: No Unintended Live Changes

> [!CAUTION]
> **ELDORADO.GG HAS NO TEST / SANDBOX ENVIRONMENT.**
> Every live write request changes real offers, prices, orders and seller status.

### Safety Rules
1. **Never send an unmocked HTTP request** in tests or automated tasks. Mock everything with `respx`.
2. **Every write command has `--dry-run`**, and dry-run sends zero write requests.
3. **Never log, print, store or commit secrets.** `ELDORADO_CLIENT_ID` and `ELDORADO_CLIENT_SECRET` are read only from `.env` via `pydantic-settings`. The access token lives **in memory only**.
4. **Write commands ask for confirmation** unless `--yes` is passed. `--yes` never skips the 1-item pilot.
5. **Never retry a write automatically** after a timeout, network error or 5xx. Raise `WriteOutcomeUnknownError`.
6. **Only use endpoints marked `[Confirmed]` in `api-spec.md`.** Never invent paths. Never use website internal endpoints or HAR files.

---

## 2. Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer, with Rich for tables and colors |
| HTTP | HTTPX, **sync only** (`httpx.Client`) |
| Models | Pydantic v2 |
| Config | `pydantic-settings` (reads `.env`) |
| Audit log | `logs/audit.jsonl` (format in [database.md](database.md)) |
| Database | None in the MVP |
| Testing | `pytest`, `respx` |

Do not add a dependency that is not listed here without updating `prd.md` first.

---

## 3. Directory Structure

```
eldorado_Seller_Api/
├── AGENTS.md                   # This file
├── README.md                   # User guide (Bangla)
├── prd.md                      # Product requirements, source of truth (Bangla)
├── ELDORADO_SELLER_API.md      # Notes from the official article (Bangla)
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
    ├── test_safety_regressions.py  # audit fixes (2026-11-14)
    ├── test_security.py
    ├── test_bidding.py
    ├── test_bot_runner.py
    ├── test_order_watch.py
    ├── test_ui.py
    └── test_audit_fixes.py
```

Layer rule: `cli` -> `services` -> `client` -> Eldorado. `models` and `core` can be used by every layer. Lower layers never import upper layers.

---

## 4. Coding Standards

### 4.1 Types and Validation
- Every function has full type hints.
- Request and response bodies use Pydantic v2 models. No raw dicts across layers.
- Money is `Decimal`, never `float`.

### 4.2 Errors
Wrap `httpx` errors in domain exceptions from `core/exceptions.py`:

| Exception | When |
|---|---|
| `AuthenticationError` | Token request fails, or a request is still rejected after one renewal |
| `RateLimitExceededError` | Still rate limited after 3 tries |
| `ResourceNotFoundError` | Offer or order id not found |
| `WriteOutcomeUnknownError` | A write timed out or got a network error or 5xx. Not retried |
| `EldoradoAPIError` | Any other API error |

### 4.3 Retry Rules
| Situation | Rule |
|---|---|
| Auth rejected | Renew token, retry once |
| Rate limited | Wait (`Retry-After` if present), max 3 tries |
| Read: network or 5xx | Exponential backoff with jitter (factor 1.5s), max 3 tries |
| Write: timeout, network or 5xx | **No retry** |

### 4.4 Logging
- Mask the Client secret, the access token and `Authorization` header values as `***REDACTED***` everywhere: logs, terminal, exception text, audit log.
- Write one audit record per change (including dry runs) to `logs/audit.jsonl` using `core/audit.py`.

---

## 5. Development Workflow

### 5.1 Setup
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

### 5.2 Tests
```powershell
pytest -v
pytest --cov=src/eldorado --cov-report=term-missing
pytest tests/test_dry_run.py -v
```

### 5.3 Working With the Live Account (strict)
Only when the user asks for it, and only with endpoints marked `[Confirmed]`:
1. The user puts real credentials in `.env`. Never ask the user to paste the secret into chat.
2. Read-only first: `eldorado offers list --limit 1`.
3. Dry run on one offer: `eldorado offers update --id <ID> --price <CURRENT_PRICE> --dry-run`.
4. Live no-op on the same offer (same price), then check the dashboard.
5. Always show the exact change before running it:
   ```
   [DRY-RUN] Would update offer 123456:
     Price: 10.00 -> 9.50 (-5.0%)
     Quantity: 50 -> 50 (unchanged)
   ```

---

## 6. Documentation Language

- User docs (`README.md`, `prd.md`, `ELDORADO_SELLER_API.md`): Bangla.
- Technical and agent docs (all other `.md` files): English.

---

## 7. Agent Checklist

- [ ] Every endpoint I used is `[Confirmed]` in `api-spec.md`.
- [ ] New dependencies are in `pyproject.toml` and allowed by `prd.md`.
- [ ] `.env` and `logs/` are in `.gitignore`.
- [ ] All HTTP calls in tests are mocked with `respx`.
- [ ] Every write command has `--dry-run` and `--yes`, and a dry-run test.
- [ ] No write is retried automatically.
- [ ] I updated `prd.md`, `api-spec.md`, `README.md` or `architecture.md` if behavior changed.
