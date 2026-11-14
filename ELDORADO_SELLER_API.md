# Eldorado Seller API - Notes

Source: https://support.eldorado.gg/en/articles/16127288-how-the-seller-api-works

Article e lekha "Updated over a week ago". Ei notes 2026-11-14 tarikhe article er sathe milano hoyeche.

## Overview

Seller API diye verified seller ra nijer software theke offer ar order manage korte pare. Eta tader jonno banano jader onek offer ache ar ek-i kaj bar bar kora automate korte chan.

- **Shudhu verified seller ra** Seller API use korte pare.
- Ekta account e shorbochcho **2 ta active credential** thakte pare.
- **Test environment nei.** Protita request live offer ar order bodle dey, tai prothome ekta offer diye try korun.

## Ki kora jay

### Offers
- Currency, top-up, item, account ar boosting offer create, update, pause, resume ar delete kora jay.
- Ekta offer ba pura ekta game er shob offer er price, quantity ar delivery time bodlano jay.
- CSV file diye onek offer ek sathe (bulk) upload kora jay.

### Orders
- Order dekha jay.
- Order delivered mark kora jay.
- Order cancel kora jay.
- Delivery details thik kora jay.
- Invoice banano jay.

### Account
- Nijeke online ba offline kora jay.
- Notification pora jay.
- Account restriction dekha jay.

## Ki kora jay na

- Withdrawal ar balance
- Message, dispute ar feedback
- Account settings, verification ar offer limit request
- Offer er chobi ar sales report

## Credential banano

1. **Dashboard > Seller API** te jan (https://www.eldorado.gg/dashboard/seller-api).
2. "Generate API client credentials" er niche credential er ekta naam din, jeta pore chinte parben.
3. Meyad bachhun: 1, 14, 30, 90 ba 365 din.
4. "Generate credentials" e click korun.
5. Je window khulbe sekhan theke **Client ID** ar **Client secret** copy korun.
6. Duto-i kothao safe kore rakhun (jemon password manager e), tarpor window ta bondho korun.

> **Sotorkota:** Client secret **shudhu ekbar dekhay**. Window bondho korar por ar ferot pawa jay na. Jar kache secret thakbe se apnar offer ar order manage korte parbe. Tai eta karo sathe share korben na, kothao post korben na, screenshot eo rakhben na.

## Authentication

1. **Access token nin:** Client ID ar Client secret `POST` kore pathan:
   ```
   POST https://eldorado.gg/api/authentication/seller/token
   ```
2. **Token use korun:** Protita API request er `Authorization` header e token ta din.
3. **Token refresh korun:** Access token **15 minute** por expire hoye jay. Tokhon upore dewa niyome notun token nin.

Article e body format nei, kintu **Seller API dashboard** e ache (2026-11-14):

- Request (JSON): `{"clientId": "<your_client_id>", "clientSecret": "<your_client_secret>"}`
- Response: `{"accessToken": "<your_access_token>", "expiresIn": 900, "tokenType": "Bearer"}`
- Header: `Authorization: Bearer <access_token>`
- Dashboard er example endpoint: `PUT https://eldorado.gg/api/orders/me/{orderId}/delivered` (request body dashboard e shudhu `{"..."}` dekhay, mane ekhono jana nei)

## Je tottho article e nei

- Offer, order ar account er **endpoint list** (deliver chara), HTTP method ar request/response format
- **Rate limit**
- Swagger/OpenAPI ba developer portal er link

Dashboard e **"View more endpoints"** link e pura endpoint list ache. Seta theke `api-spec.md` update korte hobe. Na pele support ke email korun.

## Credential manage ar revoke kora

- Seller API page e protita active credential er naam, Client ID, Client secret er shesh 4 ta character ar meyad shesh hobar tarikh dekhay.
- **Kaj na thamiye credential bodlate:** notun credential banan, app ke notun ta te switch korun, tarpor puran ta revoke korun.
- Revoke shathe shathe kaj kore ar undo kora jay na. Tokhon app ar notun token nite pare na, ar je token age dewa hoyechilo segulo 15 minute er moddhe bondho hoye jay.

## Troubleshooting

| Somossa | Ki korben |
|---|---|
| Client secret hariye geche | Eta ferot pawa jay na. Credential ta revoke kore notun ekta banan, tarpor app e update korun. |
| Credential er meyad shesh | Notun credential banan ar app e update korun. Meyad kobe shesh hobe ta age thekei dekhe rakhun. |
| Generate button kaj korche na | Apnar already 2 ta active credential ache. Je ta use koren na seta revoke korun. |
| API request reject hochhe | Token ta shomvoboto expire hoye geche, notun token nin. Token request-o fail korle dekhun credential revoke hoyeche naki meyad shesh hoyeche. |
| Secret leak hoye gele | Shathe shathe credential revoke korun ar notun ekta banan. |

## Support

Notun credential banano-r porou request fail korle, ba docs e uttor na pele, email e support er sathe jogajog korun. Email e egulo din:
- Apnar Client ID (Client secret **kokhono-i** deben na)
- Kon endpoint call korechilen ar kon shomoy
- Pura error message

Support email: **api@eldorado.gg** (article ar dashboard e deya). Chat ba contact form er kotha bola nei.

## Related links

- Seller API dashboard: https://www.eldorado.gg/dashboard/seller-api
- Currency seller guidelines: https://support.eldorado.gg/en/articles/13917846-currency-seller-guidelines
- Set up team accounts: https://support.eldorado.gg/en/articles/17021935-set-up-team-accounts
- Selling and managing offers: https://support.eldorado.gg/en/collections/19784315-selling-and-managing-offers
