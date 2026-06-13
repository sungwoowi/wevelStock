import "./globals.css";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cn } from "@/lib/utils";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { AppShell } from "@/components/nav/AppShell";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "FractalSignal",
  description: "AI 멀티에이전트 주식 분석 & 페이퍼 트레이딩 데스크",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="ko"
      suppressHydrationWarning
      className={cn("font-sans", geist.variable, geistMono.variable)}
    >
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
