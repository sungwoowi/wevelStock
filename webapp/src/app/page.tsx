import { AlertList } from "@/components/AlertList";
import { BriefingPartsCard } from "@/components/BriefingPartsCard";
import { DemoRunner } from "@/components/DemoRunner";
import { PrincipleCard } from "@/components/PrincipleCard";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl p-6 md:p-10 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          wevelStock
          <span className="ml-3 text-base font-normal text-neutral-500">
            1페이지 데모 · 버려지는 UI (Wave 6 에서 정식 웹앱 대체 예정)
          </span>
        </h1>
        <p className="mt-2 text-sm text-neutral-400">
          두 팀 · 두 패턴(규칙 + LLM) 이 풀사이클로 작동하는 것을 시연합니다.
          <br />
          API 키 없이도 mock 응답으로 데모 가능합니다.
        </p>
      </header>

      <a
        href="/production-chat"
        className="block border border-emerald-700 bg-emerald-950/50 hover:bg-emerald-900/50 rounded-md p-4 transition"
      >
        <div className="text-xs uppercase tracking-wider text-emerald-400">
          ✨ production UX — 자연어 채팅 (PROD-UX-1)
        </div>
        <div className="text-base font-medium mt-1">
          하나의 채팅창, 백단 0 노출 — 자동 분류 + 분석가/전략가 호출
        </div>
        <div className="text-xs text-neutral-400 mt-1">
          "삼성전자 살까?" → 자동 시나리오 분류 (1~11) → track_a / track_b / 분석가 호출.
          PROD-UX-1 = raw 응답, PROD-UX-2 후속 = 1~3줄 자연어 압축.
        </div>
      </a>

      <a
        href="/analyst-chat"
        className="block border border-neutral-800 bg-neutral-950/30 hover:bg-neutral-900/50 rounded-md p-4 transition"
      >
        <div className="text-xs uppercase tracking-wider text-neutral-500">
          Layer 2 · 3 — R&D 비교 데모 (백단 노출)
        </div>
        <div className="text-base font-medium mt-1">
          분석가 ↔ 전략가 좌/우 분할 (멀티턴 채팅 + agent 선택)
        </div>
        <div className="text-xs text-neutral-400 mt-1">
          agent_id / target / Layer 토글 모두 노출 — 양쪽 호출 톤·근거 비교용.
          누적 토큰·캐시 hit·비용 가시화.
        </div>
      </a>

      <DemoRunner />

      <BriefingPartsCard />

      <PrincipleCard />

      <AlertList />

      <footer className="pt-6 text-xs text-neutral-600 font-mono">
        API: <span className="text-neutral-500">
          {process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"}
        </span>
        {" · "}docs: <a href="/docs" className="underline">FastAPI docs</a>
      </footer>
    </main>
  );
}
