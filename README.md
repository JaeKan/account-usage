# account-usage

Hermes Desktop 상태바 플러그인 — Codex / Claude / Cursor / Antigravity / OpenRouter 사용량을 표시.

- 호버: 전체 구간 팝오버 (프로그레스바·API 리셋 시각 포함, 미제공 시 추측하지 않음)
- 클릭: 제공자 사용량 페이지. Cursor는 `https://cursor.com/dashboard/spending`, Antigravity는 외부 이동 없음.
- Codex `Team` 응답은 이 설치 소유자가 확인한 `Business Standard`로 표시합니다. 범용 상품 매핑이 아닙니다.
- 공급자별 독립 RPC로 응답한 칩부터 표시합니다. 백엔드 수정 반영에는 Hermes 재시작이 필요합니다.
- `account.usage` 게이트웨이 핸들러의 단일 진실 원천은 `backend/reapply_account_usage.py`입니다. Hermes 업데이트 후 칩이 `!`로 멈추면 hermes-agent 루트에서 `python <plugin>/backend/reapply_account_usage.py` → Hermes 재시작. 직접 수정 금지.

## 설치

```
<repo> → %LOCALAPPDATA%\hermes\desktop-plugins\account-usage\ 에 복사
데스크탑 ⌘K → Reload desktop plugins
```

## 검증

```
node --check plugin.js
node --test tests/icon-layout.test.mjs
# hermes-agent 루트에서 (RPC 복원·격리·리셋 크레딧 계약):
python %LOCALAPPDATA%\hermes\desktop-plugins\account-usage\tests\check_backend_contract.py
```
