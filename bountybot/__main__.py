"""Bountybot CLI — run the full hunt loop against a target.

    python3 -m bountybot hunt --target targets/demo-vault [--out reports]

Phases: scout -> hunt -> gate -> verify -> report. The run stops at the
first phase that fails to produce evidence: a candidate that fails the gate
is dropped, and a candidate whose PoC does not pass is never reported.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from . import agentid, gate, hunter, report, scope, verify


def _ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _fail(msg: str) -> None:
    print(f"  [!!] {msg}")


def cmd_hunt(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    target = Path(args.target)
    scope_path = target / "scope.json"
    if not scope_path.exists():
        print(f"[bountybot] no scope.json in {target}")
        return 1

    print(f"[bountybot] v{__version__} — target: {target}")
    print(f"[bountybot] rule: no runnable PoC means no report")
    print()

    # ---- scout ------------------------------------------------------------
    print("[scout] loading program scope ...")
    prog = scope.Scope.load(scope_path)
    print(f"[scout] program: {prog.program} v{prog.version}")
    print(f"[scout] in scope: {', '.join(prog.in_scope)}")
    print(f"[scout] known issues on file: {len(prog.known_issues)} "
          f"({', '.join(i.id for i in prog.known_issues)})")
    print(f"[scout] reward tiers: "
          + ", ".join(f"{k} ${v:,}" for k, v in prog.reward_tiers.items()))
    print()

    # ---- hunt -------------------------------------------------------------
    print("[hunt] scanning 10 DeFi bug classes ...")
    sol_files = sorted(
        p for p in target.rglob("*.sol")
        if p.is_file() and not (set(p.parts) & {"lib", "test", "out", "cache"})
    )
    all_results: list[hunter.CheckResult] = []
    for sol in sol_files:
        rel = str(sol.relative_to(target))
        all_results.extend(hunter.scan_file(sol, rel))
    findings = [c for r in all_results for c in r.candidates]
    clean = [r for r in all_results if r.status == "clean"]
    for r in all_results:
        if r.status == "finding":
            for c in r.candidates:
                print(f"[hunt] {c.bug_class} ({c.severity}): {c.file}:{c.line} "
                      f"in {c.function}()")
                print(f"[hunt]   {c.detail}")
        else:
            print(f"[hunt] {r.bug_class}: clean — {r.detail}")
    print(f"[hunt] {len(findings)} candidate(s), {len(clean)} class(es) clean")
    print()
    if not findings:
        print("[bountybot] no candidates — nothing to verify, nothing to report.")
        return 1

    # ---- verify (before the gate: the gate needs the PoC result) -----------
    print("[verify] running the proof of concept ...")
    try:
        proof = verify.verify(target)
    except Exception as exc:  # noqa: BLE001 — a failed PoC is a failed finding
        print(f"[verify] PoC runner failed: {exc}")
        return 1
    print(f"[verify] method: {proof.method} — {proof.tests_passed} passed, "
          f"{proof.tests_failed} failed")
    print(f"[verify] vault {proof.vault_before_wei / 1e18:.0f} ETH -> "
          f"{proof.vault_after_wei / 1e18:.0f} ETH; attacker drained "
          f"{proof.attacker_drained_wei / 1e18:.0f} ETH from a 1 ETH deposit")
    if not proof.passed:
        _fail("PoC did not pass — the candidate is unproven, dropping it.")
        return 1
    _ok("PoC reproduces the impact from a clean checkout")
    print()

    # ---- gate -------------------------------------------------------------
    print("[gate] 7-question triage ...")
    verdict = gate.run_gate(findings[0], prog, proof.passed, proof.impact)
    for a in verdict.answers:
        mark = "PASS" if a.passed else "FAIL"
        print(f"[gate] [{mark}] {a.question}")
        print(f"[gate]        {a.evidence}")
    print(f"[gate] verdict: {verdict.score} {'PASS' if verdict.passed else 'FAIL'}")
    print()
    if not verdict.passed:
        _fail("gate failed — the candidate is dropped, no report is written.")
        return 1

    # ---- report -----------------------------------------------------------
    print("[report] drafting the submission-grade report ...")
    path = report.write_report(findings[0], prog, verdict, proof, args.out)
    print(f"[report] wrote {path} (tier {findings[0].severity})")
    print()

    # ---- optional identity check ------------------------------------------
    if args.check_agent_id:
        name, _, wallet = args.check_agent_id.partition(":")
        print("[agentid] verifying hunter identity (read-only eth_call) ...")
        ok, msg = agentid.verify_hunter(name, wallet)
        print(f"[agentid] {'verified' if ok else 'NOT verified'}: {msg}")
        print()

    dt = time.monotonic() - t0
    print(f"[bountybot] DONE in {dt:.1f}s — 1 finding, 1 verified, 1 report drafted")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bountybot",
        description="AI agent that hunts Web3 bug bounties: scout, hunt, "
                    "gate, verify with a runnable PoC, report.",
    )
    ap.add_argument("--version", action="version", version=f"bountybot {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hunt", help="run the full loop against a target")
    h.add_argument("--target", required=True,
                   help="target dir containing scope.json + src/ + test/")
    h.add_argument("--out", default="reports",
                   help="where to write the draft report (default: reports)")
    h.add_argument("--check-agent-id", metavar="NAME:WALLET",
                   help="optional: verify an Agent ID hunter (read-only)")
    h.set_defaults(func=cmd_hunt)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
