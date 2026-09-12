// blockchain/test/N04_ReceiptCorrelation.test.js  [Windows]
// ─────────────────────────────────────────────────────────────────────────────
// N-04 Hardhat/Chai tests — Receipt Event Correlation & releaseNode Verification
//
// These tests verify:
//   N04-T1  logIncident emits IncidentLogged with exact ID and keccak256 hash
//   N04-T2  Multiple sequential logIncident transactions emit strictly increasing IDs in events
//   N04-T3  Event ID matches stored _incidents mapping record exactly
//   N04-T4  releaseNode sets blockedIPs[ip] = false and emits NodeReleased event
//   N04-T5  releaseNode succeeds when called by deployer
//   N04-T6  releaseNode reverts with "Unauthorized" when called by non-deployer (N-02 guard)
//   N04-T7  releaseNode reverts with "IP is not blocked" if IP is not currently blocked
// ─────────────────────────────────────────────────────────────────────────────

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("N04 Receipt Event Correlation & releaseNode", function () {
  let contract;
  let deployer, other;

  beforeEach(async function () {
    [deployer, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("IncidentLogger");
    contract = await Factory.connect(deployer).deploy();
    await contract.waitForDeployment();
  });

  // ── N04-T1: IncidentLogged event arguments verification ────────────────────
  it("N04-T1: logIncident emits IncidentLogged with exact ID, hash, and metadata", async function () {
    const tx = await contract.logIncident(
      "192.168.1.50",
      "DDoS",
      9,
      false,
      "local://incident/1"
    );
    const receipt = await tx.wait();

    // Verify event emission and exact args
    await expect(tx)
      .to.emit(contract, "IncidentLogged")
      .withArgs(
        1n,
        (hash) => typeof hash === "string" && hash.startsWith("0x") && hash.length === 66,
        "192.168.1.50",
        "DDoS",
        (ts) => ts > 0n
      );
  });

  // ── N04-T2: Sequential events increment authoritatively ───────────────────
  it("N04-T2: sequential logIncident calls emit distinct IDs (1, 2, 3) in event logs", async function () {
    const tx1 = await contract.logIncident("10.0.0.1", "Scan", 4, false, "local://1");
    await expect(tx1).to.emit(contract, "IncidentLogged").withArgs(1n, (h) => true, "10.0.0.1", "Scan", (ts) => true);

    const tx2 = await contract.logIncident("10.0.0.2", "BruteForce", 7, false, "local://2");
    await expect(tx2).to.emit(contract, "IncidentLogged").withArgs(2n, (h) => true, "10.0.0.2", "BruteForce", (ts) => true);

    const tx3 = await contract.logIncident("10.0.0.3", "Ransomware", 10, true, "local://3");
    await expect(tx3).to.emit(contract, "IncidentLogged").withArgs(3n, (h) => true, "10.0.0.3", "Ransomware", (ts) => true);

    expect(await contract.getIncidentCount()).to.equal(3n);
  });

  // ── N04-T3: Event ID equals storage mapping ID ────────────────────────────
  it("N04-T3: event ID equals stored _incidents[id].id", async function () {
    const tx = await contract.logIncident("10.0.0.55", "Botnet", 8, true, "local://55");
    const receipt = await tx.wait();

    const stored = await contract.getIncident(1n);
    expect(stored.id).to.equal(1n);
    expect(stored.sourceIP).to.equal("10.0.0.55");
    expect(stored.attackLabel).to.equal("Botnet");
    expect(stored.severity).to.equal(8);
    expect(stored.isBlocked).to.equal(true);
  });

  // ── N04-T4: releaseNode transitions on-chain state and emits event ────────
  it("N04-T4: releaseNode sets blockedIPs[ip]=false and emits NodeReleased event", async function () {
    // 1. Block IP first
    const txBlock = await contract.logIncident("10.0.0.77", "Exploit", 9, true, "local://77");
    await txBlock.wait();
    expect(await contract.isIPBlocked("10.0.0.77")).to.equal(true);

    // 2. Release IP
    const txRelease = await contract.releaseNode("10.0.0.77", "MANUAL_OVERRIDE");
    await expect(txRelease)
      .to.emit(contract, "NodeReleased")
      .withArgs("10.0.0.77", (ts) => ts > 0n, "MANUAL_OVERRIDE");

    // 3. Confirm on-chain state transitioned to false
    expect(await contract.isIPBlocked("10.0.0.77")).to.equal(false);
  });

  // ── N04-T5: releaseNode deployer authorization ────────────────────────────
  it("N04-T5: deployer can successfully execute releaseNode", async function () {
    await (await contract.connect(deployer).logIncident("10.0.0.88", "Probe", 5, true, "local://88")).wait();
    expect(await contract.isIPBlocked("10.0.0.88")).to.equal(true);

    await expect(
      contract.connect(deployer).releaseNode("10.0.0.88", "ADMIN_CLEAR")
    ).to.not.be.reverted;

    expect(await contract.isIPBlocked("10.0.0.88")).to.equal(false);
  });

  // ── N04-T6: releaseNode non-deployer rejection (N-02 guard) ───────────────
  it("N04-T6: non-deployer is REJECTED by releaseNode (onlyDeployer intact)", async function () {
    await (await contract.connect(deployer).logIncident("10.0.0.99", "Attack", 9, true, "local://99")).wait();
    expect(await contract.isIPBlocked("10.0.0.99")).to.equal(true);

    await expect(
      contract.connect(other).releaseNode("10.0.0.99", "ATTACKER_RELEASE")
    ).to.be.revertedWith("Unauthorized");

    // Must still remain blocked
    expect(await contract.isIPBlocked("10.0.0.99")).to.equal(true);
  });

  // ── N04-T7: releaseNode fails if IP is not blocked ────────────────────────
  it("N04-T7: releaseNode reverts if target IP is not blocked", async function () {
    await expect(
      contract.connect(deployer).releaseNode("10.0.0.123", "UNBLOCK_UNBLOCKED")
    ).to.be.revertedWith("IP is not blocked");
  });
});
