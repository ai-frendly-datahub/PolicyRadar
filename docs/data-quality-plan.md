# Data Quality Plan

- 생성 시각: `2026-04-11T16:05:37.910248+00:00`
- 우선순위: `P0`
- 데이터 품질 점수: `96`
- 가장 약한 축: `추적성`
- Governance: `high`
- Primary Motion: `compliance-risk`

## 현재 이슈

- 현재 설정상 즉시 차단 이슈 없음. 운영 지표와 freshness SLA만 명시하면 됨

## 필수 신호

- 입법예고·행정예고·의견수렴 문서
- 제재·과징금·시정명령 같은 enforcement action
- 플랫폼 약관·정책 변경 공지

## 품질 게이트

- 공식 규제 문서와 해설 기사를 분리
- 시행일·의견 제출 마감일·공포일을 별도 필드로 유지
- N2SF/CSAP/FIPS 199/FedRAMP 20x 분류는 공식 등급과 내부 오버레이를 분리

## 다음 구현 순서

- public_consultation과 enforcement_action freshness/stale 리포트를 검증 산출물에 추가
- Regulations.gov/입법예고/FTC/PIPC 후보는 source_backlog에서 parser·ToS·개인정보·case id mapping 검증 후 단계적 활성화
- 정책별 consultation deadline·effective date·enforcement outcome·근거 URL을 결과 리포트에 함께 표시

## 운영 규칙

- 원문 URL, 수집일, 이벤트 발생일은 별도 필드로 유지한다.
- 공식 source와 커뮤니티/시장 source를 같은 신뢰 등급으로 병합하지 않는다.
- collector가 인증키나 네트워크 제한으로 skip되면 실패를 숨기지 말고 skip 사유를 기록한다.
- 이 문서는 `scripts/build_data_quality_review.py --write-repo-plans`로 재생성한다.
