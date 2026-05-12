from __future__ import annotations

import sys
from importlib import import_module


_MODULE_ALIASES = {
    "analyzer": "policyradar.analyzer",
    "collector": "policyradar.collector",
    "exceptions": "policyradar.exceptions",
    "models": "policyradar.models",
    "nl_query": "policyradar.nl_query",
    "search_index": "policyradar.search_index",
    "storage": "policyradar.storage",
}

for _module_name, _target in _MODULE_ALIASES.items():
    sys.modules[f"{__name__}.{_module_name}"] = import_module(_target)


RadarStorage = import_module("policyradar.storage").RadarStorage


__all__ = ["RadarStorage"]
