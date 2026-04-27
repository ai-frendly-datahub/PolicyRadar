# PolicyRadar - 정책 정보 레이더

**🌐 Live Report**: https://ai-frendly-datahub.github.io/PolicyRadar/


정부 정책 뉴스뿐 아니라 집행 공지, 행정예고, 규제기관 가이드, 플랫폼 정책 변화를 함께 수집해 정책 실행 신호를 분석합니다.

## 프로젝트 목표

- **데이터 수집**: 정책 뉴스 RSS, 정부 공고, 집행 공지, 행정예고, 규제기관 보도자료
- **엔티티 분석**: 정책 분야별 키워드 매칭 (경제, 교육, 환경, 복지 등)
- **트렌드 리포트**: DuckDB 저장 + HTML 리포트로 {domain} 동향 시각화
- **자동화**: GitHub Actions 일일 수집 + GitHub Pages 리포트 자동 배포

## 기술적 우수성

- **안정성**: HTTP 자동 재시도(지수 백오프), DB 트랜잭션 에러 처리
- **관찰성**: 구조화된 JSON 로깅으로 파이프라인 상태 실시간 모니터링
- **품질 보증**: 단위 테스트로 코드 변경 시 회귀 버그 사전 차단
- **고성능**: 배치 처리 최적화로 대량 데이터 수집 시 성능 향상
- **운영 자동화**: Email/Webhook 알림으로 무인 운영 가능

## 빠른 시작

1. 가상환경을 만들고 의존성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```

2. 실행:
   ```bash
   python main.py --category policy --recent-days 7
   # 리포트: reports/policy_report.html
   ```

   주요 옵션: `--per-source-limit 20`, `--recent-days 5`, `--keep-days 60`, `--timeout 20`.

## GitHub Actions & GitHub Pages

- 워크플로: `.github/workflows/radar-crawler.yml`
  - 스케줄: 매일 00:00 UTC (KST 09:00), 수동 실행도 지원.
  - 환경 변수 `RADAR_CATEGORY`를 프로젝트에 맞게 수정하세요.
  - 리포트 배포 디렉터리: `reports` → `gh-pages` 브랜치로 배포.
  - DuckDB 경로: `data/radar_data.duckdb` (Pages에 올라가지 않음). 아티팩트로 7일 보관.

- 설정 방법:
  1) 저장소 Settings → Pages에서 `gh-pages` 브랜치를 선택해 활성화
  2) Actions 권한을 기본값으로 두거나 외부 PR에서도 실행되도록 설정
  3) 워크플로 파일의 `RADAR_CATEGORY`를 원하는 YAML 이름으로 변경

## 동작 방식

- **수집**: 카테고리 YAML에 정의된 소스를 수집합니다. 실행 시 DuckDB에 적재하고 보존 기간(`keep_days`)을 적용합니다.
- **분석**: 엔티티별 키워드 매칭. 매칭된 키워드를 리포트에 칩으로 표시합니다.
- **리포트**: `reports/<category>_report.html`을 생성하며, 최근 N일(기본 7일) 기사와 엔티티 히트 카운트, 수집 오류를 표시합니다.

## 정책 프레임워크 연구

- N2SF, CSAP, FIPS 199, FedRAMP 20x를 현재 워크스페이스에 어떻게 적용할지에 대한 운영 메모:
  [docs/n2sf-classification-applicability.md](/home/kjs/projects/ai-frendly-datahub/PolicyRadar/docs/n2sf-classification-applicability.md)
- `policy.yaml`에는 `SecurityClassificationFramework` 엔티티가 추가되어 공공 보안분류/클라우드 인증 정책 신호를 별도로 추적합니다.

## 소스 전략

- `공식`: White House, SEC, GovInfo, FSC, PIPC, KISA
- `운영`: Federal Register, FTC/FSC 집행/설명, PIPC/KISA 공지
- `시장`: 정책/기술 미디어와 think tank
- `커뮤니티`: Reddit 법/정치/기술 정책 담론

JavaScript/browser 소스를 제대로 수집하려면 `pip install 'radar-core[browser]'`가 필요합니다.

## 데이터 품질 운영

- `config/categories/policy.yaml`의 `data_quality`는 `public_consultation`, `enforcement_action`, `policy_effective_date`, `platform_policy_change`, `security_classification_framework` 이벤트를 분리합니다.
- `policyradar.policy_signals`는 의견수렴 마감일, 시행일, 집행 결과를 `matched_entities`의 `ConsultationDeadline`, `PolicyEffectiveDate`, `EnforcementOutcome`, `OperationalEvent`로 보강합니다.
- `source_backlog`의 Regulations.gov, lawmaking.go.kr, FTC cases, PIPC 처분 아카이브, 플랫폼 정책 페이지는 parser·ToS·개인정보·diff 검증 전까지 기본 비활성 후보로 둡니다.
- N2SF/CSAP/FIPS 199/FedRAMP 20x는 공식 제도 등급과 내부 운영 오버레이를 분리해 태깅합니다.

## 기본 경로

- DB: `data/radar_data.duckdb`
- 리포트 출력: `reports/`

## 디렉터리 구성

```
PolicyRadar/
  main.py                 # CLI 엔트리포인트
  requirements.txt        # 의존성
  config/
    config.yaml           # DB/리포트 경로 설정
    categories/
      policy.yaml  # 소스 + 엔티티 정의
  policyradar/
    collector.py          # 데이터 수집
    analyzer.py           # 엔티티 태깅
    reporter.py           # HTML 렌더링
    storage.py            # DuckDB 저장/정리
    config_loader.py      # YAML 로더
    models.py             # 데이터 클래스
  .github/workflows/      # GitHub Actions (crawler + Pages 배포)
```

<!-- DATAHUB-OPS-AUDIT:START -->
## DataHub Operations

- CI/CD workflows: `pr-checks.yml`, `radar-crawler.yml`, `release.yml`.
- GitHub Pages visualization: `reports/index.html` (valid HTML); https://ai-frendly-datahub.github.io/PolicyRadar/.
- Latest remote Pages check: HTTP 200, HTML.
- Local workspace audit: 61 Python files parsed, 0 syntax errors.
- Re-run audit from the workspace root: `python scripts/audit_ci_pages_readme.py --syntax-check --write`.
- Latest audit report: `_workspace/2026-04-14_github_ci_pages_readme_audit.md`.
- Latest Pages URL report: `_workspace/2026-04-14_github_pages_url_check.md`.
<!-- DATAHUB-OPS-AUDIT:END -->
