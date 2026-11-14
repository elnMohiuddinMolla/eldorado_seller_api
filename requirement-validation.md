# Requirements Traceability & Validation Matrix

Verification strategy and acceptance criteria for the **Eldorado Seller API Tool**. Every MVP requirement in [prd.md](prd.md) maps to a test.

> All tests mock HTTP with `respx`. No test ever calls the live Eldorado API.
> Offer, order and account paths are unknown (see [api-spec.md](api-spec.md)). Tests use the path constants defined in `src/eldorado/client/`, so they stay correct when real paths are filled in.

---

## 1. Requirements Traceability Matrix

| Req ID | Requirement | Test file | Pass criteria |
|---|---|---|---|
| **F1** | Token request and renewal | `tests/test_auth.py` | Token requested with `POST /api/authentication/seller/token`. Renewed when 60s or less remain. After an auth rejection, renewed and retried **exactly once**. Token never written to disk. |
| **F2** | Offer list and filters | `tests/test_offers.py` | `--game`, `--status`, `--limit` are applied. |
| **F3** | Offer update | `tests/test_offers.py` | Before/after table shown. Price change over 50% blocked without `--allow-big-change`. Multi-offer change runs a 1-offer pilot first and stops if it fails. Prices handled as `Decimal`. |
| **F4** | Pause / resume | `tests/test_offers.py` | Correct operation called for each id. |
| **F5** | Order list | `tests/test_orders.py` | Orders parsed and filtered by `--status`. |
| **F6** | Mark delivered | `tests/test_orders.py` | Confirmation required unless `--yes`. Answering `n` sends nothing. |
| **F7** | Online / offline | `tests/test_account.py` | Correct value sent for `online` and `offline`. |
| **F8** | Dry-run | `tests/test_dry_run.py` | **Zero** write requests for every write command when `--dry-run` is set. |
| **F15** | Audit log | `tests/test_audit.py` | One JSON line per change in `logs/audit.jsonl`, with the fields in [database.md](database.md). Dry runs have `outcome = "dry_run"`. |
| **F16** | Auto bidding | `tests/test_bidding.py` | Target = lowest other Active seller of the same package - 0.01, rounded down. Never below `min_price`, never above `max_price`. Own offers, other packages and paused offers ignored. Raises price when already cheapest. Over 50% skipped unless allowed. First change is the pilot; failed pilot stops the cycle. Unknown write outcome stops the bot, no retry. Dry run sends zero writes. Invalid `bidding.toml` refused. |
| **F17** | Settings page and app | `tests/test_ui.py`, `tests/test_bot_runner.py` | Page needs the per-run token and a local Host. Save merges rules and refuses bad values without touching the file. Preview sends no writes. App starts PAUSED; a Save wakes the bot at once; an unknown outcome or any unexpected error pauses the bot in `bidding.toml` and shows the error. |
| **NFR-ONE** | One live bot | `tests/test_audit_fixes.py` | A second live bot (`app` or `bid run`) is refused while `logs/bot.lock` is held; dry-run is allowed. |
| **NFR-SEC** | No secret leaks | `tests/test_security.py` | Secret, token and `Authorization` value never appear in log output, CLI output, exception text or the audit log. |
| **NFR-REL** | Retry rules | `tests/test_resilience.py` | Rate limit: waits, maximum 3 tries. Read with 5xx: maximum 3 tries. **Write with timeout or 5xx: no retry**, raises `WriteOutcomeUnknownError`. |

Git history leaks are checked by a pre-commit secret scanner (for example `gitleaks`), not by `pytest`.

---

## 2. Detailed Scenarios

### 2.1 F1-A: Proactive Token Renewal
- **Given:** token in memory expires in 45 seconds.
- **When:** `get_token()` is called.
- **Then:** exactly one `POST /api/authentication/seller/token` is made before the business request.

### 2.2 F1-B: Renew Once After Rejection
- **Given:** a valid-looking token. The mocked offers endpoint rejects the first call for authentication and accepts the second.
- **When:** the offer list is requested.
- **Then:** 2 calls to the offers endpoint and 1 extra token request.
- **And:** if the second call is also rejected, `AuthenticationError` is raised with no third call.

### 2.3 F3 + F8: Dry-Run Sends No Writes
- **Given:** the user runs:
  ```powershell
  eldorado bid run --once --dry-run
  ```
- **Then:**
  1. Current offers are read (read requests are allowed).
  2. The before/after table is printed.
  3. Audit log gets records with `dry_run = true`.
  4. No write request is sent.
- **Check:**
  ```python
  writes = [c for c in respx.calls if c.request.method in {"POST", "PUT", "PATCH", "DELETE"}]
  # The token request is a POST, so exclude it:
  writes = [c for c in writes if c.request.url.path != "/api/authentication/seller/token"]
  assert len(writes) == 0
  ```

### 2.4 F3: Pilot Failure Stops the Batch
- **Given:** 5 offers for the game. The mocked update fails for the first offer.
- **Then:** exactly 1 update request is sent. The other 4 offers are not touched. Summary shows the failure.

### 2.5 F3: Big Price Change Guard
- **Given:** current price `10.00`, requested price `4.00` (60% drop).
- **Then:** without `--allow-big-change`, the command stops and sends no write. With the flag, it continues to the pilot.

### 2.6 F6: Deliver With Confirmation
- **When:** `eldorado orders deliver <order_id>`.
- **Then:** prompt `Mark order <order_id> as delivered? [y/N]`. Answer `n` sends nothing. Answer `y` sends one deliver request.

### 2.7 NFR-REL: Write Timeout Is Not Retried
- **Given:** the mocked update request times out.
- **Then:** exactly 1 update request. `WriteOutcomeUnknownError` raised. Audit record has `outcome = "unknown"`. Message tells the user to check the dashboard.

---

## 3. Go / No-Go Checklist

Before using the tool on the live account:

- [ ] 1. All tests pass with at least 85% branch coverage (`pytest --cov`).
- [ ] 2. `tests/test_dry_run.py` passes for every write command.
- [ ] 3. `tests/test_security.py` passes: no secrets in any output.
- [ ] 4. `.env` and `logs/` are in `.gitignore`.
- [ ] 5. Every endpoint used is marked `[Confirmed]` in `api-spec.md`.
- [ ] 6. Pilot live test: one real offer updated to its **current** price (no real change), result checked on the dashboard.
