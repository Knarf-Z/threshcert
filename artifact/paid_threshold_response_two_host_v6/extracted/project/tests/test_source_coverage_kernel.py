from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from source_coverage_kernel import analyze  # noqa: E402


class SourceCoverageKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = analyze(ROOT)

    def test_baseline_passes_every_check(self) -> None:
        self.assertEqual(self.result["status"], "PROVED_IN_RESTRICTED_SOURCE_MODEL")
        self.assertTrue(all(self.result["checks"].values()))

    def test_consequential_obligations_are_source_discharged(self) -> None:
        self.assertEqual(
            {
                name: item["status"]
                for name, item in self.result["obligations"].items()
            },
            {
                "LC1_SOURCE_PRODUCER_COMPLETENESS": "PROVED_IN_RESTRICTED_SOURCE_MODEL",
                "LC3_SOURCE_SECRET_CONFINEMENT": "PROVED_IN_RESTRICTED_SOURCE_MODEL",
                "LC5_SOURCE_LIFECYCLE_CLOSURE": "PROVED_IN_RESTRICTED_SOURCE_MODEL",
                "LC7_SOURCE_DELIVERY_ROOT": "PROVED_IN_RESTRICTED_SOURCE_MODEL",
            },
        )

    def test_every_rule_is_derived_from_recomputed_premises(self) -> None:
        self.assertTrue(
            all(
                item["status"] == "DERIVED"
                for item in self.result["rule_derivations"].values()
            )
        )
        self.assertTrue(self.result["checks"]["UNTRUSTED_INVENTORY_RECOMPUTED"])
        self.assertTrue(
            self.result["checks"]["CPYTHON_BYTECODE_REPRESENTATION_CROSSCHECK"]
        )
    def test_claim_keeps_environment_and_off_language_limits_explicit(self) -> None:
        exclusions = " ".join(self.result["not_claimed"])
        self.assertIn("operating-system", exclusions)
        self.assertIn("hardware non-exportability", exclusions)
        self.assertIn("outside RSP-V6", exclusions)
        self.assertIn("deployment-wide", exclusions)


if __name__ == "__main__":
    unittest.main()