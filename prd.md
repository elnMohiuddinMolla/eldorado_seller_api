# PRD: Eldorado Seller API Tool

| | |
|---|---|
| **Status** | Draft v0.3 |
| **Tarikh** | 2026-11-14 |
| **Reference** | [ELDORADO_SELLER_API.md](ELDORADO_SELLER_API.md), [api-spec.md](api-spec.md) |

> **Note:** Ei PRD Eldorado er help article er upor base kore lekha. Offer, order ar account er endpoint er docs ekhono hate ashe ni. Je jinish dhore neya hoyeche seta **(Assumption)** diye mark kora. Ja uttor dorkar seta "Open Questions" e ache.
>
> **Ei file ta project er source of truth.** Tech stack, folder structure, CLI command ar safety rule ekhane final kora. Onno file er sathe ei file er na mille ei file ta thik dhorte hobe, ar onno file ta update korte hobe.

## 1. Problem

Eldorado te jader onek offer ache, tader protidin hate onek kaj korte hoy: price bodlano, stock (quantity) update kora, order deliver mark kora, online/offline hoya. Website e eshob ekta ekta kore korte onek shomoy lage ar bhul hoyar chance thake.

## 2. Goal

Eldorado Seller API use kore ekta tool banano jeta seller er bar bar kora kaj gulo automate korbe.

**Success metric:**
- Ek command e ek game er shob offer er price update kora jabe.
- Token expire hole tool nijei notun token nebe, user ke kichu korte hobe na.
- Kono Client secret ba access token code, log, disk ba git e jabe na.

## 3. User

- **Primary:** Eldorado er verified seller (apni nije), jar onek offer ache. **Shudhu verified seller ra Seller API use korte pare.**
- **Secondary (pore):** Team account er member ra. **(Assumption: team member ra API use korte parbe kina article e bola nei.)**

## 4. Scope

### 4.0 Focus (2026-11-14)

User shudhu **TopUp offer** niye kaj korbe, **je kono game er**. Account e notun TopUp offer upload korle page e nijei ashe, delete korle chole jay, ar Save e tar settings o muche jay. Ekhon: CODM, Brawl Stars, Clash of Clans, Clash Royale, Roblox, PUBG Mobile, TikTok, Free Fire, Yalla Ludo, ChatGPT. Mul kaj holo **auto bidding (F16)**. Baki feature banano thakbe, kintu agrader na.

TopUp offer Swagger er **Predefined offer** API te pore (`/api/predefinedOffers/...`). **(Assumption:** prothom read-only call e confirm korte hobe.)

### 4.1 MVP (Phase 1)

| # | Feature | Description |
|---|---|---|
| F1 | **Auth / Token manager** ✅ | `.env` theke Client ID ar secret pora. `POST https://eldorado.gg/api/authentication/seller/token` diye token neya. Token 15 minute por expire hoy, tai 60 second baki thakte notun token neya. Request authentication er karone reject hole notun token niye **ekbar** abar try kora. (**Assumption:** reject hole status code 401 ashe.) |
| F2 | **Offer list** | Offer dekha, game ba status (active/paused) diye filter kora. (**Assumption:** API te list operation ache. Article e list er kotha alada kore bola nei.) |
| F3 | **Offer update** | Ekta offer ba ek game er shob offer er price, quantity ar delivery time update kora. |
| F4 | **Pause / resume** | Ekta ba onek offer pause ar resume kora. |
| F5 | **Order list** | Order dekha, status diye filter kora. |
| F6 | **Mark delivered** | Order ke delivered mark kora. |
| F7 | **Online / offline** | Seller status online ba offline kora. |
| F8 | **Dry-run mode** | Shob write command e `--dry-run`. Ki bodlabe dekhabe, kintu kono write request pathabe na. |
| F15 | **Audit log** | Protita change (dry-run shoho) `logs/audit.jsonl` e likhe rakha. |
| F16 | **Auto bidding** | Protita TopUp offer er jonno same game ar same package er onno seller der shobcheye kom Active price khuje, tar cheye **0.01 kom** price set kora. Already shobcheye kom thakle price **jemon ache temon thake** (API 2nd price dey na, nicher 9.1 dekhun). Protita offer er **fixed minimum price (floor)** er niche kokhono namabe na. Shudhu `bidding.toml` e lekha offer gulo te chalbe. Proti **5 minute** por por chalbe. |
| F18 | **Notun order alert** | `ui`/`app` proti 60 second e seller order pore (shudhu read, `GET /api/v1/orders/me/seller/orders`). Notun order ashle page e banner + shobdo + tab title, desktop notification (allow korle), app window e beep. Page e "Orders waiting for delivery" table (Paid order, koto khon opekkha, 1 ghontar beshi hole lal). App start er age er order e alert hoy na. Buyer er tottho rakha hoy na, disk e o lekha hoy na. |
| F17 | **Settings page** | `eldorado ui` ekta local web page khole (`http://127.0.0.1:8765`, shudhu ei computer e). Protita offer er market price dekhay, Min, Max, ON/OFF edit kore `bidding.toml` e save kore. **Preview** dekhay bot ki price set korto, kichu pathay na. Page theke Eldorado te kono write jay na. Notun dependency nei (Python `http.server`). |

### 4.2 Phase 2

| # | Feature | Description |
|---|---|---|
| F9 | **Offer create / delete** | Currency, top-up, item, account ar boosting offer banano ar delete kora. |
| F10 | **CSV bulk upload** | CSV file theke onek offer ek sathe upload kora. |
| F11 | **Order cancel / delivery details thik kora** | Order cancel kora ar delivery details correct kora. |
| F12 | **Invoice** | Order er invoice generate kora. |
| F13 | **Notifications ar restrictions** | Notification pora ar account restriction check kora. |
| F14 | **Scheduler** | Nirdishto shomoy por por kaj chalano, jemon protidin raat 12 tay offline hoya. |

### 4.3 Out of Scope

Eldorado API egulo support kore na, tai ei tool o korbe na:
- Withdrawal ar balance
- Message, dispute ar feedback
- Account settings, verification ar offer limit request
- Offer er chobi ar sales report

Ar ekta jinish scope er baire: **website er internal endpoint** (browser dev tools ba HAR file theke pawa) use kora hobe na. Shudhu official Seller API use hobe.

## 5. Requirements

### 5.1 Functional
- Protita API call er age valid token thakte hobe (F1).
- Je command offer ba order bodlay, seta chalanor age dekhabe ki bodlabe (before ar after), ar `--yes` na dile confirm chaibe.
- Bulk update er por kotogula offer success hoyeche ar kotogula fail hoyeche tar summary dekhabe.

### 5.2 Security
- Client ID ar secret shudhu `.env` file e thakbe. `.env` file `.gitignore` e thakbe.
- Access token **shudhu memory te** thakbe. Disk, database ba log e lekha hobe na.
- Log, error message ar terminal e secret ba token kokhono dekhabe na. Dekhanor dorkar hole `***REDACTED***` dekhabe.
- Ekta `.env.example` file thakbe, jekhane asol value na, shudhu field er naam thakbe.

### 5.3 Reliability (retry niyom)

| Ki hoyeche | Tool ki korbe |
|---|---|
| Authentication er karone reject | Notun token niye **1 bar** retry, abar fail hole error dekhabe |
| Too many requests (rate limit, **Assumption:** 429) | `Retry-After` thakle seta mene opekkha, shorbochcho 3 bar |
| Read request e network ba 5xx error | Exponential backoff + jitter, shorbochcho 3 bar |
| **Write** request e timeout, network ba 5xx error | **Automatic retry korbe na.** Change ta hoyeche kina jana jay na, tai user ke bolbe dashboard e check korte |

### 5.4 Safety (live environment)
Eldorado te test environment nei. Tai:
- Ekadhik offer e change hole prothome **1 ta offer** e chalabe (pilot). Pilot fail korle baki gulo te chalabe na. Pilot pass korle baki gulor jonno abar confirm chaibe. `--yes` dile confirm chaibe na, kintu pilot tokhono age chalabe.
- `--dry-run` flag shob write command e thakbe.
- Price **50% er beshi** bodlale (barle ba komle) command thamabe, jodi na `--allow-big-change` deya hoy.
- Price `Decimal` hishebe rakha hobe, float na.

### 5.5 Credential
- Credential er meyad API theke jana jay na. Tai `.env` e `ELDORADO_CREDENTIAL_EXPIRES=YYYY-MM-DD` (optional) rakha jabe. Meyad shesh hote 7 din ba tar kom baki thakle tool warning dekhabe.
- Kaj na thamiye credential bodlate: dashboard e notun credential banan, `.env` update korun, tarpor puran ta revoke korun. (Ekta account e shorbochcho 2 ta active credential thakte pare.)

## 6. Technical Decisions (final)

| Bishoy | Decision |
|---|---|
| Language | Python 3.11+ |
| CLI | `typer` (`rich` diye table ar color) |
| HTTP client | `httpx`, **shudhu sync** (`httpx.Client`) |
| Model ar validation | `pydantic` v2 |
| Config | `pydantic-settings` (`.env` file pore) |
| Audit log | `logs/audit.jsonl` (protita line e ekta JSON) |
| Database | **MVP te lagbe na.** Phase 2 e dorkar hole SQLite |
| Test | `pytest` + `respx` (shob HTTP mock, kono live call na) |

### 6.1 Folder structure (final)
```
eldorado_Seller_Api/
├── .env.example
├── .gitignore
├── pyproject.toml
├── logs/                  # audit.jsonl (gitignore e)
├── src/eldorado/
│   ├── __init__.py
│   ├── cli/               # Typer command
│   │   ├── main.py
│   │   ├── offers.py
│   │   ├── orders.py
│   │   └── account.py
│   ├── services/          # business logic: diff, pilot, safety check
│   │   ├── offers.py
│   │   ├── orders.py
│   │   └── account.py
│   ├── client/            # HTTP
│   │   ├── auth.py        # token manager (F1)
│   │   ├── base.py        # base client, retry, error mapping
│   │   ├── offers.py
│   │   ├── orders.py
│   │   └── account.py
│   ├── models/            # Pydantic model
│   │   ├── auth.py
│   │   ├── offer.py
│   │   └── order.py
│   └── core/
│       ├── config.py
│       ├── exceptions.py
│       ├── logging.py     # secret mask kora
│       └── audit.py       # audit.jsonl likha
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_offers.py
    ├── test_orders.py
    ├── test_account.py
    ├── test_cli.py
    ├── test_dry_run.py
    ├── test_audit.py
    ├── test_resilience.py
    └── test_security.py
```

### 6.2 CLI command (final)

Shob write command e `--dry-run` ar `--yes` ache. Shudhu TopUp offer.

| Command | Option | Feature | Obostha |
|---|---|---|---|
| `eldorado auth check` | | F1 (token niye credential check, kichu bodlay na) | ✅ |
| `eldorado offers list` | `--game GAMEID`, `--status active/paused/closed/offline`, `--limit N` | F2 | ✅ |
| `eldorado offers update` | `--id ID`, `--price X`, `--allow-big-change` | F3 (ekta offer er price) | ✅ |
| `eldorado offers pause/resume <offer_id>...` | | F4 (onek id hole prothom ta pilot) | ✅ |
| `eldorado status online` / `offline` | | F7 | ✅ |
| `eldorado bid run` | `--once`, `--interval SECONDS`, `--config PATH` | F16 | ✅ |
| `eldorado ui` | `--port` (default 8765), `--no-browser` | F17 (shudhu settings page) | ✅ |
| `eldorado app` | `--port`, `--no-browser` | F17 (page + bot ek window e, **PAUSED** e shuru, page theke RUN) | ✅ |
| `eldorado orders deliver <order_id>` | | F6 | dry-run ✅, live bondho |
| `eldorado offers update --game`, `--quantity`, `--delivery-time` | | F3 bulk | ❌ banano hoy ni (dorkar hoy ni) |
| `eldorado orders list` | | F5 | ❌ banano hoy ni |

Ekটা live bot (`app` ba `bid run`) ek shomoy e chalte pare. `logs/bot.lock` dwitiyo bot ke atkay.

**Example:**
```
eldorado offers list --status active --limit 10
eldorado offers update --id <offer_id> --price 4.99 --dry-run
eldorado bid run --once --dry-run
eldorado app
```

## 7. Milestones

| Phase | Kaj | Shorto |
|---|---|---|
| M0 | Official endpoint docs collect kora | Dashboard ba support theke API reference pawa |
| M1 | Project setup (`pyproject.toml`, `.env.example`, `.gitignore`) + F1 (Auth) | Client ID ar secret pawa |
| M2 | F2 - F8, F15 (MVP) | M0 shesh |
| M3 | Ekta asol offer e pilot test (same price diye no-op update) | M2 shesh |
| M4 | Phase 2 feature | M3 shesh |

## 8. Risks

| Risk | Probhab | Ki korbo |
|---|---|---|
| Test environment nei, bhul request live offer bodle dite pare | High | Dry-run, confirm, pilot, 50% price guard |
| Endpoint docs pawa jachhe na | High | M0 te dashboard dekha, na pele support ke email |
| Write request timeout hole duibar change hoye jawa | Medium | Write request automatic retry hobe na |
| Secret ba token leak | Medium | `.env` + `.gitignore`, token shudhu memory te, log e mask |
| Credential er meyad shesh hoye tool bondho hoye jawa | Medium | `ELDORADO_CREDENTIAL_EXPIRES` diye age theke warning |
| Rate limit jana nei | Medium | Retry + backoff, bulk request er majhe delay |

## 9. Open Questions

1. ~~Offer, order ar account endpoint er **base URL ar endpoint list** ki?~~ **Uttor (Swagger, 2026-11-14):** `https://www.eldorado.gg/swagger/seller/index.html`. Pura list `api-spec.md` section 4 e. Offer type onujayi alada API (Currency, Item, Account, Predefined, Boosting, Swap).
2. ~~Token request er body format ki?~~ **Uttor (dashboard):** JSON `{"clientId", "clientSecret"}`, response `{"accessToken", "expiresIn": 900, "tokenType": "Bearer"}`.
3. ~~`Authorization` header er format ki `Bearer <token>`?~~ **Uttor (dashboard):** Ha, `Authorization: Bearer <access_token>`.
3a. ~~`PUT /api/orders/me/{orderId}/delivered` er request body te ki dite hoy?~~ **Uttor (Swagger):** Swagger e ei path nei. Shothik path `PUT /api/v1/orders/me/{orderId}/deliver`, kono body nei.
4. **Rate limit** koto, ar error status code gulo ki ki?
5. ~~Bulk update er jonno alada endpoint ache?~~ **Uttor (Swagger):** Ha. Protita offer type e game diye bulk price, delivery time, pause ar resume ache.
6. Team account member ra ki API use korte pare?
7. **Kon offer type** (Currency, Item, Account, TopUp/GiftCard) ar kon game niye kaj korben? Ei uttor e thik hobe MVP te kon API lagbe. Kon feature ta shobcheye agey dorkar?
8. Tool ta ki shudhu CLI hobe, naki pore web dashboard o lagbe?
9. ~~Auto pricing lagbe ki?~~ **Uttor:** Ha, F16. Competitor price `GET /api/predefinedOffers/game` theke (Swagger e public endpoint).
10. ~~Swagger er `swagger` header pathate hoy kina?~~ **Uttor (live):** na, header chara shob call kaj kore.

### 9.1 Auto bidding er niyom (F16, final)

| Niyom | Value |
|---|---|
| Undercut | Fixed `0.01` (`bidding.toml` e bodlano jay) |
| Target price | `min(onno seller der Active price) - 0.01`, 2 decimal e round down |
| Floor | Protita offer e `min_price` lagbe. Target floor er niche gele price = floor |
| Ceiling | Optional `max_price`. Target er cheye beshi hole price = ceiling |
| Competitor nei | Price bodlabe na |
| Min e atke chilen, tarpor #1 | Kom dami seller (min er niche) chole geche. `max_price` thakle bot ek cycle er jonno `max_price` e jay. Porer cycle e market e asol porer seller dekha jay, tar cheye 0.01 kom e name (jemon 4.50 -> 4.49). `max_price` na thakle min e thake |
| Already #1 | Price bodlabe na. Market endpoint protita package er **shudhu ekta offer** (shobcheye kom ta) dey, tai apni #1 hole 2nd price jana jay na. User "price barabe" chechilen, kintu API te ta shombhob na (live, 2026-11-14) |
| Package match | `attributes[].id` + `attributes[].value.id`, jemon `call-of-duty-mobile-cp=80-cp`. Package na jana gele offer skip |
| Game | Game diye kono filter nei. Naam: `GAME_NAMES` (59 CODM, 56 Brawl Stars, 18 Clash of Clans, 52 Clash Royale, 70 Roblox, 21 PUBG Mobile, 254 TikTok, 46 Free Fire, 378 Yalla Ludo, 385 ChatGPT); ojana game hole offer er seo alias theke naam |
| Region | Package match e trade environment (jemon Free Fire er Region) o mile hobe |
| Nijer offer | Competitor hishebe dhora hobe na |
| Currency | Shudhu USD offer. Onno currency hole skip |
| 50% guard | Ek bar e 50% er beshi change hole skip, jodi na offer e `allow_big_change = true` thake |
| Pilot | Protita cycle er prothom change ta pilot. Pilot fail korle oi cycle er baki change hobe na |
| Write outcome unknown | Pura bot thame (timeout ba 5xx er por kono retry na) |
| Audit log likha jay na | Unknown outcome er moto: `eldorado app` nijei paused hoy, `bid run` thame. Audit record chara bot cholte thakbe na, tai unknown write abar pathano hoy na |
| Cycle er majhe Pause | Protita live write er age `paused` abar pora hoy. Pause hole cycle er baki write pathano hoy na (`not_sent`) |
| Confirm | Start er shomoy ekbar confirm, `--yes` dile na |
