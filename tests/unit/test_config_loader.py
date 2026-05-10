from __future__ import annotations

from policyradar.analyzer import apply_entity_rules
from policyradar.collector import article_matches_source_scope
from policyradar.config_loader import load_category_config, load_category_quality_config
from policyradar.models import Article


def test_real_policy_config_exposes_data_quality_overlay() -> None:
    metadata = load_category_quality_config("policy")

    data_quality = metadata["data_quality"]
    assert isinstance(data_quality, dict)
    assert data_quality["priority"] == "P0"
    assert data_quality["primary_motion"] == "compliance-risk"
    assert "public_consultation" in data_quality["event_models"]
    assert "enforcement_action" in data_quality["event_models"]
    assert "security_classification_framework" in data_quality["event_models"]
    assert data_quality["canonical_keys"]["consultation"]["fields"]
    assert data_quality["quality_outputs"]["freshness_report"] == (
        "reports/policy_quality.json"
    )
    assert data_quality["quality_outputs"]["tracked_event_models"] == [
        "public_consultation",
        "enforcement_action",
        "policy_effective_date",
        "platform_policy_change",
        "security_classification_framework",
    ]

    backlog = metadata["source_backlog"]
    assert isinstance(backlog, dict)
    consultation_candidates = {candidate["id"] for candidate in backlog["consultation_candidates"]}
    enforcement_candidates = {candidate["id"] for candidate in backlog["enforcement_candidates"]}
    assert consultation_candidates >= {"regulations_gov_documents_api", "korea_lawmaking_notice"}
    assert enforcement_candidates >= {"ftc_cases_and_proceedings", "pipc_decision_archive"}


def test_real_policy_sources_preserve_operational_metadata() -> None:
    config = load_category_config("policy")
    sources = {source.name: source for source in config.sources}

    federal_register = sources["GovInfo Federal Register"]
    assert federal_register.trust_tier == "T1_authoritative"
    assert federal_register.config["event_model"] == "public_consultation"
    assert "public_consultation" in federal_register.info_purpose

    sec = sources["SEC Press Releases"]
    assert sec.config["event_model"] == "enforcement_action"
    assert sec.config["canonical_key_fields"]

    pipc = sources["PIPC 보도자료"]
    assert pipc.config["event_model"] == "enforcement_action"
    assert pipc.config["wait_for"] == "body"
    assert pipc.config["bypass_crawl_health"] is True
    assert pipc.config["link_selector"] == "a[href*='selectBoardArticle.do'][href*='BS074']"

    kisa = sources["KISA 보안공지"]
    assert kisa.url == "https://www.kisa.or.kr/401"
    assert kisa.config["event_model"] == "security_classification_framework"
    assert kisa.config["wait_for"] == "body"
    assert kisa.config["bypass_crawl_health"] is True
    assert kisa.config["link_selector"] == "a[href*='/401/form']"
    assert "n2sf" in kisa.config["include_keywords"]
    assert "operational overlays" in kisa.notes

    epa = sources["EPA Regulations"]
    assert epa.url == "https://www.epa.gov/taxonomy/term/226129/feed"
    assert epa.config["bypass_crawl_health"] is True

    ftc = sources["FTC News"]
    assert ftc.url == "https://www.ftc.gov/feeds/press-release.xml"
    assert ftc.enabled is False
    assert ftc.config["disabled_reason"] == "official_rss_blocked_403"


def test_broad_policy_sources_use_topic_scope_filters() -> None:
    config = load_category_config("policy")
    sources = {source.name: source for source in config.sources}

    techcrunch = sources["TechCrunch Policy"]
    assert not article_matches_source_scope(
        techcrunch,
        "TechCrunch Mobility: Who is poaching all the self-driving vehicle talent?",
        "A roundup of transportation startups and hiring moves.",
    )
    assert article_matches_source_scope(
        techcrunch,
        "FTC announces platform privacy enforcement action",
        "The settlement covers personal data and consumer protection.",
    )

    verge = sources["The Verge"]
    assert not article_matches_source_scope(
        verge,
        "Super Mario Galaxy Switch bundle deal returns",
        "Nintendo game discounts are live this week.",
    )

    the_hill = sources["The Hill"]
    assert article_matches_source_scope(
        the_hill,
        "US military will clean out Strait of Hormuz: Trump",
        "The president discussed national security and defense policy.",
    )

    reddit_technology = sources["Reddit r/technology (Tech Policy)"]
    assert article_matches_source_scope(
        reddit_technology,
        "Survey finds people distrust tech firms with personal data",
        "Privacy and data protection remain the central issue.",
    )


def test_real_policy_config_avoids_common_false_positive_terms() -> None:
    config = load_category_config("policy")
    articles = [
        Article(
            title="From LLMs to hallucinations, here's a simple guide to common AI terms",
            link="https://example.com/ai-terms",
            summary="Definitions for common AI terminology.",
            published=None,
            source="TechCrunch Policy",
            category="policy",
        ),
        Article(
            title="As the U.S. debates museum funding",
            link="https://example.com/museum-resolution",
            summary="Congress passed a resolution on cultural institutions.",
            published=None,
            source="The Hill",
            category="policy",
        ),
        Article(
            title="내 일상이 실시간으로 중계된다고? IP카메라 비밀번호 당장 바꾸세요",
            link="https://example.com/pipc-ip-camera",
            summary="Privacy regulator public notice.",
            published=None,
            source="PIPC 보도자료",
            category="policy",
        ),
        Article(
            title="FDA Releases Results from Largest-Ever Testing of Infant Formula in the U.S.",
            link="https://example.com/fda-infant-formula",
            summary="The release covers chemical contaminants in infant formula.",
            published=None,
            source="FDA News Releases",
            category="policy",
        ),
    ]

    analyzed = apply_entity_rules(articles, config.entities)

    assert "TermsChange" not in analyzed[0].matched_entities
    assert "ConsumerRights" not in analyzed[1].matched_entities
    assert "Regulation" in analyzed[1].matched_entities
    assert "Privacy" in analyzed[2].matched_entities
    assert "Regulation" in analyzed[3].matched_entities


def test_load_category_config_preserves_source_metadata(tmp_path) -> None:
    categories_dir = tmp_path / "categories"
    categories_dir.mkdir()
    (categories_dir / "policy.yaml").write_text(
        """
category_name: policy
display_name: Policy
sources:
  - name: PIPC 보도자료
    id: pipc_press
    type: javascript
    url: https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS074
    enabled: true
    trust_tier: T1_authoritative
    weight: 1.8
    content_type: enforcement_notice
    collection_tier: C3_html_js
    producer_role: government
    info_purpose:
      - enforcement
      - privacy_policy
    notes: official privacy regulator notices
    config:
      wait_for: .board_list
entities: []
""",
        encoding="utf-8",
    )

    config = load_category_config("policy", categories_dir=categories_dir)
    source = config.sources[0]

    assert source.id == "pipc_press"
    assert source.trust_tier == "T1_authoritative"
    assert source.weight == 1.8
    assert source.content_type == "enforcement_notice"
    assert source.collection_tier == "C3_html_js"
    assert source.producer_role == "government"
    assert source.info_purpose == ["enforcement", "privacy_policy"]
    assert source.notes == "official privacy regulator notices"
    assert source.config == {"wait_for": ".board_list"}
