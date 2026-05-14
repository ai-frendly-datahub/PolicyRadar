# POLICYRADAR

정부 정책 관련 뉴스, 공고, 입찰 정보를 수집하고 정책 분야별 트렌드를 분석합니다.

## STRUCTURE

```
PolicyRadar/
├── policyradar/
│   ├── collector.py              # collect_sources() — 정책 뉴스 RSS 및 정부 공고
│   ├── analyzer.py               # apply_entity_rules() — 정책 분야별 키워드 매칭 (경제, 교육, 환경, 복지 등)
│   ├── reporter.py               # generate_report() — Jinja2 HTML
│   ├── storage.py                # RadarStorage — DuckDB upsert/query/retention
│   ├── models.py                 # Source, Article, EntityDefinition, CategoryConfig
│   ├── config_loader.py          # YAML 로딩
│   ├── logger.py                 # structlog 구조화 로깅
│   ├── notifier.py               # Email/Webhook 알림
│   ├── raw_logger.py             # JSONL 원시 로깅
│   ├── search_index.py           # SQLite FTS5 전문 검색
│   ├── nl_query.py               # 자연어 쿼리 파서
│   ├── common/                   # 공유 유틸리티
│   └── mcp_server/               # MCP 서버 (server.py + tools.py)
├── config/
│   ├── config.yaml               # database_path, report_dir, raw_data_dir, search_db_path
│   └── categories/policy.yaml  # 소스 + 엔티티 정의
├── data/                         # DuckDB, search_index.db, raw/ JSONL
├── reports/                      # 생성된 HTML 리포트
├── tests/unit/                   # pytest 단위 테스트
├── main.py                       # CLI 엔트리포인트
└── .github/workflows/radar-crawler.yml
```

## ENTITIES

| Entity | Examples |
|--------|----------|
| Privacy | 개인정보, data protection, GDPR |
| TermsChange | terms update, 이용약관, policy change |
| Regulation | bill, agency, regulation, 법률 |
| Platform | Google, Apple, Meta, Microsoft |

## DEVIATIONS FROM TEMPLATE

- 플랫폼 약관 변경, 개인정보 정책, 정부 규제/입법 source를 함께 추적한다.
- 법안, 행정명령, 판결, 기관 보도자료를 각각 별도 정책 신호로 분류한다.
- 정책/보안 분류체계 작업은 `PolicyRadar/docs/n2sf-classification-applicability.md`의 공식 등급과 내부 오버레이 구분을 따른다.

## COMMANDS

```bash
python main.py --category policy --recent-days 7
python main.py --category policy --per-source-limit 50 --keep-days 90
```
