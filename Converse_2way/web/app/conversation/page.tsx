"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPostForm } from "@/lib/api";
import { startHandsFreeCall, type HandsFreeCall } from "@/lib/webrtc";
import { useLang } from "@/lib/i18n";
import { hasVoiceFor, speakText, stopSpeaking } from "@/lib/speech";

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



export default function ConversationPage() {
  const { t, lang } = useLang();
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

  const [isHandsFree, setIsHandsFree] = useState(false);
  const handsFreeCallRef = useRef<HandsFreeCall | null>(null);

  const [noVoice, setNoVoice] = useState(false);

  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  useEffect(() => {
    // Warn up front if this machine has no voice for the chosen language,
    // rather than letting playback fail silently.
    hasVoiceFor(lang).then((has) => setNoVoice(!has));
  }, [lang]);

  useEffect(() => {
    apiGet<Resident[]>("/residents").then((data) => {
      setResidents(data);
      if (data.length > 0) setSelectedResidentId(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (selectedResidentId === null) return;
    if (handsFreeCallRef.current) {
      handsFreeCallRef.current.stop();
      handsFreeCallRef.current = null;
      setIsHandsFree(false);
    }
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
        { content, lang }
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, created_at: new Date().toISOString() },
      ]);
      speakText(data.reply, lang);
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
        `/conversations/${conversationId}/messages/audio?lang=${lang}`,
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
      speakText(data.reply, lang);
    } finally {
      setIsSending(false);
    }
  }

  async function startHandsFree() {
    if (conversationId === null || isHandsFree) return;
    setIsHandsFree(true);
    handsFreeCallRef.current = await startHandsFreeCall(
      conversationId,
      (msg) => {
        setMessages((prev) => [
          ...prev,
          { role: msg.role, content: msg.text, created_at: new Date().toISOString() },
        ]);
        if (msg.role === "assistant") speakText(msg.text, lang);
      },
      {
        lang,
        // Barge-in: the moment the resident speaks, stop the assistant talking
        // over them.
        onUserSpeaking: stopSpeaking,
      },
    );
  }

  async function stopHandsFree() {
    handsFreeCallRef.current?.stop();
    handsFreeCallRef.current = null;
    setIsHandsFree(false);
    stopSpeaking();
    // Re-sync with the DB in case any turn's app-message arrived out of order.
    if (conversationId !== null) {
      const data = await apiGet<Message[]>(`/conversations/${conversationId}/messages`);
      // Skip any blank rows so they cannot show up as empty bubbles.
      setMessages(data.filter((m) => m.content && m.content.trim().length > 0));
    }
  }

  useEffect(() => {
    return () => {
      handsFreeCallRef.current?.stop();
      stopSpeaking();
    };
  }, []);

  async function handleExtract() {
    if (conversationId === null || messages.length === 0) return;
    setIsExtracting(true);
    try {
      const result = await apiPost<Extraction>(
        `/conversations/${conversationId}/extract?lang=${lang}`,
        {},
      );
      setExtraction(result);
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      <h1 className="text-xl font-medium text-neutral-900">{t.conversation}</h1>

      {noVoice && (
        <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t.noVoiceWarning}
        </p>
      )}

      <section className="flex flex-col gap-2">
        <label className="text-sm text-neutral-600" htmlFor="resident-select">
          {t.resident}
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
            {t.personality}: {selectedResident.personality} / {t.favoriteTopics}: {selectedResident.favorite_topics}
          </p>
        )}

        <button
          className="self-start text-xs text-accent underline"
          onClick={() => setShowAddForm((v) => !v)}
        >
          {t.addResident}
        </button>
        {showAddForm && (
          <div className="flex flex-col gap-2 rounded border border-neutral-200 p-3">
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder={t.name}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder={t.personalityPlaceholder}
              value={newPersonality}
              onChange={(e) => setNewPersonality(e.target.value)}
            />
            <input
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
              placeholder={t.topicsPlaceholder}
              value={newTopics}
              onChange={(e) => setNewTopics(e.target.value)}
            />
            <button
              className="self-start rounded bg-accent px-3 py-1 text-sm text-white hover:bg-accent-hover"
              onClick={handleAddResident}
            >
              {t.add}
            </button>
          </div>
        )}
      </section>

      <section className="flex flex-1 flex-col gap-3 overflow-y-auto rounded border border-neutral-200 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">{t.noConversation}</p>
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
        {isSending && <p className="text-sm text-neutral-400">{t.thinking}</p>}
        {isHandsFree && (
          <p className="text-sm text-accent">
            {t.handsFreeActive}
          </p>
        )}
      </section>

      <section className="flex gap-2">
        <button
          className={`rounded px-4 py-2 text-sm font-medium ${
            isHandsFree
              ? "bg-red-600 text-white"
              : "border border-accent text-accent hover:bg-accent hover:text-white"
          }`}
          onClick={isHandsFree ? stopHandsFree : startHandsFree}
          disabled={conversationId === null || isRecording}
        >
          {isHandsFree ? t.handsFreeStop : t.handsFreeStart}
        </button>
      </section>

      <section className="flex gap-2">
        <input
          className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
          placeholder={t.messagePlaceholder}
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={isHandsFree}
        />
        <button
          className={`rounded px-4 py-2 text-sm ${
            isRecording ? "bg-red-600 text-white" : "border border-neutral-300 text-neutral-700"
          }`}
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isSending || isHandsFree}
        >
          {isRecording ? t.stop : t.record}
        </button>
        <button
          className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-40"
          onClick={handleSend}
          disabled={isSending || !textInput.trim() || isHandsFree}
        >
          {t.send}
        </button>
      </section>

      <section className="flex flex-col gap-2 rounded border border-neutral-200 p-4">
        <button
          className="self-start rounded border border-neutral-300 px-3 py-1 text-sm text-neutral-700 disabled:opacity-40"
          onClick={handleExtract}
          disabled={isExtracting || messages.length === 0}
        >
          {isExtracting ? t.savingRecord : t.saveRecord}
        </button>
        {extraction && (
          <div className="text-sm text-neutral-600">
            <p>{t.mood}: {extraction.mood}</p>
            <p>{t.summary}: {extraction.summary}</p>
            <p>{t.notablePoints}: {extraction.notable_points}</p>
          </div>
        )}
      </section>
    </main>
  );
}
