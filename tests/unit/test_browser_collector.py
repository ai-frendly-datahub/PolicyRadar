from __future__ import annotations

from importlib import import_module


def test_collect_browser_sources_forwards_source_config(monkeypatch) -> None:
    module = import_module("policyradar.browser_collector")
    source = import_module("policyradar.models").Source(
        name="PIPC 보도자료",
        type="javascript",
        url="https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS074",
        config={"wait_for": ".board_list"},
    )
    captured: dict[str, object] = {}

    def fake_collect(*, sources, category, timeout, health_db_path):
        captured["sources"] = sources
        captured["category"] = category
        return [], []

    monkeypatch.setattr(module, "_BROWSER_COLLECTION_AVAILABLE", True)
    monkeypatch.setattr(module, "_core_collect", fake_collect)

    articles, errors = module.collect_browser_sources([source], "policy")

    assert articles == []
    assert errors == []
    assert captured["category"] == "policy"
    assert captured["sources"] == [
        {
            "name": "PIPC 보도자료",
            "type": "javascript",
            "url": "https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS074",
            "config": {"wait_for": ".board_list"},
        }
    ]
