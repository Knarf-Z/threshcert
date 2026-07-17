import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";

export async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(resolve(path), "utf8")) as T;
}

export async function writeJson(path: string, value: unknown): Promise<string> {
  const absolute = resolve(path);
  await mkdir(dirname(absolute), { recursive: true });
  const temporary = `${absolute}.tmp`;
  const text = JSON.stringify(
    value,
    (_key, item) => (typeof item === "bigint" ? item.toString() : item),
    2,
  );
  await writeFile(temporary, `${text}\n`, "utf8");
  await rename(temporary, absolute);
  return absolute;
}

export function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing required environment variable ${name}`);
  return value;
}

export function artifactReference(path: string): string {
  const absolute = resolve(path);
  const candidate = relative(process.cwd(), absolute);
  const outside = candidate === ".." || candidate.startsWith(`..${sep}`);
  const reference = candidate && !outside ? candidate : absolute;
  return reference.split(sep).join("/");
}
