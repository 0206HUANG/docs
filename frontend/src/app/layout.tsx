import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EmailAI - 企业邮箱AI托管系统",
  description: "AI-powered enterprise email management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  );
}
