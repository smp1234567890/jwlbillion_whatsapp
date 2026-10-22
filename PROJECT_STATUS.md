# Project Status

This application is a dedicated WhatsApp CRM for JWL.
It uses FastAPI, PostgreSQL (managed via Alembic), React/Vite, Capacitor, Meta WhatsApp Cloud API, and a Shopify store webhook connector.

## Security Posture & Architecture (Remediations WP1–WP9)

The codebase implements zero-trust, fail-closed controls across all critical boundaries:

1. **WP1: Schema Migration Discipline (Zero Runtime DDL)**
   - Schema alterations run exclusively through Alembic revisions (`alembic upgrade head`) during build/deployment.
   - Startup and runtime request handlers emit zero DDL.

2. **WP2: Centralized Outbound Policy & Consent Gate**
   - 100% of outbound WhatsApp message dispatches must be authorized through `policy_service.authorize_and_create_outbound`.
   - Every send creates an immutable ledger entry in `outbound_messages` with status `PENDING`, updating to `SENT` or `FAILED`.
   - Opt-out / DND records strictly block all promotional and transactional messaging. DND deletion remains neutral and never creates affirmative marketing consent.

3. **WP3: Integration Gateway & SSRF Defenses**
   - Outbound requests to external URLs are validated against allowed host lists and private IP / loopback restrictions.
   - Credentials are stored encrypted using AES-256-GCM via `secret_store`.

4. **WP4: Authentication & Session Lifecycle**
   - Auth endpoints are protected with distributed sliding-window rate limiting and lockout mechanisms.
   - Refresh tokens rotate upon use; session invalidation is triggered on password reset and privilege changes.

5. **WP5: Webhook Replay Defense & Payload Digesting**
   - Store webhooks require HMAC-SHA256 signatures via `WEBHOOK_SECRET`.
   - Meta webhooks require HMAC-SHA256 signatures via `META_APP_SECRET` and fail-closed in production.
   - Inbound webhook payloads compute canonical SHA-256 digests recorded in `inbound_webhook_events`.
   - Concurrent delivery race conditions are handled gracefully with DB-level unique constraints.

6. **WP6: Operational PII Redaction & Non-Admin Masking**
   - Customer phone numbers are masked in all application logs (`services.pii_service.mask_phone`).
   - Non-admin roles view masked phone numbers in chat and CRM interfaces.
   - Data exports require administrative step-up authentication and emit audit events.

7. **WP7: Production Guardrails & Database TLS**
   - In production, missing Redis for rate limiting fails-closed with HTTP 503.
   - PostgreSQL connections in production enforce TLS modes (`verify-full`, `verify-ca`, or `require`).

8. **WP8: Worker Row-Level Leases & Single-Scheduler Model**
   - Scheduled jobs use APScheduler and run exclusively on designated worker nodes (`SCHEDULER_ENABLED=true`).
   - Campaign broadcasts and workflow sessions acquire durable row-level leases (`claim_campaign`, `claim_workflow_session`) to eliminate duplicate dispatches across horizontally scaled workers.

9. **WP9: Continuous Integration & Deployment Verification**
   - Automated CI workflow (`.github/workflows/ci.yml`) runs Python compilation verification and the full pytest suite (121+ tests) with PostgreSQL and Redis containers on every push and PR.

## Operational Model

- **API Instances**: Set `SCHEDULER_ENABLED=false` on web instances.
- **Worker Instance**: Set `SCHEDULER_ENABLED=true` on exactly one worker instance.
- **Migrations**: Executed automatically during Render build via `render.yaml` (`pip install -r backend/requirements.txt && alembic upgrade head`).
