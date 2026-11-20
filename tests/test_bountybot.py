import unittest

from bountybot import gate, hunter, scope, verify


class TestScope(unittest.TestCase):
    def test_demo_scope_loads(self):
        s = scope.Scope.load("targets/demo-vault/scope.json")
        self.assertEqual(s.program, "DemoVault (Bountybot demo target)")
        self.assertTrue(s.is_in_scope("src/DemoVault.sol"))
        self.assertFalse(s.is_in_scope("lib/forge-std/src/Test.sol"))
        self.assertEqual(len(s.known_issues), 2)

    def test_known_issue_match(self):
        s = scope.Scope.load("targets/demo-vault/scope.json")
        self.assertIsNotNone(s.matches_known_issue(
            "rounding dust on deposit", ["rounding", "dust"]))
        self.assertIsNone(s.matches_known_issue(
            "reentrancy in withdraw", ["reentrancy", "withdraw"]))


class TestHunter(unittest.TestCase):
    def test_reentrancy_found_in_demo_vault(self):
        results = hunter.scan_file("targets/demo-vault/src/DemoVault.sol",
                                   "src/DemoVault.sol")
        by_class = {r.bug_class: r for r in results}
        self.assertEqual(by_class["REENTRANCY"].status, "finding")
        self.assertEqual(len(by_class["REENTRANCY"].candidates), 1)
        cand = by_class["REENTRANCY"].candidates[0]
        self.assertEqual(cand.function, "withdraw")
        self.assertEqual(cand.severity, "Critical")

    def test_other_nine_classes_clean(self):
        results = hunter.scan_file("targets/demo-vault/src/DemoVault.sol",
                                   "src/DemoVault.sol")
        clean = [r for r in results if r.status == "clean"]
        self.assertEqual(len(clean), 9)

    def test_clean_contract_passes_all(self):
        src = (
            "// SPDX-License-Identifier: MIT\n"
            "pragma solidity ^0.8.19;\n"
            "contract Safe {\n"
            "    mapping(address => uint256) public shares;\n"
            "    uint256 public totalShares;\n"
            "    function deposit() external payable {\n"
            "        shares[msg.sender] += msg.value;\n"
            "        totalShares += msg.value;\n"
            "    }\n"
            "    function withdraw() external {\n"
            "        uint256 amount = shares[msg.sender];\n"
            "        require(amount > 0, \"no shares\");\n"
            "        shares[msg.sender] = 0;\n"
            "        totalShares -= amount;\n"
            "        (bool ok, ) = msg.sender.call{value: amount}(\"\");\n"
            "        require(ok, \"fail\");\n"
            "    }\n"
            "}\n"
        )
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Safe.sol"
            p.write_text(src)
            results = hunter.scan_file(p, "Safe.sol")
        by_class = {r.bug_class: r for r in results}
        self.assertEqual(by_class["REENTRANCY"].status, "clean")


class TestVerifySimulation(unittest.TestCase):
    def test_python_simulation_reproduces_drain(self):
        res = verify.run_python_simulation()
        self.assertTrue(res.passed)
        self.assertEqual(res.vault_before_wei, 100 * 10 ** 18)
        self.assertEqual(res.vault_after_wei, 0)
        self.assertEqual(res.attacker_drained_wei, 101 * 10 ** 18)


class TestGate(unittest.TestCase):
    def test_gate_passes_with_proven_impact(self):
        s = scope.Scope.load("targets/demo-vault/scope.json")
        results = hunter.scan_file("targets/demo-vault/src/DemoVault.sol",
                                   "src/DemoVault.sol")
        cand = [c for r in results for c in r.candidates][0]
        proof = verify.run_python_simulation()
        verdict = gate.run_gate(cand, s, proof.passed, proof.impact)
        self.assertTrue(verdict.passed)
        self.assertEqual(verdict.score, "7/7")

    def test_gate_fails_without_poc(self):
        s = scope.Scope.load("targets/demo-vault/scope.json")
        results = hunter.scan_file("targets/demo-vault/src/DemoVault.sol",
                                   "src/DemoVault.sol")
        cand = [c for r in results for c in r.candidates][0]
        proof = verify.run_python_simulation()
        verdict = gate.run_gate(cand, s, False, proof.impact)
        self.assertFalse(verdict.passed)


if __name__ == "__main__":
    unittest.main()
