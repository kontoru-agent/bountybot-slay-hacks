# Bountybot — architecture

```
                    ┌─────────────┐
   scope.json ─────▶│    SCOUT    │  program, in-scope files,
                    │  scope.py   │  known issues, reward tiers
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
   DemoVault.sol ──▶│    HUNT     │  10 DeFi bug classes, static
                    │  hunter.py  │  patterns; 1 candidate, 9 clean
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
   PoC result ─────▶│    GATE     │  7 questions; first wrong answer
                    │  gate.py    │  kills the finding
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
   forge test ─────▶│   VERIFY    │  Foundry PoC must reproduce the
                    │  verify.py  │  impact (Python fallback if no forge)
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   REPORT    │  submission-grade markdown:
                    │  report.py  │  impact, repro, root cause, fix
                    └─────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │ IDENTITY — Agent ID (bountybot/agentid.py)                    │
   │ Every submission is gated on a Binance Agent ID (on-chain     │
   │ registry on BNB Chain). No Agent ID = no registration,        │
   │ no submission, no payout. Read-only eth_call; no keys.        │
   └──────────────────────────────────────────────────────────────┘
```

## The 10 bug classes (`bountybot/hunter.py`)

| Class | What the check looks for |
|---|---|
| REENTRANCY | external call before a state write in the same function |
| ACCESS_CONTROL | admin-looking fund-moving function without a modifier |
| ACCOUNTING_DESYNC | shares[] updated without totalShares (or vice versa) |
| ORACLE | time/price feed used in fund math |
| UNCHECKED_CALL | low-level call whose return value is not checked |
| INTEGER_OVERFLOW | pragma predating Solidity 0.8 checked arithmetic |
| SIGNATURE_REPLAY | ecrecover used with no nonce |
| PROXY | delegatecall / upgrade path |
| FLASH_LOAN | flash-loan entry point |
| ERC4626_SHARE_MANIPULATION | share-price math sensitive to donation/inflation |

Every check runs and reports. A check that finds nothing says so with a
reason — silence is not evidence.

## The 7-question gate (`bountybot/gate.py`)

1. Can an attacker do this right now against a real user who took no unusual action?
2. Does it cause real harm (stolen money, leaked PII, account takeover, code execution)?
3. Is the target in scope?
4. Is it a known issue / duplicate?
5. Is the PoC reproducible from a clean checkout?
6. Is the impact quantified with exact numbers?
7. Is there a single root cause, not a chain of unproven preconditions?

All seven must pass. The gate runs AFTER the PoC, because question 5 needs
the PoC result.

## Verification (`bountybot/verify.py`)

Primary oracle: `forge test` on the target's Foundry project — real EVM,
real numbers. Fallback: a Python simulation of the exact same vault
semantics, used only when forge is not installed, and labelled as such in
the output. Both oracles must agree on the numbers.

## The human in the loop

Bountybot drafts reports; it never files them. Filing, submitting, and any
payment are human decisions. That is a design choice, not a missing feature:
first valid report wins, but a wrong report burns the researcher's reputation
with the program.

## The LLM layer (honest description)

The hunting agent itself runs on Muse (Meta's agent) with a skill-encoded
methodology (`agentic-bug-hunter`: five phases, the 7-question gate, the 10
DeFi classes, the Foundry PoC template, report writing). The LLM does the
recon and the hunting reasoning; the PoC execution and the gate are
deterministic and must pass before any report is drafted. This repo is the
deterministic core of that system — it runs with no API key, no network,
and no paid service.
