import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const manifestPath = path.join(root, "MANIFEST.v2.sha256");
const manifest = await readFile(manifestPath, "utf8");
const lines = manifest.trim().split(/\r?\n/);
assert(lines.length > 0, "empty manifest");
for (const line of lines) {
  const match = line.match(/^([0-9a-f]{64})  (.+)$/i);
  assert(match, `malformed manifest line: ${line}`);
  const [, expected, relative] = match;
  assert(!path.isAbsolute(relative), `absolute path in manifest: ${relative}`);
  const resolved = path.resolve(root, relative);
  assert(resolved.startsWith(`${path.resolve(root)}${path.sep}`), `path escapes survey root: ${relative}`);
  const bytes = await readFile(resolved);
  const actual = createHash("sha256").update(bytes).digest("hex");
  assert.equal(actual, expected.toLowerCase(), relative);
}
console.log(`PASS: ${lines.length} manifest entries`);
