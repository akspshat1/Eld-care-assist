"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import { useLang, type Lang } from "@/lib/i18n";
import { speakText } from "@/lib/speech";

type Resident = {
  id: number;
  name: string;
};

type Reminder = {
  id: number;
  resident_id: number;
  resident_name: string;
  time: string;
  content: string;
  is_active: number;
};

type DueReminder = {
  id: number;
  resident_name: string;
  content: string;
};

const POLL_INTERVAL_MS = 30000;

function speakReminder(
  r: { resident_name: string; content: string },
  phrase: (who: string, what: string) => string,
  lang: Lang,
) {
  speakText(phrase(r.resident_name, r.content), lang);
}

export default function RemindersPage() {
  const { t, lang } = useLang();
  const [residents, setResidents] = useState<Resident[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  const [residentId, setResidentId] = useState<number | null>(null);
  const [time, setTime] = useState("09:00");
  const [content, setContent] = useState("");

  async function refreshReminders() {
    const data = await apiGet<Reminder[]>("/reminders");
    setReminders(data);
  }

  useEffect(() => {
    apiGet<Resident[]>("/residents").then((data) => {
      setResidents(data);
      if (data.length > 0) setResidentId(data[0].id);
    });
    refreshReminders();
  }, []);

  // Poll the backend for due reminders and speak them in the browser.
  useEffect(() => {
    async function poll() {
      const due = await apiGet<DueReminder[]>("/reminders/due");
      due.forEach((d) => speakReminder(d, t.reminderSpeech, lang));
    }
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  async function handleAdd() {
    if (residentId === null || !content) return;
    await apiPost("/reminders", { resident_id: residentId, time, content });
    setContent("");
    refreshReminders();
  }

  async function handleToggle(reminder: Reminder) {
    await apiPatch(`/reminders/${reminder.id}`, { is_active: !reminder.is_active });
    refreshReminders();
  }

  async function handleDelete(reminder: Reminder) {
    await apiDelete(`/reminders/${reminder.id}`);
    refreshReminders();
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      <h1 className="text-xl font-medium text-neutral-900">{t.reminders}</h1>

      <section className="flex flex-col gap-2 rounded border border-neutral-200 p-4">
        <h2 className="text-sm font-medium text-neutral-700">{t.addReminder}</h2>
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
            value={residentId ?? ""}
            onChange={(e) => setResidentId(Number(e.target.value))}
          >
            {residents.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <input
            type="time"
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
          <input
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder={t.reminderPlaceholder}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <button
            className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-40"
            onClick={handleAdd}
            disabled={!content}
          >
            {t.add}
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        {reminders.length === 0 && (
          <p className="text-sm text-neutral-400">{t.noReminders}</p>
        )}
        {reminders.map((r) => (
          <div
            key={r.id}
            className="flex items-center gap-3 rounded border border-neutral-200 p-3 text-sm"
          >
            <span className="w-20 text-neutral-500">{r.time}</span>
            <span className="w-24 text-neutral-700">{r.resident_name}</span>
            <span className="flex-1 text-neutral-900">{r.content}</span>
            <label className="flex items-center gap-1 text-xs text-neutral-500">
              <input
                type="checkbox"
                className="accent-orange-700"
                checked={!!r.is_active}
                onChange={() => handleToggle(r)}
              />
              {t.active}
            </label>
            <button
              className="text-xs text-accent underline"
              onClick={() => speakReminder(r, t.reminderSpeech, lang)}
            >
              {t.playNow}
            </button>
            <button
              className="text-xs text-red-600 underline"
              onClick={() => handleDelete(r)}
            >
              {t.delete}
            </button>
          </div>
        ))}
      </section>
    </main>
  );
}
