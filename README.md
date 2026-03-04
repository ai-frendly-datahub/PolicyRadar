# PolicyRadar

정책/약관 변화 신호를 추적하는 경량 Radar 프로젝트입니다.

## Quick Start

```bash
pip install -r requirements.txt
python main.py --category policy --recent-days 7
```

- 카테고리 설정: `config/categories/policy.yaml`
- 리포트 출력: `reports/policy_report.html`
- DB 경로: `data/radar_data.duckdb`
