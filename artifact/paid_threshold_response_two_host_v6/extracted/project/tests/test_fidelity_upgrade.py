from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(HERE / "scripts"))

from fidelity_core import build_manifest, manifest_digest, verify_tree  # noqa: E402


OPERATOR = '''from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        self.send_response(code)
    def do_GET(self):
        if self.path != "/health":
            self._send(404, {})
            return
        self._send(200, {})
    def do_POST(self):
        if self.path != "/respond":
            self._send(404, {})
            return
        self._send(200, {})
def serve():
    return ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
'''


class FidelityTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        (root / "src" / "ptr_v3").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "powershell").mkdir()
        (root / "src" / "ptr_v3" / "operator_server.py").write_text(OPERATOR, encoding="utf-8")
        (root / "scripts" / "driver.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "powershell" / "Start-Operators.ps1").write_text("Write-Host ok\n", encoding="utf-8")

    def test_baseline_and_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            manifest = build_manifest(root)
            digest = manifest_digest(manifest)
            self.assertEqual(verify_tree(root, manifest, expected_manifest_digest=digest)["status"], "PASS")

            path = root / "src" / "ptr_v3" / "operator_server.py"
            path.write_text(path.read_text(encoding="utf-8") + "\ndef x(s): return eval(s)\n", encoding="utf-8")
            result = verify_tree(root, manifest, expected_manifest_digest=digest)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["checks"]["NO_DYNAMIC_EXEC"])

    def test_extra_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            manifest = build_manifest(root)
            digest = manifest_digest(manifest)
            (root / "src" / "ptr_v3" / "rogue.py").write_text("x=1\n", encoding="utf-8")
            result = verify_tree(root, manifest, expected_manifest_digest=digest)
            self.assertFalse(result["checks"]["FILE_SET_EXACT"])


if __name__ == "__main__":
    unittest.main()
