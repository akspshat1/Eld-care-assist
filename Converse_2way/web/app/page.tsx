"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useLang } from "@/lib/i18n";

type HealthResponse = { status: string };
type ConnectionState = "loading" | "ok" | "error";

export default function Home() {
  const { t } = useLang();
  const [connection, setConnection] = useState<ConnectionState>("loading");

  useEffect(() => {
    apiGet<HealthResponse>("/health")
      .then((data) => setConnection(data.status === "ok" ? "ok" : "error"))
      .catch(() => setConnection("error"));
  }, []);

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-2xl font-medium text-neutral-900">{t.appTitle}</h1>
      <p className="text-sm text-neutral-500">
        {t.backendStatus}{" "}
        {connection === "loading" && t.checking}
        {connection === "ok" && t.ok}
        {connection === "error" && t.cannotConnect}
      </p>
    </main>
  );
}
