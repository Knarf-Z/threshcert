import { createHash } from "node:crypto";
import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const manifestPath = path.join(root, "MANIFEST.sha256");
const excluded = new Set(["MANIFEST.sha256"]);
const excludedDirectories = new Set(["node_modules", "cache", ".runtime", "__pycache__", "out", "halmos-out", "preflight-out"]);

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    const rel = path.relative(root, full).split(path.sep).join("/");
    if (excluded.has(rel)) continue;
    if (entry.isDirectory() && excludedDirectories.has(entry.name)) continue;
    if (entry.isDirectory()) out.push(...await walk(full));
    else if (entry.isFile()) out.push(rel);
  }
  return out.sort();
}

const lines = [];
for (const rel of await walk(root)) {
  const digest = createHash("sha256").update(await readFile(path.join(root, rel))).digest("hex");
  lines.push(`${digest}  ${rel}`);
}
const canonical = `${lines.join("\n")}\n`;
if (process.argv.includes("--check")) {
  const recorded = await readFile(manifestPath, "utf8");
  if (recorded !== canonical) throw new Error("MANIFEST.sha256 mismatch");
  console.log(`MANIFEST=PASS (${lines.length} files)`);
} else {
  await writeFile(manifestPath, canonical, "utf8");
  console.log(`MANIFEST=WRITTEN (${lines.length} files)`);
}
