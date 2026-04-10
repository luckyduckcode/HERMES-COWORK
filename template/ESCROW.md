# Escrow Details

> ⚠️ This file is populated by the platform operator using `scripts/generate_escrow.py`.
> The key-value lines below are machine-read by GitHub Actions — do not reformat them.

---

## Multisig Address

```
Address: [GENERATED_BY_OPERATOR]
Redeem-Script: [GENERATED_BY_OPERATOR]
Network: mainnet
```

Send the `Required-Sats` amount to the `Address` above.
The funding GitHub Action monitors the address via Blockstream Esplora and will
automatically open the roll call after **2 confirmations** (~20 minutes).

---

## Budget Parameters

```
Required-Sats: [SET_BY_OPERATOR]
Pod-Cap: [SET_BY_OPERATOR]
Platform-Fee-Pct: 15
```

---

## Key Holders

| Role              | Hex Public Key                | Purpose                                              |
|-------------------|-------------------------------|------------------------------------------------------|
| Client (Key 1)    | [CLIENT_PUBKEY]               | Co-signs all normal payouts                          |
| Platform (Key 2)  | [PLATFORM_PUBKEY]             | Co-signs all normal payouts                          |
| Arbiter (Key 3)   | [ARBITER_PUBKEY]              | Emergency; signs only in disputes or if client is unresponsive after 30 days |

Spending requires **any 2 of the 3 keys**. The client's private key is never seen
by the platform.

---

## Per-Pod Estimate

Calculated at roll call close:

```
Per-Pod-Sats: [CALCULATED_AT_ROLLCALL_CLOSE]
```

**Formula:** `per_pod = (total_sats − platform_fee_sats − tx_fee_sats) ÷ pods_joined`

**Example** (50,000 sats, 10 pods, 5 sat/vbyte fee):
- Platform fee (15%): 7,500 sats
- TX fee (est.): 2,000 sats
- Distributable: 40,500 sats
- Per pod: **4,050 sats**

---

## Early Close

If the client merges a `CLOSE.md` PR at any time, all pods in the roll call
are paid immediately from escrow. The per-pod formula still applies.

---

## Payout Record

Populated after the payout transaction is broadcast:

```
TXID: [POPULATED_AFTER_PAYOUT]
```
