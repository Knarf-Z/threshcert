from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_penalty_certificate_checks import evaluate  # noqa: E402


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
            "deployment/contracts/BondedKeyperSlasher.sol",
            "deployment/rolling-shutter/evidence-exporter/main.go",
            "deployment/rolling-shutter/docker-compose.7.yml",
            "deployment/scripts/submit-evidence.ts",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

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

        self.assertEqual(deployment["schema"], "threshcert-bonded-keyper-deployment-v1")
        self.assertEqual(job["schema"], "threshcert-release-job-v1")
        self.assertEqual(evidence["schema"], "threshcert-shutter-evidence-v1")
        self.assertEqual(slashing["schema"], "threshcert-slashing-result-v1")
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
