import { Placeholder } from "@/components/Placeholder";

export default function ChatPage() {
  return (
    <Placeholder
      title="채팅"
      note="자연어 질문 → 자동 라우팅(intent + 종목 매핑 + Track) → 종합 답변. 기존 R&D production-chat(SSE)을 production 화면으로 다듬어 흡수 예정."
      devHref="/production-chat"
    />
  );
}
