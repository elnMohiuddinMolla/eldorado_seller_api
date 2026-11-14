# Local Data & Persistence

This document defines what the **Eldorado Seller API Tool** stores on the local machine.

> **Source of truth:** [prd.md](prd.md). The MVP uses **no database**. It stores only an append-only audit log file.

---

## 1. What Is Stored Where

| Data | Where | Why |
|---|---|---|
| Client ID and Client secret | `.env` (in `.gitignore`) | Needed to request tokens |
| Access token | **Memory only** (never on disk) | The token can change live offers and orders for 15 minutes, so it is not saved |
| Audit log | `logs/audit.jsonl` (in `.gitignore`) | A record of every change, including dry runs |
| Bot lock | `logs/bot.lock` (in `.gitignore`) | Holds the PID of the one running live bot. The OS releases the lock when the process ends |
| Bidding config | `bidding.toml` (in `.gitignore`), template `bidding.example.toml` | Which offers the bot may change, with `min_price` / `max_price` |
| Offers and orders | Not stored. Read from the API when needed | Avoids stale data and keeps buyer data off the disk |

---

## 2. Audit Log Format (`logs/audit.jsonl`)

- One JSON object per line, appended only, never edited.
- UTF-8, timestamps in UTC ISO 8601.
- Money values are **strings** (for example `"4.99"`) so no precision is lost. In code they are `Decimal`.
- Never contains the Client secret, the access token, `Authorization` headers or buyer personal data.

### 2.1 Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `ts` | string | `"2026-11-14T13:25:00Z"` | Time of the action (UTC) |
| `run_id` | string | `"7f3c..."` | One id per CLI command, groups pilot and remaining items |
| `action` | string | `"offer.update"` | See 2.2 |
| `entity_type` | string | `"offer"` | `offer`, `order` or `seller_status` |
| `entity_id` | string | `"123456"` | Offer or order id from Eldorado |
| `before` | object or null | `{"price": "5.99"}` | Only the fields being changed |
| `after` | object or null | `{"price": "4.99"}` | Requested new values |
| `dry_run` | boolean | `false` | `true` when nothing was sent |
| `pilot` | boolean | `true` | `true` for the first item of a multi-item change |
| `outcome` | string | `"success"` | `success`, `failed`, `unknown`, `skipped`, `dry_run` |
| `http_status` | integer or null | `200` | Null for dry runs and network errors |
| `message` | string or null | `"timeout"` | Short error or note, secrets masked |

`outcome = "unknown"` means a write timed out or got a server error. The tool did not retry, and the user must check the dashboard.

### 2.2 Action Names

| Action | Feature |
|---|---|
| `offer.update` | F3 |
| `offer.pause` | F4 |
| `offer.resume` | F4 |
| `order.deliver` | F6 |
| `seller.status` | F7 |
| `offer.bid` | F16 (auto bidding price change, `http_status` recorded) |

Phase 2 adds `offer.create`, `offer.delete`, `offer.csv_upload`, `order.cancel`, `order.correct_delivery`.

### 2.3 Example Lines

```json
{"ts":"2026-11-14T13:25:00Z","run_id":"7f3c1a","action":"offer.update","entity_type":"offer","entity_id":"123456","before":{"price":"5.99"},"after":{"price":"4.99"},"dry_run":false,"pilot":true,"outcome":"success","http_status":200,"message":null}
{"ts":"2026-11-14T13:26:10Z","run_id":"9a2b44","action":"seller.status","entity_type":"seller_status","entity_id":"me","before":null,"after":{"online":false},"dry_run":true,"pilot":false,"outcome":"dry_run","http_status":null,"message":null}
```

The ids above are examples only. Real offer and order ids are UUIDs (for example `3fa85f64-5717-4562-b3fc-2c963f66afa6`).

---

## 3. Retention

- The audit log is never deleted automatically.
- When the file is larger than 10 MB, rename it to `audit-YYYYMMDD.jsonl` and start a new `audit.jsonl`.
- The user can delete old files by hand.

---

## 4. Phase 2: Optional SQLite

Add a database only if a Phase 2 feature really needs it, for example:
- **F10 CSV bulk upload:** tracking which rows of a large file were uploaded, so a stopped job can continue.
- **F14 Scheduler:** storing scheduled jobs.

Rules if SQLite is added later:
- Never store the access token or Client secret in it.
- Store money as `TEXT` (decimal string) or as integer cents, never `REAL`.
- Keep the ERD and the `CREATE TABLE` statements in this file identical (same table names, same foreign keys).
- If `PRAGMA incremental_vacuum` is used, set `PRAGMA auto_vacuum = INCREMENTAL` before creating any table.
