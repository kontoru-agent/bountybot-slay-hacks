# Bountybot — field results (verified state, 20 Nov 2026)

These are the real programs the Bountybot pipeline has worked. A submission
is not a win and a triaging report is not money — the numbers below are
exactly what they are, nothing more.

## XE Network (bounty.xe.network) — 39 reports filed

| Status (verified 20 Nov 2026 07:48 WIB) | Count |
|---|---|
| CLOSED · DUPLICATE | 36 |
| TRIAGING | 2 (XE-10715, XE-6235) |
| NEW | 1 (XE-18940) |

- **XE-18940** (filed 19 Nov 2026, claimed High, status NEW): block ingest
  loads the sender's full account chain 3× per block — unauthenticated
  O(chain-length) CPU/IO amplification on every node. PoC reproduced in
  0.386s from a clean run.
- Original 38 reports: 2 Critical + 7 High + 16 Medium + 14 Minor by tier;
  32 closed as duplicates on 16 Nov, 4 more on 20 Nov.
- Awards on all 39: "—". No payout received. Scoreboard: $0.

## Merkl (docs.merkl.xyz/bug-bounty, up to $100,000) — audit complete

- Scope: `DistributionCreator` + `Distributor` + 11 non-deprecated token
  wrappers (AngleProtocol/merkl-contracts, main HEAD).
- Dedupe first: C4 2025-11 + Zellic V12 (32 findings) read before hunting;
  known issues (V12 #5 campaignId collision, `tx.origin` in `_claim`) were
  confirmed present and NOT re-reported.
- **5/5 Foundry PoCs pass** (`examples/merkl-audit/MerklAudit.t.sol`).
- Candidate #1: `overrideCampaign` → 1s duration → `reallocateCampaignRewards`
  — on-chain PROVEN. Critical ONLY IF the live engine honours the override.
  Live engine test with the team's own funds: campaign live 20 Nov 03:11 WIB,
  reallocation confirmed on-chain 04:26 WIB, engine verdict pending
  (~16:30 WIB 20 Nov). Reported here as a proven primitive with an open
  question, not as a confirmed Critical.
- Candidate #2: batch claim griefing via reverting `onClaim` — Low, likely
  intended behaviour (the try/catch removal was the C4 M-02 fix itself).
- Submission rule for this program: the team lead (ONAR) submits, never the agent.

## Meta Muse (Meta bug bounty) — submitted 16 Nov 2026

- C1 #2195250948060421 (Category 1), C2 #2195252281393621 (Category 6),
  P2 #2195253114726871 (Category 7). All status New. No payout.
  Withdrawal is not possible on that platform; standard-tier findings are
  held per the team's highest-only rule.

## BNB Chain — BountybotRegistry deployed

- Contract `0x32619eba3f351cb555355f6011c9e22782253867`, deployed 19 Nov 2026
  (block 134446887, tx `0xc62868d8…`). Sourcify exact match.
- Agent ID-gated bug-bounty registry: only Binance Agent ID holders can
  register as hunters, submit findings, and get paid; escrow pays out on
  accepted findings. Repo: github.com/kontoru-agent/bountybot-registry.
- The off-chain mirror of its gate lives in `bountybot/agentid.py`
  (read-only `eth_call`, no key, no signing).
