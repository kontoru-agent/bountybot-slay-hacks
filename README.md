# Bountybot — an AI agent that hunts Web3 bug bounties

**One command. One finding. Proven, or it never gets reported.**

```bash
python3 -m bountybot hunt --target targets/demo-vault
# scout → hunt → gate → verify → report — DONE in ~6s
# 1 finding (REENTRANCY, Critical) · forge 2/2 PASS
# vault 100 ETH → 0 ETH · attacker drained 101 ETH from a 1 ETH deposit
```

🎬 **Demo video:** `demo/bountybot-demo.mp4` (2m27s, captioned — see `docs/DEMO_SCRIPT.md`)
📸 **Screenshots:** `demo/screenshots/` (scout, hunt, verify, report, architecture)

## The problem

Bug bounties pay for real vulnerabilities, but most AI "hunters" are
pattern-matchers that flood programs with unproven claims. A claim without
proof wastes the program's time, burns the researcher's reputation, and earns
nothing — most programs pay only the first *valid* report. Meanwhile, real
bounty hunting is slow, manual work: read the scope, learn the code, find the
bug, prove it, write it up. Good hunters are rare; the programs are not.

## The solution

Bountybot is an AI agent that runs the whole hunt end to end — and refuses to
report anything it cannot prove:

1. **Scout** — reads the program scope first: in-scope files, known issues,
   reward tiers. Out-of-scope is not a finding.
2. **Hunt** — statically scans for 10 DeFi bug classes (reentrancy, access
   control, accounting desync, oracle, unchecked calls, integer overflow,
   signature replay, proxy, flash loans, ERC4626 share manipulation).
3. **Gate** — a 7-question triage: real harm right now? In scope? Not a
   duplicate? PoC reproducible? Impact quantified? One root cause? The first
   wrong answer kills the finding.
4. **Verify** — runs a Foundry PoC on the real EVM. No runnable PoC means no
   report. A claim without proof is a hypothesis, not a finding.
5. **Report** — drafts a submission-grade report: exact impact numbers,
   repro steps, root cause, suggested fix.

Every submission is gated on a **Binance Agent ID** — an on-chain registry on
BNB Chain (`BountybotRegistry`, deployed and Sourcify-verified) lets only
Agent ID holders register as hunters, submit findings, and get paid from
escrow. Identity is the trust layer, not a badge on the side.

## Quickstart

```bash
# Requirements: Python 3.12+ (stdlib only, no API keys, no network).
# Foundry (forge) is used for the PoC when installed; otherwise a Python
# simulation of the same vault semantics runs instead (labelled as such).
python3 -m bountybot hunt --target targets/demo-vault --out reports

# Unit tests (stdlib unittest, no network):
python3 -m unittest discover -s tests -v

# Foundry PoC on its own:
cd targets/demo-vault && forge test -vv
```

## What is in this repo

| Path | What it is |
|---|---|
| `bountybot/` | The agent core: `scope`, `hunter`, `gate`, `verify`, `report`, `agentid` |
| `targets/demo-vault/` | Bundled demo target: scope + a vault with a planted reentrancy bug + Foundry PoC |
| `examples/merkl-audit/` | Real field work: the 5/5-PASS Foundry PoC suite from Bountybot's Merkl audit |
| `docs/` | `ARCHITECTURE.md`, `FIELD_RESULTS.md`, `DEMO_SCRIPT.md` |
| `demo/` | Demo video, full run transcript, screenshots |
| `reports/` | Example output: the report the demo run drafts |
| `tests/` | Unit tests (8 tests, stdlib only) |

## Field results — the same pipeline on real programs

Full numbers in `docs/FIELD_RESULTS.md`. Headlines (verified state, 20 Nov 2026):

- **XE Network:** 39 reports filed. XE-18940 (High, NEW) — block ingest loads
  the sender's full account chain 3× per block; PoC reproduced in 0.386s.
- **Merkl (up to $100k):** full contract audit, 5/5 Foundry PoCs pass.
  Candidate #1 (override → 1s → reallocate) is on-chain proven; whether it is
  Critical depends on a live engine test in progress — reported honestly as a
  proven primitive with an open question.
- **Meta Muse:** Category 1/2/7 submissions, 16 Nov 2026.
- **BNB Chain:** `BountybotRegistry` deployed, Sourcify exact match.

A submission is not a win and a triaging report is not money. The numbers
above are exactly what they are, nothing more.

## Built with

- **Python 3.12, standard library only** — the deterministic agent core; no
  API keys, no paid services, runs fully offline on the demo target.
- **Solidity 0.8.19 + Foundry** — the PoC oracle (real EVM, real numbers).
- **Muse (Meta's agent)** with a skill-encoded hunting methodology — the LLM
  does recon and hunting reasoning; the PoC and the gate are deterministic
  and must pass before any report is drafted. See `docs/ARCHITECTURE.md`
  for the honest breakdown.

## License

MIT — see `LICENSE`.
