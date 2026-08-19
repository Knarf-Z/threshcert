"""Negative controls for the v76 C6/B5 completeness certificate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    refinement_candidates = [
        root / "joint_incidence_refinement",
        root / "verify_v42_clean/joint_incidence_refinement",
        root / "artifact/joint_incidence_refinement",
    ]
    refinement = next((path for path in refinement_candidates if path.is_dir()), refinement_candidates[0])
    review_candidates = [root / "reviewer_revision_v76", root / "review_revision", root / "artifact/reviewer_revision_v76"]
    review_dir = next((path for path in review_candidates if path.is_dir()), review_candidates[0])
    result_candidates = [root / "results", review_dir / "results"]
    result_dir = next((path for path in result_candidates if (path / "completeness_certificates.v1.json").is_file()), result_candidates[-1])
    output = (
        args.output if args.output is not None and args.output.is_absolute()
        else root / args.output if args.output is not None
        else result_dir / "completeness_negative_controls.v1.json"
    )
    artifact_path = refinement / "artifacts/contracts/OverlappingPoolEscrow.sol/OverlappingPoolEscrow.json"
    record_path = refinement / "results/deployment_admission_local.json"
    admission_checker = refinement / "verify_deployment_admission.mjs"
    completeness_checker = review_dir / "verify_completeness_certificates_v1.py"
    certificate_path = result_dir / "completeness_certificates.v1.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    controls: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="fc-v76-") as tmp_name:
        tmp = Path(tmp_name)
        metadata_drift = dict(artifact)
        metadata_drift["buildInfoId"] = "deliberate-nonsemantic-drift"
        metadata_path = tmp / "artifact-metadata-drift.json"
        dump(metadata_path, metadata_drift)
        metadata_result = run([
            "node", str(admission_checker), "--artifact", str(metadata_path),
            "--record", str(record_path), "--certificate", str(tmp / "metadata-certificate.json"),
        ])
        controls.append({
            "mutation": "buildInfoId-only drift",
            "expected": "ACCEPT",
            "observed": "ACCEPT" if metadata_result.returncode == 0 else "REJECT",
        })

        semantic_tamper = dict(artifact)
        semantic_tamper["abi"] = [*artifact["abi"], {"type": "function", "name": "undeclaredRoute", "inputs": [], "outputs": [], "stateMutability": "nonpayable"}]
        semantic_path = tmp / "artifact-semantic-tamper.json"
        dump(semantic_path, semantic_tamper)
        semantic_result = run([
            "node", str(admission_checker), "--artifact", str(semantic_path),
            "--record", str(record_path), "--certificate", str(tmp / "semantic-certificate.json"),
        ])
        controls.append({
            "mutation": "semantic ABI route added",
            "expected": "REJECT",
            "observed": "REJECT" if semantic_result.returncode != 0 else "ACCEPT",
        })

        mutations = []
        missing_record = json.loads(json.dumps(certificate))
        missing_record["c6"]["records"].pop()
        mutations.append(("one C6 path removed", missing_record))
        bounded_reverse = json.loads(json.dumps(certificate))
        bounded_reverse["c6"]["records"][0]["reverse_proof_bounds"] = [1]
        mutations.append(("reverse proof bound inserted", bounded_reverse))
        global_escalation = json.loads(json.dumps(certificate))
        global_escalation["b5"]["deployment_global"]["status"] = "PASS"
        mutations.append(("global B5 escalated from OPEN to PASS", global_escalation))
        for index, (name, mutated) in enumerate(mutations):
            mutated_path = tmp / f"certificate-tamper-{index}.json"
            dump(mutated_path, mutated)
            result = run([
                sys.executable, str(completeness_checker),
                "--output", str(mutated_path), "--verify",
            ])
            controls.append({
                "mutation": name,
                "expected": "REJECT",
                "observed": "REJECT" if result.returncode != 0 else "ACCEPT",
            })

    passed = all(row["expected"] == row["observed"] for row in controls)
    result = {
        "schema": "fc-c6-b5-completeness-negative-controls/v1",
        "status": "PASS" if passed else "FAIL",
        "controls": controls,
        "summary": {
            "tested": len(controls),
            "matched_expectation": sum(row["expected"] == row["observed"] for row in controls),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    dump(output, result)
    for row in controls:
        print(f"{row['mutation']}={row['observed']}")
    print(f"NEGATIVE_CONTROLS={result['status']} ({result['summary']['matched_expectation']}/{result['summary']['tested']})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())