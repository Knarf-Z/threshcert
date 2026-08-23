"""Build and verify the deterministic privacy-scrubbed V6 public evidence ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 8, 8, 0, 0, 0)

CONFIG_FILES = (
    "config/code_manifest.v1.json",
    "config/code_manifest.v1.sha256",
    "config/committee.meta.v3.json",
    "config/committee.public.v3.json",
    "config/host1.v3.json",
    "config/host2.v3.json",
)
RESULT_FILES = (
    "results/canonical_result.v3.json",
    "results/capability_certificate.v3.json",
    "results/code_manifest_binding.v1.json",
    "results/code_manifest_mutation_matrix.v1.json",
    "results/coverage_certificate.v3.json",
    "results/end_to_end_certificate.v1.json",
    "results/outage_result.v3.json",
    "results/recovery_result.v3.json",
    "results/restricted_source_inventory.v2.json",
    "results/cpython_bytecode_crosscheck.v1.json",
    "results/source_coverage_kernel.v1.json",
    "results/source_coverage_mutation_matrix.v1.json",
    "results/bandit_report.v1.json",
    "results/bandit_adjudication.v1.json",
)
E2E_INPUT_FILES = {
    "source": "results/source_coverage_kernel.v1.json",
    "manifest": "config/code_manifest.v1.json",
    "manifest_digest": "config/code_manifest.v1.sha256",
    "coverage": "results/coverage_certificate.v3.json",
    "capability": "results/capability_certificate.v3.json",
    "canonical": "results/canonical_result.v3.json",
    "outage": "results/outage_result.v3.json",
    "recovery": "results/recovery_result.v3.json",
}
FORBIDDEN_PATH_PARTS = (
    "secrets/",
    "dealer_seed",
    "run_metadata",
    "baseline_preflight.metadata",
    "private_metadata",
    "nonces.log",
    "topology.v3.json",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_required(relative: str) -> bytes:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f"required public input missing: {relative}")
    return path.read_bytes()


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def validate_ready() -> tuple[dict[str, object], str, str, str]:
    manifest_raw = read_required("config/code_manifest.v1.json")
    manifest = json.loads(manifest_raw)
    manifest_digest = read_required("config/code_manifest.v1.sha256").decode("ascii").strip().upper()
    if sha256(manifest_raw) != manifest_digest:
        raise ValueError("code manifest digest mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("code manifest file map missing")
    for relative, expected in files.items():
        if sha256(read_required(relative)) != str(expected).upper():
            raise ValueError(f"live file is not bound by code manifest: {relative}")

    source_raw = read_required(E2E_INPUT_FILES["source"])
    source = json.loads(source_raw)
    source_digest = sha256(source_raw)
    if source.get("schema") != "ptr-restricted-source-kernel/v2" or source.get("status") != "PROVED_IN_RESTRICTED_SOURCE_MODEL":
        raise ValueError("restricted-source theorem is not proved")
    source_hashes = source.get("source_sha256")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("source coverage hash map missing")
    for relative, expected in source_hashes.items():
        if sha256(read_required(relative)) != str(expected).upper():
            raise ValueError(f"source coverage hash mismatch: {relative}")

    end_to_end_raw = read_required("results/end_to_end_certificate.v1.json")
    end_to_end = json.loads(end_to_end_raw)
    checks = end_to_end.get("checks")
    if end_to_end.get("status") != "PASS" or not isinstance(checks, dict) or not checks or not all(
        value is True for value in checks.values()
    ):
        raise ValueError("refusing public release without a fully passing end-to-end certificate")
    input_hashes = end_to_end.get("input_sha256")
    if not isinstance(input_hashes, dict):
        raise ValueError("end-to-end input hash map missing")
    for name, relative in E2E_INPUT_FILES.items():
        if str(input_hashes.get(name, "")).upper() != sha256(read_required(relative)):
            raise ValueError(f"end-to-end input hash mismatch: {name}")

    canonical_raw = read_required(E2E_INPUT_FILES["canonical"])
    canonical = json.loads(canonical_raw)
    canonical_digest = sha256(canonical_raw)
    binding = canonical.get("source_binding", {})
    if str(binding.get("code_manifest_sha256", "")).upper() != manifest_digest:
        raise ValueError("canonical result is not bound to the frozen code manifest")
    if str(binding.get("source_coverage_result_sha256", "")).upper() != source_digest:
        raise ValueError("canonical result is not bound to the source-coverage result")
    for name in ("outage", "recovery"):
        state = json.loads(read_required(E2E_INPUT_FILES[name]))
        state_binding = state.get("source_binding", {})
        if str(state_binding.get("code_manifest_sha256", "")).upper() != manifest_digest:
            raise ValueError(f"{name} result is not bound to the frozen code manifest")
        if str(state_binding.get("canonical_result_sha256", "")).upper() != canonical_digest:
            raise ValueError(f"{name} result is not bound to the canonical result")
    return manifest, manifest_digest, source_digest, sha256(end_to_end_raw)
def build_members() -> dict[str, bytes]:
    manifest, manifest_digest, source_digest, e2e_digest = validate_ready()
    members: dict[str, bytes] = {}
    members["project/README.md"] = read_required("README.md")
    for relative in sorted(manifest["files"]):
        members[f"project/{relative}"] = read_required(relative)
    for relative in CONFIG_FILES:
        members[f"project/{relative}"] = read_required(relative)
    template = {
        "_comment": "Public template. Insert the two LAN addresses locally; real addresses are excluded.",
        "host1": {"address": "HOST1_LAN_ADDRESS"},
        "host2": {"address": "HOST2_LAN_ADDRESS"},
    }
    members["project/config/topology.template.v3.json"] = canonical_json(template)
    for relative in RESULT_FILES:
        members[relative] = read_required(relative)
    release = {
        "schema": "ptr-two-host-public-release/v6",
        "status": "PASS",
        "code_manifest_sha256": manifest_digest,
        "source_coverage_result_sha256": source_digest,
        "end_to_end_certificate_sha256": e2e_digest,
        "privacy_transform": {
            "excluded": [
                "all operator secret shares and the private Host 2 package",
                "dealer seed and network secret material",
                "actual topology addresses and machine metadata",
                "operator replay logs and Python caches",
                "historical archives, patch backups, and failed runs",
            ],
            "canonical_result_contains_no_peer_address": True,
        },
        "not_claimed": [
            "deployment-wide route closure",
            "operating-system or interpreter integrity",
            "hardware non-exportability",
            "seven independent economic operators",
            "a measured bribery or acquisition price",
        ],
    }
    members["PUBLIC_RELEASE.json"] = canonical_json(release)
    members["README_PUBLIC_RELEASE.txt"] = (
        "V6 privacy-scrubbed two-host execution evidence.\n"
        "Run: py -3.11 project/scripts/export_public_release.py --verify-only <this zip>\n"
        "The private Host 2 share bundle is deliberately excluded.\n"
    ).encode("utf-8")
    return members


def manifest_bytes(members: dict[str, bytes]) -> bytes:
    return ("\n".join(f"{sha256(data)}  {name}" for name, data in sorted(members.items())) + "\n").encode("ascii")


def verify_archive(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP entry")
        if names != sorted(names):
            raise ValueError("ZIP entries are not sorted")
        lowered = [name.lower().replace("\\", "/") for name in names]
        for name in lowered:
            if any(part in name for part in FORBIDDEN_PATH_PARTS):
                raise ValueError(f"private path escaped into public release: {name}")

        expected_lines = archive.read("MANIFEST.sha256").decode("ascii").splitlines()
        expected: dict[str, str] = {}
        for line in expected_lines:
            digest, name = line.split("  ", 1)
            expected[name] = digest
        payload_names = [name for name in names if name != "MANIFEST.sha256"]
        if sorted(expected) != sorted(payload_names):
            raise ValueError("internal manifest file set mismatch")
        for name in payload_names:
            if sha256(archive.read(name)) != expected[name]:
                raise ValueError(f"internal manifest hash mismatch: {name}")

        manifest_raw = archive.read("project/config/code_manifest.v1.json")
        manifest_digest_raw = archive.read("project/config/code_manifest.v1.sha256")
        manifest_digest = manifest_digest_raw.decode("ascii").strip().upper()
        if sha256(manifest_raw) != manifest_digest:
            raise ValueError("archived code manifest digest mismatch")
        manifest = json.loads(manifest_raw)
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("archived code manifest file map missing")
        for relative, digest in files.items():
            member = f"project/{relative}"
            if member not in names or sha256(archive.read(member)) != str(digest).upper():
                raise ValueError(f"archived code manifest mismatch: {relative}")

        source_raw = archive.read("results/source_coverage_kernel.v1.json")
        source = json.loads(source_raw)
        source_digest = sha256(source_raw)
        if source.get("schema") != "ptr-restricted-source-kernel/v2" or source.get("status") != "PROVED_IN_RESTRICTED_SOURCE_MODEL":
            raise ValueError("archived restricted-source theorem is not proved")
        source_hashes = source.get("source_sha256")
        if not isinstance(source_hashes, dict) or not source_hashes:
            raise ValueError("archived source coverage hash map missing")
        for relative, digest in source_hashes.items():
            member = f"project/{relative}"
            if member not in names or sha256(archive.read(member)) != str(digest).upper():
                raise ValueError(f"archived source coverage mismatch: {relative}")

        archive_inputs = {
            name: (f"project/{relative}" if relative.startswith("config/") else relative)
            for name, relative in E2E_INPUT_FILES.items()
        }
        end_to_end_raw = archive.read("results/end_to_end_certificate.v1.json")
        end_to_end = json.loads(end_to_end_raw)
        checks = end_to_end.get("checks")
        if end_to_end.get("status") != "PASS" or not isinstance(checks, dict) or not checks or not all(
            value is True for value in checks.values()
        ):
            raise ValueError("archived end-to-end certificate is not fully PASS")
        input_hashes = end_to_end.get("input_sha256")
        if not isinstance(input_hashes, dict):
            raise ValueError("archived end-to-end input hash map missing")
        for name, member in archive_inputs.items():
            if str(input_hashes.get(name, "")).upper() != sha256(archive.read(member)):
                raise ValueError(f"archived end-to-end input mismatch: {name}")
        certificate = end_to_end.get("certificate", {})
        if certificate.get("certification_outcome") != {"status": "CERTIFIED", "floor": 10}:
            raise ValueError("archived status/floor outcome rejected")
        if certificate.get("named_acquirer_outflow_lower_bound") != 10 or certificate.get(
            "named_acquirer_outflow_exact_value"
        ) != 10:
            raise ValueError("archived end-to-end payment value rejected")

        canonical_raw = archive.read("results/canonical_result.v3.json")
        canonical = json.loads(canonical_raw)
        canonical_digest = sha256(canonical_raw)
        canonical_binding = canonical.get("source_binding", {})
        if str(canonical_binding.get("code_manifest_sha256", "")).upper() != manifest_digest:
            raise ValueError("archived canonical/code-manifest binding rejected")
        if str(canonical_binding.get("source_coverage_result_sha256", "")).upper() != source_digest:
            raise ValueError("archived canonical/source binding rejected")
        quantities = canonical.get("quantities", {})
        if not (
            canonical.get("schema") == "paid-threshold-response-two-host/v6"
            and canonical.get("run_passed") is True
            and quantities.get("theory_cover") == 10
            and quantities.get("catalog_certificate") == 10
            and quantities.get("observed_minimum") == 10
            and canonical.get("route_catalog", {}).get("complete_for_declared_first_four_route_grammar") is True
            and canonical.get("scope", {}).get("host1_declared_secret_directory_excludes_remote_operator_files") is True
        ):
            raise ValueError("archived canonical result rejected")

        expected_result_schemas = {
            "results/capability_certificate.v3.json": "paid-threshold-response-two-host-capability/v5",
            "results/coverage_certificate.v3.json": "paid-threshold-response-two-host-coverage/v5",
            "results/outage_result.v3.json": "paid-threshold-response-two-host-outage/v5",
            "results/recovery_result.v3.json": "paid-threshold-response-two-host-outage/v5",
        }
        for member, schema in expected_result_schemas.items():
            result = json.loads(archive.read(member))
            if result.get("schema") != schema:
                raise ValueError(f"archived result schema rejected: {member}")
        for member in ("results/outage_result.v3.json", "results/recovery_result.v3.json"):
            state = json.loads(archive.read(member))
            state_binding = state.get("source_binding", {})
            if str(state_binding.get("code_manifest_sha256", "")).upper() != manifest_digest:
                raise ValueError(f"archived state/code-manifest binding rejected: {member}")
            if str(state_binding.get("canonical_result_sha256", "")).upper() != canonical_digest:
                raise ValueError(f"archived state/canonical binding rejected: {member}")
            state_checks = state.get("checks")
            if not isinstance(state_checks, dict) or not state_checks or not all(
                value is True for value in state_checks.values()
            ):
                raise ValueError(f"archived state checks rejected: {member}")

        release = json.loads(archive.read("PUBLIC_RELEASE.json"))
        if release.get("schema") != "ptr-two-host-public-release/v6" or release.get("status") != "PASS":
            raise ValueError("public release metadata rejected")
        if not (
            release.get("code_manifest_sha256") == manifest_digest
            and release.get("source_coverage_result_sha256") == source_digest
            and release.get("end_to_end_certificate_sha256") == sha256(end_to_end_raw)
        ):
            raise ValueError("public release evidence binding rejected")

        if b"observed_peer_address" in canonical_raw:
            raise ValueError("canonical result exposes a peer address")
        private_ipv4 = re.compile(
            rb"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
        )
        exposed = [name for name in names if private_ipv4.search(archive.read(name))]
        if exposed:
            raise ValueError("private LAN address escaped into release: " + ", ".join(exposed))
    return {
        "status": "PASS",
        "entries": len(names),
        "bytes": path.stat().st_size,
        "sha256": sha256(path.read_bytes()),
    }
def export(path: Path) -> dict[str, object]:
    members = build_members()
    members["MANIFEST.sha256"] = manifest_bytes(members)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in sorted(members.items()):
            archive.writestr(zip_info(name), data)
    return verify_archive(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "two_host_execution_evidence.public.zip")
    parser.add_argument("--verify-only", type=Path)
    args = parser.parse_args()
    result = verify_archive(args.verify_only.resolve()) if args.verify_only else export(args.output.resolve())
    print(f"PUBLIC_RELEASE={result['status']}")
    print(f"PUBLIC_RELEASE_ENTRIES={result['entries']}")
    print(f"PUBLIC_RELEASE_BYTES={result['bytes']}")
    print(f"PUBLIC_RELEASE_SHA256={result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())