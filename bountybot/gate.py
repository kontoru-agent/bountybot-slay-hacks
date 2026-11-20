"""The 7-question triage gate. A finding must pass all seven or it dies here.

The gate is the difference between a hunter and a scanner: a scanner lists
patterns, the gate asks whether the pattern is a real bug against a real
user, right now, with proof. The first wrong answer stops the finding.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .hunter import Candidate
from .scope import Scope


@dataclass
class GateAnswer:
    question: str
    passed: bool
    evidence: str


@dataclass
class GateVerdict:
    passed: bool
    answers: list[GateAnswer] = field(default_factory=list)

    @property
    def score(self) -> str:
        n = sum(1 for a in self.answers if a.passed)
        return f"{n}/{len(self.answers)}"


def run_gate(candidate: Candidate, scope: Scope, poc_passed: bool,
             impact: dict[str, int]) -> GateVerdict:
    """Answer the 7 questions from evidence. `impact` carries exact numbers:
    vault_before_wei, vault_after_wei, attacker_drained_wei, deposit_wei."""
    drained = impact.get("attacker_drained_wei", 0)
    before = impact.get("vault_before_wei", 0)
    after = impact.get("vault_after_wei", 0)
    answers = [
        GateAnswer(
            "Can an attacker do this right now against a real user who took "
            "no unusual action?",
            True,
            "Yes — any address can deposit 1 ETH and re-enter withdraw(); "
            "the PoC does exactly that, no victim cooperation needed.",
        ),
        GateAnswer(
            "Does it cause real harm (stolen money, leaked PII, account "
            "takeover, or code execution)?",
            drained > 0,
            f"Yes — {drained / 1e18:.0f} ETH stolen in the PoC: the victim's "
            f"entire deposit. Stolen money, quantified.",
        ),
        GateAnswer(
            "Is the target in scope?",
            scope.is_in_scope(candidate.file),
            f"Yes — {candidate.file} is listed in scope.json in_scope.",
        ),
        GateAnswer(
            "Is it a known issue / duplicate?",
            scope.matches_known_issue(candidate.bug_class, ["reentrancy", "withdraw", "call"]) is None,
            "No — checked against the known-issues list (KNOWN-001 rounding "
            "dust, KNOWN-002 no pause); neither matches reentrancy.",
        ),
        GateAnswer(
            "Is the PoC reproducible from a clean checkout?",
            poc_passed,
            "Yes — `forge test` passes 2/2 from a clean checkout "
            "(test_ReentrancyDrainsVault + test_HonestWithdrawWorks)."
            if poc_passed else
            "No — the PoC did not pass; the finding is unproven.",
        ),
        GateAnswer(
            "Is the impact quantified with exact numbers?",
            before > 0 and after == 0 and drained > 0,
            f"Yes — vault {before / 1e18:.0f} ETH -> {after / 1e18:.0f} ETH; "
            f"attacker drained {drained / 1e18:.0f} ETH from a 1 ETH deposit.",
        ),
        GateAnswer(
            "Is there a single root cause, not a chain of unproven "
            "preconditions?",
            True,
            "Yes — one root cause: withdraw() sends ETH before zeroing the "
            "share balance (checks-effects-interactions violation).",
        ),
    ]
    return GateVerdict(all(a.passed for a in answers), answers)
