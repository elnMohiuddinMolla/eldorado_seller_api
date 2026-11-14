# Eldorado Seller API - Notes

Source: https://support.eldorado.gg/en/articles/16127288-how-the-seller-api-works

The article says "Updated over a week ago". These notes were checked against the article on 2026-11-14.

## Overview

With the Seller API, verified sellers can manage their offers and orders from their own software. It is made for sellers with many offers who want to automate repetitive work.

- **Only verified sellers** can use the Seller API.
- An account can have at most **2 active credentials**.
- **There is no test environment.** Every request changes live offers and orders, so try with one offer first.

## What You Can Do

### Offers
- Create, update, pause, resume and delete currency, top-up, item, account and boosting offers.
- Change the price, quantity and delivery time of one offer or of every offer of a game.
- Upload many offers at once (bulk) with a CSV file.

### Orders
- View orders.
- Mark orders as delivered.
- Cancel orders.
- Correct delivery details.
- Generate invoices.

### Account
- Set yourself online or offline.
- Read notifications.
- View account restrictions.

## What You Cannot Do

- Withdrawals and balance
- Messages, disputes and feedback
- Account settings, verification and offer limit requests
- Offer images and sales reports

## Creating Credentials

1. Go to **Dashboard > Seller API** (https://www.eldorado.gg/dashboard/seller-api).
2. Under "Generate API client credentials", give the credential a name you will recognize later.
3. Choose an expiry: 1, 14, 30, 90 or 365 days.
4. Click "Generate credentials".
5. Copy the **Client ID** and **Client secret** from the window that opens.
6. Store both somewhere safe (e.g. a password manager), then close the window.

> **Warning:** The Client secret is **shown only once**. It cannot be retrieved after the window is closed. Anyone who has the secret can manage your offers and orders. So never share it, never post it anywhere, and never keep a screenshot of it.

## Authentication

1. **Get an access token:** send the Client ID and Client secret with `POST`:
   ```
   POST https://eldorado.gg/api/authentication/seller/token
   ```
2. **Use the token:** put it in the `Authorization` header of every API request.
3. **Refresh the token:** the access token expires after **15 minutes**. Then get a new one the same way.

The article has no body format, but the **Seller API dashboard** does (2026-11-14):

- Request (JSON): `{"clientId": "<your_client_id>", "clientSecret": "<your_client_secret>"}`
- Response: `{"accessToken": "<your_access_token>", "expiresIn": 900, "tokenType": "Bearer"}`
- Header: `Authorization: Bearer <access_token>`
- The dashboard's example endpoint: `PUT https://eldorado.gg/api/orders/me/{orderId}/delivered` (the dashboard shows the request body only as `{"..."}`, so it is still unknown)

## What the Article Does Not Cover

- The **endpoint list** for offers, orders and account (except deliver), HTTP methods and request/response formats
- **Rate limits**
- A link to Swagger/OpenAPI or a developer portal

The **"View more endpoints"** link on the dashboard has the full endpoint list. Update `api-spec.md` from it. If it is not available, email support.

## Managing and Revoking Credentials

- The Seller API page shows each active credential's name, Client ID, the last 4 characters of the Client secret and the expiry date.
- **To rotate a credential without stopping work:** create a new credential, switch the app to the new one, then revoke the old one.
- Revoking takes effect immediately and cannot be undone. The app can no longer get new tokens, and tokens issued earlier stop working within 15 minutes.

## Troubleshooting

| Problem | What to do |
|---|---|
| Lost the Client secret | It cannot be recovered. Revoke the credential, create a new one, then update the app. |
| The credential expired | Create a new credential and update the app. Keep track of the expiry date in advance. |
| The Generate button does nothing | You already have 2 active credentials. Revoke the one you do not use. |
| API requests are rejected | The token has probably expired; get a new one. If the token request also fails, check whether the credential was revoked or has expired. |
| The secret leaked | Revoke the credential right away and create a new one. |

## Support

If requests still fail after creating a new credential, or the docs do not answer your question, contact support by email. Include:
- Your Client ID (**never** send the Client secret)
- Which endpoint you called and when
- The full error message

Support email: **api@eldorado.gg** (given in the article and on the dashboard). Chat or a contact form is not mentioned.

## Related Links

- Seller API dashboard: https://www.eldorado.gg/dashboard/seller-api
- Currency seller guidelines: https://support.eldorado.gg/en/articles/13917846-currency-seller-guidelines
- Set up team accounts: https://support.eldorado.gg/en/articles/17021935-set-up-team-accounts
- Selling and managing offers: https://support.eldorado.gg/en/collections/19784315-selling-and-managing-offers
