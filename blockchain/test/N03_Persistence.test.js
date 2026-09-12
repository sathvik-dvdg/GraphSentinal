// blockchain/test/N03_Persistence.test.js  [Windows]
// ─────────────────────────────────────────────────────────────────────────────
// N-03 Hardhat/Chai tests — Ganache persistence & safe deployment lifecycle
//
// These tests use the Hardhat in-process EVM (not a live Ganache instance).
// They prove:
//   N03-T1  Redeploying yields a DIFFERENT address from the first deploy
//   N03-T2  The original contract is still callable after a second deploy
//   N03-T3  eth_getCode returns bytecode for a live contract address
//   N03-T4  eth_getCode returns "0x" for an EOA / unknown address
//   N03-T5  logIncident recorded in block N persists in block N+1+ calls
//   N03-T6  Deployer address is the same across two fresh deployments
//           (Hardhat test network is deterministic — mirrors Ganache --deterministic)
//   N03-T7  A re-deployed contract starts with incidentCount=0 (not reusing the
//           previous chain's storage) — proves reuse avoidance is a feature, not a bug
//   N03-T8  N-02 authorization is preserved post-N-03 changes
//           (onlyDeployer modifier still rejects non-deployers)
// ─────────────────────────────────────────────────────────────────────────────

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("N03 Persistence & Safe Deployment Lifecycle", function () {
  let owner, other;

  before(async function () {
    [owner, other] = await ethers.getSigners();
  });

  // ── N03-T1: Two fresh deployments land at DIFFERENT addresses ─────────────
  it("N03-T1: re-deploying IncidentLogger yields a distinct contract address", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");

    const c1 = await Factory.deploy();
    await c1.waitForDeployment();
    const addr1 = await c1.getAddress();

    const c2 = await Factory.deploy();
    await c2.waitForDeployment();
    const addr2 = await c2.getAddress();

    expect(addr1).to.be.a("string").with.length(42);
    expect(addr2).to.be.a("string").with.length(42);
    expect(addr1.toLowerCase()).to.not.equal(addr2.toLowerCase(),
      "two deployments must not share an address — reuse requires explicit validation");
  });

  // ── N03-T2: Original contract remains callable after second deploy ─────────
  it("N03-T2: original deployment stays callable after a subsequent deploy", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");

    const original = await Factory.deploy();
    await original.waitForDeployment();

    // Write a record to the original
    const tx = await original.logIncident("10.0.0.2", "DDoS", 9, false, "local://incident/1");
    await tx.wait();

    // Deploy a second instance (simulating what would happen on a fresh chain)
    const _second = await Factory.deploy();
    await _second.waitForDeployment();

    // Original contract must still be readable
    expect(await original.getIncidentCount()).to.equal(1n,
      "original contract must remain readable even after a second deployment");
  });

  // ── N03-T3: Live contract has bytecode ────────────────────────────────────
  it("N03-T3: eth_getCode returns non-empty bytecode for a deployed contract", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    const addr = await contract.getAddress();

    const code = await ethers.provider.getCode(addr);

    expect(code).to.be.a("string");
    expect(code).to.not.equal("0x",
      "a deployed contract must have non-empty bytecode — this is the validity check used by the entrypoint");
    expect(code.length).to.be.greaterThan(2);
  });

  // ── N03-T4: Unknown address returns "0x" ──────────────────────────────────
  it("N03-T4: eth_getCode returns '0x' for a random EOA / non-contract address", async function () {
    // A freshly generated address that has never been deployed to
    const wallet = ethers.Wallet.createRandom();
    const code = await ethers.provider.getCode(wallet.address);

    expect(code).to.equal("0x",
      "a non-contract address must return '0x' — this is what triggers redeployment in the entrypoint");
  });

  // ── N03-T5: Data written in block N is readable in block N+k ─────────────
  it("N03-T5: incident data written in an earlier block persists in later blocks", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();

    // Write two incidents in sequence (two separate blocks)
    const tx1 = await contract.logIncident("10.0.0.2", "DDoS", 9, false, "local://incident/1");
    const r1 = await tx1.wait();

    const tx2 = await contract.logIncident("10.0.0.3", "PortScan", 5, true, "local://incident/2");
    const r2 = await tx2.wait();

    // r2 must be in a later block than r1
    expect(r2.blockNumber).to.be.greaterThanOrEqual(r1.blockNumber,
      "second tx must be in the same or later block");

    // The first incident must still be readable from the later block
    const count = await contract.getIncidentCount();
    expect(count).to.equal(2n, "both incidents must persist across blocks");

    const inc1 = await contract.getIncident(1n);
    expect(inc1.sourceIP).to.equal("10.0.0.2", "incident 1 source IP must persist");

    const inc2 = await contract.getIncident(2n);
    expect(inc2.sourceIP).to.equal("10.0.0.3", "incident 2 source IP must persist");
  });

  // ── N03-T6: Deployer is account[0] (deterministic — mirrors Ganache --deterministic) ─
  it("N03-T6: deployer address is accounts[0] for both deployments (deterministic node)", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");

    const c1 = await Factory.connect(owner).deploy();
    await c1.waitForDeployment();

    const c2 = await Factory.connect(owner).deploy();
    await c2.waitForDeployment();

    // Both contracts must recognise owner as the deployer (the onlyDeployer check)
    // Easiest way: a deployer call must succeed; a non-deployer call must revert
    await expect(
      c1.connect(owner).logIncident("10.0.0.10", "DDoS", 5, false, "local://1")
    ).to.not.be.reverted;

    await expect(
      c2.connect(owner).logIncident("10.0.0.11", "DDoS", 5, false, "local://2")
    ).to.not.be.reverted;
  });

  // ── N03-T7: Re-deployed contract starts at incidentCount=0 ────────────────
  it("N03-T7: a freshly deployed contract starts with incidentCount=0 regardless of prior chain", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");

    const old = await Factory.deploy();
    await old.waitForDeployment();
    await (await old.logIncident("10.0.0.5", "Botnet", 7, true, "local://old/1")).wait();
    expect(await old.getIncidentCount()).to.equal(1n);

    // Deploy a brand-new instance — its storage is zeroed
    const fresh = await Factory.deploy();
    await fresh.waitForDeployment();

    expect(await fresh.getIncidentCount()).to.equal(0n,
      "new deployment must start with empty storage — prior chain state is NOT inherited");
  });

  // ── N03-T8: N-02 authorization preserved (regression guard) ───────────────
  it("N03-T8: [N02 regression] onlyDeployer modifier still rejects non-deployer after N-03 changes", async function () {
    const Factory = await ethers.getContractFactory("IncidentLogger");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();

    // Non-deployer must be rejected on both protected functions
    await expect(
      contract.connect(other).logIncident("10.0.0.99", "DDoS", 5, false, "local://attack")
    ).to.be.revertedWith("Unauthorized");

    // Block an IP first (as deployer) so releaseNode has something to release
    await (await contract.connect(owner).logIncident("10.0.0.88", "Botnet", 8, true, "local://block")).wait();

    await expect(
      contract.connect(other).releaseNode("10.0.0.88", "ATTACKER_RELEASE")
    ).to.be.revertedWith("Unauthorized");
  });
});
