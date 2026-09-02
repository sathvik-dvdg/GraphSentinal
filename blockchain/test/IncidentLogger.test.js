// blockchain/test/IncidentLogger.test.js  [Windows]
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("IncidentLogger", function () {
  let contract;
  let owner;

  beforeEach(async function () {
    [owner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("IncidentLogger");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  // TEST 1: Basic log
  it("should log an incident and return ID=1", async function () {
    const tx = await contract.logIncident(
      "10.0.0.2",
      "DDoS",
      9,
      false,
      "local://incident/1",
    );
    await tx.wait();
    expect(await contract.getIncidentCount()).to.equal(1n);
  });

  // TEST 2: Severity bounds
  it("should reject severity 0 and 11", async function () {
    await expect(
      contract.logIncident("10.0.0.2", "DDoS", 0, false, "local://incident/2"),
    ).to.be.revertedWith("Severity: 1-10 only");
    await expect(
      contract.logIncident("10.0.0.2", "DDoS", 11, false, "local://incident/3"),
    ).to.be.revertedWith("Severity: 1-10 only");
  });

  // TEST 3: Blocking
  it("should set blockedIPs when isBlocked=true", async function () {
    await contract.logIncident(
      "10.0.0.5",
      "SSHBrute",
      8,
      true,
      "local://incident/4",
    );
    expect(await contract.isIPBlocked("10.0.0.5")).to.equal(true);
    expect(await contract.isIPBlocked("10.0.0.1")).to.equal(false);
  });

  // TEST 4: Events
  it("should emit IncidentLogged and NodeIsolated events", async function () {
    await expect(
      contract.logIncident("10.0.0.8", "Botnet", 6, true, "local://incident/5"),
    )
      .to.emit(contract, "IncidentLogged")
      .to.emit(contract, "NodeIsolated");
  });

  // TEST 5: TAMPER-PROOF DEMO — the key viva proof
  it("should detect tampered data via hash mismatch", async function () {
    await contract.logIncident(
      "10.0.0.2",
      "DDoS",
      9,
      false,
      "local://incident/6",
    );
    const incident = await contract.getIncident(1n);

    // Verify with correct data → true
    const isValid = await contract.verifyIncident(
      1n,
      "10.0.0.2",
      "DDoS",
      9,
      incident.timestamp,
    );
    expect(isValid).to.equal(true);

    // Verify with TAMPERED data (changed attackLabel) → false
    const isTampered = await contract.verifyIncident(
      1n,
      "10.0.0.2",
      "PortScan",
      9,
      incident.timestamp,
    );
    expect(isTampered).to.equal(false);
    // ↑ THIS IS YOUR VIVA DEMO PROOF POINT
  });

  // TEST 6: Unblock
  it("should release a blocked IP", async function () {
    await contract.logIncident(
      "10.0.0.3",
      "PortScan",
      7,
      true,
      "local://incident/7",
    );
    expect(await contract.isIPBlocked("10.0.0.3")).to.equal(true);
    await contract.releaseNode("10.0.0.3", "MANUAL_OVERRIDE");
    expect(await contract.isIPBlocked("10.0.0.3")).to.equal(false);
  });

  // ─── N-02 Authorization Tests (Phase N) ──────────────────────────

  // AUTH TEST 1: deployer can logIncident
  it("[N02] deployer can call logIncident", async function () {
    const [deployer] = await ethers.getSigners();
    const tx = await contract.connect(deployer).logIncident(
      "192.168.1.1",
      "SQLInjection",
      7,
      false,
      "local://incident/auth1",
    );
    await tx.wait();
    expect(await contract.getIncidentCount()).to.equal(1n);
  });

  // AUTH TEST 2: non-deployer is REJECTED by logIncident
  it("[N02] non-deployer is rejected by logIncident", async function () {
    const [, attacker] = await ethers.getSigners();
    await expect(
      contract.connect(attacker).logIncident(
        "192.168.1.2",
        "XSS",
        5,
        false,
        "local://incident/auth2",
      ),
    ).to.be.revertedWith("Unauthorized");
  });

  // AUTH TEST 3: deployer can releaseNode
  it("[N02] deployer can call releaseNode", async function () {
    const [deployer] = await ethers.getSigners();
    // First block an IP via logIncident
    await contract.connect(deployer).logIncident(
      "10.10.10.10",
      "BruteForce",
      8,
      true,
      "local://incident/auth3",
    );
    expect(await contract.isIPBlocked("10.10.10.10")).to.equal(true);
    // Deployer releases it
    await contract.connect(deployer).releaseNode("10.10.10.10", "CLEARED");
    expect(await contract.isIPBlocked("10.10.10.10")).to.equal(false);
  });

  // AUTH TEST 4: non-deployer is REJECTED by releaseNode
  it("[N02] non-deployer is rejected by releaseNode", async function () {
    const [deployer, attacker] = await ethers.getSigners();
    // Block an IP first (as deployer)
    await contract.connect(deployer).logIncident(
      "10.10.10.20",
      "RansomwareC2",
      10,
      true,
      "local://incident/auth4",
    );
    expect(await contract.isIPBlocked("10.10.10.20")).to.equal(true);
    // Attacker tries to release — must revert
    await expect(
      contract.connect(attacker).releaseNode("10.10.10.20", "ATTACKER_RELEASE"),
    ).to.be.revertedWith("Unauthorized");
    // IP must still be blocked
    expect(await contract.isIPBlocked("10.10.10.20")).to.equal(true);
  });
});
