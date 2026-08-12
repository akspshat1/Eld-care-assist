"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useLang } from "@/lib/i18n";

type Resident = {
  id: number;
  name: string;
};

type Report = {
  resident_id: number;
  resident_name: string;
  report: string;
};

function todayAsInputValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export default function ReportsPage() {
  const { t, lang } = useLang();
  const [residents, setResidents] = useState<Resident[]>([]);
  const [selectedResidentId, setSelectedResidentId] = useState(0); // 0 = all
  const [date, setDate] = useState(todayAsInputValue());
  const [reports, setReports] = useState<Report[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  useEffect(() => {
    apiGet<Resident[]>("/residents").then(setResidents);
  }, []);

  async function handleGenerate() {
    setIsLoading(true);
    setReports(null);
    try {
      const query =
        selectedResidentId === 0
          ? `?date=${date}&lang=${lang}`
          : `?date=${date}&resident_id=${selectedResidentId}&lang=${lang}`;
      const data = await apiGet<Report[]>(`/reports${query}`);
      setReports(data);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCopy(report: Report) {
    await navigator.clipboard.writeText(report.report);
    setCopiedId(report.resident_id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      <h1 className="text-xl font-medium text-neutral-900">{t.handoffReport}</h1>

      <section className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-sm text-neutral-600" htmlFor="date-input">
            {t.targetDate}
          </label>
          <input
            id="date-input"
            type="date"
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-sm text-neutral-600" htmlFor="resident-filter">
            {t.resident}
          </label>
          <select
            id="resident-filter"
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
            value={selectedResidentId}
            onChange={(e) => setSelectedResidentId(Number(e.target.value))}
          >
            <option value={0}>{t.everyone}</option>
            {residents.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <button
          className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-40"
          onClick={handleGenerate}
          disabled={isLoading}
        >
          {isLoading ? t.generating : t.generateReport}
        </button>
      </section>

      {reports !== null && reports.length === 0 && (
        <p className="text-sm text-neutral-500">
          {t.noRecords}
        </p>
      )}

      {reports?.map((r) => (
        <section key={r.resident_id} className="flex flex-col gap-2 rounded border border-neutral-200 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-neutral-900">{r.resident_name}</h2>
            <button
              className="text-xs text-accent underline"
              onClick={() => handleCopy(r)}
            >
              {copiedId === r.resident_id ? t.copied : t.copy}
            </button>
          </div>
          <textarea
            className="min-h-[160px] rounded border border-neutral-200 bg-neutral-50 p-3 text-sm text-neutral-800"
            readOnly
            value={r.report}
          />
        </section>
      ))}
    </main>
  );
}
