from __future__ import annotations

import pytest

from policyradar.models import Article, EntityDefinition


def _apply_entity_rules_py39(
    articles: list[Article], entities: list[EntityDefinition]
) -> list[Article]:
    """Apply entity rules (Python 3.9 compatible version)."""
    analyzed: list[Article] = []
    lowered_entities = [
        EntityDefinition(
            name=e.name,
            display_name=e.display_name,
            keywords=[kw.lower() for kw in e.keywords],
        )
        for e in entities
    ]

    for article in articles:
        haystack = f"{article.title}\n{article.summary}".lower()
        matches: dict[str, list[str]] = {}
        for entity, lowered_entity in zip(entities, lowered_entities):
            hit_keywords = [kw for kw in lowered_entity.keywords if kw and kw in haystack]
            if hit_keywords:
                matches[entity.name] = hit_keywords
        article.matched_entities = matches
        analyzed.append(article)

    return analyzed


@pytest.mark.integration
def test_entity_extraction_integration(
    sample_articles: list[Article],
    sample_entities: list[EntityDefinition],
) -> None:
    """Test entity extraction integration: apply rules → verify tagged entities."""
    analyzed = _apply_entity_rules_py39(sample_articles, sample_entities)

    assert len(analyzed) == 5
    assert all(isinstance(a, Article) for a in analyzed)

    article_1 = analyzed[0]
    assert "economic_policy" in article_1.matched_entities
    assert "경제" in article_1.matched_entities["economic_policy"]

    article_2 = analyzed[1]
    assert "education_policy" in article_2.matched_entities
    assert "교육" in article_2.matched_entities["education_policy"]

    article_3 = analyzed[2]
    assert "environment_policy" in article_3.matched_entities
    assert "환경" in article_3.matched_entities["environment_policy"]

    article_4 = analyzed[3]
    assert "welfare_policy" in article_4.matched_entities
    assert "복지" in article_4.matched_entities["welfare_policy"]

    article_5 = analyzed[4]
    assert "regulatory_reform" in article_5.matched_entities
    assert "규제" in article_5.matched_entities["regulatory_reform"]
