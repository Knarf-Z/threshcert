"""Reproducible reviewer-facing boundary, mutation, and route-baseline audit.

This audit deliberately stays below the EVM proof boundary.  It consumes the
frozen records produced by the admitted runtime and receipt bridge, while the
route baseline independently enumerates the finite OPE schema from the
manuscript's equations.  Agreement with the certificate is a sanity check, not
an additional EVM-semantics proof.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE = ROOT / "verify_v42_clean" / "joint_incidence_refinement" / "results" / "refinement_certificate.json"
ADMISSION_NEGATIVE = ROOT / "verify_v42_clean" / "joint_incidence_refinement" / "results" / "deployment_admission_negative.json"
RSP_RESULT = ROOT / "code" / "artifact" / "rsp_soundness_supplement_v2" / "frozen" / "rsp_differential_validation.v1.json"
RECEIPT_RESULT = ROOT / "paid_threshold_response_two_host_v6" / "results" / "ope_receipt_bridge.v1.json"
OUTPUT = ROOT / "results" / "reviewer_gate_matrix.v1.json"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def hand_written_route_baseline() -> dict[str, Any]:
    """Enumerate the finite OPE equations without importing a project checker."""

    roots: list[tuple[int, ...]] = []
    for y in itertools.product(range(3), repeat=7):
        if sum(y[:4]) <= 2 and sum(y[3:]) <= 2:
            roots.append(tuple(y))

    terminal_sets = list(itertools.combinations(range(7), 4))
    edges: list[tuple[tuple[int, ...], tuple[int, ...], int]] = []
    for y in roots:
        for selected in terminal_sets:
            quote = sum(2 - y[index] for index in selected)
            edges.append((y, selected, quote))

    minimum = min(row[2] for row in edges)
    maximum = max(row[2] for row in edges)
    minimizers = [
        {"credits": list(y), "selected": list(selected), "quote": quote}
        for y, selected, quote in edges
        if quote == minimum
    ]
    return {
        "method": "direct_product_enumeration_of_declared_OPE_equations",
        "admissible_roots": len(roots),
        "terminal_sets": len(terminal_sets),
        "root_terminal_edges": len(edges),
        "minimum_residual_payment": minimum,
        "maximum_residual_payment": maximum,
        "first_minimizer": minimizers[0],
        "minimizer_count": len(minimizers),
    }


def gate_matrix() -> list[dict[str, Any]]:
    return [
        {
            "gate": "B1",
            "name": "usable delivery",
            "mutation": "wrong buyer / unusable material",
            "construction": "Keep the visible payment fixed but bind the output to another buyer or set u=0.",
            "expected_status": "MODEL-REFUTED or UNKNOWN",
            "coverage": "explicit single-gate countermodel",
        },
        {
            "gate": "B2",
            "name": "named funding",
            "mutation": "outside sponsor funding",
            "construction": "Keep the receipt fixed and add an acquisition-linked sponsor who supplies the debit.",
            "expected_status": "MODEL-REFUTED or UNKNOWN",
            "coverage": "explicit single-gate countermodel",
        },
        {
            "gate": "B3",
            "name": "atomicity",
            "mutation": "early delivery",
            "construction": "Release usable output before irreversible payment and let the buyer stop before paying.",
            "expected_status": "MODEL-REFUTED or UNKNOWN",
            "coverage": "explicit single-gate countermodel",
        },
        {
            "gate": "B4",
            "name": "return/control closure",
            "mutation": "refund, reimbursement, or common control",
            "construction": "Add a scope-matched return or common controller that offsets the visible debit.",
            "expected_status": "MODEL-REFUTED or UNKNOWN",
            "coverage": "explicit single-gate countermodel",
        },
        {
            "gate": "B5",
            "name": "route closure",
            "mutation": "open bypass",
            "construction": "Add an undeclared successful route that supplies the same output without the checked debit.",
            "expected_status": "MODEL-REFUTED or UNKNOWN",
            "coverage": "explicit single-gate countermodel",
        },
    ]


def gate_omission_subsets(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Materialize every nonempty subset of omitted gates."""

    gate_ids = [row["gate"] for row in gates]
    rows: list[dict[str, Any]] = []
    for mask in range(1, 1 << len(gate_ids)):
        omitted = [gate_ids[index] for index in range(len(gate_ids)) if mask & (1 << index)]
        retained = [gate_id for gate_id in gate_ids if gate_id not in omitted]
        rows.append(
            {
                "omitted_gates": omitted,
                "retained_gates": retained,
                "compatible_completion_template": True,
                "interpretation": "logical compatible-world template, not an observed attack",
            }
        )
    return rows

def mutation_matrix(rsp: dict[str, Any], admission: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    semantic_rows = []
    for name, row in sorted(rsp["mutants"].items()):
        witness = row.get("first_witness") or {}
        semantic_rows.append(
            {
                "family": "restricted-source semantic",
                "mutation": name,
                "status": row["status"],
                "first_failure_witness_present": bool(witness),
                "witness_program": witness.get("program"),
                "witness_guards": witness.get("guards"),
            }
        )

    admission_rows = [
        {
            "family": "deployment admission",
            "mutation": name,
            "status": "REJECTED",
            "first_failure_witness_present": True,
        }
        for name in admission["rejectedTamperCases"]
    ]

    receipt_rows = []
    for name, row in sorted(receipt["negative_cases"].items()):
        receipt_rows.append(
            {
                "family": "receipt bridge",
                "mutation": name,
                "status": "REJECTED" if row.get("rejected") else "MISSED",
                "first_failure_witness_present": bool(row.get("reason")),
                "reason": row.get("reason"),
            }
        )

    rows = semantic_rows + admission_rows + receipt_rows
    return {
        "rows": rows,
        "families": {
            "restricted_source_semantic": {
                "tested": len(semantic_rows),
                "caught": sum(row["status"] == "CAUGHT" for row in semantic_rows),
                "coverage": {
                    "programs": rsp["scope"]["programs"],
                    "concrete_executions": rsp["scope"]["cpython_executions"],
                    "trace_mismatches": len(rsp["mismatches"]),
                },
            },
            "deployment_admission": {
                "tested": len(admission_rows),
                "caught": sum(row["status"] == "REJECTED" for row in admission_rows),
            },
            "receipt_bridge": {
                "tested": len(receipt_rows),
                "caught": sum(row["status"] == "REJECTED" for row in receipt_rows),
            },
        },
    }


def main() -> None:
    certificate = read_json(CERTIFICATE)
    admission = read_json(ADMISSION_NEGATIVE)
    rsp = read_json(RSP_RESULT)
    receipt = read_json(RECEIPT_RESULT)

    baseline = hand_written_route_baseline()
    certified = certificate["declaredTransactionSchema"]
    finite = certificate["finiteCheck"]
    route_comparison = {
        "baseline": baseline,
        "certificate": {
            "admissible_roots": certified["initialStates"],
            "terminal_sets": certified["terminalSets"],
            "root_terminal_edges": certified["acquisitionMacroEdges"],
            "minimum_residual_payment": finite["minimumResidualPayment"],
            "maximum_residual_payment": finite["maximumResidualPayment"],
        },
        "all_fields_agree": (
            baseline["admissible_roots"] == certified["initialStates"]
            and baseline["terminal_sets"] == certified["terminalSets"]
            and baseline["root_terminal_edges"] == certified["acquisitionMacroEdges"]
            and baseline["minimum_residual_payment"] == finite["minimumResidualPayment"]
            and baseline["maximum_residual_payment"] == finite["maximumResidualPayment"]
        ),
        "interpretation": "sanity check against the materialized certificate; not an EVM-semantics proof",
    }

    gates = gate_matrix()
    omission_subsets = gate_omission_subsets(gates)
    receipt_negative = {
        "tested": len(receipt["negative_cases"]),
        "rejected": sum(row.get("rejected") is True for row in receipt["negative_cases"].values()),
        "all_rejected": all(row.get("rejected") is True for row in receipt["negative_cases"].values()),
    }
    mutations = mutation_matrix(rsp, admission, receipt)
    checks = {
        "five_single_gate_countermodels_explicit": len(gates) == 5,
        "all_nonempty_gate_omission_subsets_covered": len(omission_subsets) == 31
        and all(row["compatible_completion_template"] for row in omission_subsets),
        "route_baseline_agrees": route_comparison["all_fields_agree"],
        "receipt_negative_cases_rejected": receipt_negative["all_rejected"],
        "semantic_mutations_all_caught": mutations["families"]["restricted_source_semantic"]["caught"] == mutations["families"]["restricted_source_semantic"]["tested"],
        "admission_mutations_all_rejected": mutations["families"]["deployment_admission"]["caught"] == mutations["families"]["deployment_admission"]["tested"],
        "receipt_mutations_all_rejected": mutations["families"]["receipt_bridge"]["caught"] == mutations["families"]["receipt_bridge"]["tested"],
    }
    result = {
        "schema": "reviewer_gate_matrix.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": {
            "logical_gate_matrix_is_runtime_execution": False,
            "route_baseline_is_independent_of_project_checkers": True,
            "global_payment_certificate": False,
        },
        "checks": checks,
        "gate_countermodels": {
            "single_gate_rows": gates,
            "omission_subsets": omission_subsets,
            "nonempty_omission_subsets": len(omission_subsets),
            "interpretation": "logical compatible-world templates, not observed attacks",
        },
        "route_comparison": route_comparison,
        "receipt_negative": receipt_negative,
        "mutation_matrix": mutations,
        "source_records": {
            "certificate": str(CERTIFICATE.relative_to(ROOT)),
            "admission_negative": str(ADMISSION_NEGATIVE.relative_to(ROOT)),
            "rsp_result": str(RSP_RESULT.relative_to(ROOT)),
            "receipt_result": str(RECEIPT_RESULT.relative_to(ROOT)),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "status": result["status"], "checks": checks}, indent=2, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
