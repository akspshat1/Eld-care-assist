"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPostForm } from "@/lib/api";

type Resident = {
  id: number;
  name: string;
  personality: string;
  favorite_topics: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

type Extraction = {
  mood: string;
  summary: string;
  notable_points: string;
};

function speak(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ja-JP";
  window.speechSynthesis.speak(utterance);
}

export default function ConversationPage() {
  const [residents, setResidents] = useState<Resident[]>([]);
  const [selectedResidentId, setSelectedResidentId] = useState<number | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPersonality, setNewPersonality] = useState("");
  const [newTopics, setNewTopics] = useState("");

  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  useEffect(() => {
    apiGet<Resident[]>("/residents").then((data) => {
      setResidents(data);
      if (data.length > 0) setSelectedResidentId(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (selectedResidentId === null) return;
    apiPost<{ conversation_id: number }>("/conversations", {
      resident_id: selectedResidentId,
    }).then((data) => {
      setConversationId(data.conversation_id);
      setMessages([]);
      setExtraction(null);
    });
  }, [selectedResidentId]);

  const selectedResident = residents.find((r) => r.id === selectedResidentId) ?? null;

  async function handleAddResident() {
    if (!newName) return;
    await apiPost("/residents", {
      name: newName,
      personality: newPersonality,
      favorite_topics: newTopics,
    });
    const updated = await apiGet<Resident[]>("/residents");
    setResidents(updated);
    setNewName("");
    setNewPersonality("");
    setNewTopics("");
    setShowAddForm(false);
  }

  async function handleSend() {
    if (!textInput.trim() || conversationId === null || isSending) return;
    const content = textInput.trim();
    setTextInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content, created_at: new Date().toISOString() },
    ]);
    setIsSending(true);
    try {
      const data = await apiPost<{ reply: string }>(
        `/conversations/${conversationId}/messages`,
        { content }
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, created_at: new Date().toISOString() },
      ]);
      speak(data.reply);
    } finally {
      setIsSending(false);
    }
  }

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    audioChunksRef.current = [];
    recorder.ondataavailable = (e) => audioChunksRef.current.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      handleAudioSend(new Blob(audioChunksRef.current, { type: recorder.mimeType }));
    };
    mediaRecorderRef.current = recorder;
    recorder.start();
    setIsRecording(true);
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }

  async function handleAudioSend(audioBlob: Blob) {
    if (conversationId === null) return;
    setIsSending(true);
    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "audio.webm");
      const data = await apiPostForm<{ transcribed_text: string; reply: string }>(
        `/conversations/${conversationId}/messages/audio`,
        formData
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: data.transcribed_text,
          created_at: new Date().toISOString(),
        },
        { role: "assistant", content: data.reply, created_at: new Date().toISOString() },
      ]);
      speak(data.reply);
    } finally {
      setIsSending(false);
    }
  }

  async function handleExtract() {
    if (conversationId === null || messages.length === 0) return;
    setIsExtracting(true);
    try {
      const result = await apiPost<Extraction>(`/conversations/${conversationId}/extract`, {});
      setExtraction(result);
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      <h1 className="text-xl font-medium text-neutral-900">会話</h1>

      <section className="flex flex-col gap-2">
        <label className="text-sm text-neutral-600" htmlFor="resident-select">
          入居者
        </label>
        <select
          id="resident-select"
          className="rounded border border-neutral-300 px-3 py-2 text-sm"
          value={selectedResidentId ?? ""}
          onChange={(e) => setSelectedResidentId(Number(e.target.value))}
        >
          {residents.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        {selectedResident && (
          <p className="text-xs text-neutral-500">
            性格: {selectedResident.personality} / 好きな話題: {selectedResident.favorite_topics}
          </p>
        )}

        <button
          className="self-start text-xs text-accent underline"
          onClick={() => setShowAddForm((v) => !v)}
        >
          新しい入居者を追加
        </button>
        {showAddForm && (
          <div className="flex flex-col gap-2 rounded border border-neutral-200 p-3">
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder="名前"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder="性格"
              value={newPersonality}
              onChange={(e) => setNewPersonality(e.target.value)}
            />
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder="好きな話題（「、」で区切る）"
              value={newTopics}
              onChange={(e) => setNewTopics(e.target.value)}
            />
            <button
              className="self-start rounded bg-accent px-3 py-1 text-sm text-white hover:bg-accent-hover"
              onClick={handleAddResident}
            >
              追加
            </button>
          </div>
        )}
      </section>

      <section className="flex flex-1 flex-col gap-3 overflow-y-auto rounded border border-neutral-200 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">まだ会話がありません。</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[80%] rounded px-3 py-2 text-sm ${
              m.role === "user"
                ? "self-end bg-accent text-white"
                : "self-start bg-neutral-100 text-neutral-900"
            }`}
          >
            {m.content}
          </div>
        ))}
        {isSending && <p className="text-sm text-neutral-400">考え中...</p>}
      </section>

      <section className="flex gap-2">
        <input
          className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
          placeholder="メッセージを入力してください"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
        />
        <button
          className={`rounded px-4 py-2 text-sm ${
            isRecording ? "bg-red-600 text-white" : "border border-neutral-300 text-neutral-700"
          }`}
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isSending}
        >
          {isRecording ? "停止" : "録音"}
        </button>
        <button
          className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-40"
          onClick={handleSend}
          disabled={isSending || !textInput.trim()}
        >
          送信
        </button>
      </section>

      <section className="flex flex-col gap-2 rounded border border-neutral-200 p-4">
        <button
          className="self-start rounded border border-neutral-300 px-3 py-1 text-sm text-neutral-700 disabled:opacity-40"
          onClick={handleExtract}
          disabled={isExtracting || messages.length === 0}
        >
          {isExtracting ? "記録を作成中..." : "この会話の記録を保存"}
        </button>
        {extraction && (
          <div className="text-sm text-neutral-600">
            <p>気分: {extraction.mood}</p>
            <p>要約: {extraction.summary}</p>
            <p>特記事項: {extraction.notable_points}</p>
          </div>
        )}
      </section>
    </main>
  );
}
