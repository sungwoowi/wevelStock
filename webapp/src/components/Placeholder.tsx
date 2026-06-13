import Link from "next/link";

/** 2차 구현 예정 화면용 placeholder. 탭/라우트 존재 보장 (404 방지). */
export function Placeholder({
  title,
  note,
  devHref,
}: {
  title: string;
  note: string;
  devHref?: string;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-bold text-foreground">{title}</h1>
      <p className="max-w-md text-sm text-muted-foreground">{note}</p>
      <span className="rounded-full border border-amber/70 bg-amber-bg px-3 py-1 text-xs font-medium text-amber">
        다음 세션 구현 예정
      </span>
      {devHref && (
        <Link href={devHref} className="text-xs text-primary underline">
          R&D 버전 보기
        </Link>
      )}
    </div>
  );
}
