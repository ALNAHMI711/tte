# Repository Consolidation Plan

## Canonical target

`ALNAHMI711/tte` is the canonical trading-platform target. Existing repositories are source material, not independent runtime dependencies.

## Sources reviewed

| Source | Useful material | Decision |
|---|---|---|
| `ALNAHMI711/tte` | Auth, sessions, CSRF, secrets, audit, risk, kill switch, Binance Testnet boundary, paper execution, chart terminal | Keep as the security/runtime foundation |
| `ALNAHMI711/M1` | Lightweight Charts indicator library and indicator architecture | Preserve/adapt into TTE chart terminal |
| `ALNAHMI711/MM` | Drawing primitives and chart interaction ideas | Reimplemented safely in TTE rather than copying the old app shell |
| `ALNAHMI711/Akm` | Historical trading-bot context | Do not import until concrete, non-duplicated source files are available |
| `ALNAHMI711/Ahmed-Alnahmi-711` | Arabic RTL dashboard layout, responsive cards, React component organization, WebSocket reconnect concept, Docker/Nginx frontend deployment ideas | Port UX/architecture ideas only; do not copy fake/demo trading state or its weaker auth/API assumptions |

## Non-negotiable consolidation rules

1. TTE remains the single runtime authority.
2. No frontend can submit an order directly to Binance.
3. Market data crosses a server-side authenticated boundary.
4. LIVE remains fail-closed.
5. Risk validation remains mandatory for every execution path.
6. Secrets never enter frontend code, Git, browser storage, or logs.
7. Demo balances, fake PnL, fake positions, and fake live statuses are prohibited.
8. Existing MIT/Apache notices are preserved when code is materially reused.
9. Features are migrated in small CI-verified batches.
10. M1/MM are not deleted until the migrated functionality is verified in TTE and the source repositories are explicitly approved for retirement.

## Current integration order

1. Chart + indicator + drawing foundation.
2. Incremental market/indicator updates.
3. Dashboard UX consolidation.
4. Persistent API-account/secret management using TTE's encrypted secret store.
5. Strategy catalog and backtest/paper workflow.
6. Risk and execution orchestration.
7. Docker/Nginx production deployment.
8. Only then consider enabling additional LIVE capability.

## Rejected source patterns

The old `Ahmed-Alnahmi-711` frontend contains hard-coded balances, positions and live states. These are intentionally **not** imported into TTE because they would create false production state and conflict with TTE's fail-closed security model.
