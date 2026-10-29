from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from policyradar.collector import (
    RateLimiter,
    _collect_single,
    _extract_govinfo_html_url,
    _maybe_replace_govinfo_summary,
    _parse_html_text,
    _passes_include_keywords,
    _text_has_any_keyword,
)
from policyradar.config_loader import load_category_config
from policyradar.models import Source


_HTML_URL = "https://www.govinfo.gov/content/pkg/BILLS-119hr1ih/html/BILLS-119hr1ih.htm"
_LINK_LIST_SUMMARY = (
    "<h2>Content Files</h2>\n"
    f'<a href="{_HTML_URL}">TEXT</a><br />\n'
    "<h2>Metadata download</h2>"
)
_BILL_HTML = """<html><body><pre>
119th CONGRESS
  2d Session
                                H. R. 1

                                 A BILL

This Act may be cited as the Sample Act.

SEC. 2. PRIVACY.

The commission shall issue a privacy regulation.
</pre><script>ignore me</script></body></html>"""
_POLICY_KEYWORDS = [
    "privacy",
    "regulation",
    "regulator",
    "antitrust",
    "FTC",
    "FCC",
    "SEC",
    "bill",
    "law",
    "lawsuit",
    "ruling",
    "executive order",
    "AI policy",
    "terms of service",
]


def _rss(title: str, summary: str, link: str = "https://example.com/item") -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
<title>{title}</title>
<link>{link}</link>
<description>{summary}</description>
</item></channel></rss>""".encode()


def _response(*, content: bytes | None = None, text: str = "", status_code: int = 200) -> Mock:
    response = Mock()
    response.content = content if content is not None else text.encode()
    response.text = text
    response.status_code = status_code
    response.raise_for_status = Mock()
    return response


def _source(name: str, **config: object) -> Source:
    return Source(
        name=name,
        type="rss",
        url="https://example.com/feed.xml",
        config=dict(config),
    )


class TestIncludeKeywordGate:
    def test_missing_field_keeps_unrelated_item(self) -> None:
        source = _source("TechCrunch Policy")
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.return_value = _response(content=_rss("New phone", "A gadget roundup"))
            articles = _collect_single(source, category="policy", limit=5, timeout=5)

        assert len(articles) == 1
        assert articles[0].title == "New phone"

    def test_keyword_in_title_is_case_insensitive(self) -> None:
        source = _source("The Hill", include_keywords=["ftc"])
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.return_value = _response(content=_rss("FTC opens a review", "Details later"))
            articles = _collect_single(source, category="policy", limit=5, timeout=5)

        assert len(articles) == 1
        assert _passes_include_keywords(source, articles[0].title, articles[0].summary)

    def test_keyword_only_in_summary_passes(self) -> None:
        assert _text_has_any_keyword(
            "Roundup", "An executive order landed today", ["executive order"]
        )

    def test_no_keyword_is_skipped(self) -> None:
        source = _source("The Verge", include_keywords=["privacy", "regulation"])
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.return_value = _response(
                content=_rss("Camera review", "Megapixels and battery life")
            )
            articles = _collect_single(source, category="policy", limit=5, timeout=5)

        assert articles == []

    def test_short_keyword_does_not_match_inside_another_word(self) -> None:
        keywords = ["bill", "law"]
        assert _text_has_any_keyword("Startup raises a billion", "funding note", keywords) is False
        assert _text_has_any_keyword("Lawyer conference", "no statute", keywords) is False
        assert _text_has_any_keyword("House passes a bill", "public law text", keywords) is True

    def test_empty_keyword_list_blocks(self) -> None:
        source = _source("The Hill", include_keywords=[])
        assert _passes_include_keywords(source, "FTC ruling", "privacy") is False


class TestGovInfoHtmlSummary:
    def test_extracts_public_html_link(self) -> None:
        assert _extract_govinfo_html_url(_LINK_LIST_SUMMARY) == _HTML_URL

    def test_parse_keeps_leading_plain_text(self) -> None:
        long_html = "<html><body><pre>" + ("privacy regulation " * 80) + "</pre></body></html>"
        parsed = _parse_html_text(long_html)
        assert len(parsed) == 1000
        assert parsed.startswith("privacy regulation")
        assert "<" not in parsed

    def test_parse_drops_script_and_collapses_pre_whitespace(self) -> None:
        parsed = _parse_html_text(_BILL_HTML)
        assert "Sample Act" in parsed
        assert "privacy regulation" in parsed
        assert "ignore me" not in parsed
        assert "\n" not in parsed

    def test_replaces_summary_with_parsed_body(self) -> None:
        source = Source(
            name="GovInfo Bills", type="rss", url="https://www.govinfo.gov/rss/bills.xml"
        )
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.side_effect = [
                _response(content=_rss("H.R. 1", _LINK_LIST_SUMMARY, link=_HTML_URL)),
                _response(text=_BILL_HTML, status_code=200),
            ]
            articles = _collect_single(source, category="policy", limit=5, timeout=5)

        assert len(articles) == 1
        assert articles[0].summary.startswith("119th CONGRESS")
        assert "Content Files" not in articles[0].summary
        assert len(articles[0].summary) <= 1000
        assert mock_get.call_args_list[1].args[0] == _HTML_URL

    def test_403_keeps_link_list(self) -> None:
        source = Source(
            name="GovInfo Public and Private Laws",
            type="rss",
            url="https://www.govinfo.gov/rss/plaw.xml",
        )
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.return_value = _response(text="denied", status_code=403)
            replaced = _maybe_replace_govinfo_summary(source, _LINK_LIST_SUMMARY, timeout=5)

        assert replaced == _LINK_LIST_SUMMARY

    def test_challenge_page_keeps_link_list(self) -> None:
        source = Source(
            name="GovInfo Bills", type="rss", url="https://www.govinfo.gov/rss/bills.xml"
        )
        challenge = "<html><title>Just a moment...</title><body>Checking your browser</body></html>"
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.return_value = _response(text=challenge, status_code=200)
            replaced = _maybe_replace_govinfo_summary(source, _LINK_LIST_SUMMARY, timeout=5)

        assert replaced == _LINK_LIST_SUMMARY

    def test_timeout_keeps_link_list(self) -> None:
        source = Source(
            name="GovInfo Bills", type="rss", url="https://www.govinfo.gov/rss/bills.xml"
        )
        with patch("policyradar.collector.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("timed out")
            replaced = _maybe_replace_govinfo_summary(source, _LINK_LIST_SUMMARY, timeout=5)

        assert replaced == _LINK_LIST_SUMMARY

    def test_other_sources_do_not_fetch_html(self) -> None:
        source = Source(name="The Hill", type="rss", url="https://thehill.com/feed/")
        with patch("policyradar.collector.requests.get") as mock_get:
            replaced = _maybe_replace_govinfo_summary(source, _LINK_LIST_SUMMARY, timeout=5)

        assert replaced == _LINK_LIST_SUMMARY
        mock_get.assert_not_called()

    def test_rate_limiter_runs_before_get_and_spaces_hosts(self) -> None:
        source = Source(
            name="GovInfo Bills", type="rss", url="https://www.govinfo.gov/rss/bills.xml"
        )
        events: list[str] = []

        class OrderingLimiter(RateLimiter):
            def acquire(self) -> None:
                events.append("acquire")
                super().acquire()

        limiter = OrderingLimiter(min_interval=0.2)

        def fake_get(url: str, timeout: int = 5, headers: dict[str, str] | None = None) -> Mock:
            events.append("get")
            return _response(text=_BILL_HTML, status_code=200)

        with patch("policyradar.collector.requests.get", side_effect=fake_get):
            started = time.monotonic()
            first = _maybe_replace_govinfo_summary(
                source, _LINK_LIST_SUMMARY, timeout=5, rate_limiter=limiter
            )
            second = _maybe_replace_govinfo_summary(
                source, _LINK_LIST_SUMMARY, timeout=5, rate_limiter=limiter
            )
            elapsed = time.monotonic() - started

        assert first.startswith("119th CONGRESS")
        assert second.startswith("119th CONGRESS")
        assert events == ["acquire", "get", "acquire", "get"]
        assert elapsed >= 0.2


class TestPolicyCategoryConfig:
    def test_loader_keeps_keyword_gate_optional(self, tmp_path: Path) -> None:
        config_path = tmp_path / "sample.yaml"
        config_path.write_text(
            """
category_name: sample
sources:
  - name: Open
    type: rss
    url: https://example.com/open.xml
  - name: Gated
    type: rss
    url: https://example.com/gated.xml
    include_keywords:
      - Privacy
      - FTC
entities: []
""",
            encoding="utf-8",
        )

        loaded = load_category_config("sample", categories_dir=tmp_path)

        assert "include_keywords" not in loaded.sources[0].config
        assert loaded.sources[1].config["include_keywords"] == ["Privacy", "FTC"]

    def test_policy_yaml_noise_edits(self) -> None:
        loaded = load_category_config("policy")
        names = [source.name for source in loaded.sources]
        by_name = {source.name: source for source in loaded.sources}

        assert "GovInfo Federal Register" not in names
        assert "GovInfo Congressional Reports" not in names
        assert "Reddit r/law" not in names
        assert "Reddit r/politics" not in names
        assert "GovInfo Bills" in names
        assert "GovInfo Public and Private Laws" in names

        propublica = by_name["ProPublica Regulation"]
        assert propublica.url == "https://www.propublica.org/topics/regulation/feed"

        # 분류 참고 기준에서 잘못 지운 비율이 10%를 넘겨 게이트를 적용하지 않는다.
        for source_name in ("TechCrunch Policy", "The Verge", "The Hill", "EFF Updates"):
            assert "include_keywords" not in by_name[source_name].config
        assert by_name["TechCrunch Policy"].url == "https://techcrunch.com/feed/"

        entities = {
            entity.name: [keyword.lower() for keyword in entity.keywords]
            for entity in loaded.entities
        }
        banned = {"act", "federal", "law", "house", "senate", "white house", "apple"}
        for entity_name in ("Regulation", "Legislation", "Platform"):
            assert banned.isdisjoint(entities[entity_name])

        assert "privacy act" in entities["Regulation"]
        assert "public law" in entities["Regulation"]
        assert "federal register" in entities["Regulation"]
        assert "house of representatives" in entities["Regulation"]
        assert "senate committee" in entities["Regulation"]
        assert "privacy act" in entities["Legislation"]
        assert "house of representatives" in entities["Legislation"]
        assert "senate committee" in entities["Legislation"]
        assert "apple app store" in entities["Platform"]
        assert "white house" in entities["ExecutiveOrder"]


def test_news_sources_are_not_keyword_gated() -> None:
    loaded = load_category_config("policy")
    for source_name in ("TechCrunch Policy", "The Verge", "The Hill"):
        source = next(item for item in loaded.sources if item.name == source_name)
        assert "include_keywords" not in source.config


@pytest.mark.parametrize(
    ("title", "summary", "expected"),
    [
        ("Privacy bill advances", "", True),
        ("MARKETS", "the sec filed a lawsuit", True),
        ("AI Policy draft", "terms of service update", True),
        ("Sports night", "scores and weather", False),
    ],
)
def test_keyword_gate_examples(title: str, summary: str, expected: bool) -> None:
    assert _text_has_any_keyword(title, summary, _POLICY_KEYWORDS) is expected
