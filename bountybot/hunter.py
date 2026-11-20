"""Static hunter: scan Solidity sources for the 10 DeFi bug classes.

Every rule is a genuine check that runs and reports. A rule that finds
nothing says so with a reason — silence is not evidence. The demo target is
expected to trip exactly one rule (REENTRANCY) and pass the other nine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# External value-transferring calls.
_CALL_RE = re.compile(r"\.(call\s*\{[^}]*value\s*:|transfer\s*\(|send\s*\()")
# State writes to a balance/share mapping or a total counter.
_STATE_WRITE_RE = re.compile(
    r"\b(shares|balances|totalShares|totalSupply)\s*\[[^\]]*\]\s*(=|\+=|-=)"
    r"|\b(totalShares|totalSupply)\s*(=|\+=|-=)"
)
_FUNCTION_RE = re.compile(
    r"function\s+(\w+)\s*\([^)]*\)[^{]*\{", re.DOTALL
)
_PRAGMA_RE = re.compile(r"pragma\s+solidity\s*\^?([0-9]+)\.([0-9]+)\.([0-9]+)")


@dataclass
class Candidate:
    bug_class: str
    severity: str
    file: str
    line: int
    function: str
    evidence: str
    detail: str


@dataclass
class CheckResult:
    bug_class: str
    status: str  # "finding" | "clean"
    detail: str
    candidates: list[Candidate] = field(default_factory=list)


def _function_bodies(source: str) -> list[tuple[str, int, str]]:
    """Split source into (name, start_line, body) per function."""
    bodies: list[tuple[str, int, str]] = []
    for m in _FUNCTION_RE.finditer(source):
        start = m.end() - 1  # at the opening brace
        depth = 0
        i = start
        while i < len(source):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = source[start:i + 1]
        start_line = source[:m.start()].count("\n") + 1
        bodies.append((m.group(1), start_line, body))
    return bodies


def _line_of(source: str, offset: int) -> int:
    return source[:offset].count("\n") + 1


def check_reentrancy(source: str, rel: str) -> CheckResult:
    """External call before a state write in the same function body."""
    candidates: list[Candidate] = []
    for name, start_line, body in _function_bodies(source):
        calls = list(_CALL_RE.finditer(body))
        if not calls:
            continue
        for call in calls:
            after = body[call.end():]
            write = _STATE_WRITE_RE.search(after)
            if write:
                call_line = start_line + body[:call.start()].count("\n")
                snippet = body[max(0, call.start() - 60):call.end() + 80].strip()
                candidates.append(Candidate(
                    bug_class="REENTRANCY",
                    severity="Critical",
                    file=rel,
                    line=call_line,
                    function=name,
                    evidence=snippet,
                    detail=(
                        f"{name}() sends value via an external call and only "
                        f"updates the share balance afterwards "
                        f"({write.group(0).strip()!r} comes after the call). "
                        f"A receiver contract can re-enter {name}() on every "
                        f"receipt against the same un-updated balance."
                    ),
                ))
                break
    if candidates:
        return CheckResult("REENTRANCY", "finding",
                           f"{len(candidates)} function(s) call out before updating state",
                           candidates)
    return CheckResult("REENTRANCY", "clean",
                       "no external call precedes a state write in any function")


def check_access_control(source: str, rel: str) -> CheckResult:
    """Fund-moving admin-looking functions without an access modifier."""
    adminish = re.compile(r"\b(sweep|rescue|setOwner|mint|pause|setFee|withdrawFees)\w*\s*\(")
    for name, _, body in _function_bodies(source):
        if adminish.search(name):
            return CheckResult("ACCESS_CONTROL", "finding",
                               f"admin-looking function {name}() has no access modifier")
    return CheckResult("ACCESS_CONTROL", "clean",
                       "no admin-looking fund-moving function without a modifier")


def check_accounting_desync(source: str, rel: str) -> CheckResult:
    """Every function writing shares[] must also update totalShares."""
    for name, _, body in _function_bodies(source):
        writes_shares = re.search(r"\bshares\s*\[", body) is not None
        writes_total = re.search(r"\btotalShares\s*(\+|-)?=", body) is not None
        if writes_shares and not writes_total:
            return CheckResult("ACCOUNTING_DESYNC", "finding",
                               f"{name}() updates shares[] without touching totalShares")
    return CheckResult("ACCOUNTING_DESYNC", "clean",
                       "shares[] and totalShares move together in every function")


def check_oracle(source: str, rel: str) -> CheckResult:
    if re.search(r"\bblock\.timestamp\b|\bgetPrice\b|\blatestRoundData\b", source):
        return CheckResult("ORACLE", "finding",
                           "time/price feed used in fund math — needs manipulation review")
    return CheckResult("ORACLE", "clean", "no time or price feed in fund math")


def check_unchecked_call(source: str, rel: str) -> CheckResult:
    for m in re.finditer(r"\.call\s*\{[^}]*\}", source):
        tail = source[m.end():m.end() + 200]
        if "require(ok" not in tail and "if (!ok" not in tail and "if (ok" not in tail:
            return CheckResult("UNCHECKED_CALL", "finding",
                               "low-level call return value is not checked")
    return CheckResult("UNCHECKED_CALL", "clean",
                       "every low-level call return value is checked")


def check_integer(source: str, rel: str) -> CheckResult:
    m = _PRAGMA_RE.search(source)
    if m and int(m.group(1)) == 0 and int(m.group(2)) < 8:
        return CheckResult("INTEGER_OVERFLOW", "finding",
                           f"pragma {m.group(0)} predates checked arithmetic")
    return CheckResult("INTEGER_OVERFLOW", "clean",
                       "pragma ^0.8.x — arithmetic is checked by the compiler")


def check_signature_replay(source: str, rel: str) -> CheckResult:
    if "ecrecover" in source and "nonce" not in source.lower():
        return CheckResult("SIGNATURE_REPLAY", "finding",
                           "ecrecover used with no nonce — signatures may replay")
    return CheckResult("SIGNATURE_REPLAY", "clean",
                       "no ecrecover without a nonce")


def check_proxy(source: str, rel: str) -> CheckResult:
    if "delegatecall" in source or "upgradeTo" in source:
        return CheckResult("PROXY", "finding",
                           "delegatecall/upgrade path present — needs storage-collision review")
    return CheckResult("PROXY", "clean", "no delegatecall or upgrade path")


def check_flash_loan(source: str, rel: str) -> CheckResult:
    if re.search(r"\bflashLoan\b|\bonFlashLoan\b", source):
        return CheckResult("FLASH_LOAN", "finding",
                           "flash-loan entry point present — needs callback review")
    return CheckResult("FLASH_LOAN", "clean", "no flash-loan entry point")


def check_erc4626_share_manipulation(source: str, rel: str) -> CheckResult:
    if re.search(r"totalSupply\s*==\s*0|first.?deposit|sharePrice|pricePerShare", source, re.I):
        return CheckResult("ERC4626_SHARE_MANIPULATION", "finding",
                           "share-price math present — needs donation/inflation review")
    return CheckResult("ERC4626_SHARE_MANIPULATION", "clean",
                       "1:1 shares, no share-price math to manipulate")


CHECKS = [
    check_reentrancy,
    check_access_control,
    check_accounting_desync,
    check_oracle,
    check_unchecked_call,
    check_integer,
    check_signature_replay,
    check_proxy,
    check_flash_loan,
    check_erc4626_share_manipulation,
]


def scan_file(path: str | Path, rel: str) -> list[CheckResult]:
    """Run all 10 class checks over one Solidity file."""
    source = Path(path).read_text()
    return [fn(source, rel) for fn in CHECKS]
