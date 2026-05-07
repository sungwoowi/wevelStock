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
        href="/analyst-chat"
        className="block border border-emerald-900 bg-emerald-950/30 hover:bg-emerald-950/50 rounded-md p-4 transition"
      >
        <div className="text-xs uppercase tracking-wider text-emerald-500">
          Layer 2 — 추론부 데모
        </div>
        <div className="text-base font-medium mt-1">
          자산전략가에 자유 질문 (멀티턴 채팅)
        </div>
        <div className="text-xs text-neutral-400 mt-1">
          canon (19K chars) + RAG 회수 (박종훈 강의) + persona 결합 응답.
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
