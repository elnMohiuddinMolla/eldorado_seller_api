# Eldorado Seller API Specification

> **Specification Version:** 0.4 (Draft)
> **Sources:**
> 1. [How the Seller API works](https://support.eldorado.gg/en/articles/16127288-how-the-seller-api-works) (Eldorado help center, checked 2026-11-14).
> 2. The **Seller API dashboard** (`https://www.eldorado.gg/dashboard/seller-api`), sections "2. Get an access token" and "3. Call the seller API" (screenshots, 2026-11-14).
> 3. The official **Swagger spec** `https://www.eldorado.gg/swagger/seller/swagger.json` ("Eldorado Seller API", OAS 3.0), read in a logged-in browser on 2026-11-14. Only the spec document was read; no endpoint was executed.
>
> **Status:** Endpoint paths, parameters and body schemas below come from the Swagger spec and are `[Confirmed] (swagger)`. Response *behavior* (real status codes, error bodies, rate limits) is still unknown until a read-only live call is made. Do not write client code against any path that is not marked `[Confirmed]`.

## 0. Tag Legend

| Tag | Meaning |
|---|---|
| `[Confirmed]` | Stated in an official Eldorado source: the help center article or the Seller API dashboard (source noted when it is the dashboard) |
| `[Assumed]` | A guess based on common API practice. Must be verified before use |
| `[Unknown]` | Not documented anywhere we have access to |
| `[Tool Design]` | Behavior of *our* tool, not of Eldorado's API |

---

## 1. Global Facts

| Item | Value | Tag |
|---|---|---|
| Who can use the API | Verified sellers only | `[Confirmed]` |
| Sandbox / test environment | **None.** Every request changes live offers and orders | `[Confirmed]` |
| Token endpoint host | `https://www.eldorado.gg`. `https://eldorado.gg` answers **301** to the `www` host (seen on the first live token request, 2026-11-14) | `[Confirmed]` |
| Base URL for seller endpoints | `https://eldorado.gg` (dashboard curl example). The Swagger `servers` entry is `https://www.eldorado.gg/`. **Use `https://www.eldorado.gg`** (the bare host redirects with 301). The tool never follows redirects | `[Confirmed]` |
| Media type | JSON (`Content-Type: application/json` in the dashboard example) | `[Confirmed]` |
| Paging | `pageIndex` is **1-based**. `pageIndex=0` returns `400 {"code":400,"messages":["The following properties have invalid values: PageIndex."],"correlationId":null}` (live, 2026-11-14) | `[Confirmed]` (live) |
| Error body | `{"code": int, "messages": [str], "correlationId": str?}` (seen on a live 400; Swagger says `ProblemDetails`) | `[Confirmed]` (live) |
| Money in JSON | `MoneyBaseDTO = {"amount": number, "currency": Currency}`, e.g. `{"amount": 4.99, "currency": "USD"}`. The tool keeps `Decimal` internally and serializes to a JSON number | `[Confirmed] (swagger)` |
| `swagger` header | Swagger marks a header `swagger` as required, but every live call works without it (2026-11-14). The tool does not send it | `[Confirmed]` (live) |
| Security scheme in spec | None declared. Protected operations are labelled `(Auth)` in their summary. Auth is the bearer token (section 3) | `[Confirmed] (swagger)` |
| Rate limits | Not documented and no rate-limit headers. Live (2026-11-14): 3 bursts of ~20 market reads within ~10 s, 4 in parallel, got **HTTP 429**. The tool now reads at most 2 in parallel and the page caches Eldorado data for 60 s | `[Confirmed]` exists, size `[Unknown]` |
| Official API reference location | Swagger UI: `https://www.eldorado.gg/swagger/seller/index.html` (linked as "View more endpoints" on the dashboard). Needs a logged-in browser session; without it the server returns `403 "User is unauthorized to access Swagger."` | `[Confirmed]` exists |

---

## 2. Credentials `[Confirmed]`

- Generated at **Dashboard > Seller API** (`https://www.eldorado.gg/dashboard/seller-api`).
- Each credential has a **Client ID** and a **Client secret**.
- The Client secret is **shown only once** and cannot be recovered.
- Maximum **2 active credentials** per account.
- Expiration options: **1, 14, 30, 90 or 365 days**.
- The dashboard lists each credential's name, Client ID, last 4 characters of the secret, and expiration date.
- **Revoking** is immediate and cannot be undone. The credential can no longer request tokens, and tokens already issued stop working **within 15 minutes**.
- **Rotation without downtime:** generate a new credential, switch the app to it, then revoke the old one.

---

## 3. Authentication

### 3.1 Token Request

| Item | Value | Tag |
|---|---|---|
| Method | `POST` | `[Confirmed]` |
| URL | `https://www.eldorado.gg/api/authentication/seller/token` (the dashboard shows the bare host, which 301-redirects) | `[Confirmed]` |
| Inputs | Client ID and Client secret | `[Confirmed]` |
| Body encoding | JSON | `[Confirmed]` (dashboard) |
| Field names | `clientId`, `clientSecret` | `[Confirmed]` (dashboard) |

Request body (from the dashboard):

```json
{ "clientId": "<your_client_id>", "clientSecret": "<your_client_secret>" }
```

### 3.2 Token Response

| Item | Value | Tag |
|---|---|---|
| Token lifetime | **15 minutes** (`expiresIn: 900`) | `[Confirmed]` |
| Fields | `accessToken`, `expiresIn` (seconds), `tokenType` | `[Confirmed]` (dashboard) |

```json
{ "accessToken": "<your_access_token>", "expiresIn": 900, "tokenType": "Bearer" }
```

### 3.3 Using the Token

| Item | Value | Tag |
|---|---|---|
| Header name | `Authorization` | `[Confirmed]` |
| Header value format | `Bearer <access_token>` | `[Confirmed]` (dashboard) |
| Required on | Every API call | `[Confirmed]` |

### 3.4 Token Handling `[Tool Design]`

- Keep the token **in memory** and request a new one when less than 60 seconds remain.
- If a request is rejected because of authentication, request a new token and **retry once**. If it fails again, stop with an error.
- Never log the token or the Client secret.

---

## 4. Capabilities and Endpoints

All paths below are `[Confirmed] (swagger)` unless noted. `*` = required. `Auth` = needs the bearer token. Bodies marked "none" have no `requestBody` in the spec.

### 4.0 Offer Types (important)

Eldorado has **separate offer APIs per offer type**. There is no single "offers" endpoint. The tool must know which type an offer is before it can list or change it.

| Swagger group | Offer type (`Category`) | Base path |
|---|---|---|
| `CurrencyOfferPrivate` | Currency | `/api/v1/currency-management/me/offers` |
| `ItemOfferPrivate` | CustomItem (items) | `/api/v1/item-management/me/offers` |
| `FlexibleOfferPrivate` / `FlexibleOfferUserPrivate` | Account | `/api/flexibleOffers/...`, `/api/flexibleOffersUser/me/...` |
| `PredefinedOfferPrivate` / `PredefinedOfferUserPrivate` | Predefined offers (likely TopUp / GiftCard, `[Assumed]`) | `/api/predefinedOffers/...`, `/api/predefinedOffersUser/me/...` |
| `BoostingOfferSellerPrivate` | Boosting | `/api/boostingOffers/...` |
| `SwapBuyOfferPrivate` | Swap buy offers | `/api/v1/swap-management/me/buy-offers` |

The user sells **TopUp only** (prd.md 4.0). The tool implements the Predefined API with `category=TopUp`. That TopUp offers live in the Predefined API is `[Assumed]` until `eldorado offers list` returns them.

### 4.1 Offers: Currency (`/api/v1/currency-management/me/offers`)

| Capability | PRD | Method & Path | Params / Body | Response |
|---|---|---|---|---|
| List | F2 | `GET /api/v1/currency-management/me/offers` | query `pageIndex`, `pageSize`. Spec also lists a body `CurrencyOfferFilteredWithStateRequest` on this GET (`[Unknown]` how it is sent) | `IndexBasedPagedResult<object>` |
| Get one | F2 | `GET .../offers/{id}` | | 200, 404 `ProblemDetails` |
| Change price | F3 | `PUT .../offers/{id}/change-price` | body `MoneyBaseDTO` | `MoneyBaseDTO` |
| Change quantity | F3 | `PUT .../offers/{id}/change-quantity` | body: bare JSON integer | integer |
| Pause / resume | F4 | `PUT .../offers/{id}/pause`, `PUT .../offers/{id}/resume` | none | 200 |
| Full update | F3 | `PUT .../offers/{id}` | body `CurrencyOfferPrivateDTO` | 200 |
| Bulk change price (game) | F3 | `POST .../offers/bulk/{gameId}/change-price` | body `CurrencyOfferPriceWithinLimitRequest` | `OfferBulkActionOffersCountPrivateDTO` |
| Bulk change delivery time | F3 | `POST .../offers/bulk/change-delivery-time` | body `CurrencyOfferDeliveryTimeWithinLimitRequest` | same |
| Bulk pause all active | F4 | `POST .../offers/bulk/pause-all-active` | body `CurrencyOfferFilteredRequest` | same |
| Bulk resume latest paused | F4 | `POST .../offers/bulk/{gameId}/resume-latest-paused` | body `CurrencyOfferFilteredRequest` | same |
| Create | F9 | `POST .../offers` | body `CurrencyOfferPrivateDTO` | 201 |
| Delete one / all | F9 | `DELETE .../offers/{id}`, `DELETE .../offers/delete-all` | delete-all body `CurrencyOfferFilteredWithStateRequest` | 204 |
| Import | F10 | `POST .../offers/import/web` (array of `CurrencyOfferPrivateDTO`), `POST .../offers/import/csv` | | 201 |

### 4.2 Offers: Items (`/api/v1/item-management/me/offers`)

| Capability | PRD | Method & Path | Params / Body | Response |
|---|---|---|---|---|
| List | F2 | `GET /api/v1/item-management/me/offers` (also `GET .../offers/me/search`, same params) | query `offerState`, `gameId`, `category`, `searchQuery`, `deliveryTime`, `lowestPrice`, `highestPrice`, `pageIndex`, `pageSize`, `offerSortingCriterion`, `isAscending`, trade environment filters | `IndexBasedPagedResult<ItemOfferPublicDTO>` |
| Change price | F3 | `PUT .../offers/{offerId}/price` | body `MoneyBaseDTO` | `MoneyBaseDTO` |
| Change quantity | F3 | `PUT .../offers/{offerId}/quantity` | body: bare JSON integer | integer |
| Pause / resume | F4 | `POST .../offers/{offerId}/pause`, `POST .../offers/{offerId}/resume` (**POST**, not PUT) | none | 200 |
| Full update | F3 | `PUT .../offers/{offerId}` | body `ItemOfferPutPrivateDTO` | `ItemOfferPublicDTO` |
| Bulk price (game) | F3 | `POST .../offers/game/{gameId}/price` | body `ItemOfferPriceWithinLimitRequestDTOV2` | `OfferBulkActionOffersCountPrivateDTO` |
| Bulk delivery time | F3 | `POST .../offers/delivery-time` | body `ItemOfferDeliveryTimeRequestDTOV2` | same |
| Bulk pause / resume | F4 | `POST .../offers/pause`, `POST .../offers/game/{gameId}/resume` | body `ItemOfferBulkActionRequestDTOV2` | same |
| Create / delete | F9 | `POST .../offers`, `POST .../offers/item`, `DELETE .../offers/{offerId}`, `DELETE .../offers`, `DELETE .../offers/delete` | | |

### 4.3 Offers: Account (flexible) and Predefined

Both use the same shape. Replace `X` with `flexibleOffersUser` (account) or `predefinedOffersUser` (predefined). All take optional query `api-version`.

| Capability | PRD | Method & Path | Params / Body |
|---|---|---|---|
| List (account) | F2 | `GET /api/flexibleOffers/me/search` | query `offerState`, `gameId`, `category`, `searchQuery`, `pageIndex`, `pageSize`, ... Response `IndexBasedPagedResult<FlexibleOfferPrivateDTO>` |
| **Market (all sellers)** | F16 | `GET /api/predefinedOffers/game` (public, group `PredefinedOfferPublic`) | query `gameId`, `category`, `tradeEnvironmentId`, trade env values, `queryAttributes`, `pageIndex`, `pageSize`. Response `IndexBasedPagedResult<PredefinedOfferGroupPublicViewModel>` = `{offer, user: {id, username, isVerifiedSeller}, userOrderInfo, deliveryTime}`. **Live (2026-11-14): returns ONE offer per package** (looks like the cheapest; my offers were always above it). Package filters (`queryAttributes` in any encoding) do not reveal more sellers. The package is in `offer.attributes[].value` (`{"id": "80-cp", "name": "80 CP"}`), a field the Swagger `IOfferAttributeDTO` schema leaves out. `offerAttributeIdValues` and `tradeEnvironmentValues` are usually empty |
| List (predefined) | F2 | `GET /api/predefinedOffers/me` | query `offerState`, `gameId`, `category`, `pageIndex`, `pageSize`, ... Response `IndexBasedPagedResult<PredefinedOfferPrivateViewDTO>` |
| Change price | F3 | `PUT /api/X/me/{id}/changePrice` | body `MoneyBaseDTO` |
| Change quantity (predefined only) | F3 | `PUT /api/predefinedOffersUser/me/{id}/changeQuantity` | body: bare JSON integer |
| Pause / resume | F4 | `PUT /api/X/me/{id}/pause`, `PUT /api/X/me/{id}/resume` | none |
| Bulk price (game) | F3 | `PUT /api/X/me/changePriceForAll/{gameId}` | query `amount*`, `currency*`, `offerState`, filters. No body |
| Bulk delivery time | F3 | `PUT /api/X/me/changeDeliveryTimeForAll` | query `deliveryTime*`, filters |
| Bulk pause / resume | F4 | `PUT /api/X/me/pauseAllActive`, `PUT /api/X/me/resumeLatestPaused/{gameId}` | query filters |
| Delete | F9 | `DELETE /api/X/me/{id}`, `DELETE /api/X/me/deleteAll` | |

Account offers also have secret-detail endpoints (`/api/flexibleOffersUser/me/offers/{offerId}/secretDetails`, policy `SecretDetails`). The tool must **never** read, log or store these.

### 4.4 Orders (`UserOrderSellerPrivate`, v1)

| Capability | PRD | Method & Path | Params / Body | Response |
|---|---|---|---|---|
| List seller orders | F5, F18 | `GET /api/v1/orders/me/seller/orders` | query `displayFilter*` (`DisplaySellingOrders` for sold orders), `orderState` (`OrderStateViewModel`), `gameId`, `category`, `query`, `isAscendingDateOrder`, `ignorePendingReviewOrders`, `filterByActiveWarranty`, `orderGroup`, `pageSize`, `cursorValue`, `cursorColumn`, `pageDirection` | `CursorBasedPagedResult<OrderPrivateViewModel>` |
| Mark delivered | F6 | `PUT /api/v1/orders/me/{orderId}/deliver` | **no body** | `OrderGetSellerPrivateDTO` |
| Cancel | F11 | `POST /api/v1/orders/me/{orderId}/cancel` | body `CancelationPostSellerDTO` | `OrderGetSellerPrivateDTO` |
| Extend delivery time | F11 | `POST /api/v1/orders/me/{orderId}/extend-delivery-time` | body `ExtendDeliveryTimeRequestDTO` | 204 |
| Correct delivery details | F11 | `POST /api/v1/orders/me/{orderId}/delivery-details/correction` | body `DeliveryDetailsCorrectionPostSellerDTO` | `OrderGetSellerPrivateDTO` |
| Invoice | F12 | `GET /api/v1/orders/me/invoice/generate` | query `fromDate`, `untilDate` | |
| Sold order data / order data | | `GET /api/v1/orders/me/sold-order-data`, `GET /api/v1/orders/me/order-data` | query `fromDate`, `untilDate` | |
| Seller API eligibility | F1 | `GET /api/v1/orders/me/seller-api-eligibility` | | `{"isEligible": bool}` |
| Pending review count | | `GET /api/v1/orders/me/pending-review-order-count` | | |

> **Deliver path conflict.** The dashboard example shows `PUT /api/orders/me/{orderId}/delivered` with a `{"..."}` body. That path does **not exist** in the Swagger spec. Swagger has `PUT /api/v1/orders/me/{orderId}/deliver` with no body, and the old `PUT /api/orders/me/{orderId}/deliver` marked *"deprecated. Use PUT /api/v1/orders/me/{orderId}/deliver instead."* The tool uses the **v1 Swagger path with no body**.

The group `UserOrderSellerPrivateObsolete` (`/api/orders/me/...`, camelCase paths) is deprecated. Do not use it.

### 4.5 Account (`OfferUserPrivate`, notifications)

| Capability | PRD | Method & Path | Params / Body |
|---|---|---|---|
| Go online | F7 | `PUT /api/offerUser/me/switchOnline` | none |
| Go offline | F7 | `PUT /api/offerUser/me/switchOffline` | none |
| Restrictions | F13 | `GET /api/offerUser/me/restrictions` | Response `GameCategoryApprovalBaseDTO` |
| Bulk CSV upload | F10 | `POST /api/offerUser/me/bulkUploadCsv` | query `category`; `GET /api/offerUser/me/csvUploadExample` gives a template |
| Notifications | F13 | `GET /api/notifications/me`, `GET /api/notifications/me/unread-count`, `PUT /api/notifications/me/{notificationId}/markAsRead`, `PUT /api/notifications/me/markAllAsRead` | |

### 4.6 Key Schemas `[Confirmed] (swagger)`

```
MoneyBaseDTO            { amount*: number, currency*: Currency }
OfferBulkActionOffersCountPrivateDTO
                        { offersInGivenFilterCount*: int, bulkActionOffersCount*: int,
                          isTotalOffersForBulkActionLimitReached*: bool }
IndexBasedPagedResult<T>  { pageSize, pageIndex, totalPages, recordCount, results: [T] }
CursorBasedPagedResult<T> { pageSize, results: [T], cursor, pageDirection,
                            previousPageCursor, nextPageCursor }
AugmentedGameFilterDTO  { gameId, category, tradeEnvironmentId,
                          tradeEnvironmentValue0..2 }
CurrencyOfferPriceWithinLimitRequest
                        { augmentedGameFilter*, attributes?, offerState*, pricePerUnit*: MoneyBaseDTO }
ItemOfferPriceWithinLimitRequestDTOV2
                        { pricePerUnit*: MoneyBaseDTO, offerState, augmentedGameFilter*,
                          attributes?, deliveryTime }
Offer (item / account / predefined list items, shared fields)
                        { id (uuid), gameId, category, gameCategoryTitle, offerTitle, quantity,
                          minQuantity, pricePerUnit: MoneyBaseDTO, pricePerUnitInUSD,
                          guaranteedDeliveryTime, offerState, offerVersion, expireDate, ... }
Order (OrderPrivateViewModel)
                        { id (uuid), offerId, purchaseQuantity, totalPrice: MoneyBaseDTO,
                          state: { state: OrderState, createdDate }, createdDate,
                          deliveryTime, buyerUsername, sellerUsername, orderOfferDetails, ... }
ProblemDetails          { type, title, status, detail, instance }   (RFC 7807 error body)
```

Enums:

| Enum | Values |
|---|---|
| `OfferState` | `Active`, `Paused`, `Closed`, `Offline` |
| `Category` | `Account`, `CustomItem`, `Currency`, `Boosting`, `RequestedBoosting`, `ManagedBoosting`, `TopUp`, `GiftCard` |
| `OrderStateViewModel` (list filter) | `Paid`, `Disputed`, `Delivered`, `Received`, `Completed`, `Canceled`, `PendingReview` |
| `OrderState` | `Paid`, `Delivered`, `Disputed`, `DeliveredDisputed`, `Completed`, `Canceled`, `Received`, `PendingReview`, `Initialized` |
| `DisplayFilter` | `DisplayBuyingOrders`, `DisplaySellingOrders` |
| `GuaranteedDeliveryTime` | `Instant`, `Automated`, `Minute5`, `Minute20`, `Hour1`, `Hour2`, `Hour3`, `Hour5`, `Hour8`, `Hour12`, `Day1`, `Day2`, `Day3`, `Day5`, `Day7`, `Day10`, `Day14`, `Day28`, `Day45`, `Day60`, `Day80`, `Day100`, `NotApplicable` |
| `PageDirection` | `Next`, `Previous` |
| `Currency` | `USD`, `EUR`, `GBP`, ... (33 ISO codes) |
| `SellerCancelationReason` | `Mutual_Agreement`, `Out_Of_Stock`, `Buyer_Did_Not_Respond`, `Seller_Going_Offline`, `Other`, ... (16 values) |

### 4.7 Not Available in the API `[Confirmed]`

- Withdrawals and balance
- Messages, disputes and feedback
- Account settings, verification and offer limit requests
- Offer images and sales reports

---

## 5. Errors

### 5.1 What the Article Says `[Confirmed]`

| Situation | Likely cause |
|---|---|
| API requests are rejected | The access token has probably expired. Request a new one |
| The token request itself fails | The credential was revoked or has expired |
| Generate button is unavailable (dashboard) | 2 active credentials already exist. Revoke one you no longer use |
| Client secret lost | Cannot be recovered. Revoke the credential and generate a new one |
| Credential expired | It can no longer request tokens. Generate a new credential and update the app |
| Client secret may have been exposed | Revoke that credential right away, then generate a new one |

HTTP status codes and the error body format are `[Unknown]`.

### 5.2 Planned Handling `[Tool Design]`

These rules are our own safe defaults and must be adjusted once the real status codes are known.

| Situation | Tool action |
|---|---|
| Authentication rejected (probably 401) | Get a new token, retry once, then stop |
| Too many requests (if the API sends 429) | Wait (use `Retry-After` if present), maximum 3 tries |
| Server error (5xx) or network error on a read | Exponential backoff with jitter, maximum 3 tries |
| Timeout, network error or 5xx on a write | **No retry.** Raise `WriteOutcomeUnknownError` |
| Any other error | Stop and show the full error message, with secrets masked |

> **Do not automatically retry write requests** (price update, deliver, cancel) after a timeout. The change may already have been applied on the live account.

---

## 6. Support `[Confirmed]`

If requests keep failing after generating new credentials, or the API documentation doesn't answer a question, **email** Eldorado at **api@eldorado.gg** (given in the article and on the Seller API dashboard). Include:
- Your Client ID (**never** the Client secret)
- The endpoint you called and the request time
- The full error message

---

## 7. How to Fill the Unknowns

1. The endpoint list is in the Swagger spec (section 1, "Official API reference location"). Open it in a logged-in browser and read `swagger.json`. Never press "Try it out" / "Execute": it sends a live request.
2. Still `[Unknown]`: rate limits and most error status codes. (Answered live: host is `www.eldorado.gg`, paging is 1-based, the `swagger` header is not needed, the error body is `{code, messages, correlationId}`.) Learn these from the first **read-only** live call (`eldorado offers list --limit 1`), then record them here.
3. If something is unclear, email api@eldorado.gg.
4. Do **not** take endpoints from the website's own network traffic (browser dev tools / HAR files). Those are internal endpoints, not the Seller API, and HAR files contain your login session.
