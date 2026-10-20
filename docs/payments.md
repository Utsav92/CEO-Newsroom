# Stripe payments (optional)

A restricted test key has been saved and verified. Local webhook setup remains pending the restricted key’s Debugging Tools Write permission; checkout stays disabled until a real signing secret is configured. Pricing remains visible and checkout is disabled. Prices are USD per month: Silver $2, Gold $3, Platinum $5. No feature quotas are assigned to tiers.

To connect later:

1. Use your Stripe test environment first. Save STRIPE_SECRET_KEY in the ignored project .env.local. Keep it server-only and out of chat.
2. For local testing, install the Stripe CLI, sign in and run `stripe listen --forward-to http://127.0.0.1:8788/api/billing/webhook`. Save its signing secret as STRIPE_WEBHOOK_SECRET in that same file. Keep the listener running. Set PUBLIC_APP_URL=http://127.0.0.1:8788 and restart the app.
3. For hosted operation, set PUBLIC_APP_URL to your exact HTTPS origin and register an HTTPS endpoint ending /api/billing/webhook in Stripe. Use that endpoint's signing secret. Listen for checkout.session.completed, checkout.session.async_payment_succeeded, invoice.paid, invoice.payment_failed, customer.subscription.updated and customer.subscription.deleted.
4. Enable eligible wallets and USD bank transfers in Stripe, and configure the customer portal for cancellation/management. Account country and customer eligibility determine available methods. Bank transfers use monthly invoices with a seven-day due period.
5. Test successful, declined, unpaid, expired and cancelled payments before switching to live mode. Live keys require HTTPS. No live payment was exercised during implementation.

Card options open Stripe-hosted subscription checkout. Apple Pay and Google Pay appear on eligible devices/accounts. Mastercard is a card network; all card choices use Stripe's card checkout. QR produces a scannable link to the account's real checkout session. Bank transfer opens a Stripe-hosted invoice and relies on reconciliation. Stripe handles card and bank details.

The server owns amounts and recurrence, reuses pending orders and idempotency keys after uncertain failures, verifies subscription ownership and USD monthly price, and activates only on a confirmed paid invoice with an active subscription. Returning from checkout is insufficient. Signed webhooks are time-limited and duplicate event IDs are recorded. Settings also offers Check payment status and Manage subscription. Resolve pending payments before choosing another plan/method. An indeterminate request older than Stripe's idempotency retention needs merchant reconciliation; never clear it without checking Stripe.

Implementation follows [subscription checkout](https://docs.stripe.com/api/checkout/sessions/create), [bank-transfer subscriptions](https://docs.stripe.com/billing/subscriptions/bank-transfer) and [webhooks](https://docs.stripe.com/webhooks).


Settings → Pricing → Billing history & renewal retrieves only the signed-in account’s invoices, with older pages, hosted invoice links and PDF downloads. Local payment attempts remain readable during Stripe outages and are explicitly separated from invoices. Stop monthly renewal requires confirmation, preserves the current period and issues no refund. Resume monthly renewal is available until the subscription ends. Ownership is checked server-side before either update. Stripe’s portal handles payment details and other merchant-configured management. Pending QR checkouts are restored when reopening Pricing.


Restricted server keys are supported: rk_test_ displays test mode, while rk_live_ requires an HTTPS app URL just like sk_live_. A publishable pk_ key cannot enable checkout. The provided restricted test key is saved only in ignored project .env.local and passed to Stripe as a server header.

For local webhooks, `python scripts/stripe_local.py --prepare` obtains the real CLI signing secret and writes it directly to ignored .env.local. Then keep `python scripts/stripe_local.py` running alongside the app. The helper reads the API key from local configuration, forwards only the required event types from this account, and redacts keys from CLI output. Install the official Stripe CLI or pass its executable path with --cli. Restricted keys need Debugging Tools → Write (stripecli_session_write) for the local relay, in addition to the integration’s customer, checkout, subscription, product/price, invoice and customer portal permissions. Restart the backend after preparing the signing secret.
