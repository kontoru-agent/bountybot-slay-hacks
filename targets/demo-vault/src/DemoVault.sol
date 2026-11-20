// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title DemoVault — INTENTIONALLY VULNERABLE demo target for Bountybot.
/// @notice This contract is a teaching/demo target with a PLANTED reentrancy bug.
///          DO NOT deploy it with real funds. It exists so Bountybot can
///          demonstrate its full hunt -> verify -> report loop on a real,
///          provable bug, with no network and no API keys.
/// @dev The bug: withdraw() sends ETH via a low-level call BEFORE zeroing the
///      caller's share balance (checks-effects-interactions violation). A
///      malicious receiver re-enters withdraw() on every ETH receipt and
///      drains the vault, because the share balance is still untouched
///      while the nested calls run.
contract DemoVault {
    mapping(address => uint256) public shares;
    uint256 public totalShares;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    /// @notice Deposit ETH, receive 1:1 shares.
    function deposit() external payable {
        require(msg.value > 0, "zero deposit");
        shares[msg.sender] += msg.value;
        totalShares += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    /// @notice Withdraw your full share balance as ETH.
    /// @dev BUG (planted): the external call happens BEFORE the state update.
    ///      The share balance is only zeroed after the ETH has been sent, so a
    ///      receiver contract can re-enter this function and withdraw again
    ///      and again against the same un-updated balance.
    function withdraw() external {
        uint256 amount = shares[msg.sender];
        require(amount > 0, "no shares");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "ETH transfer failed");
        shares[msg.sender] = 0;
        totalShares -= amount;
        emit Withdrawn(msg.sender, amount);
    }

    /// @notice ETH currently held by the vault.
    function balance() external view returns (uint256) {
        return address(this).balance;
    }
}
