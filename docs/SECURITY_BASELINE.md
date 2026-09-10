# Security Baseline

## Authentication

- Passwords are stored only as Argon2id hashes.
- Passwords shorter than 12 characters are rejected by the foundation helper.
- Session identifiers are generated with the cryptographic random generator and are opaque.
- Sensitive control-panel actions require a separate short-lived step-up grant bound to the current session.
- Credentials, session tokens, API keys and secrets must never be committed to Git or written to logs.

## Trading safety

- Paper Trading remains the default path.
- LIVE Trading stays disabled until every release gate passes.
- AI, Telegram, strategies and UI code must never bypass the Risk Engine.
- Withdrawal permission is never required for trading integrations.
- Emergency stop blocks new orders and automation; it must not randomly liquidate positions.

## Next security gates

1. HTTP authentication/session integration.
2. Login rate limiting and account lockout policy.
3. CSRF and secure cookie policy for browser sessions.
4. Secret storage with encryption-at-rest and masking.
5. Audit events for authentication and sensitive changes.
6. Security dependency scanning and secret scanning in CI.
