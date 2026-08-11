import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "会話×記録自動化AI",
  description: "高齢者施設向け 会話×記録自動化AI",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <nav className="flex gap-4 border-b border-neutral-200 px-6 py-3 text-sm text-neutral-600">
          <Link href="/conversation" className="hover:text-accent">
            会話
          </Link>
          <Link href="/reports" className="hover:text-accent">
            申し送りレポート
          </Link>
          <Link href="/reminders" className="hover:text-accent">
            リマインダー
          </Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
