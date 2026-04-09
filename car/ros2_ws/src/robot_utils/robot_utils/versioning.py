from __future__ import annotations

"""Shared version parsing and engine-expression evaluation helpers.

These helpers are intentionally strict: unsupported expressions and malformed
versions are treated as unsatisfied instead of being implicitly accepted.
"""

from dataclasses import dataclass
import re

_COMPARATOR_PATTERN = re.compile(r'^(>=|<=|>|<|=)?\s*(\d+(?:\.\d+)*)$')


def parse_version_tuple(value: str) -> tuple[int, ...]:
    """Parse one version string into a comparable integer tuple.

    Args:
        value: Version string such as ``v20.19.0`` or ``10.5``.

    Returns:
        Parsed numeric tuple. Empty tuple means the value is unsupported.

    Raises:
        None.

    Boundary behavior:
        Non-numeric prefixes, prerelease metadata, and empty values are
        tolerated. Only the first dotted numeric segment is used.
    """
    match = re.search(r'\d+(?:\.\d+)*', str(value))
    if not match:
        return ()
    return tuple(int(part) for part in match.group(0).split('.'))


def compare_version_tuples(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    """Compare two parsed version tuples using zero-padding."""
    width = max(len(left), len(right))
    left_padded = left + (0,) * (width - len(left))
    right_padded = right + (0,) * (width - len(right))
    if left_padded < right_padded:
        return -1
    if left_padded > right_padded:
        return 1
    return 0


def satisfies_engine_expression(version: str, expression: str) -> bool:
    """Evaluate one package.json style engine expression.

    Args:
        version: Installed runtime version string.
        expression: Comparator expression, optionally using OR branches with
            ``||`` and AND comparators separated by whitespace.

    Returns:
        ``True`` when the version satisfies at least one OR branch.

    Raises:
        None.

    Boundary behavior:
        Empty expressions, malformed comparators, and unparsable versions are
        rejected instead of being accepted optimistically.
    """
    current = parse_version_tuple(version)
    if not current:
        return False
    normalized = str(expression or '').strip()
    if not normalized:
        return False
    for branch in normalized.split('||'):
        comparators = [item for item in branch.strip().split() if item]
        if not comparators:
            continue
        branch_ok = True
        for comparator_text in comparators:
            match = _COMPARATOR_PATTERN.match(comparator_text)
            if not match:
                branch_ok = False
                break
            operator = match.group(1) or '='
            target = parse_version_tuple(match.group(2))
            relation = compare_version_tuples(current, target)
            if operator == '>=':
                ok = relation >= 0
            elif operator == '<=':
                ok = relation <= 0
            elif operator == '>':
                ok = relation > 0
            elif operator == '<':
                ok = relation < 0
            else:
                ok = relation == 0
            if not ok:
                branch_ok = False
                break
        if branch_ok:
            return True
    return False
