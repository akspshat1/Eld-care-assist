"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type HealthResponse = { status: string };
type ConnectionState = "loading" | "ok" | "error";

export default function Home() {
  const [connection, setConnection] = useState<ConnectionState>("loading");

  useEffect(() => {
    apiGet<HealthResponse>("/health")
      .then((data) => setConnection(data.status === "ok" ? "ok" : "error"))
      .catch(() => setConnection("error"));
  }, []);

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-medium text-neutral-900">会話×記録自動化AI</h1>
      <p className="text-sm text-neutral-500">
        バックエンド接続:{" "}
        {connection === "loading" && "確認中..."}
        {connection === "ok" && "OK"}
        {connection === "error" && "接続できません"}
      </p>
    </main>
  );
}
