import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { recoverMessageAddress } from "viem";

const inputPath = process.argv[2] ?? "results/ope_process_routes.v1.json";
const input = JSON.parse(await readFile(inputPath, "utf8"));
assert.equal(input.schema, "ope-controlled-process-routes/v1");
assert.equal(input.route_count, 35);

for (const route of input.routes) {
  const auth = route.request_authentication;
  assert.equal(auth.scheme, "EIP-191/secp256k1");
  const recovered = await recoverMessageAddress({
    message: auth.message,
    signature: auth.signature,
  });
  assert.equal(recovered.toLowerCase(), input.roles.attacker.toLowerCase());
  assert.equal(auth.recovered_signer.toLowerCase(), input.roles.attacker.toLowerCase());
  for (const value of [
    route.contract.address,
    route.payment_transaction.hash,
    route.payment_transaction.from,
    route.payment_transaction.value_wei,
    route.selected_member_indices.join(","),
  ]) {
    assert.ok(auth.message.toLowerCase().includes(String(value).toLowerCase()));
  }
}

console.log("OPE_BUYER_AUTH=PASS");
console.log("OPE_BUYER_AUTH_ROUTES=35_OF_35");
