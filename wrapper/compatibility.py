"""
Compatibility matrix loader and gate.

Loads `config/compatibility-matrix.yaml` and answers two questions:

  1. Is (source_archetype, target_mode) a supported MVP combination?
  2. If not, what message do we show the user?

A tiny hand-written YAML reader is used so we don't need to add PyYAML to
the project for one config file. It supports only the subset of YAML this
matrix uses: top-level mappings, nested mappings, sequences of mappings,
scalar strings/ints/booleans/null, and `>-`/`|` block scalars folded into
single strings. Anything outside that subset will raise.

If the matrix file grows beyond what this parser handles, swap to PyYAML
and delete the parser. Nothing else in the wrapper consumes YAML today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Tiny YAML reader (single file, narrow subset)
# ---------------------------------------------------------------------------

_BOOL = {"true": True, "false": False}
_NULL = {"null", "~", ""}


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if not s:
        return None
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.lower() in _BOOL:
        return _BOOL[s.lower()]
    if s.lower() in _NULL:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        return s


def _strip_comment(line: str) -> str:
    in_str = None
    out = []
    for ch in line:
        if in_str:
            out.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    """Parse a block (mapping or sequence) at the given indent. Returns (value, next_index)."""
    i = start
    # Skip blanks/comments.
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i += 1
    if i >= len(lines):
        return None, i

    first = lines[i]
    first_indent = _indent(first)
    if first_indent < indent:
        return None, i

    is_seq = first.lstrip().startswith("- ")
    if is_seq:
        items: list[Any] = []
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            cur_indent = _indent(line)
            if cur_indent < first_indent or not stripped.startswith("- "):
                break
            rest = stripped[2:]
            # Scalar sequence item: "- foo" with no key. Distinguish from
            # mapping item ("- key: value") by checking for a top-level colon.
            if not re.match(r"^[A-Za-z_][\w\-]*\s*:", rest):
                items.append(_parse_scalar(rest))
                i += 1
                continue
            # Mapping item: rewrite the line so the mapping parser sees the
            # first key at virtual_indent and recurses normally.
            virtual_indent = cur_indent + 2
            virtual = " " * virtual_indent + rest
            tmp = lines[:i] + [virtual] + lines[i + 1:]
            value, next_i = _parse(tmp, i, virtual_indent)
            items.append(value)
            i = next_i
        return items, i

    # Mapping.
    mapping: dict[str, Any] = {}
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        cur_indent = _indent(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            # Shouldn't happen if recursion is correct.
            break

        m = re.match(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$", stripped)
        if not m:
            raise ValueError(f"unparseable line {i + 1}: {line!r}")
        key, value_part = m.group(1), m.group(2)

        if value_part in (">-", "|", ">"):
            # Block scalar: collect all subsequent lines indented deeper than `indent`.
            buf: list[str] = []
            j = i + 1
            block_indent = None
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                nxt_indent = _indent(nxt)
                if nxt_indent <= indent:
                    break
                if block_indent is None:
                    block_indent = nxt_indent
                buf.append(nxt[block_indent:].rstrip())
                j += 1
            joined = " ".join(s.strip() for s in buf if s.strip())
            mapping[key] = joined
            i = j
            continue

        if value_part == "":
            # Nested block follows.
            child, next_i = _parse(lines, i + 1, indent + 2)
            mapping[key] = child if child is not None else {}
            i = next_i
            continue

        mapping[key] = _parse_scalar(value_part)
        i += 1
    return mapping, i


def _load_yaml(text: str) -> Any:
    raw_lines = text.splitlines()
    cleaned = [_strip_comment(line) for line in raw_lines]
    value, _ = _parse(cleaned, 0, 0)
    return value or {}


# ---------------------------------------------------------------------------
# Matrix model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Combination:
    source: str
    target: str
    supported: bool
    phase: int | None
    reason: str | None
    reference_repo: str | None


class CompatibilityMatrix:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        raw = data.get("combinations") or []
        if not isinstance(raw, list):
            raise ValueError(
                f"`combinations` must be a list, got {type(raw).__name__}. "
                f"Check the YAML structure of the matrix file."
            )
        combos: list[Combination] = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError(
                    f"each combination must be a mapping, got {type(entry).__name__}: {entry!r}"
                )
            combos.append(
                Combination(
                    source=entry.get("source", ""),
                    target=entry.get("target", ""),
                    supported=bool(entry.get("supported", False)),
                    phase=entry.get("phase"),
                    reason=entry.get("reason"),
                    reference_repo=entry.get("reference_repo"),
                )
            )
        self.combinations: tuple[Combination, ...] = tuple(combos)

    @property
    def schema_version(self) -> int:
        return int(self._data.get("schema_version", 0))

    def lookup(self, source: str, target: str) -> Combination | None:
        for c in self.combinations:
            if c.source == source and c.target == target:
                return c
        return None

    def supported_pairs(self) -> list[Combination]:
        return [c for c in self.combinations if c.supported]


def _default_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "compatibility-matrix.yaml"


def load_matrix(path: Path | None = None) -> CompatibilityMatrix:
    p = path or _default_path()
    text = p.read_text(encoding="utf-8")
    data = _load_yaml(text)
    if not isinstance(data, dict):
        raise ValueError(f"matrix root must be a mapping, got {type(data).__name__}")
    return CompatibilityMatrix(data)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class UnsupportedCombination(Exception):
    """Raised when a (source, target) pair is not enabled for the current MVP."""


def assert_supported(
    source: str,
    target: str,
    *,
    matrix: CompatibilityMatrix | None = None,
) -> Combination:
    """Return the matched Combination if supported, else raise UnsupportedCombination.

    Callers should catch the exception and present its message to the user;
    the message is already user-facing and references docs/mvp-scope.md.
    """
    m = matrix or load_matrix()
    combo = m.lookup(source, target)
    if combo is None:
        raise UnsupportedCombination(
            f"unknown combination: source={source!r}, target={target!r}. "
            f"See docs/mvp-scope.md for supported combinations."
        )
    if not combo.supported:
        phase = f"phase {combo.phase}" if combo.phase else "no committed phase"
        reason = combo.reason or "not supported in the current MVP."
        raise UnsupportedCombination(
            f"{source} -> {target} is not enabled ({phase}). {reason} "
            f"See docs/mvp-scope.md."
        )
    return combo
