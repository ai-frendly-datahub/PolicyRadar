from __future__ import annotations

import importlib
import sys


_ALIASES = {
    "analyzer": "policyradar.analyzer",
    "collector": "policyradar.collector",
    "exceptions": "policyradar.exceptions",
    "models": "policyradar.models",
    "nl_query": "policyradar.nl_query",
    "reporter": "policyradar.reporter",
    "search_index": "policyradar.search_index",
    "storage": "policyradar.storage",
}


for _name, _target in _ALIASES.items():
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(_target)


__all__ = sorted(_ALIASES)
