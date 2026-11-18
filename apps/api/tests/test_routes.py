"""Every router calls functions that exist (runs without a database).

A route like ``service.statistics`` only fails when it is requested, and the endpoint tests
need PostgreSQL: this catches a function deleted or renamed by mistake on any machine.
"""

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_routers_only_call_functions_that_exist():
    missing = []
    for router in sorted((ROOT / "app").glob("*/router.py")):
        text = router.read_text(encoding="utf-8")
        module = importlib.import_module(".".join(router.relative_to(ROOT).with_suffix("").parts))
        aliases = set(re.findall(r"from app\.\w+ import (?:\w+ as )?(\w+)\n", text)) | {"service"}
        for alias in aliases:
            target = getattr(module, alias, None)
            if target is None or not hasattr(target, "__file__"):
                continue  # not a module (a class or function imported by name)
            for name in set(re.findall(rf"\b{alias}\.([a-zA-Z_]\w*)", text)):
                if not hasattr(target, name):
                    missing.append(f"{router.relative_to(ROOT)}: {alias}.{name}")
    assert missing == []


def test_statistics_routes_are_wired():
    from app.statistics import service

    for name in ("statistics", "breakdown", "matches", "opponents", "placements", "head_to_head"):
        assert callable(getattr(service, name)), name
