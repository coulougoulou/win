"""Petits utilitaires de navigation dans des JSON de forme inconnue."""

from __future__ import annotations

from typing import Iterator


def deep_find_dicts(data, required_any: tuple[str, ...], max_depth: int = 25) -> Iterator[dict]:
    """Parcourt un JSON et rend chaque dict portant au moins une des cles voulues.

    Les sources changent la forme de leur payload sans preavis ; chercher par
    forme plutot que par chemin evite de casser a chaque refonte.
    """
    stack = [(data, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            continue
        if isinstance(node, dict):
            if any(key in node for key in required_any):
                yield node
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
