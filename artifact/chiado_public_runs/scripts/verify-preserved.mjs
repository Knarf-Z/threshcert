import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const results = path.join(root, "results");
const files = {
  canonical: "phase2_chiado.json",
  covered: "phase2_chiado_covered_run2.json",
  calibration: "phase2_chiado_underfunded_run1.json",
};
const expectedHashes = {
  canonical: "461f753b1a24dc6b023755a1efc6fc8871c9906ce3ea347c1f680ecad8222a6c",
  covered: "461f753b1a24dc6b023755a1efc6fc8871c9906ce3ea347c1f680ecad8222a6c",
  calibration: "79f87e1b1c88e23fed292c69882ab19b60dccada0ee265f3fcdd456e0641017f",
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}
function fullHash(value) {
  return typeof value === "string" && /^0x[0-9a-f]{64}$/i.test(value);
}
function fullAddress(value) {
  return typeof value === "string" && /^0x[0-9a-f]{40}$/i.test(value);
}
function checkRun(run, kind) {
  assert(run.network?.chainId === 10200, `${kind}: wrong chain ID`);
  assert(run.scenarios?.length === 3, `${kind}: expected three scenarios`);
  const expected = new Map([
    ["sequential", "1,1,1,1"],
    ["atomic_package", "4"],
    ["repeated_packages", "2,2"],
  ]);
  for (const scenario of run.scenarios) {
    assert(expected.get(scenario.mode) === scenario.grouping.join(","), `${kind}: grouping mismatch`);
    assert(fullAddress(scenario.contractAddress), `${kind}: truncated contract address`);
    assert(fullHash(scenario.deployTransactionHash), `${kind}: truncated deployment hash`);
    assert(fullHash(scenario.rewardWithdrawalTransactionHash), `${kind}: truncated reward withdrawal hash`);
    assert(fullHash(scenario.treasuryWithdrawalTransactionHash), `${kind}: truncated treasury withdrawal hash`);
    assert(scenario.slashTransactionHashes.every(fullHash), `${kind}: truncated slash hash`);
    assert(scenario.transactions.length > 0, `${kind}: missing transactions`);
    for (const tx of scenario.transactions) {
      assert(fullHash(tx.hash), `${kind}: truncated transaction hash`);
      assert(fullHash(tx.blockHash), `${kind}: truncated block hash`);
      assert(tx.status === "success", `${kind}: non-success receipt`);
    }
    const covered = kind === "covered";
    assert(scenario.rewardCoversEnforcementGas === covered, `${kind}: reward-coverage flag mismatch`);
    assert(scenario.realizedCoveredBondLossWei === (covered ? "40000000000000000" : "8000000000000000"), `${kind}: bond loss mismatch`);
    assert(scenario.callerRewardAccruedWei === (covered ? "12000000000000000" : "2000000000000000"), `${kind}: reward mismatch`);
    assert(scenario.treasuryAccruedBeforeWithdrawalWei === (covered ? "28000000000000000" : "6000000000000000"), `${kind}: treasury mismatch`);
  }
}

const buffers = {};
const parsed = {};
for (const [kind, name] of Object.entries(files)) {
  buffers[kind] = await readFile(path.join(results, name));
  const actual = sha256(buffers[kind]);
  assert(actual === expectedHashes[kind], `${name}: SHA-256 mismatch (${actual})`);
  parsed[kind] = JSON.parse(buffers[kind].toString("utf8"));
}
assert(buffers.canonical.equals(buffers.covered), "canonical and preserved covered JSON differ");
assert(parsed.covered.status === "PUBLIC_SCOPED_EXECUTION", "covered status mismatch");
assert(parsed.calibration.status === "PUBLIC_SCOPED_EXECUTION_REWARD_UNDERFUNDED", "calibration status mismatch");
checkRun(parsed.covered, "covered");
checkRun(parsed.calibration, "calibration");

const recoveryScenarios = [...parsed.calibration.scenarios, ...parsed.covered.scenarios];
const recoveryAddresses = recoveryScenarios.map((scenario) => scenario.contractAddress.toLowerCase());
assert(recoveryScenarios.length === 6, "settlement plan: expected six contracts");
assert(new Set(recoveryAddresses).size === 6, "settlement plan: duplicate address");
const recoveryTotalWei = recoveryScenarios.reduce(
  (sum, scenario) => sum + BigInt(scenario.remainingBondWei),
  0n,
);
const latestReleaseTime = recoveryScenarios.reduce(
  (latest, scenario) => {
    const release = BigInt(scenario.job.releaseTime);
    return release > latest ? release : latest;
  },
  0n,
);
assert(recoveryTotalWei === 108000000000000000n, "settlement plan: aggregate bond mismatch");
assert(latestReleaseTime === 1785808050n, "settlement plan: latest release mismatch");
console.log(
  `CHIADO_SETTLEMENT_PLAN=PASS contracts=6 remainingWei=${recoveryTotalWei} latestReleaseTime=${latestReleaseTime}`,
);
console.log("CHIADO_PRESERVED_HASHES=PASS");
console.log("CHIADO_CANONICAL_COPY_IDENTITY=PASS");
console.log("CHIADO_FULL_ADDRESSES_TX_AND_BLOCK_HASHES=PASS");
console.log("CHIADO_CALIBRATION_STATUS=PASS");
console.log("CHIADO_FRESH_EXECUTION_STATUS=PASS");
console.log("CHIADO_PRESERVED_RESULTS=PASS");
