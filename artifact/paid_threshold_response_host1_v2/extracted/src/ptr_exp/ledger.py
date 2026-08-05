from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResponseRecord:
    """One response emission and the payment events attached to it.

    ``credit_step`` and ``release_step`` carry the atomicity evidence read by
    (B3).  ``credit_step is None`` together with ``ordering_evidence`` False
    means the transcript does not record the order at all, which is an
    evidentiary gap rather than a counterexample.
    """

    operator_id: int
    price: int
    route: str
    response_hash: str
    credit_step: int | None
    release_step: int
    proof_valid: bool
    usable: bool
    debit_id: str | None
    ordering_evidence: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "operator_id": self.operator_id,
            "price": self.price,
            "route": self.route,
            "response_hash": self.response_hash,
            "credit_step": self.credit_step,
            "release_step": self.release_step,
            "proof_valid": self.proof_valid,
            "usable": self.usable,
            "debit_id": self.debit_id,
            "ordering_evidence": self.ordering_evidence,
        }


@dataclass
class ReturnRecord:
    """A return into some principal's control class.

    ``kind`` is one of ``refund``, ``reimbursement`` or ``external_funding``.
    ``beneficiary`` names the principal the value flows to; only returns whose
    beneficiary lies in the named-buyer control closure are netted against the
    buyer's debit.
    """

    return_id: str
    kind: str
    beneficiary: str
    amount: int
    accounted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "return_id": self.return_id,
            "kind": self.kind,
            "beneficiary": self.beneficiary,
            "amount": self.amount,
            "accounted": self.accounted,
        }


@dataclass
class OrderLedger:
    order_id: str
    buyer: str
    prices: dict[int, int]
    deposit_source: str
    deposit: int
    buyer_debit: int
    sponsor_funding: int
    escrow_remaining: int
    responses: list[ResponseRecord] = field(default_factory=list)
    returns: list[ReturnRecord] = field(default_factory=list)
    operator_credits: dict[int, int] = field(default_factory=dict)
    operator_debit_ids: dict[int, str] = field(default_factory=dict)
    step: int = 0
    success_step: int | None = None

    @classmethod
    def open(
        cls,
        order_id: str,
        buyer: str,
        prices: dict[int, int],
        source: str = "buyer",
    ) -> "OrderLedger":
        if any(price < 0 for price in prices.values()):
            raise ValueError("negative price")
        deposit = sum(prices.values())
        buyer_debit = deposit if source == "buyer" else 0
        sponsor_funding = deposit if source != "buyer" else 0
        return cls(
            order_id=order_id,
            buyer=buyer,
            prices=dict(prices),
            deposit_source=source,
            deposit=deposit,
            buyer_debit=buyer_debit,
            sponsor_funding=sponsor_funding,
            escrow_remaining=deposit,
        )

    def _tick(self) -> int:
        self.step += 1
        return self.step

    def _debit_id(self, operator_id: int) -> str:
        return f"debit-{self.order_id}-op{operator_id}"

    def credit_before_release(
        self,
        operator_id: int,
        response_hash: str,
        proof_valid: bool,
        usable: bool,
        route: str = "paid_response",
        price_override: int | None = None,
    ) -> ResponseRecord:
        if operator_id in self.operator_credits:
            raise ValueError("operator already credited")
        price = self.prices[operator_id] if price_override is None else price_override
        if self.escrow_remaining < price:
            raise ValueError("insufficient escrow")
        credit_step = self._tick()
        self.escrow_remaining -= price
        self.operator_credits[operator_id] = price
        debit_id = self._debit_id(operator_id)
        self.operator_debit_ids[operator_id] = debit_id
        release_step = self._tick()
        record = ResponseRecord(
            operator_id=operator_id,
            price=price,
            route=route,
            response_hash=response_hash,
            credit_step=credit_step,
            release_step=release_step,
            proof_valid=proof_valid,
            usable=usable,
            debit_id=debit_id,
        )
        self.responses.append(record)
        return record

    def release_before_credit(
        self,
        operator_id: int,
        response_hash: str,
        proof_valid: bool,
        usable: bool,
        route: str = "paid_response",
    ) -> ResponseRecord:
        """Break atomicity only: the declared paid route is kept, so (B5) is
        untouched and only (B3) sees a counterexample."""
        release_step = self._tick()
        price = self.prices[operator_id]
        if self.escrow_remaining < price:
            raise ValueError("insufficient escrow")
        credit_step = self._tick()
        self.escrow_remaining -= price
        self.operator_credits[operator_id] = price
        debit_id = self._debit_id(operator_id)
        self.operator_debit_ids[operator_id] = debit_id
        record = ResponseRecord(
            operator_id=operator_id,
            price=price,
            route=route,
            response_hash=response_hash,
            credit_step=credit_step,
            release_step=release_step,
            proof_valid=proof_valid,
            usable=usable,
            debit_id=debit_id,
        )
        self.responses.append(record)
        return record

    def record_untimed(
        self,
        operator_id: int,
        response_hash: str,
        proof_valid: bool,
        usable: bool,
    ) -> ResponseRecord:
        """A paid response whose credit/release order was never recorded."""
        record = self.credit_before_release(operator_id, response_hash, proof_valid, usable)
        record.ordering_evidence = False
        return record

    def record_bypass(
        self,
        operator_id: int,
        response_hash: str,
        proof_valid: bool,
        usable: bool,
    ) -> ResponseRecord:
        """An unmapped route with a zero required debit.

        The zero debit is still credited before release, so payment atomicity
        holds vacuously and only (B5) sees a counterexample.
        """
        return self.credit_before_release(
            operator_id,
            response_hash,
            proof_valid,
            usable,
            route="bypass_response",
            price_override=0,
        )

    def mark_success(self) -> None:
        self.success_step = self._tick()

    def finalize_refund(self) -> None:
        """Return the unused escrow to whoever funded it."""
        if self.escrow_remaining:
            amount = self.escrow_remaining
            self.escrow_remaining = 0
            self.returns.append(
                ReturnRecord(
                    return_id=f"refund-{self.order_id}",
                    kind="refund",
                    beneficiary=self.buyer if self.deposit_source == "buyer" else self.deposit_source,
                    amount=amount,
                    accounted=True,
                )
            )
            self._tick()

    def add_reimbursement(self, amount: int, accounted: bool = False) -> None:
        if amount < 0:
            raise ValueError("negative reimbursement")
        self.returns.append(
            ReturnRecord(
                return_id=f"reimbursement-{self.order_id}",
                kind="reimbursement",
                beneficiary=self.buyer,
                amount=amount,
                accounted=accounted,
            )
        )
        self._tick()

    @property
    def credits_total(self) -> int:
        return sum(self.operator_credits.values())

    def returns_to_buyer(self, kind: str | None = None) -> int:
        return sum(
            record.amount
            for record in self.returns
            if record.beneficiary == self.buyer and (kind is None or record.kind == kind)
        )

    @property
    def refund_to_buyer(self) -> int:
        return self.returns_to_buyer("refund")

    @property
    def reimbursement_to_buyer(self) -> int:
        return self.returns_to_buyer("reimbursement")

    @property
    def named_buyer_net_outflow(self) -> int:
        """O = max{0, D - R - F} over the named-buyer control closure."""
        return max(0, self.buyer_debit - self.returns_to_buyer())

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "buyer": self.buyer,
            "deposit_source": self.deposit_source,
            "deposit": self.deposit,
            "buyer_debit": self.buyer_debit,
            "sponsor_funding": self.sponsor_funding,
            "refund_to_buyer": self.refund_to_buyer,
            "reimbursement_to_buyer": self.reimbursement_to_buyer,
            "credits_total": self.credits_total,
            "named_buyer_net_outflow": self.named_buyer_net_outflow,
            "success_step": self.success_step,
            "responses": [record.to_dict() for record in self.responses],
            "returns": [record.to_dict() for record in self.returns],
        }
