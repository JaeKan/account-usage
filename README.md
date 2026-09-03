# account-usage

Hermes Desktop 상태바 플러그인 — Codex / Claude / OpenRouter 사용량을 칩 3개로 표시.

- 호버: 전체 구간 팝오버 (프로그레스바·리셋 시각 포함)
- 클릭: 각 제공자 사용량 페이지 외부 열기

## 설치

```
<repo> → %LOCALAPPDATA%\hermes\desktop-plugins\account-usage\ 에 복사
데스크탑 ⌘K → Reload desktop plugins
```

## 검증

```
node --check plugin.js
node --test tests/icon-layout.test.mjs
```
