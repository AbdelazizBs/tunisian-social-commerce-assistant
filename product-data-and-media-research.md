# Product data and customer media research

**Question:** How should a Tunisia-first assistant learn new products and answer when buyers send voice notes, screenshots, product photos, or text descriptions?
**Checked:** 2026-10-17
**Scope:** Official Meta and OpenAI documentation, plus product-design recommendations grounded in those API contracts.

## Findings from official sources

### Seller Page posts can trigger product-import work

Meta Page webhooks support a `feed` field that sends notifications when a Page feed changes. A feed event can include the post ID, message text, and whether a post was added. The app must be installed on the Page. Meta lists `pages_manage_metadata` and `pages_show_list` for feed webhooks. The Page feed API can read Page posts, but needs the Page access and read permissions described in its reference. Apps need Advanced Access to receive Messenger webhooks from customers who are not app roles, so onboarding and App Review are launch dependencies, not details to postpone indefinitely.

Sources:

- [Meta Webhooks for Pages](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages)
- [Meta Page Feed API](https://developers.facebook.com/docs/graph-api/reference/page/feed/)
- [Meta Messenger webhooks](https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks)

A Page feed webhook is a change notification, not a normalized product feed. The event gives a post ID and text; the app then retrieves the Page post and its attachments. A post may have multiple attachments. The API does not supply reliable product SKU, variant, price, or current-stock facts merely because the post exists.

### Meta catalogs already represent product and variant data

Meta catalog fields include product ID, title, description, image, price, availability, size, color, and `item_group_id` for grouping variants. Meta's WhatsApp catalog documentation says a catalog must be uploaded and connected to a WhatsApp Business Account before catalog messages can be used. A business with an existing catalog can connect it; otherwise, a catalog can be created with Commerce API or Commerce Manager. Meta documents one catalog per WABA.

WhatsApp multi-product messages can display up to 30 catalog items. Customers can add items to a cart and submit it. An order webhook contains product retailer IDs, quantities, item prices, and currency. If each size/color variant has its own retailer ID, the application can map the returned ID to the exact variant. This is more reliable than trying to recover a variant from free-text after the customer has selected a catalog item.

Sources:

- [Meta catalog fields](https://developers.facebook.com/documentation/ads-commerce/commerce-platform/catalog/fields)
- [Upload inventory to Meta](https://developers.facebook.com/documentation/business-messaging/whatsapp/catalogs/upload-inventory)
- [WhatsApp multi-product messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/catalogs/multi-product-messages)
- [WhatsApp order webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/order)

### Buyer images and voice notes arrive as media events

WhatsApp image and audio messages have distinct webhook types and media IDs. The Media API can return a temporary media URL for downloading the original file. The URL expires after five minutes; a media ID from a webhook is downloadable for seven days. WhatsApp supports image files and audio formats including OGG/Opus. Messenger message webhooks can carry image, audio, video, or file attachments.

OpenAI's current speech-to-text guide describes the `gpt-transcribe` model and lists supported audio formats and a 25 MB upload limit. WhatsApp voice recordings commonly arrive as OGG/Opus, which is not among the formats listed in that guide, so an implementation using that endpoint must transcode and test the audio. The docs do not promise Tunisian dialect or Arabizi accuracy. Test real Tunisian voice notes before enabling automatic replies from transcripts.

Sources:

- [WhatsApp image webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/image)
- [WhatsApp audio webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/audio)
- [WhatsApp media API](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)
- [Messenger webhooks and attachment events](https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks)
- [OpenAI speech-to-text](https://developers.openai.com/api/docs/guides/speech-to-text)

## Recommendation

### Make the seller-approved catalog the fact source

Use one product record per sellable variant or a parent product with explicit child variants. Store stable product/variant IDs, seller-approved photos, title, local-language descriptions, price, size, color, availability, and stock-update time. The catalog can be owned by our service for shops without a database. If the seller already has a Meta catalog, import or connect it rather than asking them to re-enter every item. Avoid two writable catalogs with unclear authority.

Treat exact stock differently from product identity. A social post tells us a product was advertised, not how many units are still available. Exact inventory stays trustworthy only if sales and stock changes are recorded or synced. Until then, use `available`, `sold out`, or `check with seller`, show when availability was last confirmed, and do not promise stock based on a recent post.

### Turn new Page posts into reviewed product drafts

Recommended flow:

1. Seller authorizes a Page connection.
2. A `feed` webhook signals a new post. Use the post ID to retrieve its text and attachments.
3. Create an import batch. Extract each clearly separate product candidate from its caption and attached image. A post with several standalone photos can create several drafts; a collage or ambiguous image remains one draft needing manual split/selection.
4. Show the seller each draft with source post, image, parsed title/price/size/color, and missing fields. Seller edits and approves each product and its availability before customer use.
5. Updates to price, variants, and availability create a reviewable change, not a silent overwrite. Keep the approved product record as the source of truth.

This preserves the seller's current posting habit while preventing a caption or image model from silently inventing stock and variants. Permission review and real-page testing are required before treating automatic post detection as a guaranteed feature.

### Interpret buyer media as a search query, not a product record

Normalize all inbound content into an evidence bundle:

- Text stays text.
- Voice is downloaded promptly, transcribed, and tagged with detected language when available. Do not rely on an uncalibrated transcript-confidence score; require customer confirmation of consequential details and hand off unclear transcripts.
- Images and screenshots are downloaded, captioned/OCR-processed as useful, and compared with seller-approved catalog images and product text.
- Text descriptions are matched against product names, aliases, color, size, and descriptions.

Retrieve a small set of candidate products from the shop's catalog. Answer with a product only when the match is clear and its current price/availability are known. When multiple visually similar items remain, show the candidate images/names and ask the buyer which one they mean. Do not infer exact SKU, size, or live stock from a generic photo, screenshot, voice transcript, or caption. If no match is safe, send the question to the owner.

For customer photos, captions and OCR are clues; catalog matching must identify a known item. A general vision model can describe a garment but may confuse near-identical patterns, colors under different lighting, and model photos. Measure top-candidate accuracy on shop-approved examples before allowing automatic product claims.

### Prefer structured product choices where available

For WhatsApp, a connected Meta catalog can support single- or multi-product messages. When the customer sends a catalog cart, use product IDs and quantities from the order webhook rather than extracting those fields from prose. This should be an optional guided ordering path, not a prerequisite for all shops; many target sellers may not yet have a catalog. Our catalog and order flow must still handle text, images, and ordinary messages.

## Product decision

Adopt a hybrid ingestion and answer path:

- Our service maintains the approved product/variant catalog for every shop.
- Existing Meta catalogs may be connected or imported after permission checks.
- Connected Page posts can produce product drafts after the required permissions and app review are proven.
- The seller approves each extracted product and stock state.
- Inbound buyer text, photos, screenshots, and, after dialect testing, voice notes search the catalog. They never establish product facts or stock by themselves.
- A WhatsApp catalog cart, when available, is parsed structurally.

This design covers sellers with and without websites while preserving a single truth source and a safe fallback when the media is ambiguous.
