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
});
