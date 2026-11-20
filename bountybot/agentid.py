"""Agent ID identity layer — the trust anchor for Bountybot's on-chain flow.

Before a hunter can register or submit a finding through Bountybot, their
wallet must hold a Binance Agent ID (SPACE ID Agent ID, ERC-721 on BNB Chain).
Holder check is balanceOf(address) > 0, exactly as the on-chain registry
(BountybotRegistry) enforces it. All checks here are read-only eth_call —
no transaction, no key, no signing.

The on-chain registry is deployed on BNB Chain mainnet and Sourcify-verified;
this module is its off-chain mirror, so invalid submissions never reach the
chain (and never waste the hunter's gas).
"""
from __future__ import annotations

import json
import re
import urllib.request

AGENT_ID_CONTRACT = "0x60b9262456de011f7d15a54cdd8c48baaa8b022f"
REGISTRY_CONTRACT = "0x32619eba3f351cb555355f6011c9e22782253867"
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
BALANCE_OF_SELECTOR = "0x70a08231"  # balanceOf(address)
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62})\.ai$")


def _is_hex_address(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", value or "") is not None


def is_agent_id_holder(address: str, rpc_url: str = BSC_RPC_URL) -> bool:
    """True when the address holds at least one Agent ID (read-only)."""
    if not _is_hex_address(address):
        raise ValueError(f"not an EVM address: {address!r}")
    data = BALANCE_OF_SELECTOR + "000000000000000000000000" + address[2:].lower()
    payload = json.dumps({
        "jsonrpc": "2.0", "method": "eth_call",
        "params": [{"to": AGENT_ID_CONTRACT, "data": data}, "latest"], "id": 1,
    }).encode()
    req = urllib.request.Request(
        rpc_url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "curl/8.5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.load(resp)
    if "error" in body:
        raise RuntimeError(f"RPC error: {body['error']}")
    return int(body["result"], 16) > 0


def normalize_agent_id_name(name: str) -> str:
    """Validate + normalize an Agent ID name. Raises ValueError if invalid."""
    cleaned = (name or "").strip().lower()
    if not cleaned:
        raise ValueError("Agent ID name is empty")
    if len(cleaned) > 64:
        raise ValueError("Agent ID name over 64 chars")
    if _NAME_RE.fullmatch(cleaned) is None:
        raise ValueError(
            "Agent ID name must look like 'name.ai' "
            "(lowercase letters, digits, hyphens, ending in .ai)"
        )
    return cleaned


def verify_hunter(agent_id_name: str, wallet: str,
                  rpc_url: str = BSC_RPC_URL) -> tuple[bool, str]:
    """One verdict for a hunter: (ok, reason). Read-only; needs network."""
    if not _is_hex_address(wallet):
        return False, f"invalid wallet address: {wallet!r}"
    try:
        name = normalize_agent_id_name(agent_id_name)
    except ValueError as exc:
        return False, str(exc)
    try:
        holder = is_agent_id_holder(wallet, rpc_url)
    except Exception as exc:  # noqa: BLE001 — surface RPC failures as a verdict
        return False, f"Agent ID check failed: {exc}"
    if not holder:
        return False, f"wallet {wallet} holds no Agent ID"
    return True, f"verified: {name} @ {wallet}"
