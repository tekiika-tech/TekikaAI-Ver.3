import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Agency — Tekika AI",
  description: "完全ローカル動作のプライベートAIエージェント Web UI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <html lang="ja">
      <body className="bg-zinc-900 text-zinc-100 antialiased">{children}</body>
    </html>
  );
}
