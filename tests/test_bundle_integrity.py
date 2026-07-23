from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "deployment" / "scripts"))

from run_penalty_certificate_checks import evaluate  # noqa: E402
from run_production_evidence_audit import (  # noqa: E402
    audit_production_evidence,
    evaluate_member,
)
from verify_chiado_certificate import build_certificate  # noqa: E402
from verify_chiado_certificate_rewarded import (  # noqa: E402
    build_certificate as build_certificate_rewarded,
)


class BundleIntegrityTests(unittest.TestCase):
    def test_no_secret_or_environment_payloads(self) -> None:
        forbidden_files = {".env", "id_rsa", "id_ed25519"}
        forbidden_directories = {".venv", "venv", ".idea", "node_modules"}
        for path in ROOT.rglob("*"):
            relative = path.relative_to(ROOT)
            self.assertNotIn(relative.name, forbidden_files)
            self.assertTrue(forbidden_directories.isdisjoint(relative.parts), relative)

    def test_scaling_repeat_bundle(self) -> None:
        paths = sorted((ROOT / "results" / "solver_scaling_repeats").glob("*.csv"))
        self.assertEqual(len(paths), 10)
        for path in paths:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 6)
            self.assertEqual([int(row["n"]) for row in rows], [8, 10, 12, 14, 16, 18])

    def test_real_deployment_sources_present(self) -> None:
        required = [
            "data/production_keyper_set_20260613.json",
            "data/production_member_evidence.csv",
            "scripts/run_production_evidence_audit.py",
            "scripts/verify_production_snapshot_live.py",
            "deployment/contracts/BondedKeyperSlasher.sol",
            "deployment/rolling-shutter/evidence-exporter/main.go",
            "deployment/rolling-shutter/docker-compose.7.yml",
            "deployment/scripts/submit-evidence.ts",
            "deployment/scripts/verify_chiado_certificate.py",
            "deployment/scripts/verify-chiado-live.ts",
            "deployment/certificates/chiado-execution-certificate.json",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_production_snapshot_is_pinned_and_member_specific(self) -> None:
        snapshot = json.loads(
            (ROOT / "data/shutter_keyper_snapshot.json").read_text(encoding="utf-8")
        )
        provenance = json.loads(
            (ROOT / "data/production_keyper_set_20260613.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(snapshot["archival_block_number"], 46_666_718)
        self.assertEqual(
            snapshot["archival_block_hash"],
            "0x574ec26ee7b2e2bfddd991bf99d37a79455428bc4dfe342b0ccf55d071229b60",
        )
        self.assertEqual(snapshot["active_keyper_set_index"], 10)
        self.assertEqual(
            snapshot["active_keyper_set_contract"].lower(),
            "0xe817e77109e2e6a8025eb30db3542ec18bbde828",
        )
        self.assertEqual(snapshot["committee_size"], 7)
        self.assertEqual(snapshot["threshold_count"], 4)
        self.assertEqual(len(set(map(str.lower, snapshot["member_addresses"]))), 7)
        self.assertEqual(
            list(map(str.lower, snapshot["member_addresses"])),
            list(map(str.lower, provenance["keyper_set"]["members"])),
        )
        self.assertTrue(provenance["keyper_set"]["finalized"])
        self.assertEqual(provenance["keyper_set"]["activation_block"], 46_271_880)

    def test_production_evidence_audit(self) -> None:
        result = audit_production_evidence()
        self.assertEqual(result["snapshot"]["membership_records_verified"], 7)
        self.assertEqual(
            result["certificate"]["ordered_certified_member_floors"],
            ["0"] * 7,
        )
        self.assertEqual(result["certificate"]["threshold_cover_lower_bound"], "0")
        self.assertEqual(result["certificate"]["positive_member_floors"], 0)
        self.assertEqual(
            result["certificate"][
                "minimum_positive_members_for_positive_certificate"
            ],
            4,
        )
        self.assertEqual(
            result["certificate"]["additional_positive_member_floors_needed"], 4
        )
        self.assertEqual(
            result["activation"]["status"], "NOT_CERTIFIED_USE_THRESHOLD_COVER"
        )
        self.assertEqual(
            result["claim"]["actual_member_resistance"], "UNKNOWN_NOT_MEASURED"
        )
        self.assertTrue(
            all(member["direct_path_gap"] for member in result["members"])
        )
        self.assertTrue(
            all(member["penalty_path_gap"] for member in result["members"])
        )

        recorded_path = ROOT / "results" / "production_evidence_audit.json"
        recorded_bytes = recorded_path.read_bytes()
        self.assertTrue(recorded_bytes.endswith(b"\n"))
        self.assertNotIn(b"\r\n", recorded_bytes)
        recorded = json.loads(recorded_bytes)
        self.assertEqual(recorded, result)

    def test_production_evidence_gates_require_auditable_material(self) -> None:
        with (ROOT / "data/production_member_evidence.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            row = next(csv.DictReader(handle))

        claimed_without_evidence = dict(row)
        claimed_without_evidence["base_resistance_floor"] = "25"
        self.assertEqual(
            evaluate_member(claimed_without_evidence)["certified_member_floor"], "0"
        )

        direct = dict(claimed_without_evidence)
        direct["base_resistance_evidence_status"] = "CERTIFIED"
        self.assertEqual(evaluate_member(direct)["certified_member_floor"], "25")

        nominal_only = dict(row)
        nominal_only["nominal_penalty_floor"] = "20"
        nominal_only["joint_enforcement_probability_floor"] = "0.5"
        self.assertEqual(evaluate_member(nominal_only)["certified_member_floor"], "0")

        complete_penalty = dict(nominal_only)
        for field in (
            "attribution_evidence_status",
            "forfeiture_evidence_status",
            "enforcement_evidence_status",
        ):
            complete_penalty[field] = "CERTIFIED"
        self.assertEqual(
            evaluate_member(complete_penalty)["certified_member_floor"], "10"
        )

    def test_public_deployment_records_are_cross_consistent(self) -> None:
        deployment_root = ROOT / "deployment"
        deployment = json.loads(
            (deployment_root / "results/deployment-chiado.json").read_text(
                encoding="utf-8"
            )
        )
        job = json.loads(
            (deployment_root / "results/job-chiado.json").read_text(encoding="utf-8")
        )
        evidence = json.loads(
            (deployment_root / "evidence/shutter-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        slashing = json.loads(
            (deployment_root / "results/slashing-chiado.json").read_text(
                encoding="utf-8"
            )
        )
        keyper_set = json.loads(
            (deployment_root / "runtime/keyper-set.json").read_text(encoding="utf-8")
        )

        self.assertEqual(deployment["schema"], "fc-bonded-keyper-deployment-v1")
        self.assertEqual(job["schema"], "fc-release-job-v1")
        self.assertEqual(evidence["schema"], "fc-shutter-evidence-v1")
        self.assertEqual(slashing["schema"], "fc-slashing-result-v1")
        self.assertEqual({deployment["chainId"], job["chainId"], slashing["chainId"]}, {10200})
        self.assertEqual(
            {deployment["contract"].lower(), job["contract"].lower(), slashing["contract"].lower()},
            {"0x3c16dd5689d67d51c076fe80cb7189041c107721"},
        )

        self.assertEqual(deployment["committeeSize"], 7)
        self.assertEqual(deployment["threshold"], 4)
        self.assertEqual(keyper_set["threshold"], 4)
        self.assertEqual(evidence["threshold"], 4)
        self.assertEqual(evidence["numKeypers"], 7)
        self.assertEqual(deployment["totalBondWei"], "7000000000000")
        self.assertEqual(deployment["initialCertificateWei"], "4000000000000")

        deployment_addresses = [
            item["address"].lower()
            for item in sorted(deployment["keypers"], key=lambda item: item["index"])
        ]
        set_addresses = [
            item["address"].lower()
            for item in sorted(keyper_set["keypers"], key=lambda item: item["index"])
        ]
        share_addresses = [
            item["keyperAddress"].lower()
            for item in sorted(evidence["shares"], key=lambda item: item["memberIndex"])
        ]
        self.assertEqual(len(set(deployment_addresses)), 7)
        self.assertEqual(deployment_addresses, set_addresses)
        self.assertEqual(deployment_addresses, share_addresses)

        transactions = [deployment["transactions"]["deploy"]]
        transactions.extend(deployment["transactions"]["registrations"])
        transactions.append(deployment["transactions"]["freeze"])
        self.assertEqual(len(transactions), 9)
        self.assertTrue(all(item["status"] == "success" for item in transactions))

        self.assertEqual(job["jobId"], slashing["jobId"])
        self.assertEqual(job["identityHash"], evidence["identityHash"])
        self.assertEqual(job["identityPreimage"], evidence["identityPreimage"])
        self.assertEqual(job["eon"], evidence["eon"])
        self.assertTrue(evidence["aggregateKeyValid"])
        self.assertTrue(evidence["reconstructionMatchesStoredKey"])
        self.assertEqual(len(evidence["shares"]), 7)
        self.assertTrue(all(item["shareValid"] for item in evidence["shares"]))
        self.assertTrue(all(item["nativeSignatureValid"] for item in evidence["shares"]))

        member = evidence["shares"][slashing["memberIndex"]]
        self.assertEqual(slashing["keyperAddress"].lower(), member["keyperAddress"].lower())
        self.assertEqual(slashing["shareHash"], member["shareHash"])
        self.assertEqual(slashing["memberSignatureHash"], member["nativeSignatureHash"])
        self.assertEqual(slashing["verifier"].lower(), deployment["verifier"].lower())
        self.assertEqual(
            int(job["releaseTime"]) - int(slashing["observedAt"]),
            int(slashing["prematureBySeconds"]),
        )
        self.assertGreater(int(slashing["prematureBySeconds"]), 0)
        self.assertEqual(slashing["certificateBeforeWei"], "4000000000000")
        self.assertEqual(slashing["certificateAfterWei"], "3000000000000")
        self.assertEqual(slashing["transaction"]["status"], "success")
        self.assertEqual(
            slashing["transaction"]["hash"],
            "0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd",
        )

    def test_machine_readable_chiado_certificate(self) -> None:
        certificate_path = (
            ROOT / "deployment" / "certificates" / "chiado-execution-certificate.json"
        )
        recorded = json.loads(certificate_path.read_text(encoding="utf-8"))
        self.assertEqual(recorded, build_certificate())
        self.assertEqual(
            recorded["claim"]["status"],
            "POSITIVE_WITHIN_RECORDED_TESTNET_MECHANISM",
        )
        self.assertEqual(recorded["certificate"]["before"]["value"], "4000000000000")
        self.assertEqual(recorded["certificate"]["after"]["value"], "3000000000000")
        self.assertIsNone(
            recorded["claim"]["unconditionalProductionAttackCostLowerBound"]
        )
        self.assertEqual(
            recorded["claim"]["productionShutterCertificate"],
            "NOT_CERTIFIED",
        )

    def test_machine_readable_chiado_certificate_rewarded(self) -> None:
        certificate_path = (
            ROOT
            / "deployment"
            / "certificates"
            / "chiado-execution-certificate-rewarded.json"
        )
        recorded = json.loads(certificate_path.read_text(encoding="utf-8"))
        self.assertEqual(recorded, build_certificate_rewarded())
        self.assertEqual(
            recorded["claim"]["status"],
            "POSITIVE_WITHIN_RECORDED_TESTNET_MECHANISM",
        )
        self.assertEqual(recorded["certificate"]["before"]["value"], "80000000000000000")
        self.assertEqual(recorded["certificate"]["after"]["value"], "60000000000000000")
        self.assertTrue(recorded["enforcementIncentive"]["rewardCoversGasCost"])
        self.assertGreater(int(recorded["enforcementIncentive"]["netSubmitterGainWei"]), 0)
        self.assertEqual(
            recorded["claim"]["productionShutterCertificate"],
            "NOT_CERTIFIED",
        )

    def test_public_record_references_are_portable(self) -> None:
        result_root = ROOT / "deployment/results"
        job = json.loads((result_root / "job-chiado.json").read_text(encoding="utf-8"))
        slashing = json.loads(
            (result_root / "slashing-chiado.json").read_text(encoding="utf-8")
        )
        references = [job["deploymentFile"]]
        references.extend(
            slashing[name] for name in ("deploymentFile", "jobFile", "evidenceFile")
        )
        for reference in references:
            self.assertFalse(PureWindowsPath(reference).is_absolute(), reference)
            self.assertFalse(PurePosixPath(reference).is_absolute(), reference)
            self.assertNotIn("\\", reference)

    def test_dune_provenance_references_existing_files(self) -> None:
        provenance_path = ROOT / "data" / "dune" / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        for dataset in provenance["datasets"]:
            referenced = provenance_path.parent / dataset["file"]
            self.assertTrue(referenced.is_file(), referenced)
            if dataset["query_id"] is not None:
                self.assertEqual(
                    dataset["query_url"],
                    f"https://dune.com/queries/{dataset['query_id']}",
                )
        self.assertFalse(provenance["query_sql_included"])

    def test_selected_coverage_rows_match_full_curve(self) -> None:
        raw = ROOT / "data" / "dune" / "raw"
        with (raw / "certificate_coverage_curve.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            curve = {
                row["certified_per_keyper_resistance_usd"]: row
                for row in csv.DictReader(handle)
            }
        with (raw / "04_empirical_target_coverage_selected.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            selected = list(csv.DictReader(handle))
        self.assertEqual(len(selected), 7)
        for row in selected:
            self.assertEqual(curve[row["certified_per_keyper_resistance_usd"]], row)

    def test_penalty_evidence_gate(self) -> None:
        complete = ROOT / "data" / "evidence_ledger_controlled_penalty.csv"
        incomplete = (
            ROOT / "data" / "evidence_ledger_controlled_penalty_one_unattributable.csv"
        )
        _, complete_value = evaluate(complete, 4)
        _, incomplete_value = evaluate(incomplete, 4)
        self.assertEqual(complete_value, 10_000)
        self.assertEqual(incomplete_value, 7_500)


if __name__ == "__main__":
    unittest.main()
