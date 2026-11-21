# Shopify track: what exists and what they want (researched 2026-11-21)

## What Shopify wants built
Shopping that happens inside any agent or app: discovery, cart, checkout and order tracking, all through Shop MCP. The bonus track names "product discovery to a shopping agent".

## Tools you can call today
- **Shop MCP**, remote server at `https://mcp.shop.com/`. Tools: `search_catalog`, `lookup_catalog`, `get_product`, `search_locations`, `lookup_locations`, `ask_business`, `create_cart`, `get_cart`, `update_cart`, `create_checkout`, `get_checkout`, `update_checkout`, `complete_checkout`, `get_account`, `search_orders`, `get_order`, plus spend-request tools.
- **Catalog MCP:** Global at `https://catalog.shopify.com/api/ucp/mcp` (every merchant), Storefront at `https://{storeDomain}/api/ucp/mcp` (one store).
- **Shop CLI:** `npm i -g @shopify/shop`, then `shop search 'ceramic coffee dripper'`. Repo: https://github.com/Shopify/shop (MIT).
- **Search by photo:** pass `like: {image: {content_type, data}}` with base64 bytes (CLI flag `--like-image`). You can also search "like" a product or variant ID.
- **Media:** `get_product` returns every image. Catalog filters can select products with 3D models or video (per the Fall '26 post).

## Auth and speed to start
- Search, product lookup, carts and checkout creation work anonymously, with no key, account or dev store.
- Sign in with Shop (OAuth at `accounts.shop.app`, scope `personal_agent`) is optional. You need it for Shop Pay, saved addresses and orders.
- Keyless access cannot get rate-limit increases. Cache results during the live demo.

## Checkout rules for agents
- Signed out: the agent returns `continue_url` and the buyer pays on the merchant's page.
- Signed in: `complete_checkout` runs only after the buyer confirms the total and picks the payment method. The agent never picks it.
- No test-mode checkout is documented. Stop the demo at `continue_url` so nothing is actually bought.
- No webhooks. Poll `get_checkout` for status `completed`.

## Shopify people at the event
No names are public. The event page lists Shopify among the judges, and Shopify Solutions Engineers are on site and in Discord. Get a name from Discord `#announcements` or their badge, then look up their public talks and posts.

## Questions to ask the Shopify engineer
1. Is there a test-mode checkout for Shop MCP, or should demos stop at `continue_url`?
2. What rate limits apply to keyless `search_catalog` with image input during a live demo?
3. Does photo search work better on a tight crop plus a text query, or on the image alone?
4. Can Universal Checkout combine several merchants into one cart today?
5. For the Shopify prize, do judges prefer a shopper-facing agent or a merchant tool?

## Sources
- https://shop.dev/docs , https://shop.dev/docs/quickstart , https://shop.dev/docs/authentication , https://shop.dev/docs/checkout
- https://mcp.shop.com/skill.md
- https://shopify.dev/docs/agents , https://shopify.dev/docs/agents/catalog
- https://shopify.dev/changelog/add-shopping-and-shop-pay-checkout-to-any-agent-with-shop-mcp
- https://www.shopify.com/news/fall-26-edition-developer
- https://github.com/Shopify/shop
- Event judges: https://cerebralvalley.ai/events

## Update (12:40 PM): deeper findings
- Judges from Shopify: Natalie Jordan (Core App and Tech Partnerships Manager) and Angel Guerrero (Senior Solutions Engineer). Source: https://cerebralvalley.ai/e/gemini-4-nyc.md
- Photo search: `search_catalog` with `like: [{image: {content_type, data}}]`, base64 bytes only (JPEG, PNG, WebP, AVIF, HEIC), request cap 4 MiB, up to two `like` entries. Filters: price, rating, ships_to, condition. 1 to 50 results per page. https://shop.dev/docs/search
- Media filter: `image`, `video`, `external_video`, `model_3d`. Video and 3D need the draft `dev.shopify.catalog.global` extension in your agent profile.
- `search_locations` (Oct 22): one merchant's stores within a radius, filtered by up to 10 variant IDs in stock. It does not reserve items. https://shop.dev/docs/locations
- `ask_business`: the merchant's own answer about policy, warranty or materials. Not for price or stock.
- Carts are one merchant each, so each store has its own `continue_url`. Universal Checkout (early access, Nov 20) joins up to 15 merchants through Shop Pay, but needs an allowlisted client ID.
- Rate limit: Global Catalog allows 5 requests per second per client. Catalog API calls need a public `meta.ucp-agent.profile` URL or return 422. Token-tier calls need a `Shopify-Buyer-IP` header.
- Merchant side: `shopify store create dev --demo-data` (CLI 4.8), then `shopify store auth` and `shopify store execute --allow-mutations` for Admin GraphQL writes (products, media, inventory, discounts). Dev MCP only reads docs. No official Admin MCP found.
- WebMCP on every Liquid and Hydrogen storefront: `search_catalog`, `browse_store`, `get_product`, cart tools, `proceed_to_checkout`, `ask_business`. Chromium origin trial only. https://shopify.dev/docs/api/web-mcp
- Catalog beta (Oct 27): `sources: ["external"]` returns brands that don't sell on Shopify (US only, no Shopify checkout).
