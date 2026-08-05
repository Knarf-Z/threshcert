from __future__ import annotations

from dataclasses import dataclass
import multiprocessing as mp
import os
from typing import Sequence

from .crypto import (
    Ciphertext,
    PartialDecryption,
    ThresholdKeySet,
    combine_partials,
    create_partial,
    encrypt_capability,
    verify_partial,
    verify_threshold_result,
)
from .ledger import OrderLedger
from .utils import canonical_json_bytes, int_to_bytes, sha256_hex
from .witness import (
    AggregationWitness,
    AllocationEntry,
    AllocationWitness,
    RouteCoverageEvidence,
    bitmap_of,
    catalog_hash,
    scope_hash,
)

COVERED_ROUTES = ("paid_response",)
PROOF_KERNEL = "finite-service-interface-scan/v1"


@dataclass(frozen=True)
class Operator:
    operator_id: int
    share: int
    public_share: int

    def respond(self, ciphertext: Ciphertext, seed: int) -> PartialDecryption:
        return create_partial(self.operator_id, self.share, self.public_share, ciphertext, seed=seed)


@dataclass
class ExecutionResult:
    order_id: str
    buyer: str
    consumer: str
    resource: str
    epoch: int
    responder_ids: list[int]
    response_order: list[int]
    prices: list[int]
    threshold: int
    aggregate_valid: bool
    gateway_accepted: bool
    plaintext: int | None
    ledger: OrderLedger
    used_responses: list[PartialDecryption]
    mode: str
    worker_pids: list[int]

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "buyer": self.buyer,
            "consumer": self.consumer,
            "resource": self.resource,
            "epoch": self.epoch,
            "responder_ids": self.responder_ids,
            "response_order": self.response_order,
            "prices": self.prices,
            "threshold": self.threshold,
            "aggregate_valid": self.aggregate_valid,
            "gateway_accepted": self.gateway_accepted,
            "plaintext": hex(self.plaintext) if self.plaintext is not None else None,
            "ledger": self.ledger.to_dict(),
            "mode": self.mode,
        }


def response_hash(response: PartialDecryption) -> str:
    return sha256_hex(canonical_json_bytes(response.to_dict()))


def build_aggregation_witness(result: ExecutionResult) -> AggregationWitness:
    """Name ``Q_c(h)`` from the transcript rather than inferring it."""
    operator_ids = tuple(response.operator_id for response in result.used_responses)
    hashes = tuple(response_hash(response) for response in result.used_responses)
    plaintext_hash = (
        sha256_hex(int_to_bytes(result.plaintext)) if result.plaintext is not None else ""
    )
    return AggregationWitness(
        order_id=result.order_id,
        buyer=result.buyer,
        resource=result.resource,
        epoch=result.epoch,
        responder_bitmap=bitmap_of(operator_ids),
        operator_ids=operator_ids,
        partial_response_hashes=hashes,
        aggregate_valid=result.aggregate_valid,
        plaintext_hash=plaintext_hash,
    )


def build_allocation_witness(
    result: ExecutionResult,
    aggregation: AggregationWitness,
) -> AllocationWitness:
    """Attribute pairwise disjoint debits and named returns to counted responders.

    Refunds and reimbursements are attributed to the responder set as a whole and
    then split by the recorded per-operator debit, so no return identifier is
    consumed twice.  A sponsor-funded deposit produces no buyer-attributable
    debit, which is what makes the allocation fail its per-member clause.
    """
    ledger = result.ledger
    counted = list(aggregation.operator_ids)
    hash_by_operator = dict(zip(aggregation.operator_ids, aggregation.partial_response_hashes))
    record_by_operator = {record.operator_id: record for record in ledger.responses}

    buyer_funded = ledger.deposit_source == "buyer"
    returns_to_buyer = [record for record in ledger.returns if record.beneficiary == ledger.buyer]
    # Only the returns that offset counted debits are allocated; the refund of the
    # unused escrow offsets no counted debit and is therefore not attributed.
    offsetting = [record for record in returns_to_buyer if record.kind != "refund"]
    offset_total = sum(record.amount for record in offsetting)
    offset_ids = tuple(record.return_id for record in offsetting)

    entries: list[AllocationEntry] = []
    remaining_offset = offset_total
    for position, operator_id in enumerate(counted):
        record = record_by_operator.get(operator_id)
        debit = (record.price if record is not None else 0) if buyer_funded else 0
        external_funding = 0 if buyer_funded else (record.price if record is not None else 0)
        take = min(debit, remaining_offset)
        remaining_offset -= take
        entries.append(
            AllocationEntry(
                operator_id=operator_id,
                responder_bitmap=aggregation.responder_bitmap,
                response_hash=hash_by_operator.get(operator_id, ""),
                debit_id=record.debit_id if record is not None else None,
                debit=debit,
                refund_ids=offset_ids if position == 0 and offset_ids else (),
                refund=take,
                funding_ids=(f"sponsor-{ledger.order_id}",) if external_funding else (),
                external_funding=external_funding,
            )
        )
    return AllocationWitness(
        order_id=result.order_id,
        responder_bitmap=aggregation.responder_bitmap,
        entries=tuple(entries),
    )


def build_coverage_evidence(
    result: ExecutionResult,
    *,
    status: str = "PROVED",
    committee_size: int = 7,
) -> RouteCoverageEvidence:
    bypass_trace = None
    if status == "REFUTED":
        counted = {response.operator_id for response in result.used_responses}
        bypass = [
            record.to_dict()
            for record in result.ledger.responses
            if record.operator_id in counted and record.route not in COVERED_ROUTES
        ]
        bypass_trace = {
            "order_id": result.order_id,
            "unmapped_usable_responses": bypass,
            "required_debit": sum(int(record["price"]) for record in bypass),
        }
    return RouteCoverageEvidence(
        status=status,
        scope_hash=scope_hash(result.buyer, result.resource, result.threshold, committee_size),
        route_catalog_hash=catalog_hash(COVERED_ROUTES),
        covered_routes=COVERED_ROUTES,
        excluded_routes=(),
        proof_kernel=PROOF_KERNEL,
        bypass_trace=bypass_trace,
    )


def _operator_worker(conn, operator: Operator) -> None:
    try:
        while True:
            message = conn.recv()
            if message.get("command") == "stop":
                conn.send({"stopped": True, "pid": os.getpid()})
                return
            if message.get("command") != "respond":
                conn.send({"error": "unknown command", "pid": os.getpid()})
                continue
            ciphertext = Ciphertext.from_dict(message["ciphertext"])
            response = operator.respond(ciphertext, seed=int(message["seed"]))
            conn.send({"response": response.to_dict(), "pid": os.getpid()})
    finally:
        conn.close()


class ThresholdResponseService:
    def __init__(self, keyset: ThresholdKeySet, prices: Sequence[int]) -> None:
        if len(prices) != keyset.n:
            raise ValueError("price count mismatch")
        self.keyset = keyset
        self.prices = list(prices)
        self.operators = [
            Operator(i + 1, keyset.secret_shares[i], keyset.public_shares[i]) for i in range(keyset.n)
        ]

    def public_interface(self) -> list[str]:
        """The complete list of operations an operator process exposes."""
        return ["respond", "stop"]

    def execute(
        self,
        responder_ids: Sequence[int],
        response_order: Sequence[int] | None = None,
        *,
        order_id: str,
        buyer: str = "buyer-1",
        resource: str = "resource-early-plaintext",
        epoch: int = 1,
        seed: int = 1,
        deposit_source: str = "buyer",
        ablation: str | None = None,
        process_mode: bool = False,
    ) -> ExecutionResult:
        if len(set(responder_ids)) != len(responder_ids):
            raise ValueError("duplicate responder")
        if len(responder_ids) < self.keyset.threshold:
            raise ValueError("coalition below threshold")
        order = list(response_order or responder_ids)
        if set(order) != set(responder_ids):
            raise ValueError("response order mismatch")

        ciphertext = encrypt_capability(self.keyset.public_key, buyer, resource, order_id, seed=seed)
        price_map = {i + 1: price for i, price in enumerate(self.prices)}
        ledger = OrderLedger.open(order_id, buyer, price_map, source=deposit_source)
        responses: dict[int, PartialDecryption] = {}
        worker_pids: list[int] = []

        process_parents: dict[int, object] = {}
        processes: list[mp.Process] = []
        if process_mode:
            context = mp.get_context("spawn" if os.name == "nt" else "fork")
            for operator in self.operators:
                parent, child = context.Pipe()
                process = context.Process(target=_operator_worker, args=(child, operator), daemon=True)
                process.start()
                child.close()
                process_parents[operator.operator_id] = parent
                processes.append(process)

        try:
            for position, operator_id in enumerate(order):
                operator = self.operators[operator_id - 1]
                response_seed = seed * 1000 + operator_id * 31 + position
                if process_mode:
                    parent = process_parents[operator_id]
                    parent.send({"command": "respond", "ciphertext": ciphertext.to_dict(), "seed": response_seed})
                    reply = parent.recv()
                    response = PartialDecryption.from_dict(reply["response"])
                    worker_pids.append(int(reply["pid"]))
                else:
                    response = operator.respond(ciphertext, seed=response_seed)
                valid = verify_partial(operator.public_share, ciphertext, response)
                digest = response_hash(response)

                if ablation == "bypass":
                    ledger.record_bypass(operator_id, digest, valid, valid)
                elif ablation == "early_release":
                    ledger.release_before_credit(operator_id, digest, valid, valid)
                elif ablation == "untimed":
                    ledger.record_untimed(operator_id, digest, valid, valid)
                else:
                    ledger.credit_before_release(operator_id, digest, valid, valid)
                responses[operator_id] = response

            used = [responses[operator_id] for operator_id in order[: self.keyset.threshold]]
            all_valid = all(
                verify_partial(self.keyset.public_shares[response.operator_id - 1], ciphertext, response)
                for response in used
            )
            plaintext: int | None = None
            aggregate_valid = False
            if all_valid:
                plaintext = combine_partials(ciphertext, used, self.keyset.threshold)
                aggregate_valid = verify_threshold_result(ciphertext, plaintext)

            consumer = "mallory" if ablation == "wrong_buyer" else buyer
            gateway_accepted = aggregate_valid and consumer == ciphertext.buyer
            if gateway_accepted:
                ledger.mark_success()

            ledger.finalize_refund()
            if ablation == "reimbursement" and gateway_accepted:
                ledger.add_reimbursement(ledger.credits_total, accounted=False)

            return ExecutionResult(
                order_id=order_id,
                buyer=buyer,
                consumer=consumer,
                resource=resource,
                epoch=epoch,
                responder_ids=list(responder_ids),
                response_order=list(order),
                prices=list(self.prices),
                threshold=self.keyset.threshold,
                aggregate_valid=aggregate_valid,
                gateway_accepted=gateway_accepted,
                plaintext=plaintext,
                ledger=ledger,
                used_responses=used,
                mode="multiprocess" if process_mode else "in_process",
                worker_pids=worker_pids,
            )
        finally:
            for parent in process_parents.values():
                try:
                    parent.send({"command": "stop"})
                    parent.recv()
                except (BrokenPipeError, EOFError, ConnectionResetError, OSError):
                    pass
                parent.close()
            for process in processes:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
