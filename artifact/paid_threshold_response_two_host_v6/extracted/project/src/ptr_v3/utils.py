from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def int_to_bytes(value: int) -> bytes:
    if value < 0:
        raise ValueError("value must be nonnegative")
    length = max(1, (value.bit_length() + 7) // 8)
    return value.to_bytes(length, "big")


def encode_parts(parts: Iterable[bytes]) -> bytes:
    out = bytearray()
    for part in parts:
        out.extend(len(part).to_bytes(8, "big"))
        out.extend(part)
    return bytes(out)


def hash_bytes(*parts: bytes) -> bytes:
    return hashlib.sha256(encode_parts(parts)).digest()


def hash_to_int(modulus: int, *parts: bytes) -> int:
    if modulus <= 1:
        raise ValueError("modulus must be > 1")
    return int.from_bytes(hash_bytes(*parts), "big") % modulus


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Write canonical JSON with LF endings on every platform.

    ``Path.write_text`` applies the platform newline translation, which would
    make the canonical digest differ between Windows and Linux for byte-identical
    content. The whole point of the canonical/metadata split is that the digest
    travels, so the newline is pinned here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
