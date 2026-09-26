# Data Dictionary (LATAM Bank Dataset — greppable translation)

This is a plain-text, greppable translation of `LATAM_Bank_Complete_Data_Dictionary.pdf` and
`LATAM_Bank_Dataset_Summary.pdf` (repository root), kept for fast lookup during development.
**Those PDFs are the source of truth** — if this file and the PDFs ever disagree, the PDFs
win; re-derive this file rather than editing around a discrepancy. See `docs/data-lineage.md`
for how each table is used in this system, and `docs/domain-model.md` for how raw columns map
onto this system's own entities.

Dataset: LATAM Bank Dataset, Factored Datathon 2026, v1.0.0, generated July 2026. ~19,000,000
rows, 13 tables, countries Mexico/Colombia/Argentina, date range 2023-06-17 to 2026-06-17,
currencies MXN/COP/ARS/USD, all text in Spanish (Mexican/Colombian/Argentine variants).
**Entirely synthetic — label as `SYNTHETIC` in any output.** Known data-quality
characteristics: ~2% duplicates, ~5% nulls in nullable fields, late-arriving partitions,
schema evolution over time (`docs/data-lineage.md` § 2).

## Dimension tables

### customers (150,000 rows) — Core Banking, monthly_snapshot
`customer_id` PK · `document_number` UNIQUE · `document_type` (DNI, CURP, CC, CE, Passport) ·
`first_name` · `last_name` · `date_of_birth` · `gender` (M/F/O) · `email` · `mobile_phone` ·
`landline_phone` · `address` · `city` · `state` · `country` (Mexico/Colombia/Argentina) ·
`postal_code` · `detected_accent` (mexican/colombian/argentine/neutral) · `segment`
(Premium/Plus/Basic/Student) · `credit_score` (300–850) · `estimated_monthly_income` ·
`occupation` · `marital_status` · `education_level` · `registration_date` ·
`registration_branch_id` FK→branches · `customer_status` (Active/Inactive/Suspended/Closed) ·
`last_updated` · `accepts_marketing`

### products (400,000 rows) — Core Banking, monthly_snapshot
`product_id` PK · `customer_id` FK→customers · `product_type` (Checking Account, Savings
Account, Credit Card, Debit Card, Personal Loan, Mortgage, Investment, ...) · `product_number`
UNIQUE · `currency` (MXN/COP/ARS/USD) · `current_balance` · `credit_limit` · `interest_rate` ·
`opening_date` · `expiration_date` · `opening_branch_id` FK→branches · `product_status`
(Active/Blocked/Closed/Suspended) · `opening_channel` (Branch/Web/App/Call Center) ·
`has_linked_app` · `days_past_due` · `last_transaction_date` · `last_updated`

### branches (350 rows) — Internal, full_snapshot
`branch_id` PK · `branch_code` UNIQUE · `branch_name` · `branch_type` (Main/Express/Premium/
Corporate) · `address` · `city` · `state` · `country` · `postal_code` · `geographic_zone`
(Urban/Suburban/Rural) · `phone` · `email` · `opening_time` · `closing_time` · `has_atms` ·
`atm_count` · `has_teller_windows` · `teller_window_count` · `latitude` · `longitude` ·
`branch_opening_date` · `branch_status` (Active/Temporarily Closed/Closed)

### service_agents (1,200 rows) — Internal, monthly_snapshot
`agent_id` PK · `employee_code` UNIQUE · `first_name` · `last_name` · `email` · `phone` ·
`native_accent` (mexican/colombian/argentine) · `country_of_origin` · `assigned_branch_id`
FK→branches · `agent_type` (Phone/In-Person/Digital/Hybrid) · `experience_level` (Junior/
Mid-Senior/Senior/Specialist) · `languages` · `specialty` · `hire_date` · `avg_csat` (1–5) ·
`total_monthly_interactions` · `agent_status` (Active/Vacation/Leave/Inactive) · `work_shift`
(Morning/Afternoon/Night/Rotating)

### marketing_campaigns (200 rows) — Internal, full_snapshot
`campaign_id` PK · `campaign_name` · `description` · `campaign_type` (Email/SMS/Push/WhatsApp/
Voice/Mix) · `campaign_objective` (Acquisition/Retention/Cross-sell/Up-sell/Reactivation) ·
`promoted_product` · `target_segment` · `target_country` · `start_date` · `end_date` ·
`budget` · `campaign_status` (Planned/Active/Paused/Completed) · `expected_conversion_rate`

*Not used by the fraud/dispute workflow — retained here for completeness only.*

## Fact tables

### transactions (5,000,000 rows) — Core Banking, daily partition — **primary table**
`transaction_id` PK · `transaction_date` · `process_date` (partition key) · `product_id`
FK→products · `customer_id` FK→customers · `transaction_type` (Deposit/Withdrawal/Transfer/
Payment/Purchase/Adjustment) · `transaction_category` (Food/Transport/Services/Entertainment/
Health/Other) · `amount` · `currency` · `amount_usd` · `channel` (ATM/Branch/Web/App/POS/
Transfer) · `branch_id` FK→branches · `merchant_name` · `merchant_category` (MCC) ·
`transaction_country` · `transaction_city` · `transaction_status` (Approved/Declined/Pending/
Reversed) · `response_code` · **`is_fraud`** · **`fraud_score`** (0–100) · `latitude` ·
`longitude`.
**`is_fraud`/`fraud_score` are synthetic label-generation artifacts — excluded from model
features, see `docs/data-lineage.md` § 5.**

### call_center_interactions (800,000 rows) — Contact Center, daily
`interaction_id` PK · `interaction_date` · `process_date` · `customer_id` FK→customers ·
`agent_id` FK→service_agents · `interaction_type` (Inbound Call/Outbound Call/Chat/Email/
Video) · `channel` (Phone/Web Chat/WhatsApp/Email/App) · `contact_reason` · `reason_category`
(Transactional/Product/Technical/Commercial/Complaint) · `duration_seconds` ·
`wait_time_seconds` · `was_resolved` (FCR) · `requires_followup` · `detected_sentiment`
(Positive/Neutral/Negative/Very Negative) · `sentiment_score` (-1 to 1) ·
`customer_detected_accent` · `agent_used_accent` · `was_escalated` · `mentioned_products` ·
`has_transcript` · `has_recording`. **Entry point for a dispute/fraud report.**

### call_transcripts (200,000 rows) — Contact Center, daily
`transcript_id` PK · `interaction_id` FK→call_center_interactions · `process_date` ·
`customer_id` FK→customers · `agent_id` FK→service_agents · `full_text` · `customer_text` ·
`agent_text` · `detected_language` · `detected_accent` · `accent_confidence` ·
`detected_keywords` · `mentioned_entities` (JSON) · `detected_intents` · `main_topics` ·
`transcription_model` · `audio_quality` · `duration_seconds`. **Source of the customer's
verbatim statement for the Case Packet (`docs/human-oversight.md` § 3).**

### satisfaction_surveys (250,000 rows) — Contact Center, daily
`survey_id` PK · `survey_date` · `process_date` · `interaction_id` FK · `customer_id` FK ·
`agent_id` FK · `survey_type` (CSAT/NPS/CES) · `send_channel` · `main_score` · `nps_category`
(Promoter/Passive/Detractor) · `question_1..3_text/response` · `open_comments` ·
`comment_sentiment` · `response_time_hours` · `campaign_response_rate`.
*Not used by the core fraud/dispute workflow — relevant to evaluation of customer experience
only.*

### digital_events (10,000,000 rows) — Digital Banking, daily — **device/session source**
`event_id` PK · `event_date` · `process_date` · `customer_id` FK · `session_id` ·
`event_type` (PageView/Click/FormSubmit/Login/Logout/Error/Purchase) · `event_category`
(Navigation/Transaction/Authentication/Product) · `channel` (Android App/iOS App/Desktop Web/
Mobile Web) · `platform` · `browser` · `app_version` · `page_url` · `page_title` · `action` ·
`element_id` · `product_id` FK · `event_value` · `duration_seconds` · `ip_address` ·
`ip_country` · `ip_city` · `is_mobile` · `referrer` · `utm_source/medium/campaign`.
**Source for the derived `Device` entity (`docs/domain-model.md` § Device) — no standalone
device table exists in the dataset.**

### complaints (80,000 rows) — PQR, daily — **dispute-history source**
`complaint_id` PK · `creation_date` · `process_date` · `customer_id` FK · `case_type`
(Complaint/Claim/Request/Suggestion) · `category` · `subcategory` · `reception_channel`
(Call Center/Email/Web/App/Branch/Regulator) · `affected_product_id` FK→products ·
`related_branch_id` FK→branches · `origin_interaction_id` FK→call_center_interactions ·
`description` · `claimed_amount` · `currency` · `priority` (Low/Medium/High/Critical) ·
`status` (Open/In Process/Escalated/Resolved/Closed/Rejected) · `assigned_agent_id`
FK→service_agents · `assignment_date` · `first_response_date` · `resolution_date` ·
`closing_date` · `sla_breached` · `resolution_days` · `resolution` · `compensation_granted` ·
`resolution_satisfaction` · `is_repeat_complainer`.

### campaign_sends (2,000,000 rows) — Internal, daily
`send_id` PK · `send_date` · `process_date` · `campaign_id` FK→marketing_campaigns ·
`customer_id` FK→customers · `send_channel` · `template_used` · `subject` · `send_status`
(Sent/Failed/Bounced/Blocked) · `was_delivered` · `was_opened` · `open_date` · `was_clicked` ·
`click_date` · `click_count` · `had_conversion` · `conversion_date` · `conversion_value` ·
`open_device` · `open_country` · `failure_reason` · `send_cost`.
*Not used by the fraud/dispute workflow.*

## Reference tables

### daily_exchange_rates (3,000 rows) — Reference, daily
`date` PK · `source_currency` PK · `target_currency` PK · `exchange_rate` · `buy_rate` ·
`sell_rate` · `source`. **Used to reconcile `transactions.amount` vs. `amount_usd` when the
latter is missing or stale.**

## Foreign keys relevant to this workflow

```
transactions.customer_id      → customers.customer_id
transactions.product_id       → products.product_id
transactions.branch_id        → branches.branch_id
products.customer_id          → customers.customer_id
call_center_interactions.customer_id → customers.customer_id
call_center_interactions.agent_id    → service_agents.agent_id
call_transcripts.interaction_id      → call_center_interactions.interaction_id
complaints.customer_id               → customers.customer_id
complaints.affected_product_id       → products.product_id
complaints.origin_interaction_id     → call_center_interactions.interaction_id
digital_events.customer_id           → customers.customer_id
digital_events.product_id            → products.product_id
```

A small percentage of orphaned records exist intentionally for referential-integrity testing —
handle missing joins as an `Unknown` (`docs/domain-model.md` § 4), not as an ingestion crash.

## Tables not used by this workflow

`marketing_campaigns`, `campaign_sends`, `satisfaction_surveys`, and `branches` (beyond simple
lookups) are part of the dataset but out of scope for the chosen fraud/dispute workflow
(`docs/product-requirements.md` § 3). They remain available if a future phase extends scope.
