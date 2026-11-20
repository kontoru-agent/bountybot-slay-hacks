"""Bountybot — an AI agent that hunts Web3 bug bounties end to end.

Pipeline: scout (scope) -> hunt (static scan) -> gate (7-question triage)
-> verify (runnable PoC) -> report (submission-grade draft).

Rule of the agent: no runnable PoC means no report. A claim without proof
is a hypothesis, not a finding.
"""

__version__ = "0.1.0"
__all__ = ["scope", "hunter", "gate", "verify", "report", "agentid"]
