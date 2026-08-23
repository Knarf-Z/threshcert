from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ("B310", "MEDIUM", "HIGH", "src\\ptr_v3\\coordinator.py", 92),
    ("B310", "MEDIUM", "HIGH", "src\\ptr_v3\\coordinator.py", 100),
    ("B311", "LOW", "HIGH", "src\\ptr_v3\\crypto.py", 55),
    ("B105", "LOW", "MEDIUM", "src\\ptr_v3\\dealer.py", 36),
    ("B105", "LOW", "MEDIUM", "src\\ptr_v3\\evidence.py", 23),
    ("B104", "MEDIUM", "MEDIUM", "src\\ptr_v3\\operator_server.py", 271),
}
DISPOSITIONS = {
    "B310": (
        "The two calls receive URLs constructed by OperatorEndpoint.url or a "
        "literal http prefix plus the typed endpoint. No request-controlled URL "
        "scheme reaches urlopen; coordinator normal forms are frozen."
    ),
    "B311": (
        "random.Random is reachable only when an explicit test seed is supplied. "
        "The physical experiment calls encrypt_capability without a seed, and "
        "RSP-V6 freezes that call plus secrets.randbelow/token_bytes."
    ),
    "B105": (
        "The reported strings are a schema tag and the literal gate status PASS, "
        "not credentials."
    ),
    "B104": (
        "The CLI default permits the remote Host 2 service to listen on its LAN "
        "interface. This is intentional exposure, not treated as harmless; the "
        "accepted application surface is limited to the two checked routes and "
        "the deployment still relies on host firewall and OS integrity."
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and explicitly adjudicate the frozen Bandit 1.9.4 report."
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "results" / "bandit_report.v1.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "bandit_adjudication.v1.json",
    )
    args = parser.parse_args()
    report: dict[str, Any] = json.loads(args.report.read_text(encoding="utf-8"))
    rows = {
        (
            str(item["test_id"]),
            str(item["issue_severity"]),
            str(item["issue_confidence"]),
            str(item["filename"]),
            int(item["line_number"]),
        )
        for item in report.get("results", [])
    }
    totals = report.get("metrics", {}).get("_totals", {})
    checks = {
        "REPORT_HAS_NO_ERRORS": report.get("errors") == [],
        "NO_HIGH_SEVERITY_FINDINGS": totals.get("SEVERITY.HIGH") == 0,
        "EXPECTED_FINDING_SET_EXACT": rows == EXPECTED,
        "ALL_FINDINGS_HAVE_EXPLICIT_DISPOSITION": all(
            row[0] in DISPOSITIONS for row in rows
        ),
        "NO_NOSEC_SUPPRESSIONS": totals.get("nosec") == 0,
    }
    output = {
        "schema": "ptr-bandit-adjudication/v1",
        "tool": {
            "name": "Bandit",
            "version": "1.9.4",
            "role": "third-party generic security scan; not a proof kernel",
        },
        "status": "REVIEWED_NO_HIGH_SEVERITY" if all(checks.values()) else "FAIL",
        "checks": checks,
        "report_sha256": sha256(args.report),
        "totals": totals,
        "findings": [
            {
                "test_id": row[0],
                "severity": row[1],
                "confidence": row[2],
                "file": row[3],
                "line": row[4],
                "disposition": DISPOSITIONS[row[0]],
            }
            for row in sorted(rows)
        ],
        "not_claimed": [
            "absence of vulnerabilities",
            "soundness of the RSP-V6 theorem",
            "operating-system or network-stack integrity",
            "that intentional LAN exposure is risk free",
        ],
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, ok in checks.items():
        print(f"{name}={'PASS' if ok else 'FAIL'}")
    print(f"BANDIT_ADJUDICATION={output['status']}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
