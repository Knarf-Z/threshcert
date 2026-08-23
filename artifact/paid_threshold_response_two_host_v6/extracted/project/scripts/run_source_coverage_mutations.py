from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_coverage_kernel import analyze  # noqa: E402


Mutation = Callable[[Path], None]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one mutation anchor, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def operator(root: Path) -> Path:
    return root / "src" / "ptr_v3" / "operator_server.py"


def crypto(root: Path) -> Path:
    return root / "src" / "ptr_v3" / "crypto.py"


def experiment(root: Path) -> Path:
    return root / "src" / "ptr_v3" / "experiment.py"


def extra_entry(root: Path) -> None:
    replace_once(
        operator(root),
        "        def do_POST(self) -> None:\n",
        "        def do_PUT(self) -> None:\n"
        "            self._send(200, {\"partial_decryption\": \"cached\"})\n\n"
        "        def do_POST(self) -> None:\n",
    )


def extra_route(root: Path) -> None:
    replace_once(
        operator(root),
        '            if self.path != "/health":\n',
        '            if self.path not in ("/health", "/export"):\n',
    )


def direct_response_sink(root: Path) -> None:
    replace_once(
        operator(root),
        "        def do_GET(self) -> None:\n",
        "        def do_GET(self) -> None:\n"
        "            self.wfile.write(b\"undeclared-response\")\n",
    )


def share_leak(root: Path) -> None:
    replace_once(
        operator(root),
        "        def do_GET(self) -> None:\n",
        "        def do_GET(self) -> None:\n"
        "            leaked_share = state.share\n",
    )


def dynamic_eval(root: Path) -> None:
    path = operator(root)
    path.write_text(path.read_text(encoding="utf-8") + "\ndef source_bypass(expr):\n    return eval(expr)\n", encoding="utf-8", newline="\n")


def process_import(root: Path) -> None:
    path = operator(root)
    path.write_text(path.read_text(encoding="utf-8") + "\nimport subprocess\n", encoding="utf-8", newline="\n")


def second_listener(root: Path) -> None:
    path = operator(root)
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\ndef second_listener(state):\n"
          "    return ThreadingHTTPServer((\"127.0.0.1\", 9999), build_handler(state))\n",
        encoding="utf-8",
        newline="\n",
    )


def lifecycle_replacement(root: Path) -> None:
    replace_once(
        operator(root),
        "        def do_POST(self) -> None:\n",
        "        def do_POST(self) -> None:\n"
        "            state.share = state.share\n",
    )


def plaintext_oracle(root: Path) -> None:
    replace_once(
        crypto(root),
        '            "plaintext_commitment": self.plaintext_commitment,\n',
        '            "plaintext_commitment": self.plaintext_commitment,\n'
        '            "plaintext": "leaked-test-oracle",\n',
    )


def deterministic_experiment_seed(root: Path) -> None:
    replace_once(
        experiment(root),
        "    return encrypt_capability(committee.public_key, committee.buyer, committee.resource, order_id)\n",
        "    return encrypt_capability(committee.public_key, committee.buyer, committee.resource, order_id, seed=1)\n",
    )


def threshold_bypass(root: Path) -> None:
    replace_once(
        experiment(root),
        "    plaintext: int | None = None\n",
        "    plaintext: int | None = 1\n",
    )


def delivery_bypass(root: Path) -> None:
    replace_once(
        experiment(root),
        "    gateway_accepted = aggregate_valid and actual_consumer == ciphertext.buyer\n",
        "    gateway_accepted = True\n",
    )


def extra_producer(root: Path) -> None:
    path = operator(root)
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\ndef undeclared_producer(state, ciphertext, epoch):\n"
          "    return create_partial(state.operator_id, state.share, state.public_share, ciphertext, epoch)\n",
        encoding="utf-8",
        newline="\n",
    )


def unsigned_runtime_source(root: Path) -> None:
    replace_once(
        operator(root),
        "                runtime_source_digest=RUNTIME_SOURCE_DIGEST,\n",
        "",
    )


CASES: tuple[tuple[str, Mutation, tuple[str, ...]], ...] = (
    ("extra_request_entry", extra_entry, ("HANDLER_AND_ENTRY_METHODS_EXACT",)),
    ("undeclared_http_route", extra_route, ("ROUTE_GUARDS_EXACT",)),
    ("direct_response_sink", direct_response_sink, ("RAW_HTTP_SINKS_CONFINED",)),
    ("secret_share_leak", share_leak, ("SECRET_SHARE_READ_CONFINED_TO_PRODUCER",)),
    ("dynamic_eval", dynamic_eval, ("NO_DYNAMIC_NATIVE_OR_PROCESS_ESCAPE",)),
    ("process_import", process_import, ("NO_DYNAMIC_NATIVE_OR_PROCESS_ESCAPE",)),
    ("second_listener", second_listener, ("SINGLE_DECLARED_LISTENER",)),
    ("lifecycle_replacement", lifecycle_replacement, ("SENSITIVE_STATE_LIFECYCLE_EXACT",)),
    ("plaintext_oracle", plaintext_oracle, ("CRITICAL_NORMAL_FORMS_EXACT",)),
    ("deterministic_experiment_seed", deterministic_experiment_seed, ("CRITICAL_NORMAL_FORMS_EXACT",)),
    ("threshold_plaintext_bypass", threshold_bypass, ("THRESHOLD_AND_BUYER_GUARD_DELIVERY_ROOT",)),
    ("delivery_root_bypass", delivery_bypass, ("THRESHOLD_AND_BUYER_GUARD_DELIVERY_ROOT",)),
    ("second_capability_producer", extra_producer, ("PARTIAL_PRODUCER_SITE_UNIQUE",)),
    ("unsigned_runtime_source", unsigned_runtime_source, ("RUNTIME_SOURCE_BINDING_END_TO_END",)),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regression mutations for the RSP-V6 proof kernel; not a soundness proof.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "source_coverage_mutation_matrix.v1.json",
    )
    args = parser.parse_args()
    source = args.root.resolve() / "src"
    baseline = analyze(args.root.resolve())
    rows: list[dict[str, object]] = []
    all_caught = baseline["status"] == "PROVED_IN_RESTRICTED_SOURCE_MODEL"

    with tempfile.TemporaryDirectory(prefix="ptr-source-coverage-") as temp:
        temp_root = Path(temp)
        for name, mutation, expected_failures in CASES:
            case_root = temp_root / name
            shutil.copytree(source, case_root / "src")
            (case_root / "scripts").mkdir(parents=True)
            shutil.copy2(args.root.resolve() / "scripts" / "run_two_host.py", case_root / "scripts" / "run_two_host.py")
            (case_root / "results").mkdir(parents=True)
            shutil.copy2(args.root.resolve() / "results" / "restricted_source_inventory.v2.json", case_root / "results" / "restricted_source_inventory.v2.json")
            mutation(case_root)
            result = analyze(case_root)
            failed = sorted(check for check, ok in result["checks"].items() if not ok)
            caught = result["status"] == "REJECTED" and all(check in failed for check in expected_failures)
            all_caught = all_caught and caught
            rows.append(
                {
                    "mutation": name,
                    "status": "CAUGHT" if caught else "MISSED",
                    "expected_failed_checks": list(expected_failures),
                    "actual_failed_checks": failed,
                }
            )
            print(f"{name}={'CAUGHT' if caught else 'MISSED'}")

    output = {
        "schema": "ptr-source-coverage-mutations/v1",
        "status": "PASS" if all_caught else "FAIL",
        "baseline_status": baseline["status"],
        "mutations_caught": sum(row["status"] == "CAUGHT" for row in rows),
        "mutations_total": len(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"SOURCE_COVERAGE_MUTATIONS_CAUGHT={output['mutations_caught']}/{output['mutations_total']}")
    print(f"SOURCE_COVERAGE_MUTATION_MATRIX={output['status']}")
    print(f"SOURCE_COVERAGE_MUTATION_RESULT={args.output}")
    return 0 if all_caught else 1


if __name__ == "__main__":
    raise SystemExit(main())