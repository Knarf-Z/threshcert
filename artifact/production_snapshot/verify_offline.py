#!/usr/bin/env python3
"""Offline, non-mutating verification of the pinned production snapshot audit."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GENERATOR = ROOT / "scripts" / "run_production_evidence_audit.py"
RESULT_JSON = ROOT / "results" / "production_evidence_audit.json"
RESULT_CSV = ROOT / "results" / "production_member_evidence_audit.csv"
PROVENANCE = ROOT / "data" / "production_keyper_set_20260613.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("production_audit_generator", GENERATOR)
require(spec is not None and spec.loader is not None, "cannot load audit generator")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

expected = module.audit_production_evidence()
recorded = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
require(recorded == expected, "production evidence JSON differs from recomputation")

provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
anchor = provenance["audit_anchor"]
manager = provenance["manager"]
keyper_set = provenance["keyper_set"]
require(provenance["chain_id"] == 100, "unexpected production chain ID")
require(anchor["block_number"] == 46666718, "unexpected pinned block")
require(anchor["block_hash"].lower() == "0x574ec26ee7b2e2bfddd991bf99d37a79455428bc4dfe342b0ccf55d071229b60", "unexpected pinned block hash")
require(manager["active_keyper_set_index"] == 10, "unexpected active set index")
require(keyper_set["num_members"] == 7 and keyper_set["threshold"] == 4, "unexpected committee dimensions")
require(len({x.lower() for x in keyper_set["members"]}) == 7, "member addresses are not distinct")
require(recorded["certificate"]["threshold_cover_lower_bound"] == "0", "production certificate is not zero")
require(recorded["claim"]["actual_member_resistance"] == "UNKNOWN_NOT_MEASURED", "zero evidence was relabeled as zero resistance")

fields = [
    "member_index", "address", "weight", "committee_membership_status",
    "actual_resistance_status", "base_resistance_contribution",
    "penalty_contribution", "insurance_or_compensation_contribution",
    "certified_member_floor", "activation_branch_status", "direct_path_gap",
    "penalty_path_gap", "activation_path_gap",
]
expected_rows = []
for member in expected["members"]:
    row = dict(member)
    for field in ("direct_path_gap", "penalty_path_gap", "activation_path_gap"):
        row[field] = "|".join(row[field]) or "NONE"
    expected_rows.append({field: str(row[field]) for field in fields})
with RESULT_CSV.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    require(reader.fieldnames == fields, "production member CSV schema mismatch")
    recorded_rows = list(reader)
require(recorded_rows == expected_rows, "production member CSV differs from recomputation")

print(f"PRODUCTION_SNAPSHOT_BLOCK={anchor['block_number']}")
print(f"PRODUCTION_SNAPSHOT_HASH={anchor['block_hash']}")
print(f"PRODUCTION_ACTIVE_SET_INDEX={manager['active_keyper_set_index']}")
print(f"PRODUCTION_COMMITTEE={keyper_set['threshold']}-OF-{keyper_set['num_members']}")
print("PRODUCTION_CERTIFICATE=0_PUBLIC_FLOOR_CERTIFICATE")
print("PRODUCTION_ACTUAL_RESISTANCE=UNKNOWN_NOT_MEASURED")
print(f"PRODUCTION_RECORD_SHA256={sha256(PROVENANCE)}")
print(f"PRODUCTION_RESULT_SHA256={sha256(RESULT_JSON)}")
print("PRODUCTION_SNAPSHOT_OFFLINE=PASS")