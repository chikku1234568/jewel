"""Every placeholder module must stay importable."""

import importlib
import pkgutil

import jewel


def test_all_modules_import() -> None:
    names = [m.name for m in pkgutil.walk_packages(jewel.__path__, prefix="jewel.")]
    assert names, "no modules discovered"
    for name in names:
        importlib.import_module(name)
