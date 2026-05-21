"""Tests for the encryption export compliance scanner (MVP §4.6)."""

from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter.compliance.api_scanner import (
    ENCRYPTION_EXPORT_CATEGORY,
    ENCRYPTION_EXPORT_DOC_URL,
    scan_all,
    to_findings,
)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class TestEncryptionExportScan(unittest.TestCase):

    # ── detects known crypto imports ──────────────────────────────────────

    def test_detects_crypto_js(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/util.ts", "import CryptoJS from 'crypto-js';")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertTrue(len(enc) >= 1)
        self.assertEqual(enc[0].pattern, "crypto-js")

    def test_detects_subtle_crypto_api(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/crypto.ts",
                   "const key = await crypto.subtle.generateKey(algo, true, ['encrypt']);")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertTrue(len(enc) >= 1)
        patterns = {f.pattern for f in enc}
        self.assertIn("crypto.subtle", patterns)

    def test_detects_node_forge(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/pki.ts", "import forge from 'node-forge';")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertTrue(any(f.pattern == "node-forge" for f in enc))

    def test_detects_tweetnacl(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/box.ts", "import nacl from 'tweetnacl';")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertTrue(any(f.pattern == "tweetnacl" for f in enc))

    def test_detects_openpgp(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/pgp.ts", "import * as openpgp from 'openpgp';")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertTrue(any(f.pattern == "openpgp" for f in enc))

    # ── no false positives ────────────────────────────────────────────────

    def test_no_finding_for_math_random(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/util.ts", "const r = Math.random();")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertEqual(enc, [])

    def test_no_finding_for_https_fetch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/api.ts",
                   "const res = await fetch('https://api.example.com/data');")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertEqual(enc, [])

    def test_skips_node_modules(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "node_modules/crypto-js/index.js",
                   "import CryptoJS from 'crypto-js';")
            _write(root, "src/clean.ts", "const x = 1;")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertEqual(enc, [])

    def test_skips_comment_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/util.ts",
                   "// import CryptoJS from 'crypto-js'; // disabled\n"
                   "const x = 1;\n")
            findings = scan_all(root)
        enc = [f for f in findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        self.assertEqual(enc, [])


class TestToFindingsEncryption(unittest.TestCase):
    """Verify to_findings() emits Layer-B warnings for EncryptionExport."""

    def _enc_findings(self, pattern: str = "crypto-js") -> list:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/util.ts", f"import CryptoJS from '{pattern}';")
            api_findings = scan_all(root)
        enc = [f for f in api_findings if f.category == ENCRYPTION_EXPORT_CATEGORY]
        return to_findings(enc)

    def test_severity_is_warning_not_blocker(self) -> None:
        out = self._enc_findings()
        self.assertTrue(len(out) > 0)
        for f in out:
            self.assertEqual(f.severity, "warning")

    def test_category_prefix(self) -> None:
        out = self._enc_findings()
        for f in out:
            self.assertTrue(f.category.startswith("compliance.encryption-export."))

    def test_doc_link_is_encryption_url(self) -> None:
        out = self._enc_findings()
        for f in out:
            self.assertEqual(f.doc_link, ENCRYPTION_EXPORT_DOC_URL)

    def test_reason_mentions_ITSAppUsesNonExemptEncryption(self) -> None:
        out = self._enc_findings()
        self.assertTrue(any("ITSAppUsesNonExemptEncryption" in f.reason for f in out))

    def test_recommended_fix_mentions_ERN(self) -> None:
        out = self._enc_findings()
        self.assertTrue(any("ERN" in f.recommended_fix for f in out))

    def test_privacy_manifest_findings_still_blocker(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts", "localStorage.setItem('key', 'val');")
            api_findings = scan_all(root)
        privacy = [f for f in api_findings if f.category != ENCRYPTION_EXPORT_CATEGORY]
        out = to_findings(privacy)
        self.assertTrue(len(out) > 0)
        for f in out:
            self.assertEqual(f.severity, "blocker")

    def test_mixed_findings_correct_severities(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/app.ts",
                   "localStorage.setItem('k','v');\n"
                   "import CryptoJS from 'crypto-js';\n")
            all_findings = scan_all(root)
        out = to_findings(all_findings)
        blockers = [f for f in out if f.severity == "blocker"]
        warnings = [f for f in out if f.severity == "warning"]
        self.assertTrue(len(blockers) >= 1)
        self.assertTrue(len(warnings) >= 1)
