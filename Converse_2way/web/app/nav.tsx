"use client";

import Link from "next/link";
import { LangToggle, useLang } from "@/lib/i18n";

/** Nav bar. A client component so the language toggle can live in it. */
export default function Nav() {
  const { t } = useLang();
  return (
    <nav className="flex items-center gap-4 border-b border-neutral-200 px-6 py-3 text-sm text-neutral-600">
      <Link href="/conversation" className="hover:text-accent">
        {t.navConversation}
      </Link>
      <Link href="/reports" className="hover:text-accent">
        {t.navReports}
      </Link>
      <Link href="/reminders" className="hover:text-accent">
        {t.navReminders}
      </Link>
      <LangToggle />
    </nav>
  );
}
