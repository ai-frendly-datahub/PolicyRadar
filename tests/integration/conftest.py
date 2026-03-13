from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from policyradar.models import Article, CategoryConfig, EntityDefinition, Source
from policyradar.storage import RadarStorage


@pytest.fixture
def tmp_storage(tmp_path: Path) -> RadarStorage:
    """Create a temporary RadarStorage instance for testing."""
    db_path = tmp_path / "test.duckdb"
    storage = RadarStorage(db_path)
    yield storage
    storage.close()


@pytest.fixture
def sample_articles() -> list[Article]:
    """Create sample articles with realistic government policy data."""
    now = datetime.now(UTC)
    return [
        Article(
            title="2024년 경제정책 방향 발표",
            link="https://policy.example.com/economy-2024",
            summary="정부가 2024년 경제정책 방향을 발표했습니다. 일자리 창출과 소비 활성화에 중점.",
            published=now,
            source="policy_news",
            category="policy",
            matched_entities={},
        ),
        Article(
            title="교육개혁 정책안 공개",
            link="https://policy.example.com/education-2024",
            summary="교육부가 교육개혁 정책안을 공개했습니다. 대학입시 제도 개선 포함.",
            published=now,
            source="policy_news",
            category="policy",
            matched_entities={},
        ),
        Article(
            title="환경정책 강화 방안",
            link="https://policy.example.com/environment-2024",
            summary="환경부가 탄소중립 달성을 위한 정책을 강화합니다. 재생에너지 확대 등.",
            published=now,
            source="policy_news",
            category="policy",
            matched_entities={},
        ),
        Article(
            title="복지정책 확대 계획",
            link="https://policy.example.com/welfare-2024",
            summary="보건복지부가 사회복지 정책 확대 계획을 발표했습니다.",
            published=now,
            source="policy_news",
            category="policy",
            matched_entities={},
        ),
        Article(
            title="규제개혁 추진 현황",
            link="https://policy.example.com/regulation-2024",
            summary="정부가 규제개혁 추진 현황을 보고했습니다. 불필요한 규제 폐지 진행 중.",
            published=now,
            source="policy_news",
            category="policy",
            matched_entities={},
        ),
    ]


@pytest.fixture
def sample_entities() -> list[EntityDefinition]:
    """Create sample entities with government policy keywords."""
    return [
        EntityDefinition(
            name="economic_policy",
            display_name="경제정책",
            keywords=["경제", "일자리", "소비", "성장", "투자"],
        ),
        EntityDefinition(
            name="education_policy",
            display_name="교육정책",
            keywords=["교육", "학교", "대학", "입시", "개혁"],
        ),
        EntityDefinition(
            name="environment_policy",
            display_name="환경정책",
            keywords=["환경", "탄소", "에너지", "기후", "재생"],
        ),
        EntityDefinition(
            name="welfare_policy",
            display_name="복지정책",
            keywords=["복지", "사회", "지원", "보건", "의료"],
        ),
        EntityDefinition(
            name="regulatory_reform",
            display_name="규제개혁",
            keywords=["규제", "개혁", "폐지", "완화", "혁신"],
        ),
    ]


@pytest.fixture
def sample_config(tmp_path: Path, sample_entities: list[EntityDefinition]) -> CategoryConfig:
    """Create a sample CategoryConfig for testing."""
    sources = [
        Source(
            name="policy_news",
            type="rss",
            url="https://policy.example.com/feed",
        ),
    ]
    return CategoryConfig(
        category_name="policy",
        display_name="정부정책",
        sources=sources,
        entities=sample_entities,
    )
