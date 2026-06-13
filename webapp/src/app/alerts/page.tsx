import { Placeholder } from "@/components/Placeholder";

export default function AlertsPage() {
  return (
    <Placeholder
      title="알림"
      note="🔴 즉시 / 🟢 발생 시 / 🔵 하루 정량 알림. /api/notifications(영속·미독 카운트·읽음 처리)는 동작 중 — 화면 본체는 다음 세션."
    />
  );
}
