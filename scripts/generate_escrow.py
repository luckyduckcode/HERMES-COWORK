#!/usr/bin/env python3
"""
generate_escrow.py
==================
Generate a P2WSH 2-of-3 multisig Bitcoin escrow address for a Hermes-Cowork swarm.

No external dependencies — pure Python stdlib only.

Usage:
    python generate_escrow.py \\
        --client   <client_compressed_pubkey_hex> \\
        --platform <platform_compressed_pubkey_hex> \\
        --arbiter  <arbiter_compressed_pubkey_hex> \\
        [--network mainnet|testnet] \\
        [--budget-sats <int>] \\
        [--pod-cap <int>]

Output:
    Prints the bech32 escrow address, redeem script, and a ready-to-paste
    ESCROW.md block for the swarm repository.

Key holder roles:
    client   (Key 1) — co-signs all normal payouts
    platform (Key 2) — co-signs all normal payouts
    arbiter  (Key 3) — emergency key; used only in disputes or when the
                       client is unresponsive after the 30-day deadline

Example (testnet):
    python generate_escrow.py \\
        --client   02a1633cafcc01ebfb6d78e39f687a1f0995c62fc95f51ead10a02ee0be551b5dc \\
        --platform 0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798 \\
        --arbiter  02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5 \\
        --network testnet \\
        --budget-sats 50000 \\
        --pod-cap 50
"""

import argparse
import hashlib
import sys


# ---------------------------------------------------------------------------
# BIP-173 bech32 encoding (no external dependency)
# ---------------------------------------------------------------------------

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: list[int]) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if (b >> i) & 1 else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data: bytes, frombits: int, tobits: int, pad: bool = True) -> list[int]:
    acc = bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for v in data:
        if v < 0 or v >> frombits:
            return []
        acc = ((acc << frombits) | v) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return []
    return ret


def _bech32_encode(hrp: str, data: list[int]) -> str:
    combined = data + [
        ((_bech32_polymod(_bech32_hrp_expand(hrp) + data + [0] * 6) ^ 1) >> (5 * (5 - i))) & 31
        for i in range(6)
    ]
    return hrp + "1" + "".join(_CHARSET[d] for d in combined)


def p2wsh_address(redeem_script_bytes: bytes, network: str = "mainnet") -> str:
    """Encode a P2WSH bech32 address for the given redeem script."""
    hrp = "bc" if network == "mainnet" else "tb"
    script_hash = hashlib.sha256(redeem_script_bytes).digest()
    converted = _convertbits(script_hash, 8, 5)
    return _bech32_encode(hrp, [0] + converted)  # witness version 0


# ---------------------------------------------------------------------------
# 2-of-3 multisig redeem script builder
# ---------------------------------------------------------------------------

def build_2of3_redeem_script(pubkeys: list[bytes]) -> bytes:
    """
    Build a standard 2-of-3 multisig redeem script.

    Script layout:
        OP_2 <push 33> <pk1> <push 33> <pk2> <push 33> <pk3> OP_3 OP_CHECKMULTISIG
    """
    if len(pubkeys) != 3:
        raise ValueError("Exactly 3 public keys required.")
    for pk in pubkeys:
        if len(pk) != 33:
            raise ValueError(
                f"Expected a 33-byte compressed public key, got {len(pk)} bytes: {pk.hex()[:16]}..."
            )

    script = bytes([0x52])  # OP_2
    for pk in pubkeys:
        script += bytes([0x21]) + pk  # push 33 bytes + key
    script += bytes([0x53, 0xAE])  # OP_3  OP_CHECKMULTISIG
    return script


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a P2WSH 2-of-3 multisig escrow address for Hermes-Cowork."
    )
    parser.add_argument("--client",       required=True, help="Client compressed public key (33-byte hex)")
    parser.add_argument("--platform",     required=True, help="Platform compressed public key (33-byte hex)")
    parser.add_argument("--arbiter",      required=True, help="Arbiter compressed public key (33-byte hex)")
    parser.add_argument("--network",      default="mainnet", choices=["mainnet", "testnet"])
    parser.add_argument("--budget-sats",  type=int, default=0, help="Budget in satoshis (informational)")
    parser.add_argument("--pod-cap",      type=int, default=0, help="Maximum number of pods (informational)")
    args = parser.parse_args()

    # Validate and decode public keys
    pubkeys = []
    for role, hex_key in [("client", args.client), ("platform", args.platform), ("arbiter", args.arbiter)]:
        if len(hex_key) != 66:
            print(f"ERROR: --{role} key must be 66 hex characters (33-byte compressed pubkey).", file=sys.stderr)
            sys.exit(1)
        if hex_key[:2] not in ("02", "03"):
            print(f"ERROR: --{role} key does not look like a compressed pubkey (must start with 02 or 03).", file=sys.stderr)
            sys.exit(1)
        try:
            pubkeys.append(bytes.fromhex(hex_key))
        except ValueError:
            print(f"ERROR: --{role} key is not valid hex.", file=sys.stderr)
            sys.exit(1)

    # Build redeem script and derive address
    try:
        redeem_script = build_2of3_redeem_script(pubkeys)
        address = p2wsh_address(redeem_script, network=args.network)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    redeem_script_hex = redeem_script.hex()

    # Fee estimates
    platform_fee_sats = int(args.budget_sats * 0.15) if args.budget_sats else 0
    est_tx_fee_sats   = 2000  # rough estimate for a multi-output P2WSH tx

    # --- Console output ---
    SEP = "=" * 62
    print(SEP)
    print("HERMES-COWORK ESCROW  —  P2WSH 2-of-3 Multisig")
    print(SEP)
    print(f"Network        : {args.network}")
    print(f"Address        : {address}")
    print(f"Redeem Script  : {redeem_script_hex}")
    print()
    print("Key holders    :")
    print(f"  Key 1 (client)   : {args.client}")
    print(f"  Key 2 (platform) : {args.platform}")
    print(f"  Key 3 (arbiter)  : {args.arbiter}")
    if args.budget_sats:
        print()
        print(f"Budget         : {args.budget_sats:,} sats")
        if args.pod_cap:
            print(f"Pod Cap        : {args.pod_cap}")
        print(f"Platform Fee   : {platform_fee_sats:,} sats  (15%)")
        print(f"Est. TX Fee    : {est_tx_fee_sats:,} sats")
        distributable = args.budget_sats - platform_fee_sats - est_tx_fee_sats
        if args.pod_cap and distributable > 0:
            per_pod = distributable // args.pod_cap
            print(f"Per-Pod (est.) : {per_pod:,} sats  ({distributable:,} / {args.pod_cap} pods)")
    print()
    print(SEP)
    print("ESCROW.md BLOCK  —  paste into the swarm repository")
    print(SEP)
    print()
    print(f"Address: {address}")
    print(f"Redeem-Script: {redeem_script_hex}")
    print(f"Network: {args.network}")
    if args.budget_sats:
        print(f"Required-Sats: {args.budget_sats}")
    if args.pod_cap:
        print(f"Pod-Cap: {args.pod_cap}")
    print("Platform-Fee-Pct: 15")
    print()
    print("Send the Required-Sats amount to the Address above.")
    print("The funding GitHub Action will open the roll call after 2 confirmations (~20 min).")
    print()
    print("To verify the address independently:")
    print(f"  python3 -c \"import hashlib; s=bytes.fromhex('{redeem_script_hex}'); print(hashlib.sha256(s).hexdigest())\"")


if __name__ == "__main__":
    main()
