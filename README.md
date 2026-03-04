# PolicyRadar

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

정책 변경, 약관 업데이트, 규제 동향을 자동 추적하여 소비자와 기업이 중요한 정책 변화를 놓치지 않도록 돕는 레이더 프로젝트입니다.

## 프로젝트 목표

- **정책 변경 감지**: 개인정보 정책, 이용약관, 규제 변경 등 주요 정책 뉴스를 일일 자동 수집
- **약관 변경 추적**: 주요 플랫폼(Google, Apple, Meta 등)의 서비스 약관 변경 동향 모니터링
- **변경 감지 자동화**: MCP `change_detect` 도구로 정책/약관 변경 신호를 자동으로 탐지·알림
- **규제 동향 분석**: 독점 규제, 공정거래, 소비자 보호 관련 법률/규제 변화 추적
- **AI 정책 도우미**: MCP 서버를 통해 AI 어시스턴트에서 정책 정보를 자연어로 검색

## 주요 기능

1. **RSS 자동 수집**: TechCrunch, The Verge, EFF Updates 등에서 정책 관련 기사 수집
2. **엔티티 매칭**: 개인정보 정책, 약관 변경, 규제/법률, 플랫폼 정책, 소비자 권리 5개 카테고리
3. **DuckDB 저장**: UPSERT 시맨틱 기반 기사 저장
4. **JSONL 원본 보존**: `data/raw/YYYY-MM-DD/{source}.jsonl`
5. **SQLite FTS5 검색**: 전문검색으로 정책 관련 빠른 검색
6. **자연어 쿼리**: "최근 2주 개인정보 관련" 같은 자연어 검색
7. **HTML 리포트**: 정책 카테고리별 변경 사항이 포함된 자동 리포트
8. **MCP 서버**: search, recent_updates, sql, top_trends, change_detect

## 빠른 시작

```bash
pip install -r requirements.txt
python main.py --category policy --recent-days 7
```

- 리포트: `reports/policy_report.html`
- DB: `data/radar_data.duckdb`
- Raw JSONL: `data/raw/YYYY-MM-DD/*.jsonl`

## 프로젝트 구조

```
PolicyRadar/
├── policyradar/
│   ├── collector.py       # RSS 수집
│   ├── analyzer.py        # 엔티티 키워드 매칭
│   ├── storage.py         # DuckDB 스토리지
│   ├── reporter.py        # HTML 리포트
│   ├── raw_logger.py      # JSONL 원본 기록
│   ├── search_index.py    # SQLite FTS5
│   ├── nl_query.py        # 자연어 쿼리 파서
│   └── mcp_server/        # MCP 서버 (5개 도구)
├── config/categories/policy.yaml
├── tests/
├── .github/workflows/
└── main.py
```

## MCP 서버 도구

| 도구 | 설명 |
|------|------|
| `search` | FTS5 기반 자연어 검색 |
| `recent_updates` | 최근 수집 기사 조회 |
| `sql` | 읽기 전용 SQL 쿼리 |
| `top_trends` | 엔티티 언급 빈도 트렌드 |
| `change_detect` | 정책/약관 변경 신호 감지 |

## 테스트

```bash
pytest tests/ -v
```

## CI/CD

- `.github/workflows/radar-crawler.yml`: 매일 00:00 UTC 자동 수집
- GitHub Pages로 리포트 자동 배포
