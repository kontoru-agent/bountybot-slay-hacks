"""Proof-of-concept runner. A finding without a runnable PoC is a hypothesis.

Primary oracle: `forge test` on the target's Foundry project (real EVM,
real numbers). Fallback: a Python simulation of the exact same vault
semantics, used only when forge is not installed — and labelled as such.
Both oracles must agree on the numbers: vault 100 ETH -> 0, attacker
drains 101 ETH from a 1 ETH deposit.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import __version__  # noqa: F401  (keeps the package version importable)


@dataclass
class VerifyResult:
    method: str  # "forge" | "python-simulation"
    passed: bool
    tests_passed: int
    tests_failed: int
    vault_before_wei: int
    vault_after_wei: int
    attacker_drained_wei: int
    raw_output: str = ""

    @property
    def impact(self) -> dict[str, int]:
        return {
            "vault_before_wei": self.vault_before_wei,
            "vault_after_wei": self.vault_after_wei,
            "attacker_drained_wei": self.attacker_drained_wei,
            "deposit_wei": 10 ** 18,
        }


def find_forge() -> str | None:
    for cand in ("forge", str(Path.home() / ".foundry" / "bin" / "forge")):
        if shutil.which(cand):
            return cand
    return None


def _parse_forge_logs(output: str) -> dict[str, int]:
    nums: dict[str, int] = {}
    for label, key in (
        ("vault balance before (wei)", "vault_before_wei"),
        ("vault balance after (wei)", "vault_after_wei"),
        ("attacker drained (wei)", "attacker_drained_wei"),
    ):
        m = re.search(rf"{re.escape(label)}:\s*(\d+)", output)
        if m:
            nums[key] = int(m.group(1))
    return nums


def run_forge(target_dir: str | Path) -> VerifyResult:
    forge = find_forge()
    if forge is None:
        raise RuntimeError("forge not found")
    proc = subprocess.run(
        [forge, "test", "-vv"], cwd=str(target_dir),
        capture_output=True, text=True, timeout=300,
    )
    output = proc.stdout + proc.stderr
    passed_tests = len(re.findall(r"\[PASS\]", output))
    failed_tests = len(re.findall(r"\[FAIL\]", output))
    nums = _parse_forge_logs(output)
    ok = proc.returncode == 0 and failed_tests == 0 and passed_tests > 0
    return VerifyResult(
        method="forge",
        passed=ok,
        tests_passed=passed_tests,
        tests_failed=failed_tests,
        vault_before_wei=nums.get("vault_before_wei", 0),
        vault_after_wei=nums.get("vault_after_wei", 0),
        attacker_drained_wei=nums.get("attacker_drained_wei", 0),
        raw_output=output,
    )


class SimVault:
    """Python model of DemoVault with the SAME bug: ETH sent before the
    share balance is zeroed. The attacker's receive() re-enters here."""

    def __init__(self) -> None:
        self.shares: dict[str, int] = {}
        self.total_shares = 0
        self.balance = 0

    def deposit(self, who: str, amount: int) -> None:
        self.shares[who] = self.shares.get(who, 0) + amount
        self.total_shares += amount
        self.balance += amount

    def withdraw(self, who: str, on_receive) -> None:
        amount = self.shares.get(who, 0)
        assert amount > 0, "no shares"
        self.balance -= amount
        on_receive(amount)  # BUG: external call before the state update
        self.shares[who] = 0
        self.total_shares -= amount


def run_python_simulation() -> VerifyResult:
    """Reproduce the drain with the Python model (forge absent)."""
    vault = SimVault()
    vault.deposit("victim", 100 * 10 ** 18)
    before = vault.balance
    drained = {"wei": 0}

    def attacker_receive(amount: int) -> None:
        drained["wei"] += amount
        if vault.balance >= 10 ** 18:
            vault.withdraw("attacker", attacker_receive)

    vault.deposit("attacker", 10 ** 18)
    vault.withdraw("attacker", attacker_receive)
    ok = vault.balance == 0 and drained["wei"] == 101 * 10 ** 18
    return VerifyResult(
        method="python-simulation",
        passed=ok,
        tests_passed=1 if ok else 0,
        tests_failed=0 if ok else 1,
        vault_before_wei=before,
        vault_after_wei=vault.balance,
        attacker_drained_wei=drained["wei"],
        raw_output=(
            "python-simulation: vault 100 ETH -> 0 ETH, "
            "attacker drained 101 ETH from a 1 ETH deposit"
        ),
    )


def verify(target_dir: str | Path) -> VerifyResult:
    """Forge first; Python simulation only when forge is not installed."""
    if find_forge() is not None:
        return run_forge(target_dir)
    return run_python_simulation()
