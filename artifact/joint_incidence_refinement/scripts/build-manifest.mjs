import { createHash } from "node:crypto";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = join(root, "MANIFEST.sha256");
const excluded = new Set([
  ".runtime",
  "artifacts",
  "cache",
  "node_modules",
  "out",
  "halmos-out",
  "preflight-out",
]);

async function filesUnder(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (excluded.has(entry.name)) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await filesUnder(path));
    } else if (
      path !== manifestPath &&
      !entry.name.endsWith(".log")
    ) {
      files.push(path);
    }
  }
  return files;
}

const files = (await filesUnder(root)).sort();
const lines = [];
for (const path of files) {
  const digest = createHash("sha256")
    .update(await readFile(path))
    .digest("hex");
  lines.push(`${digest}  ${relative(root, path).split(sep).join("/")}`);
}
const expected = `${lines.join("\n")}\n`;

if (process.argv.includes("--check")) {
  const actual = await readFile(manifestPath, "utf8").catch(() => "");
  if (actual !== expected) {
    throw new Error("MANIFEST=FAIL");
  }
  console.log("MANIFEST=PASS");
} else {
  await writeFile(manifestPath, expected, "utf8");
  console.log(`MANIFEST=WRITTEN files=${lines.length}`);
}
