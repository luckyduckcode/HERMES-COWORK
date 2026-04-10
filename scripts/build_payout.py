#!/usr/bin/env python3
"""
build_payout.py
===============
Build an unsigned payout transaction for a Hermes-Cowork swarm.

Reads ROLLCALL.md and ESCROW.md to determine recipients and amounts,
fetches confirmed UTXOs from Blockstream Esplora, and outputs an unsigned
raw transaction hex ready for two-party signing.

Usage:
    python build_payout.py \\
        --rollcall path/to/ROLLCALL.md \\
        --escrow   path/to/ESCROW.md \\
        [--platform-address <bech32_address>] \\
        [--network mainnet|testnet] \\
        [--fee-rate <sat_per_vbyte>]

    The unsigned hex is printed to stdout. All diagnostics go to stderr.
    Pipe stdout to a file:
        python build_payout.py ... > unsigned_payout.txt

Requirements:
    pip install requests

Signing (two of three key holders must sign):
    Import the unsigned hex into Bitcoin Core:
        bitcoin-cli signrawtransactionwithkey <hex> \\
            '["<WIF_private_key>"]' \\
            '[{"txid":"<utxo_txid>","vout":<vout>,"scriptPubKey":"<p2wsh_spk_hex>","redeemScript":"<redeem_script_hex>","amount":<btc_float>}]'

    Or use Sparrow / Electrum by importing the redeem script and the unsigned hex.

    After both Key 1 (client) and Key 2 (platform) have signed:
        broadcast via https://blockstream.info/tx/push
        or: bitcoin-cli sendrawtransaction <fully_signed_hex>
"""

import argparse
import re
import sys

try:
    import requests
except ImportError:
    print("ERROR: requests is required.  pip install requests", file=sys.stderr)
    sys.exit(1)

ESPLORA = {
    "mainnet": "https://blockstream.info/api",
    "testnet": "https://blockstream.info/testnet/api",
}

# ---------------------------------------------------------------------------
# BIP-173 bech32 utilities (no external dependency)
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


def _convertbits(data, frombits: int, tobits: int, pad: bool = True) -> list[int]:
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


def bech32_decode(bech: str):
    """Return (hrp, data) for a valid bech32 string, or raise ValueError."""
    bech = bech.lower()
    if "1" not in bech:
        raise ValueError(f"Not a bech32 address: {bech}")
    pos = bech.rindex("1")
    hrp, encoded = bech[:pos], bech[pos + 1:]
    if len(hrp) < 1 or len(encoded) < 6:
        raise ValueError(f"Malformed bech32: {bech}")
    data = [_CHARSET.find(c) for c in encoded]
    if any(d == -1 for d in data):
        raise ValueError(f"Invalid bech32 character in: {bech}")
    if _bech32_polymod(_bech32_hrp_expand(hrp) + data) != 1:
        raise ValueError(f"Bad bech32 checksum: {bech}")
    return hrp, data[:-6]


def address_to_scriptpubkey(addr: str, network: str = "mainnet") -> bytes:
    """
    Decode a native-segwit (bech32) address and return its scriptPubKey bytes.

    Supports P2WPKH (bc1q.../tb1q... 20-byte hash) and
    P2WSH (bc1q.../tb1q... 32-byte hash) and P2TR (bc1p.../tb1p...).
    Only bech32 addresses are accepted (no legacy P2PKH/P2SH).
    """
    expected_hrp = "bc" if network == "mainnet" else "tb"
    hrp, data = bech32_decode(addr)
    if hrp != expected_hrp:
        raise ValueError(
            f"Address {addr} has HRP '{hrp}' but expected '{expected_hrp}' for {network}."
        )
    witness_version = data[0]
    witness_program = bytes(_convertbits(data[1:], 5, 8, False))
    if len(witness_program) not in (20, 32):
        raise ValueError(f"Unexpected witness program length {len(witness_program)} in {addr}.")
    opcode = 0x00 if witness_version == 0 else (0x50 + witness_version)
    return bytes([opcode, len(witness_program)]) + witness_program


# ---------------------------------------------------------------------------
# Raw transaction builder (no external dependency)
# ---------------------------------------------------------------------------

def _varint(n: int) -> bytes:
    if n < 0xFD:
        return bytes([n])
    elif n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    elif n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def build_unsigned_tx(
    utxos: list[dict],
    outputs: list[tuple[bytes, int]],   # (scriptPubKey, sats)
) -> str:
    """
    Build an unsigned Bitcoin transaction (non-segwit serialisation).

    The transaction has no signatures; it must be signed by Key 1 and Key 2
    before broadcasting.  Bitcoin Core's signrawtransactionwithkey handles
    the segwit witness construction automatically given the prevtx metadata.

    Returns the raw transaction as a lowercase hex string.
    """
    raw = b""
    raw += (2).to_bytes(4, "little")          # version 2

    # Inputs
    raw += _varint(len(utxos))
    for utxo in utxos:
        raw += bytes.fromhex(utxo["txid"])[::-1]  # little-endian txid
        raw += utxo["vout"].to_bytes(4, "little")
        raw += _varint(0)                          # empty scriptSig (unsigned)
        raw += (0xFFFFFFFF).to_bytes(4, "little")  # sequence

    # Outputs
    raw += _varint(len(outputs))
    for spk, sats in outputs:
        raw += sats.to_bytes(8, "little")
        raw += _varint(len(spk))
        raw += spk

    raw += (0).to_bytes(4, "little")           # locktime
    return raw.hex()


# ---------------------------------------------------------------------------
# File parsers
# ---------------------------------------------------------------------------

def parse_rollcall(path: str) -> list[dict]:
    """
    Parse ROLLCALL.md and return a list of pod dicts.

    Each dict has keys: pod_id, handle, pod_type, btc_address.
    Header and separator rows are skipped.
    """
    pods = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            # Skip header row and separator row (e.g. |---|---|...)
            if "Pod ID" in line or re.fullmatch(r"\|[-| ]+\|", line):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 4:
                continue
            pod_id, handle, pod_type, btc_address = (parts + [""] * 4)[:4]
            if not btc_address or btc_address.lower() in ("bitcoin payout address", ""):
                continue
            pods.append({
                "pod_id":     pod_id,
                "handle":     handle,
                "pod_type":   pod_type,
                "btc_address": btc_address,
            })
    return pods


def parse_escrow(path: str) -> dict:
    """Parse key: value lines from ESCROW.md."""
    data = {}
    keys = ("Address", "Redeem-Script", "Required-Sats", "Pod-Cap",
            "Platform-Fee-Pct", "Network")
    with open(path) as f:
        for line in f:
            line = line.strip()
            for k in keys:
                if line.startswith(f"{k}:"):
                    data[k] = line.split(":", 1)[1].strip()
    return data


# ---------------------------------------------------------------------------
# Esplora API
# ---------------------------------------------------------------------------

def fetch_utxos(address: str, api_base: str) -> list[dict]:
    """Fetch confirmed UTXOs for a Bitcoin address via Blockstream Esplora."""
    url = f"{api_base}/address/{address}/utxo"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return [u for u in resp.json() if u.get("status", {}).get("confirmed", False)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an unsigned Hermes-Cowork payout transaction."
    )
    parser.add_argument("--rollcall",         required=True,  help="Path to ROLLCALL.md")
    parser.add_argument("--escrow",           required=True,  help="Path to ESCROW.md")
    parser.add_argument("--platform-address", default="",     help="Platform BTC address for fee output")
    parser.add_argument("--network",          default="mainnet", choices=["mainnet", "testnet"])
    parser.add_argument("--fee-rate",         type=int, default=5, help="Sat/vbyte (default: 5)")
    args = parser.parse_args()

    api_base = ESPLORA[args.network]

    # --- Parse files ---
    pods = parse_rollcall(args.rollcall)
    if not pods:
        print("ERROR: No pods found in ROLLCALL.md.", file=sys.stderr)
        sys.exit(1)

    escrow = parse_escrow(args.escrow)
    address          = escrow.get("Address", "").strip()
    required_sats    = int(escrow.get("Required-Sats", "0") or 0)
    fee_pct          = float(escrow.get("Platform-Fee-Pct", "15") or 15) / 100.0
    redeem_script_hex = escrow.get("Redeem-Script", "")
    network_from_file = escrow.get("Network", args.network)

    if not address:
        print("ERROR: No Address found in ESCROW.md.", file=sys.stderr)
        sys.exit(1)

    if network_from_file != args.network:
        print(
            f"WARNING: ESCROW.md says network={network_from_file} but --network={args.network}. "
            "Using ESCROW.md value.",
            file=sys.stderr,
        )
        args.network = network_from_file
        api_base = ESPLORA[args.network]

    print(f"Escrow address : {address}", file=sys.stderr)
    print(f"Pods to pay    : {len(pods)}", file=sys.stderr)
    print(f"Network        : {args.network}", file=sys.stderr)

    # --- Fetch UTXOs ---
    print("Fetching UTXOs from Esplora...", file=sys.stderr)
    try:
        utxos = fetch_utxos(address, api_base)
    except Exception as exc:
        print(f"ERROR fetching UTXOs: {exc}", file=sys.stderr)
        sys.exit(1)

    if not utxos:
        print(
            "ERROR: No confirmed UTXOs found at escrow address.\n"
            "       Has the client sent bitcoin to the address?",
            file=sys.stderr,
        )
        sys.exit(1)

    total_input_sats = sum(u["value"] for u in utxos)
    print(f"Confirmed sats : {total_input_sats:,}", file=sys.stderr)

    # --- Fee calculation ---
    # Estimate vbytes:
    #   overhead:        10  (version 4 + locktime 4 + input count 1 + output count 1)
    #   per P2WSH input: 41  (outpoint 36 + scriptSig len 1 + sequence 4; witness handled separately)
    #   per P2WPKH out:  31  (value 8 + scriptPubKey len 1 + OP_0+push+20_bytes = 22)
    n_inputs   = len(utxos)
    n_outputs  = len(pods) + (1 if args.platform_address else 0)
    est_vbytes = 10 + 41 * n_inputs + 31 * n_outputs
    tx_fee     = est_vbytes * args.fee_rate

    platform_fee  = int(total_input_sats * fee_pct)
    distributable = total_input_sats - platform_fee - tx_fee

    if distributable <= 0:
        print("ERROR: Insufficient funds after fees.", file=sys.stderr)
        print(f"  Total input    : {total_input_sats:,} sats", file=sys.stderr)
        print(f"  Platform fee   : {platform_fee:,} sats ({fee_pct * 100:.0f}%)", file=sys.stderr)
        print(f"  TX fee (est.)  : {tx_fee:,} sats ({est_vbytes} vbytes @ {args.fee_rate} sat/vbyte)", file=sys.stderr)
        sys.exit(1)

    per_pod   = distributable // len(pods)
    remainder = distributable - per_pod * len(pods)

    print(f"Platform fee   : {platform_fee:,} sats ({fee_pct*100:.0f}%)", file=sys.stderr)
    print(f"TX fee (est.)  : {tx_fee:,} sats  ({est_vbytes} vbytes @ {args.fee_rate} sat/vbyte)", file=sys.stderr)
    print(f"Distributable  : {distributable:,} sats", file=sys.stderr)
    print(f"Per-pod        : {per_pod:,} sats", file=sys.stderr)
    if remainder:
        print(f"Remainder      : {remainder} sats  → added to first pod", file=sys.stderr)
    print(file=sys.stderr)

    # --- Build output list ---
    outputs: list[tuple[bytes, int]] = []

    # Platform fee output (optional — only if operator supplied their BTC address)
    if args.platform_address and platform_fee > 0:
        try:
            spk = address_to_scriptpubkey(args.platform_address, args.network)
        except ValueError as exc:
            print(f"ERROR: Invalid --platform-address: {exc}", file=sys.stderr)
            sys.exit(1)
        outputs.append((spk, platform_fee))
        print(f"  PLATFORM  {args.platform_address}  {platform_fee:,} sats", file=sys.stderr)
    elif platform_fee > 0:
        print(
            f"WARNING: --platform-address not provided; platform fee ({platform_fee:,} sats) "
            "is included in pod distribution.",
            file=sys.stderr,
        )
        # redistribute platform fee among pods
        per_pod = (distributable + platform_fee) // len(pods)
        remainder = (distributable + platform_fee) - per_pod * len(pods)

    # Pod outputs
    for i, pod in enumerate(pods):
        amount = per_pod + (remainder if i == 0 else 0)
        try:
            spk = address_to_scriptpubkey(pod["btc_address"], args.network)
        except ValueError as exc:
            print(
                f"ERROR: Bad address for pod {pod['pod_id']} ({pod['handle']}): {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        outputs.append((spk, amount))
        print(f"  {pod['pod_id']:<10} {pod['handle']:<20} {pod['btc_address']}  {amount:,} sats", file=sys.stderr)

    # --- Build unsigned transaction ---
    print(file=sys.stderr)
    print("Building unsigned transaction...", file=sys.stderr)
    try:
        tx_hex = build_unsigned_tx(utxos, outputs)
    except Exception as exc:
        print(f"ERROR building transaction: {exc}", file=sys.stderr)
        sys.exit(1)

    # Signing instructions
    print(file=sys.stderr)
    print("─" * 60, file=sys.stderr)
    print("Unsigned transaction hex → stdout", file=sys.stderr)
    print(file=sys.stderr)
    print("Signing with Bitcoin Core (repeat for each key holder):", file=sys.stderr)
    prevtxs = "[" + ",".join(
        f'{{"txid":"{u["txid"]}","vout":{u["vout"]},'
        f'"scriptPubKey":"0020{__import__("hashlib").sha256(bytes.fromhex(redeem_script_hex)).hexdigest() if redeem_script_hex else "..."}","redeemScript":"{redeem_script_hex}","amount":{u["value"]/1e8:.8f}}}'
        for u in utxos
    ) + "]" if redeem_script_hex else "[{see ESCROW.md for redeemScript}]"
    print(f"  bitcoin-cli signrawtransactionwithkey <hex> '[\"<WIF_key>\"]' '{prevtxs}'", file=sys.stderr)
    print(file=sys.stderr)
    print("After both Key 1 and Key 2 have co-signed:", file=sys.stderr)
    print("  broadcast via https://blockstream.info/tx/push", file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    print(tx_hex)  # ← stdout only, suitable for piping


if __name__ == "__main__":
    main()
