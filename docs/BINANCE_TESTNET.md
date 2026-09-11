# Binance Testnet Safety Gate

The first exchange integration is deliberately limited to Binance Testnet.

## Required gates

- Testnet environment must be explicit.
- API credentials must be present but are never committed to Git.
- Withdrawal permission must be disabled.
- The configured outbound/trusted IP must be a valid IP address and, for real Binance connectivity, must be allow-listed in Binance API settings.
- Live execution remains disabled regardless of Testnet preflight success.
- All trading requests must pass through the Risk Engine before execution.

## Scope

This milestone validates configuration safety only. It does not claim that network connectivity, account permissions, market data, or order placement have been verified against Binance. Those require an explicit Testnet connectivity adapter and integration tests.
