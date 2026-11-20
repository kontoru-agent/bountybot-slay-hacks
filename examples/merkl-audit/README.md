# Merkl audit — real field work by the Bountybot pipeline

This is the actual Foundry proof-of-concept suite from Bountybot's audit of
the Merkl bug bounty program (docs.merkl.xyz/bug-bounty, rewards up to
$100,000), run 20 Nov 2026. It is included as field evidence that the same
hunt → verify → report pipeline in this repo works on real, production
contracts — not only on the bundled demo vault.

## Result: 5/5 PASS

```
[PASS] test_OverrideEarlyEndAndReallocate()          (candidate #1, Critical-conditional)
[PASS] test_BatchGriefingRevertingOnClaim()           (candidate #2, Low)
[PASS] test_WrapperTransferDeliveryAndBurn()          (behavioural, no finding)
[PASS] test_WrapperBurnRevertsWhenFeeRecipientZero()  (edge case, NOT live)
[PASS] test_CampaignIdCollisionCreatorVictim()        (known V12 #5, do NOT report)
```

## Candidate #1 (the important one)

A campaign creator can early-end a LIVE campaign via `overrideCampaign`
(the post-audit code removed the end-date-in-future check, and the minimum
duration dropped from 1 hour to 1 second) and then redirect any address's
unclaimed rewards via `reallocateCampaignRewards`. On-chain, the PoC proves
the mappings are set. Whether it is Critical depends on the off-chain Merkl
engine honouring the override — a live engine test with the team's own funds
was running at the time of writing (reallocation confirmed on-chain
20 Nov 2026 04:26 WIB; engine verdict pending). The finding is reported here
as what it is: a proven on-chain primitive with a clearly-labelled open
question, not as a confirmed Critical. That honesty is the point of the gate.

## How to run it

This file alone is not runnable — it tests the real Merkl contracts. To
reproduce:

```bash
git clone https://github.com/AngleProtocol/merkl-contracts
# set up a Foundry project with remappings:
#   merkl/=../merkl-contracts/contracts/
#   @openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/
#   forge-std/=lib/forge-std/src/
forge test -vv   # solc 0.8.19, OZ v4.9.6, forge-std v1.9.0
```

All funds in the PoC are mock ERC20 minted in-test; all actors are test
addresses. No mainnet, no live chain, no user funds. The full audit notes
(including the dedupe against the Zellic V12 audit and the C4 2025 audit)
are in `docs/FIELD_RESULTS.md`.
