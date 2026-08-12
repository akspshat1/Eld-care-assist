"use client";

/**
 * UI translations. English is the default; a toggle in the nav switches to
 * Japanese and the choice is remembered in localStorage.
 *
 * Only interface text lives here. Conversation content, personas and AI
 * replies stay in whatever language the model and the data use.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Lang = "en" | "ja";

const STRINGS = {
  en: {
    // layout / nav
    appTitle: "Conversation & Care-Record AI",
    navConversation: "Conversation",
    navReports: "Handoff Report",
    navReminders: "Reminders",

    // home
    backendStatus: "Backend connection:",
    checking: "checking...",
    ok: "OK",
    cannotConnect: "cannot connect",

    // conversation
    conversation: "Conversation",
    resident: "Resident",
    personality: "Personality",
    favoriteTopics: "Favourite topics",
    addResident: "Add a new resident",
    name: "Name",
    personalityPlaceholder: "Personality",
    topicsPlaceholder: "Favourite topics (separate with 、)",
    add: "Add",
    noConversation: "No conversation yet.",
    thinking: "Thinking...",
    handsFreeActive: "Hands-free conversation active — just speak and it replies.",
    handsFreeStop: "End hands-free conversation",
    handsFreeStart: "Start hands-free conversation",
    messagePlaceholder: "Type a message",
    stop: "Stop",
    record: "Record",
    send: "Send",
    savingRecord: "Creating record...",
    saveRecord: "Save a record of this conversation",
    mood: "Mood",
    summary: "Summary",
    notablePoints: "Notable points",

    // reports
    handoffReport: "Handoff Report",
    targetDate: "Date",
    everyone: "Everyone",
    generating: "Generating...",
    generateReport: "Generate report",
    noRecords:
      "No conversation records found for this day. Save a record on the Conversation page first.",
    copied: "Copied",
    copy: "Copy",

    // reminders
    reminders: "Reminders",
    addReminder: "Add a new reminder",
    reminderPlaceholder:
      "Content (e.g. time to take medicine, drink water, exercise)",
    noReminders: "No reminders yet.",
    active: "Active",
    playNow: "Play now",
    delete: "Delete",
    /** Spoken aloud, so it stays natural in each language. */
    reminderSpeech: (who: string, what: string) => `${who}, it's time for ${what}.`,
    noVoiceWarning:
      "No text-to-speech voice for this language is installed on this computer, so replies cannot be read aloud. Install one in Windows Settings > Time & language > Language & region > (language) > Options > Speech, or open this page in Microsoft Edge, which provides online voices.",
  },
  ja: {
    appTitle: "会話×記録自動化AI",
    navConversation: "会話",
    navReports: "申し送りレポート",
    navReminders: "リマインダー",

    backendStatus: "バックエンド接続:",
    checking: "確認中...",
    ok: "OK",
    cannotConnect: "接続できません",

    conversation: "会話",
    resident: "入居者",
    personality: "性格",
    favoriteTopics: "好きな話題",
    addResident: "新しい入居者を追加",
    name: "名前",
    personalityPlaceholder: "性格",
    topicsPlaceholder: "好きな話題（「、」で区切る）",
    add: "追加",
    noConversation: "まだ会話がありません。",
    thinking: "考え中...",
    handsFreeActive: "ハンズフリー会話中... 話しかけると自動で応答します。",
    handsFreeStop: "ハンズフリー会話を終了",
    handsFreeStart: "ハンズフリー会話を開始",
    messagePlaceholder: "メッセージを入力してください",
    stop: "停止",
    record: "録音",
    send: "送信",
    savingRecord: "記録を作成中...",
    saveRecord: "この会話の記録を保存",
    mood: "気分",
    summary: "要約",
    notablePoints: "特記事項",

    handoffReport: "申し送りレポート",
    targetDate: "対象日",
    everyone: "全員",
    generating: "生成中...",
    generateReport: "レポートを生成",
    noRecords:
      "この日の会話記録が見つかりません。会話ページで記録を保存してからお試しください。",
    copied: "コピーしました",
    copy: "コピー",

    reminders: "リマインダー",
    addReminder: "新しいリマインダーを追加",
    reminderPlaceholder: "内容（例: お薬を飲む時間、水分補給、体操の時間）",
    noReminders: "まだリマインダーがありません。",
    active: "有効",
    playNow: "今すぐ再生",
    delete: "削除",
    reminderSpeech: (who: string, what: string) =>
      `${who}さん、${what}の時間です。`,
    noVoiceWarning:
      "このパソコンにこの言語の音声合成ボイスが入っていないため、読み上げできません。Windowsの設定＞時刻と言語＞言語と地域＞（言語）＞オプション＞音声 から追加するか、オンライン音声が使える Microsoft Edge で開いてください。",
  },
};
// No `as const`: it would pin every English string to its own literal type,
// and the Japanese dictionary would then fail to match.

type Dict = (typeof STRINGS)["en"];

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Dict;
}>({ lang: "en", setLang: () => {}, t: STRINGS.en });

const STORAGE_KEY = "care_ui_lang";

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  // Read the saved choice after mount: server and first client render must
  // match, so this cannot be done in useState's initialiser.
  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "ja" || saved === "en") setLangState(saved);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    window.localStorage.setItem(STORAGE_KEY, l);
  }, []);

  return (
    <LangContext.Provider value={{ lang, setLang, t: STRINGS[lang] }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}

/** EN / 日本語 switch for the nav bar. */
export function LangToggle() {
  const { lang, setLang } = useLang();
  const base =
    "px-2 py-0.5 text-xs font-medium transition-colors cursor-pointer";
  return (
    <div className="ml-auto flex overflow-hidden rounded border border-neutral-300">
      <button
        type="button"
        onClick={() => setLang("en")}
        className={`${base} ${
          lang === "en" ? "bg-neutral-800 text-white" : "text-neutral-500"
        }`}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLang("ja")}
        className={`${base} ${
          lang === "ja" ? "bg-neutral-800 text-white" : "text-neutral-500"
        }`}
      >
        日本語
      </button>
    </div>
  );
}
