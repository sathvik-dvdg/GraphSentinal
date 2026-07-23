// blockchain/scripts/deploy.js  [Windows]
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("\n═══════════════════════════════════════════════");
  console.log("  GraphSentinel — IncidentLogger Deployment");
  console.log("═══════════════════════════════════════════════");

  // Get deployer account (Ganache account[0])
  const [deployer] = await ethers.getSigners();
  console.log(`Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);

  // Deploy contract
  console.log("\nDeploying IncidentLogger...");
  const Factory = await ethers.getContractFactory("IncidentLogger");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`✅ Deployed at: ${address}`);

  // Verify contract responds
  const count = await contract.getIncidentCount();
  console.log(`✅ Contract live — incidentCount: ${count}`);

  // ── Export ABI ────────────────────────────────────────────────
  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/IncidentLogger.sol/IncidentLogger.json",
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

  const abiDest = path.join(__dirname, "../web3_bridge/contract_abi.json");
  fs.writeFileSync(abiDest, JSON.stringify(artifact.abi, null, 2));
  console.log(`✅ ABI exported → web3_bridge/contract_abi.json`);

  // ── Write .env files ──────────────────────────────────────────
  const blockchainEnv = `CONTRACT_ADDRESS=${address}\nGANACHE_URL=http://127.0.0.1:8545\n`;
  fs.writeFileSync(path.join(__dirname, "../.env"), blockchainEnv);
  console.log(`✅ blockchain/.env written`);

  // Append to backend .env (for Sairaj)
  const backendEnvPath = path.join(__dirname, "../../backend/.env");
  const backendEnvEntry = `\n# ─── Blockchain (from Skanda's deploy) ───\nCONTRACT_ADDRESS=${address}\n`;

  if (fs.existsSync(backendEnvPath)) {
    // Remove old CONTRACT_ADDRESS line if exists
    let existing = fs.readFileSync(backendEnvPath, "utf8");
    existing = existing
      .replace(/CONTRACT_ADDRESS=.*/g, "");
    fs.writeFileSync(backendEnvPath, existing + backendEnvEntry);
  } else {
    // If backend folder doesn't exist yet, we just create the .env file anyway so Sairaj has it later
    fs.mkdirSync(path.join(__dirname, "../../backend"), { recursive: true });
    fs.writeFileSync(backendEnvPath, backendEnvEntry);
  }
  console.log(`✅ backend/.env updated with CONTRACT_ADDRESS`);

  console.log("\n═══════════════════════════════════════════════");
  console.log("  SHARE WITH SAIRAJ:");
  console.log(`  CONTRACT_ADDRESS = ${address}`);
  console.log("  (already written to backend/.env)");
  console.log("═══════════════════════════════════════════════\n");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
