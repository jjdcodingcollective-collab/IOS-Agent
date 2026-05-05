"""Tests for the compatibility-matrix loader and gate."""

from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wrapper.compatibility import (
    CompatibilityMatrix,
    UnsupportedCombination,
    assert_supported,
    load_matrix,
)


def _write(tmpdir: str, body: str) -> Path:
    p = Path(tmpdir) / "matrix.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class TestParser(unittest.TestCase):
    def test_minimal_matrix(self) -> None:
        with TemporaryDirectory() as tmp:
            p = _write(
                tmp,
                """
                schema_version: 1
                combinations:
                  - source: web
                    target: wrap
                    supported: true
                    phase: 1
                """,
            )
            m = load_matrix(p)
            self.assertEqual(m.schema_version, 1)
            self.assertEqual(len(m.combinations), 1)
            self.assertTrue(m.combinations[0].supported)
            self.assertEqual(m.combinations[0].source, "web")
            self.assertEqual(m.combinations[0].target, "wrap")

    def test_block_scalar_reason_folds(self) -> None:
        with TemporaryDirectory() as tmp:
            p = _write(
                tmp,
                """
                schema_version: 1
                combinations:
                  - source: java
                    target: wrap
                    supported: false
                    phase: null
                    reason: >-
                      Nonsensical combination: Java source
                      has no web layer to wrap.
                """,
            )
            m = load_matrix(p)
            self.assertIn("Nonsensical", m.combinations[0].reason or "")
            self.assertIn("no web layer", m.combinations[0].reason or "")
            self.assertIsNone(m.combinations[0].phase)

    def test_scalar_sequence(self) -> None:
        with TemporaryDirectory() as tmp:
            p = _write(
                tmp,
                """
                schema_version: 1
                source_archetypes:
                  web:
                    label: Web
                    detection_hints:
                      - package.json
                      - index.html
                combinations: []
                """,
            )
            m = load_matrix(p)
            self.assertEqual(m.combinations, ())

    def test_real_matrix_loads(self) -> None:
        # Smoke test the actual file shipped with the repo.
        m = load_matrix()
        self.assertGreaterEqual(m.schema_version, 1)
        self.assertGreater(len(m.combinations), 0)
        # Sanity: at least one entry per declared target mode.
        targets = {c.target for c in m.combinations}
        self.assertIn("wrap", targets)
        self.assertIn("bridge", targets)
        self.assertIn("port", targets)


class TestGate(unittest.TestCase):
    def _matrix_with(self, supported: bool) -> CompatibilityMatrix:
        with TemporaryDirectory() as tmp:
            p = _write(
                tmp,
                f"""
                schema_version: 1
                combinations:
                  - source: web
                    target: wrap
                    supported: {"true" if supported else "false"}
                    phase: 1
                    reason: test reason
                """,
            )
            return load_matrix(p)

    def test_supported_pair_passes(self) -> None:
        m = self._matrix_with(supported=True)
        combo = assert_supported("web", "wrap", matrix=m)
        self.assertTrue(combo.supported)

    def test_unsupported_pair_raises(self) -> None:
        m = self._matrix_with(supported=False)
        with self.assertRaises(UnsupportedCombination) as ctx:
            assert_supported("web", "wrap", matrix=m)
        self.assertIn("phase 1", str(ctx.exception))
        self.assertIn("test reason", str(ctx.exception))
        self.assertIn("docs/mvp-scope.md", str(ctx.exception))

    def test_unknown_pair_raises_with_helpful_message(self) -> None:
        m = self._matrix_with(supported=True)
        with self.assertRaises(UnsupportedCombination) as ctx:
            assert_supported("xyz", "abc", matrix=m)
        self.assertIn("unknown combination", str(ctx.exception))
        self.assertIn("docs/mvp-scope.md", str(ctx.exception))

    def test_real_matrix_blocks_python_to_wrap(self) -> None:
        # Guards against marketing accidentally promoting an excluded source.
        with self.assertRaises(UnsupportedCombination) as ctx:
            assert_supported("python", "wrap")
        self.assertIn("python", str(ctx.exception))
        self.assertIn("wrap", str(ctx.exception))

    def test_real_matrix_has_no_supported_pairs_yet(self) -> None:
        # MVP gate: no combination flips to supported until App Store approval
        # of the reference app, per docs/mvp-scope.md Definition of Done.
        m = load_matrix()
        self.assertEqual(m.supported_pairs(), [])


if __name__ == "__main__":
    unittest.main()
