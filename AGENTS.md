# POLICYRADAR

정책 뉴스와 함께 집행 공지, 행정예고, 규제기관 가이드, 플랫폼 정책 변화를 수집해 정책 실행 신호를 분석합니다.

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
│   └── categories/{domain}.yaml  # 소스 + 엔티티 정의
├── data/                         # DuckDB, search_index.db, raw/ JSONL
├── reports/                      # 생성된 HTML 리포트
├── tests/unit/                   # pytest 단위 테스트
├── main.py                       # CLI 엔트리포인트
└── .github/workflows/radar-crawler.yml
```

## ENTITIES

| Entity | Examples |
|--------|----------|
| Regulation / TermsChange | bill, act, policy update, 약관 변경 |
| EnforcementAction / PublicConsultation | fine, settlement, public comment, 행정예고 |
| AgencyGuidance / PlatformPolicy | guidance, clarification, 운영정책, developer policy |

## DEVIATIONS FROM TEMPLATE

- `javascript` 소스로 규제기관 공지와 보도자료 페이지를 수집한다.
- taxonomy 기준으로 `공식 + 운영 + 시장 + 커뮤니티` 레이어를 유지한다.
- config loader가 source 메타데이터(`trust_tier`, `info_purpose`, `config`)를 보존한다.
- 정책 분류체계/N2SF/CSAP/FedRAMP 20x 적용 메모:
  [n2sf-classification-applicability.md](docs/n2sf-classification-applicability.md)
- `config/categories/policy.yaml`에는 `SecurityClassificationFramework` 엔티티가 추가되어 공공 보안분류 정책을 별도 태깅한다.

## COMMANDS

```bash
python main.py --category policy --recent-days 7
python main.py --category policy --per-source-limit 50 --keep-days 90
pip install 'radar-core[browser]'
```
