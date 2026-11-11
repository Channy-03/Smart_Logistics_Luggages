import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = { title: "R_ROUTE", description: "반품을 돌려보내지 않는 물류" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" />
      </head>
      <body className="font-sans">
        <Nav />
        <main className="mx-auto max-w-[1180px] px-4 pb-24 pt-7">{children}</main>
      </body>
    </html>
  );
}
