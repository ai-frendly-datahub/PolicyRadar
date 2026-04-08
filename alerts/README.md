# PolicyRadar Alert System

PolicyRadar의 정책 변경 알림 시스템입니다. DuckDB에서 수집된 기사를 분석하여 중요한 정책 변경을 감지하고 알림을 전송합니다.

## 기능

- **정책 변경 감지**: 시행, 개정, 폐지, 신설 등 핵심 키워드 기반 탐지
- **우선순위 분류**: 긴급/중요/정보 3단계 우선순위
- **한국어 알림 메시지**: 한국어로 작성된 알림 메시지 생성
- **Telegram 연동**: Telegram Bot을 통한 알림 전송 (선택사항)

## 설치

PolicyRadar의 의존성이 이미 설치되어 있다면 추가 설치가 필요 없습니다.

```bash
cd PolicyRadar
pip install -r requirements.txt
```

## 사용법

### CLI 사용

#### 정책 변경 스캔
```bash
# 기본 스캔 (최근 24시간)
python -m alerts.alert_monitor --db-path data/radar_data.duckdb

# 시간 범위 지정
python -m alerts.alert_monitor --db-path data/radar_data.duckdb --hours 48

# JSON 출력
python -m alerts.alert_monitor --db-path data/radar_data.duckdb --output json
```

#### Telegram 알림 전송
```bash
# 환경변수 설정 필요
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# 알림 전송
python -m alerts.telegram_notifier --db-path data/radar_data.duckdb

# 미리보기 (전송 없이)
python -m alerts.telegram_notifier --db-path data/radar_data.duckdb --dry-run
```

### Python API 사용

```python
from pathlib import Path
from alerts import AlertMonitor

# 모니터 초기화
monitor = AlertMonitor(Path("data/radar_data.duckdb"))

# 정책 변경 스캔
alerts = monitor.scan_articles(category="policy", hours=24)

# 알림 메시지 생성
message = monitor.generate_alert_message(alerts)
print(message)
```

## 설정

`config.yaml`에서 알림 설정을 커스터마이징할 수 있습니다.

### 키워드 설정
```yaml
alert_keywords:
  implementation:
    - "시행"
    - "시행령"
  amendment:
    - "개정"
    - "개정안"
  abolition:
    - "폐지"
  establishment:
    - "신설"
    - "제정"
```

### 임계값 설정
```yaml
thresholds:
  min_articles: 1           # 최소 알림 기사 수
  max_articles_per_alert: 10 # 알림당 최대 기사 수
  recent_hours: 24          # 스캔 시간 범위
```

### 우선순위 설정
```yaml
priority_levels:
  high:
    keywords: ["시행", "폐지", "제정"]
    description: "즉각 조치 필요"
  medium:
    keywords: ["개정", "개정안"]
    description: "검토 필요"
  low:
    keywords: ["신설", "도입"]
    description: "정보 제공"
```

## Telegram 봇 설정

1. [@BotFather](https://t.me/BotFather)에서 새 봇 생성
2. 봇 토큰 받기 (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
3. 채팅 ID 확인:
   - 개인 채팅: 봇에 메시지 전송 후 `https://api.telegram.org/bot{TOKEN}/getUpdates` 호출
   - 그룹: 그룹에 봇 추가 후 위와 같이 확인
4. 환경변수 설정:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export TELEGRAM_CHAT_ID="your-chat-id"
   ```

## GitHub Actions 연동

워크플로우에서 데이터 수집 후 알림을 실행하려면:

```yaml
- name: Run Policy Alert Monitor
  continue-on-error: true
  env:
    TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
  run: |
    python -m alerts.telegram_notifier \
      --db-path data/radar_data.duckdb \
      --category policy \
      --hours 24
```

## 출력 예시

### 텍스트 출력
```
[정책 변경 알림] 2026-04-08 10:30

=== 긴급 (즉각 조치 필요) ===
  - 개인정보보호법 시행령 개정안 시행
    출처: 법제처
    키워드: 시행, 개정
    링크: https://example.com/article1

=== 중요 (검토 필요) ===
  - 금융소비자보호법 일부개정
    출처: 금융위원회
    키워드: 개정
    링크: https://example.com/article2

총 2건의 정책 변경이 감지되었습니다.
```

### JSON 출력
```json
{
  "timestamp": "2026-04-08T01:30:00+00:00",
  "category": "policy",
  "hours_scanned": 24,
  "alert_count": 2,
  "alerts": [
    {
      "title": "개인정보보호법 시행령 개정안 시행",
      "link": "https://example.com/article1",
      "source": "법제처",
      "priority": "high",
      "matched_keywords": ["시행", "개정"]
    }
  ]
}
```

## 종료 코드

- `0`: 정상 종료 (긴급 알림 없음)
- `1`: 긴급(high) 우선순위 알림 존재

이를 활용하여 CI/CD 파이프라인에서 긴급 정책 변경 시 추가 조치를 트리거할 수 있습니다.
