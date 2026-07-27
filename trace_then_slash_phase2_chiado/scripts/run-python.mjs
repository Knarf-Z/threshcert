import { spawnSync } from "node:child_process";

const scriptArguments = process.argv.slice(2);
if (scriptArguments.length === 0) {
  throw new Error("missing Python script argument");
}

const candidates = process.platform === "win32"
  ? [
      ["py", ["-3.11"]],
      ["py", ["-3"]],
      ["python", []],
    ]
  : [
      ["python3", []],
      ["python", []],
    ];

for (const [command, prefix] of candidates) {
  const result = spawnSync(command, [...prefix, ...scriptArguments], {
    stdio: "inherit",
  });
  if (result.error?.code === "ENOENT") {
    continue;
  }
  process.exit(result.status ?? 1);
}

throw new Error("no usable Python interpreter found");
