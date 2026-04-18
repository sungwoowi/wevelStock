# webapp (Next.js 1페이지 데모)

## 역할
토대 데모용 1페이지 UI. **버려지는 코드** — Wave 6에서 정식 웹앱으로 대체 예정.

## 구성
- `src/app/page.tsx` — 유일한 페이지. DemoRunner + PrincipleCard + BriefingCard + AlertList
- `src/components/` — 각 카드 컴포넌트
- `src/lib/api.ts` — `fetcher` + 타입

## 실행
```bash
npm install     # 또는 pnpm install (윈도우에서 EPERM 나면 npm 사용)
npm run dev     # 또는 pnpm dev
# http://localhost:3000
```

`NEXT_PUBLIC_API_BASE` 환경변수로 서버 주소 지정 (기본 http://localhost:8000).

## 규칙
- **API 호출은 server/api 로만**. 직접 DB 접근 금지.
- 5초 polling (SWR). WebSocket은 Wave 6 이후 고려.
- 버려질 코드이므로 과도한 추상화 금지.
