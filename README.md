# Quality Process Job Recommender

매일 08:00 KST에 품질/공정 관련 공고를 수집하고, 경력기술서 기반 프로필과의 적합도를 계산해 추천합니다.

## 포함 소스 (우선순위)
- `wanted`
- `jobkorea`
- `saramin`
- `linkedin`
- `remoteok` (글로벌 보조 소스)

각 소스는 페이지 구조 변경/차단 가능성이 있어 실패 시 자동으로 skip되고 전체 파이프라인은 계속 진행됩니다.

## 스코어링 기준
- 직무 키워드 일치: `45%`
- 산업 도메인 키워드 일치: `20%`
- 스킬/툴 키워드 일치: `20%`
- 연차/레벨 신호 일치: `15%`

`config/profile.yaml`에서 가중치/키워드를 조정할 수 있습니다.

## 결과물
- `output/latest.json`
- `output/latest.md`
- 실행 시각별 `output/recommendations_*.json|md`

## 이메일 알림 (GitHub Secrets)
아래 Secrets를 저장소에 설정하세요.
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_TO` (콤마로 다중 수신자)

예시(Gmail):
- host: `smtp.gmail.com`
- port: `587`
- password: 앱 비밀번호

## GitHub Actions
- `.github/workflows/daily.yml`
  - `cron: 0 23 * * *` (UTC 기준, KST 08:00)
- `.github/workflows/manual.yml`
  - 수동 테스트 실행

## 로컬 실행
```powershell
pip install -r requirements.txt
python scripts/run_daily.py --limit 20
```

## 주의
- 공개 사이트 크롤링은 사이트 정책/robots.txt를 준수해야 합니다.
- 소스별 차단/구조 변경 시 selector 보정이 필요할 수 있습니다.
