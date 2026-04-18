import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "wevelStock",
  description: "AI 주식 분석 & 매매가이드 시스템",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}
