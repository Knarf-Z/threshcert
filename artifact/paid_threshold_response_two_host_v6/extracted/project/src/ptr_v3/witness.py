"""Proof objects, extended with the host each counted response came from.

The v2 objects carried operator identity; v3 adds ``host_id`` to both the
aggregation and the allocation witness, so a claim about *where* the threshold
was reached is part of the record the verifier checks rather than prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Sequence

from .utils import canonical_json_bytes, sha256_hex

FORBIDDEN_PUBLIC_FIELDS = ("seed", "network_seed", "secret_shares", "secret_share", "network_secret_key")


def bitmap_of(operator_ids: Sequence[int]) -> str:
    mask = 0
    for operator_id in operator_ids:
        if operator_id <= 0:
            raise ValueError("operator ids are 1-based")
        mask |= 1 << (operator_id - 1)
    return f"0x{mask:02x}"


def ids_of_bitmap(bitmap: str) -> list[int]:
    mask = int(bitmap, 16)
    out: list[int] = []
    index = 0
    while mask:
        index += 1
        if mask & 1:
            out.append(index)
        mask >>= 1
    return out


@dataclass(frozen=True)
class AggregationWitness:
    order_id: str
    buyer: str
    resource: str
    epoch: int
    responder_bitmap: str
    operator_ids: tuple[int, ...]
    host_ids: tuple[str, ...]
    partial_response_hashes: tuple[str, ...]
    aggregate_valid: bool
    plaintext_hash: str

    def counted_by_host(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for operator_id, host_id in zip(self.operator_ids, self.host_ids):
            out.setdefault(host_id, []).append(operator_id)
        return {host: sorted(ids) for host, ids in sorted(out.items())}

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "aggregation_witness",
            "order_id": self.order_id,
            "buyer": self.buyer,
            "resource": self.resource,
            "epoch": self.epoch,
            "responder_bitmap": self.responder_bitmap,
            "operator_ids": list(self.operator_ids),
            "host_ids": list(self.host_ids),
            "counted_by_host": self.counted_by_host(),
            "partial_response_hashes": list(self.partial_response_hashes),
            "aggregate_valid": self.aggregate_valid,
            "plaintext_hash": self.plaintext_hash,
        }


@dataclass(frozen=True)
class AllocationEntry:
    operator_id: int
    host_id: str
    responder_bitmap: str
    response_hash: str
    debit_id: str | None
    debit: int
    refund_ids: tuple[str, ...]
    refund: int
    funding_ids: tuple[str, ...]
    external_funding: int

    @property
    def net_allocated_outflow(self) -> int:
        return self.debit - self.refund - self.external_funding

    def to_dict(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "host_id": self.host_id,
            "responder_bitmap": self.responder_bitmap,
            "response_hash": self.response_hash,
            "debit_id": self.debit_id,
            "debit": self.debit,
            "refund_ids": list(self.refund_ids),
            "refund": self.refund,
            "funding_ids": list(self.funding_ids),
            "external_funding": self.external_funding,
            "net_allocated_outflow": self.net_allocated_outflow,
        }


@dataclass(frozen=True)
class AllocationWitness:
    order_id: str
    responder_bitmap: str
    entries: tuple[AllocationEntry, ...]

    @property
    def total_allocated(self) -> int:
        return sum(entry.net_allocated_outflow for entry in self.entries)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "allocation_witness",
            "order_id": self.order_id,
            "responder_bitmap": self.responder_bitmap,
            "entries": [entry.to_dict() for entry in self.entries],
            "total_allocated": self.total_allocated,
        }


@dataclass(frozen=True)
class RouteCoverageEvidence:
    status: str  # PROVED | REFUTED | UNKNOWN
    scope_hash: str
    route_catalog_hash: str
    covered_routes: tuple[str, ...]
    excluded_routes: tuple[str, ...]
    proof_kernel: str
    served_http_routes: tuple[str, ...] = ()
    bypass_trace: dict[str, object] | None = None
    deployment_wide: bool = False
    coverage_scope: str = "declared finite program language over the two configured hosts"

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "route_coverage_evidence",
            "status": self.status,
            "scope_hash": self.scope_hash,
            "route_catalog_hash": self.route_catalog_hash,
            "covered_routes": list(self.covered_routes),
            "excluded_routes": list(self.excluded_routes),
            "served_http_routes": list(self.served_http_routes),
            "proof_kernel": self.proof_kernel,
            "bypass_trace": self.bypass_trace,
            "deployment_wide": self.deployment_wide,
            "coverage_scope": self.coverage_scope,
        }


@dataclass(frozen=True)
class SeparationWitness:
    """Whether the two configured hosts are actually two machines.

    Nothing else in this artifact establishes it. ``operator_hosts`` in the
    committee file is a label host 1 chose, and an operator's ``host_id`` is a
    string it reports about itself; a single machine can serve both labels on
    two ports and every other check in the pipeline still passes. This witness
    is the only place where the claim is decided, and it is decided from what
    host 1 observed rather than from what the configuration says.

    ``PASS`` requires both an observed non-local TCP peer address for every
    remote operator and a self-reported machine digest that differs from the
    local one. A single loopback or self-addressed peer is a counterexample:
    that operator demonstrably ran on this machine.
    """

    status: str  # PASS | FAIL_COUNTEREXAMPLE | FAIL_CLOSED_MISSING_EVIDENCE
    reason: str
    local_machine_digest: str
    remote_machine_digests: dict[str, list[str]]
    probes: tuple[dict[str, object], ...]
    distinct_machines_observed: int
    method: str = "tcp-peer-address + self-reported machine digest; no attestation"

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, object]:
        """The canonical half: verdicts only.

        Addresses and fingerprints identify a particular pair of machines and
        would make the canonical result unreproducible off this network, so they
        live in the run metadata. What stays here is what a reader needs to know
        the claim was decided rather than assumed, and it is identical on any
        correctly separated pair.
        """

        return {
            "type": "host_separation_witness",
            "status": self.status,
            "reason": self.reason,
            "distinct_machines_observed": self.distinct_machines_observed,
            "observations": [
                {
                    "operator_id": probe["operator_id"],
                    "configured_host_id": probe["configured_host_id"],
                    "is_remote": probe["is_remote"],
                    "peer_is_loopback": probe["peer_is_loopback"],
                    "peer_equals_local": probe["peer_equals_local"],
                    "machine_differs_from_coordinator": probe["machine_differs_from_coordinator"],
                }
                for probe in sorted(self.probes, key=lambda p: int(p["operator_id"]))
            ],
            "method": self.method,
            "identifying_values_recorded_in": "run_metadata.v3.json",
        }

    def to_metadata_dict(self) -> dict[str, object]:
        """The non-canonical half: the addresses and fingerprints observed."""

        return {
            "type": "host_separation_observations",
            "status": self.status,
            "local_machine_digest": self.local_machine_digest,
            "machine_digests_by_configured_host": {
                host: sorted(digests) for host, digests in sorted(self.remote_machine_digests.items())
            },
            "probes": [
                dict(sorted(probe.items()))
                for probe in sorted(self.probes, key=lambda p: int(p["operator_id"]))
            ],
        }


def build_separation_witness(
    local_host_id: str,
    local_machine_digest: str,
    probes: Sequence[dict[str, object]],
    health_by_operator: dict[int, dict[str, object]],
    operator_hosts: dict[int, str],
) -> SeparationWitness:
    remote_ids = sorted(op for op, host in operator_hosts.items() if host != local_host_id)
    digests_by_host: dict[str, list[str]] = {}
    for operator_id, info in sorted(health_by_operator.items()):
        digest = str(info.get("machine_digest", ""))
        host = operator_hosts.get(operator_id, "?")
        if digest and digest not in digests_by_host.setdefault(host, []):
            digests_by_host[host].append(digest)

    enriched: list[dict[str, object]] = []
    for probe in probes:
        operator_id = int(probe["operator_id"])
        reported = str(health_by_operator.get(operator_id, {}).get("machine_digest", ""))
        enriched.append(
            {
                **probe,
                "is_remote": operator_hosts.get(operator_id) != local_host_id,
                "reported_machine_digest": reported,
                "machine_differs_from_coordinator": bool(reported) and reported != local_machine_digest,
            }
        )
    probes = enriched

    probe_by_operator = {int(p["operator_id"]): p for p in probes}
    missing = [op for op in remote_ids if op not in probe_by_operator or op not in health_by_operator]
    all_digests = {d for digests in digests_by_host.values() for d in digests}
    observed = len(all_digests)

    if missing:
        return SeparationWitness(
            "FAIL_CLOSED_MISSING_EVIDENCE",
            f"no endpoint probe or health record for remote operators {missing}",
            local_machine_digest,
            digests_by_host,
            tuple(probes),
            observed,
        )

    local_addressed = [
        op
        for op in remote_ids
        if probe_by_operator[op]["peer_is_loopback"] or probe_by_operator[op]["peer_equals_local"]
    ]
    if local_addressed:
        return SeparationWitness(
            "FAIL_COUNTEREXAMPLE",
            f"remote operators {local_addressed} answered on this machine's own address",
            local_machine_digest,
            digests_by_host,
            tuple(probes),
            observed,
        )

    # An operator that reports no fingerprint at all leaves the claim resting on
    # the address alone, which a second interface on this machine would satisfy.
    undigested = [op for op in remote_ids if not str(health_by_operator[op].get("machine_digest", ""))]
    if undigested:
        return SeparationWitness(
            "FAIL_CLOSED_MISSING_EVIDENCE",
            f"remote operators {undigested} report no machine fingerprint",
            local_machine_digest,
            digests_by_host,
            tuple(probes),
            observed,
        )

    shared = [
        op
        for op in remote_ids
        if str(health_by_operator[op].get("machine_digest", "")) == local_machine_digest
    ]
    if shared:
        return SeparationWitness(
            "FAIL_COUNTEREXAMPLE",
            f"remote operators {shared} report this machine's own fingerprint",
            local_machine_digest,
            digests_by_host,
            tuple(probes),
            observed,
        )

    return SeparationWitness(
        "PASS",
        "every remote operator answered from a non-local address and reports a different machine",
        local_machine_digest,
        digests_by_host,
        tuple(probes),
        observed,
    )


@dataclass(frozen=True)
class HostLocalSecretFilePlacementWitness:
    """Check the declared host-local secret directory and public bundle.

    The witness enumerates operator secret files in one configured directory,
    rejects any remote-operator file there, and rejects secret fields in the
    public bundle. It does not scan the whole host, prove secure erasure, show
    hardware non-exportability, or establish independent economic control.
    """

    status: str  # PASS | FAIL_COUNTEREXAMPLE | FAIL_CLOSED_MISSING_EVIDENCE
    reason: str
    local_host_id: str
    local_operators: tuple[int, ...]
    remote_operators: tuple[int, ...]
    secret_files_present: tuple[int, ...]
    public_bundle_clean: bool

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "host_local_secret_file_placement_witness",
            "status": self.status,
            "reason": self.reason,
            "local_host_id": self.local_host_id,
            "local_operators": list(self.local_operators),
            "remote_operators": list(self.remote_operators),
            "secret_files_present": list(self.secret_files_present),
            "public_bundle_carries_no_secret": self.public_bundle_clean,
            "method": "configured secret-directory enumeration + public-bundle field check; not a whole-host scan or erasure proof",
        }


def build_host_local_secret_file_placement_witness(
    local_host_id: str,
    secret_dir: Path,
    public_bundle_path: Path,
    operator_hosts: dict[int, str],
) -> HostLocalSecretFilePlacementWitness:
    local = tuple(sorted(op for op, host in operator_hosts.items() if host == local_host_id))
    remote = tuple(sorted(op for op, host in operator_hosts.items() if host != local_host_id))

    present: list[int] = []
    if secret_dir.exists():
        for path in secret_dir.glob("operator-*.secret.json"):
            digits = "".join(ch for ch in path.stem if ch.isdigit())
            if digits:
                present.append(int(digits))
    present_t = tuple(sorted(present))

    if not public_bundle_path.exists():
        return HostLocalSecretFilePlacementWitness(
            "FAIL_CLOSED_MISSING_EVIDENCE",
            f"public bundle {public_bundle_path.name} not found",
            local_host_id, local, remote, present_t, False,
        )
    bundle = json.loads(public_bundle_path.read_text(encoding="utf-8"))
    text = json.dumps(bundle)
    bundle_clean = not any(field in bundle for field in FORBIDDEN_PUBLIC_FIELDS) and "secret" not in text

    foreign = tuple(op for op in present_t if op in remote)
    missing_local = tuple(op for op in local if op not in present_t)

    if not bundle_clean:
        return HostLocalSecretFilePlacementWitness(
            "FAIL_COUNTEREXAMPLE",
            "public committee bundle still carries seed or secret material",
            local_host_id, local, remote, present_t, False,
        )
    if foreign:
        return HostLocalSecretFilePlacementWitness(
            "FAIL_COUNTEREXAMPLE",
            f"this host holds secret files for remote operators {list(foreign)}",
            local_host_id, local, remote, present_t, bundle_clean,
        )
    if missing_local:
        return HostLocalSecretFilePlacementWitness(
            "FAIL_CLOSED_MISSING_EVIDENCE",
            f"this host is missing its own secret files {list(missing_local)}",
            local_host_id, local, remote, present_t, bundle_clean,
        )
    return HostLocalSecretFilePlacementWitness(
        "PASS",
        "the declared secret directory contains only local-operator files and the public bundle has no secret fields",
        local_host_id, local, remote, present_t, bundle_clean,
    )


@dataclass
class WitnessCheck:
    ok: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "failures": list(self.failures)}


def verify_allocation_witness(
    aggregation: AggregationWitness,
    allocation: AllocationWitness,
    floors: dict[int, int],
    observed_outflow: int,
) -> WitnessCheck:
    failures: list[str] = []

    if allocation.order_id != aggregation.order_id:
        failures.append("order_id mismatch between aggregation and allocation witnesses")
    if allocation.responder_bitmap != aggregation.responder_bitmap:
        failures.append("responder bitmap mismatch between aggregation and allocation witnesses")

    counted = set(aggregation.operator_ids)
    hash_by_operator = dict(zip(aggregation.operator_ids, aggregation.partial_response_hashes))
    host_by_operator = dict(zip(aggregation.operator_ids, aggregation.host_ids))
    allocated = {entry.operator_id for entry in allocation.entries}
    if allocated != counted:
        failures.append(f"allocation covers {sorted(allocated)} but the counted set is {sorted(counted)}")

    seen_debit_ids: set[str] = set()
    seen_return_ids: set[str] = set()
    for entry in allocation.entries:
        if entry.operator_id not in counted:
            failures.append(f"operator {entry.operator_id} is not in the aggregation bitmap")
        if entry.responder_bitmap != aggregation.responder_bitmap:
            failures.append(f"operator {entry.operator_id} carries a foreign responder bitmap")
        if hash_by_operator.get(entry.operator_id) != entry.response_hash:
            failures.append(f"operator {entry.operator_id} response hash differs from the aggregation witness")
        if host_by_operator.get(entry.operator_id) != entry.host_id:
            failures.append(f"operator {entry.operator_id} host differs from the aggregation witness")
        if entry.debit_id is None:
            failures.append(f"operator {entry.operator_id} has no debit identifier")
        elif entry.debit_id in seen_debit_ids:
            failures.append(f"debit identifier {entry.debit_id} allocated more than once")
        else:
            seen_debit_ids.add(entry.debit_id)
        for return_id in tuple(entry.refund_ids) + tuple(entry.funding_ids):
            if return_id in seen_return_ids:
                failures.append(f"return identifier {return_id} allocated more than once")
            else:
                seen_return_ids.add(return_id)
        floor = floors.get(entry.operator_id, 0)
        if entry.net_allocated_outflow < floor:
            failures.append(
                f"operator {entry.operator_id} nets {entry.net_allocated_outflow} below its floor {floor}"
            )

    if allocation.total_allocated > observed_outflow:
        failures.append(
            f"allocated total {allocation.total_allocated} exceeds the realized outflow {observed_outflow}"
        )

    return WitnessCheck(ok=not failures, failures=failures)


def scope_hash(
    buyer: str, resource: str, threshold: int, committee_size: int, hosts: Sequence[str]
) -> str:
    return sha256_hex(
        canonical_json_bytes(
            {
                "buyer": buyer,
                "resource": resource,
                "threshold": threshold,
                "committee_size": committee_size,
                "hosts": sorted(hosts),
            }
        )
    )


def catalog_hash(routes: Sequence[str]) -> str:
    return sha256_hex(canonical_json_bytes(sorted(routes)))
