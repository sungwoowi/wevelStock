import { AlertList } from "@/components/AlertList";
import { BriefingCard } from "@/components/BriefingCard";
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

      <DemoRunner />

      <div className="grid md:grid-cols-2 gap-4">
        <PrincipleCard />
        <BriefingCard />
      </div>

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
