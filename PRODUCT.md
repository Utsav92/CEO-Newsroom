# CEO Newsroom

Readers follow technology reporting and official company videos, ask questions, and receive researched explanations from clearly labeled AI-simulated CEO presenters. Presenters are independent simulations with no executive endorsement. Shared-company topics can receive separate company perspectives. Answers distinguish evidence, reasoning and uncertainty.

Readers can save articles with hearts, return to saved conversations, and navigate new reporting without losing their reading position. Official company YouTube uploads refresh daily while the server is running. Actual audio/visual video understanding requires the configured Gemini service.

Accounts use email and password with server-side sessions. First-account registration through localhost retains existing history. Other accounts have separate conversations, saved articles, preferences, membership and answer-language choice. Reporting, videos and briefing snapshots are shared server content. Readers can edit their display name and change their password using the current password. Password changes rotate the current session and revoke other sessions. Email recovery and verification are outside the current implementation.

Settings contains Preferences, Account, Pricing and Language. Account offers Sign out. Confirmed pricing is USD monthly: Silver $2, Gold $3 and Platinum $5. No tier quotas are defined. Stripe is the chosen provider. Stripe activation is pending local credentials; checkout stays disabled until configured. The integration offers hosted card checkout and eligible Google Pay/Apple Pay, Mastercard/credit/debit options, monthly bank-transfer invoices and a QR link to a real checkout session. Only server-verified paid subscriptions activate membership. Pricing includes invoice links/PDFs, older invoice pages, payment-attempt history, and controls to stop or resume renewal at the billing-period boundary. Stopping renewal requires an explicit confirmation and does not issue a refund.

Language selection controls new CEO answers and follow-up questions in 12 languages. Interface copy, original reporting and existing answers retain their original language.

The supplied CEO artwork and the established green visual identity are retained. The verified environment is a local Windows server with SQLite and one backend worker. Public hosting requires additional operational controls.


Security defaults keep registration local, enforce authenticated account isolation, and restrict manual shared-source refresh to the owner. Sessions have an API-idle timeout and a five-session cap. The app is not presented as unhackable or as a completed public-hosting security assessment; see SECURITY.md.
