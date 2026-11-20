# Bountybot demo — script (what the video shows)

Video: `demo/bountybot-demo.mp4` — 1280×720, 24 fps, ~2m27s, silent with
captions. Rendered frame by frame from the real run log
(`demo/demo_run.log`) — no screen recorder, no staged output.

## Beats

| Time | Beat | What the viewer sees |
|---|---|---|
| 0:00–0:08 | Title | BOUNTYBOT — an AI agent that hunts Web3 bug bounties end to end. |
| 0:08–0:13 | Command | `$ python3 -m bountybot hunt --target targets/demo-vault` |
| 0:13–0:33 | 1 · SCOUT | Scope loads: program, 1 file in scope, 2 known issues, reward tiers. |
| 0:33–1:08 | 2 · HUNT | 10 classes scanned. REENTRANCY (Critical) fires at `withdraw()` line 37; the other 9 report clean with reasons. |
| 1:08–1:39 | 3 · VERIFY | `forge test` 2/2 PASS. Vault 100 ETH → 0 ETH; attacker drained 101 ETH from a 1 ETH deposit. |
| 1:39–2:14 | 4 · GATE | 7 questions, 7/7 PASS — real harm, in scope, not a duplicate, PoC reproducible, impact quantified, one root cause. |
| 2:14–2:26 | 5 · REPORT | Submission-grade draft written: `reports/demo-vault-reentrancy.md`. DONE in ~6s. |
| 2:26–2:46 | Field results | The same pipeline on real programs: XE (39 reports), Merkl (5/5 PoCs), Meta Muse, BNB Chain registry. |

## Screenshots

- `demo/screenshots/01-scout.png` — scope loaded
- `demo/screenshots/02-hunt.png` — the REENTRANCY candidate + 9 clean classes
- `demo/screenshots/03-verify.png` — forge 2/2 PASS, exact drain numbers
- `demo/screenshots/04-report.png` — gate 7/7 PASS, report written, DONE
- `demo/screenshots/05-architecture.png` — pipeline diagram

## Reproduce the run

```bash
python3 -m bountybot hunt --target targets/demo-vault --out reports
# expect: 1 candidate (REENTRANCY, Critical), forge 2/2 PASS,
# vault 100 ETH -> 0 ETH, attacker drained 101 ETH, gate 7/7 PASS,
# reports/demo-vault-reentrancy.md written, DONE in ~6s.
```
