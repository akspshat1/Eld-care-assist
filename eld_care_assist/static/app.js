/* Elder Care Assistant - single-page front end.
   Everything talks to the one FastAPI server on this origin. */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* ---------------- translations ---------------- */
const T = {
 en: {
  brand:"Elder Care Assistant",
  tabHome:"Today", tabCheckin:"Check-in", tabTalk:"Talk", tabMeds:"Medicines", tabReport:"Report",
  todayTitle:"Today at a glance", quickStart:"Quick start", recentTitle:"Recent check-ins",
  cWellbeing:"WELLBEING", cLastCheck:"LAST CHECK-IN", cMeds:"MEDICINES TODAY", cTalks:"CONVERSATIONS",
  btnStartCheckin:"Start today's check-in", btnTalk:"Have a chat", btnMeds:"Medicines",
  checkinTitle:"Daily condition check-in",
  checkinSub:"A few simple questions, then an optional photo and voice note.",
  stepPhoto:"Photo (optional)",
  photoHelp:"A quick photo lets the app note the facial expression. The photo is never saved.",
  btnOpenCam:"Open camera", btnSnap:"Take photo", btnRetake:"Retake",
  stepVoice:"Voice note (optional)", voiceHelp:"Say how you are feeling in your own words.",
  btnRecord:"● Record", btnStop:"■ Stop", btnFinish:"Finish check-in",
  talkTitle:"Conversation",
  talkSub:"Type or speak. Spoken turns are saved so their tone can be analysed later.",
  chatPlaceholder:"Say something…", btnSend:"Send",
  btnAnalyzeVoice:"Analyse voice tone", btnSaveRecord:"Save conversation record",
  medsTitle:"Medicines", mScheduled:"SCHEDULED", mTaken:"TAKEN", mMissed:"MISSED", mNext:"NEXT",
  addRx:"Add a prescription",
  rxHelp:"Upload a photo of the prescription, or paste the text. You check it before anything is saved.",
  btnRxPhoto:"Choose a photo", btnReadRx:"Read with AI",
  rxPlaceholder:"Amlodipine 5mg — 1 tablet once daily in the morning, 30 days",
  reportTitle:"Handoff report", reportSub:"Everything from today, written up for the next caregiver.",
  btnMakeReport:"Generate report", btnExport:"Export CSV",
  disclaimer:"This app supports care — it does not provide diagnosis or medical advice. Emotion readings from a photo or voice are weak signals and can be wrong. Always rely on a person's own words and a caregiver's judgement, and contact medical help for anything urgent.",
  taken:"Taken", skip:"Skip", undo:"Undo", nothingToday:"Nothing scheduled today.",
  noRecent:"No check-ins yet.", noMeds:"No medicines saved yet.",
  reading:"Reading…", thinking:"Thinking…", working:"Working…",
  greetHello:n=>`Hello, ${n}.`,
  wellLabel:s=>`${s}/100`,
  answered:(a,b)=>`${a} of ${b} answered`,
  faceSeen:(e,c)=>`Photo noted: looks ${e} (${c}% confidence). A single photo is weak evidence.`,
  noFace:"No face found — try again with better light.",
  heard:t=>`Heard: “${t}”`,
  toneWas:(e,c)=>`Tone of voice: ${e} (${c}%)`,
  needAnswer:"Please answer at least one question.",
  needPerson:"Please choose who this is for.",
  savedCheckin:"Check-in saved.",
  urgentTitle:"Needs attention now",
  urgentBody:"Please tell a caregiver or nurse straight away. If this is an emergency, call for medical help.",
  concerns:"Worth watching", suggestions:"What might help",
  analysing:"Analysing recordings…", analysed:(n,d)=>`Analysed ${n} recording(s). Overall tone: ${d}.`,
  noRecordings:"No saved recordings yet — use the microphone button when you talk.",
  recordSaved:"Conversation record saved.",
  reviewRx:"Check this before saving", saveRx:"Save these medicines", cancel:"Cancel",
  name:"Name", strength:"Strength", dose:"Dose", times:"Times (HH:MM, comma separated)",
  days:"Days", remove:"Remove", savedN:n=>`Saved ${n} medicine(s).`,
  noRx:"Nothing could be read. Try a clearer photo, or paste the text.",
  emptyReport:"Nothing recorded today yet.",
  btnVoiceCheckin:"🎙 Answer by talking", btnVoiceStop:"■ Stop",
  vcIdle:"The app will read each question aloud and listen for your answer.",
  vcActive:"Talking — answer naturally. Press stop when you are done.",
  vcFilled:(a,b)=>`Filled in ${a} of ${b} answers from the conversation — check them below.`,
  vcDone:"All questions answered. Add a photo if you like, then finish.",
  btnHandsFree:"🎙 Hands-free conversation", btnHandsFreeStop:"■ End conversation",
  hfIdle:"Talk normally — no buttons. It listens, replies, and listens again.",
  hfConnecting:"Connecting…", hfActive:"Listening — just speak.",
  micDenied:"Microphone unavailable. Check the browser's permission.",
  camDenied:"Camera unavailable. Check the browser's permission."
 },
 ja: {
  brand:"高齢者ケア アシスタント",
  tabHome:"今日", tabCheckin:"体調チェック", tabTalk:"会話", tabMeds:"お薬", tabReport:"申し送り",
  todayTitle:"今日のようす", quickStart:"すぐ始める", recentTitle:"最近のチェック",
  cWellbeing:"調子", cLastCheck:"最終チェック", cMeds:"今日のお薬", cTalks:"会話",
  btnStartCheckin:"今日の体調チェックを始める", btnTalk:"お話しする", btnMeds:"お薬",
  checkinTitle:"毎日の体調チェック",
  checkinSub:"かんたんな質問のあと、写真と音声（任意）をお願いします。",
  stepPhoto:"お写真（任意）",
  photoHelp:"お顔の表情を記録します。写真そのものは保存されません。",
  btnOpenCam:"カメラを開く", btnSnap:"撮影する", btnRetake:"撮り直す",
  stepVoice:"音声メモ（任意）", voiceHelp:"今の気持ちをご自身の言葉でお話しください。",
  btnRecord:"● 録音", btnStop:"■ 停止", btnFinish:"チェックを終わる",
  talkTitle:"会話",
  talkSub:"入力でも音声でも話せます。音声は後で声の調子を分析できるよう保存されます。",
  chatPlaceholder:"お話ししてください…", btnSend:"送信",
  btnAnalyzeVoice:"声の調子を分析", btnSaveRecord:"会話の記録を保存",
  medsTitle:"お薬", mScheduled:"予定", mTaken:"服用済み", mMissed:"飲み忘れ", mNext:"次",
  addRx:"処方箋を追加",
  rxHelp:"処方箋の写真か、文字を貼り付けてください。保存前に必ずご確認ください。",
  btnRxPhoto:"写真を選ぶ", btnReadRx:"AIで読み取る",
  rxPlaceholder:"アムロジピン錠5mg 1回1錠 1日1回朝食後 30日分",
  reportTitle:"申し送りレポート", reportSub:"今日の記録を次の介護者向けにまとめます。",
  btnMakeReport:"レポートを作成", btnExport:"CSVで書き出す",
  disclaimer:"このアプリは介護の補助です。診断や医療的な助言は行いません。写真や声から読み取る感情は弱い手がかりで、誤ることがあります。ご本人の言葉と介護者の判断を優先し、緊急時は医療機関にご連絡ください。",
  taken:"飲んだ", skip:"飲まない", undo:"取り消す", nothingToday:"今日の予定はありません。",
  noRecent:"まだ記録がありません。", noMeds:"まだお薬が登録されていません。",
  reading:"読み取り中…", thinking:"考え中…", working:"処理中…",
  greetHello:n=>`${n}さん、こんにちは。`,
  wellLabel:s=>`${s}/100`,
  answered:(a,b)=>`${b}問中 ${a}問に回答`,
  faceSeen:(e,c)=>`お写真から：${e}（確信度${c}%）。写真1枚では弱い手がかりです。`,
  noFace:"お顔を認識できませんでした。明るい場所でもう一度お試しください。",
  heard:t=>`聞き取り：「${t}」`,
  toneWas:(e,c)=>`声の調子：${e}（${c}%）`,
  needAnswer:"少なくとも1問にお答えください。",
  needPerson:"どなたの記録か選んでください。",
  savedCheckin:"チェックを保存しました。",
  urgentTitle:"すぐに確認が必要です",
  urgentBody:"すぐに介護者か看護師にお伝えください。緊急の場合は医療機関に連絡してください。",
  concerns:"気になる点", suggestions:"できそうなこと",
  analysing:"録音を分析しています…", analysed:(n,d)=>`${n}件を分析しました。全体の声の調子：${d}。`,
  noRecordings:"保存された録音がありません。マイクボタンでお話しください。",
  recordSaved:"会話の記録を保存しました。",
  reviewRx:"保存する前にご確認ください", saveRx:"このお薬を保存", cancel:"やめる",
  name:"薬の名前", strength:"強さ", dose:"1回量", times:"時刻（HH:MM、カンマ区切り）",
  days:"日数", remove:"削除", savedN:n=>`${n}件を保存しました。`,
  noRx:"読み取れませんでした。はっきりした写真か、文字を貼り付けてお試しください。",
  emptyReport:"今日の記録はまだありません。",
  btnVoiceCheckin:"🎙 話して答える", btnVoiceStop:"■ 停止",
  vcIdle:"質問を読み上げます。お答えください。",
  vcActive:"会話中です。自然にお答えください。終わったら停止を押してください。",
  vcFilled:(a,b)=>`会話から${b}問中${a}問を記入しました。下でご確認ください。`,
  vcDone:"すべてお答えいただきました。写真を撮って、終了してください。",
  btnHandsFree:"🎙 ハンズフリー会話", btnHandsFreeStop:"■ 会話を終える",
  hfIdle:"ボタンなしで、普通にお話しください。聞いて、返事して、また聞きます。",
  hfConnecting:"接続中…", hfActive:"お聞きしています。どうぞお話しください。",
  micDenied:"マイクを使用できません。ブラウザの許可をご確認ください。",
  camDenied:"カメラを使用できません。ブラウザの許可をご確認ください。"
 }
};

let lang = localStorage.getItem("eca_lang") || "en";
const t = k => T[lang][k];

let state = {
  residents: [], residentId: null, health: null,
  questions: [], answers: {}, face: null, voice: null, transcript: "",
  conversationId: null, rxDraft: null
};

/* ---------------- language ---------------- */
function setLang(l) {
  lang = l; localStorage.setItem("eca_lang", l);
  document.documentElement.lang = l;
  $("langEn").className = l === "en" ? "on" : "";
  $("langJa").className = l === "ja" ? "on" : "";
  document.querySelectorAll("[data-i]").forEach(el => {
    const v = T[lang][el.dataset.i];
    if (typeof v === "string") el.textContent = v;
  });
  document.querySelectorAll("[data-ph]").forEach(el => {
    const v = T[lang][el.dataset.ph];
    if (typeof v === "string") el.placeholder = v;
  });
  $("brandName").textContent = t("brand");
  loadQuestions();
  refreshTab();
}

/* ---------------- tabs ---------------- */
document.querySelectorAll("nav button").forEach(b => {
  b.onclick = () => go(b.dataset.tab);
});
function go(tab) {
  document.querySelectorAll("nav button").forEach(x =>
    x.classList.toggle("on", x.dataset.tab === tab));
  document.querySelectorAll(".panel").forEach(x =>
    x.classList.toggle("on", x.id === tab));
  refreshTab();
}
const currentTab = () => document.querySelector("nav button.on").dataset.tab;
function refreshTab() {
  const tab = currentTab();
  if (tab === "home") loadHome();
  if (tab === "meds") loadMeds();
}

/* ---------------- boot ---------------- */
(async function boot() {
  setLang(lang);
  try {
    state.health = await (await fetch("/api/health")).json();
    if (!state.health.features.groq) {
      $("homeAlerts").innerHTML =
        `<div class="banner err">${esc(state.health.groq_message || "Groq key missing")}</div>`;
    }
  } catch (e) { /* server not reachable; pages still render */ }

  const r = await (await fetch("/api/residents")).json();
  state.residents = r.residents;
  const sel = $("who");
  sel.innerHTML = state.residents.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  state.residentId = state.residents[0]?.id ?? null;
  sel.onchange = () => { state.residentId = Number(sel.value); state.conversationId = null;
                         $("chat").innerHTML = ""; refreshTab(); };
  await loadQuestions();
  loadHome();
})();

/* ================= HOME ================= */
async function loadHome() {
  if (!state.residentId) return;
  const name = state.residents.find(p => p.id === state.residentId)?.name || "";
  $("homeGreeting").textContent = t("greetHello")(name);

  const h = await (await fetch(`/api/checkin/history?resident_id=${state.residentId}&limit=5`)).json();
  const latest = h.checkins[0];
  $("hWell").textContent = latest && latest.wellbeing != null ? t("wellLabel")(latest.wellbeing) : "—";
  $("hWell").style.color = latest ? scoreColor(latest.wellbeing) : "";
  $("hLast").textContent = latest ? `${latest.day} ${latest.time}` : "—";
  $("hTalks").textContent = h.checkins.length;

  $("homeRecent").innerHTML = h.checkins.length ? h.checkins.map(c => `
      <div class="c" style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;gap:10px">
          <b style="color:${scoreColor(c.wellbeing)}">${c.wellbeing ?? "—"}/100</b>
          <span class="sub">${c.day} ${c.time}</span>
        </div>
        <div class="sub" style="margin-top:6px">${esc(c.summary || "")}</div>
        ${c.concerns.length ? `<div class="sub" style="color:var(--amber);margin-top:6px">⚠ ${c.concerns.map(esc).join(" · ")}</div>` : ""}
      </div>`).join("") : `<p class="sub">${t("noRecent")}</p>`;

  $("homeTrend").innerHTML = h.trend.length > 1 ? sparkline(h.trend) : "";

  try {
    const m = await (await fetch("/api/medications/today")).json();
    $("hMeds").textContent = m.total ? `${m.taken}/${m.total}` : "—";
  } catch (e) { $("hMeds").textContent = "—"; }
}

const scoreColor = s => s == null ? "" : (s >= 60 ? "var(--good)" : s < 40 ? "var(--warn)" : "var(--amber)");

function sparkline(trend) {
  const w = 260, h = 60, max = 100;
  const step = trend.length > 1 ? w / (trend.length - 1) : w;
  const pts = trend.map((d, i) => `${i * step},${h - (d.score / max) * h}`).join(" ");
  return `<div class="sub" style="margin-bottom:6px">Last ${trend.length} days</div>
    <svg width="${w}" height="${h}" style="overflow:visible">
      <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2.5"
                stroke-linecap="round" stroke-linejoin="round"/>
      ${trend.map((d, i) => `<circle cx="${i * step}" cy="${h - (d.score / max) * h}" r="3.5"
                fill="${d.score >= 60 ? "#16a34a" : d.score < 40 ? "#dc2626" : "#d97706"}"/>`).join("")}
    </svg>`;
}

/* ================= CHECK-IN ================= */
async function loadQuestions() {
  try {
    const j = await (await fetch(`/api/checkin/questions?lang=${lang}`)).json();
    state.questions = j.questions;
    renderQuestions();
  } catch (e) { /* offline */ }
}

function renderQuestions() {
  $("ciQuestions").innerHTML = state.questions.map(q => `
    <div class="step">
      <h3>${esc(q.text)}</h3>
      <div class="opts">
        ${q.options.map(o => `
          <button class="opt ${q.urgent ? "urgent" : ""} ${state.answers[q.id] === o.value ? "on" : ""}"
                  onclick="answer('${q.id}','${o.value}')">
            <span class="ic">${o.icon || ""}</span>${esc(o.label)}
          </button>`).join("")}
      </div>
    </div>`).join("");
  updateProgress();
}

function answer(qid, value) {
  state.answers[qid] = value;
  renderQuestions();
}

function updateProgress() {
  const total = state.questions.length;
  const done = Object.keys(state.answers).length;
  $("ciProg").style.width = total ? `${100 * done / total}%` : "0";
}

/* ---- camera ---- */
let camStream = null;
async function openCam() {
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
  } catch (e) { $("ciFaceOut").innerHTML = `<span style="color:var(--warn)">${t("camDenied")}</span>`; return; }
  const v = $("ciVideo");
  v.srcObject = camStream; v.classList.remove("hide");
  $("ciCanvas").classList.add("hide");
  $("ciSnapBtn").classList.remove("hide");
  $("ciRetake").classList.add("hide");
  $("ciCamBtn").classList.add("hide");
}

function stopCam() {
  if (camStream) { camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  $("ciVideo").classList.add("hide");
}

async function snap() {
  const v = $("ciVideo"), c = $("ciCanvas");
  c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
  c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
  stopCam();
  c.classList.remove("hide");
  $("ciSnapBtn").classList.add("hide");
  $("ciRetake").classList.remove("hide");
  $("ciFaceOut").innerHTML = `<span class="spinner"></span>${t("working")}`;

  const blob = await new Promise(res => c.toBlob(res, "image/jpeg", 0.9));
  try {
    const j = await (await fetch("/api/checkin/photo", { method: "POST", body: blob })).json();
    if (!j.ok) { $("ciFaceOut").innerHTML = `<span style="color:var(--warn)">${esc(j.message)}</span>`; return; }
    if (!j.found) { state.face = null; $("ciFaceOut").textContent = t("noFace"); return; }
    state.face = j.face;
    $("ciFaceOut").innerHTML = `<div class="banner info">${t("faceSeen")(j.face.emotion, Math.round(j.face.confidence))}</div>`;
  } catch (e) { $("ciFaceOut").textContent = String(e); }
}

/* ---- WAV recording (shared) ---- */
function encodeWAV(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  str(0,"RIFF"); view.setUint32(4, 36 + samples.length*2, true); str(8,"WAVE");
  str(12,"fmt "); view.setUint32(16,16,true); view.setUint16(20,1,true);
  view.setUint16(22,1,true); view.setUint32(24,rate,true);
  view.setUint32(28,rate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
  str(36,"data"); view.setUint32(40, samples.length*2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

function makeRecorder() {
  let ctx, stream, node, src, chunks = [];
  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      src = ctx.createMediaStreamSource(stream);
      node = ctx.createScriptProcessor(4096, 1, 1);
      chunks = [];
      node.onaudioprocess = e => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      src.connect(node); node.connect(ctx.destination);
    },
    async stop() {
      node.disconnect(); src.disconnect();
      stream.getTracks().forEach(t => t.stop());
      const rate = ctx.sampleRate;
      await ctx.close();
      let total = 0; chunks.forEach(c => total += c.length);
      if (total / rate < 0.4) return null;
      const flat = new Float32Array(total);
      let o = 0; chunks.forEach(c => { flat.set(c, o); o += c.length; });
      return encodeWAV(flat, rate);
    }
  };
}

let ciRec = null;
async function toggleCiRec() {
  const btn = $("ciRecBtn");
  if (ciRec) {
    const blob = await ciRec.stop(); ciRec = null;
    btn.textContent = t("btnRecord"); btn.className = "btn grey";
    $("ciRecStatus").textContent = "";
    if (!blob) return;
    $("ciVoiceOut").innerHTML = `<span class="spinner"></span>${t("working")}`;
    try {
      const j = await (await fetch(`/api/checkin/voice?lang=${lang}`, { method: "POST", body: blob })).json();
      if (!j.ok) { $("ciVoiceOut").innerHTML = `<span style="color:var(--warn)">${esc(j.message)}</span>`; return; }
      state.transcript = j.transcript || "";
      state.voice = j.voice || null;
      $("ciVoiceOut").innerHTML =
        `<div class="banner info">${esc(t("heard")(state.transcript))}` +
        (j.voice ? `<br>${esc(t("toneWas")(j.voice.emotion, Math.round(j.voice.confidence)))}` : "") +
        `</div>`;
    } catch (e) { $("ciVoiceOut").textContent = String(e); }
  } else {
    try {
      ciRec = makeRecorder(); await ciRec.start();
      btn.textContent = t("btnStop"); btn.className = "btn red";
      $("ciRecStatus").textContent = "●";
    } catch (e) { ciRec = null; $("ciVoiceOut").innerHTML = `<span style="color:var(--warn)">${t("micDenied")}</span>`; }
  }
}

async function submitCheckin() {
  $("ciError").innerHTML = "";
  if (!state.residentId) { $("ciError").innerHTML = `<div class="banner err">${t("needPerson")}</div>`; return; }
  if (!Object.keys(state.answers).length) {
    $("ciError").innerHTML = `<div class="banner err">${t("needAnswer")}</div>`; return; }

  const btn = $("ciSubmit");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${t("thinking")}`;
  try {
    const j = await (await fetch("/api/checkin/submit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resident_id: state.residentId, answers: state.answers,
                             face: state.face, voice: state.voice,
                             transcript: state.transcript, lang })
    })).json();
    if (!j.ok) { $("ciError").innerHTML = `<div class="banner err">${esc(j.message)}</div>`; return; }
    showCheckinResult(j);
    state.answers = {}; state.face = null; state.voice = null; state.transcript = "";
    renderQuestions();
    $("ciFaceOut").innerHTML = ""; $("ciVoiceOut").innerHTML = "";
    loadHome();
  } finally {
    btn.disabled = false; btn.textContent = t("btnFinish");
  }
}

function showCheckinResult(j) {
  const urgent = j.urgent ? `
    <div class="banner err" style="font-size:17px">
      <b>⚠ ${t("urgentTitle")}</b><br>${t("urgentBody")}
    </div>` : "";
  $("ciResult").innerHTML = urgent + `
    <div class="c">
      <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">
        <div><div class="score" style="color:${scoreColor(j.wellbeing)}">${j.wellbeing ?? "—"}</div>
             <div class="sub">/100</div></div>
        <div style="flex:1;min-width:220px">
          <div class="banner ${j.tone === "good" ? "good" : j.tone === "watch" ? "warn" : "info"}"
               style="margin:0">${esc(j.summary || t("savedCheckin"))}</div>
        </div>
      </div>
      ${j.concerns?.length ? `<p style="margin:14px 0 4px"><b>${t("concerns")}</b></p>
        <ul>${j.concerns.map(c => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
      ${j.suggestions?.length ? `<p style="margin:12px 0 4px"><b>${t("suggestions")}</b></p>
        <ul>${j.suggestions.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
    </div>`;
  $("ciResult").scrollIntoView({ behavior: "smooth", block: "nearest" });
}


/* ---------- voice check-in: one spoken conversation ----------
   Uses the same hands-free pipeline as the Talk tab, with an interviewer
   prompt. Afterwards the answers are pulled out of the transcript and shown
   in the form below, so the caregiver can see and correct what was heard. */
let vcCall = null, vcConvId = null;

async function toggleVoiceCheckin() {
  const btn = $("vcBtn");
  if (vcCall) { await finishVoiceCheckin(); return; }
  if (!state.residentId) { $("vcStatus").textContent = t("needPerson"); return; }

  btn.disabled = true;
  $("vcStatus").textContent = t("hfConnecting");
  $("vcHeard").innerHTML = "";
  try {
    const pc = await startCheckinCall();
    vcCall = pc;
    btn.disabled = false;
    btn.className = "btn red";
    btn.innerHTML = `<span>${t("btnVoiceStop")}</span>`;
    $("vcStatus").textContent = t("vcActive");
  } catch (e) {
    btn.disabled = false;
    $("vcStatus").innerHTML = `<span style="color:var(--warn)">${esc(String(e.message || e))}</span>`;
  }
}

/* Mirrors startHandsFreeCall, but posts to the check-in start endpoint so the
   backend uses the interview prompt and hands back the conversation id. */
async function startCheckinCall() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  const pc = new RTCPeerConnection();
  stream.getTracks().forEach(tr => pc.addTrack(tr, stream));

  const channel = pc.createDataChannel("chat");
  channel.onmessage = ev => {
    try {
      const m = JSON.parse(ev.data);
      if (!m || (m.role !== "user" && m.role !== "assistant")) return;
      if (typeof m.text !== "string" || !m.text.trim()) return;
      addCheckinLine(m.role, m.text);
      if (m.role === "assistant") say(m.text, lang);
    } catch {}
  };

  // level meter + barge-in
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  let stopWatch = () => {};
  if (AudioCtx) {
    const ctx = new AudioCtx();
    const source = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser(); an.fftSize = 1024;
    source.connect(an);
    const buf = new Float32Array(an.fftSize);
    let loud = 0;
    const timer = setInterval(() => {
      an.getFloatTimeDomainData(buf);
      let sum = 0; for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      $("vcLevel").style.width = `${Math.round(Math.min(1, rms * 12) * 100)}%`;
      if (rms > 0.045) { loud++; if (loud === 3) shutUp(); } else loud = 0;
    }, 100);
    stopWatch = () => { clearInterval(timer); source.disconnect(); ctx.close().catch(()=>{}); };
  }

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const res = await fetch("/api/checkin/voice/start", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: offer.sdp, type: offer.type, lang,
                           resident_id: state.residentId }) });
  const ans = await res.json();
  if (!ans.ok) {
    stopWatch(); stream.getTracks().forEach(tr => tr.stop()); pc.close();
    throw new Error(ans.message || "Could not start.");
  }
  vcConvId = ans.conversation_id;
  await pc.setRemoteDescription({ sdp: ans.sdp, type: ans.type });

  return { stop() { stopWatch(); try { channel.close(); } catch {}
                    stream.getTracks().forEach(tr => tr.stop()); pc.close(); } };
}

function addCheckinLine(role, text) {
  const box = $("vcHeard");
  const d = document.createElement("div");
  d.className = "msg " + (role === "user" ? "user" : "bot");
  d.style.maxWidth = "100%";
  d.style.marginBottom = "6px";
  d.textContent = text;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

async function finishVoiceCheckin() {
  const btn = $("vcBtn");
  if (vcCall) { vcCall.stop(); vcCall = null; }
  shutUp();
  btn.className = "btn";
  btn.innerHTML = `<span>${t("btnVoiceCheckin")}</span>`;
  $("vcLevel").style.width = "0";

  if (!vcConvId) { $("vcStatus").textContent = t("vcIdle"); return; }
  $("vcStatus").innerHTML = `<span class="spinner"></span>${t("working")}`;
  try {
    const j = await (await fetch("/api/checkin/voice/finish", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: vcConvId, lang }) })).json();
    if (!j.ok) { $("vcStatus").innerHTML = `<span style="color:var(--warn)">${esc(j.message)}</span>`; return; }

    Object.assign(state.answers, j.answers || {});
    if (j.quote) state.transcript = j.quote;
    renderQuestions();
    const got = Object.keys(j.answers || {}).length;
    $("vcStatus").textContent = t("vcFilled")(got, state.questions.length);
    $("ciQuestions").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    $("vcStatus").innerHTML = `<span style="color:var(--warn)">${esc(String(e))}</span>`;
  } finally { vcConvId = null; }
}

/* ================= TALK ================= */
async function ensureConversation() {
  if (state.conversationId) return state.conversationId;
  const j = await (await fetch("/api/conversation/start", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resident_id: state.residentId })
  })).json();
  state.conversationId = j.conversation_id;
  return state.conversationId;
}

function addBubble(role, text, tone) {
  const d = document.createElement("div");
  d.className = "msg " + (role === "user" ? "user" : "bot");
  d.innerHTML = esc(text) + (tone ? `<span class="tone">🎤 ${esc(tone)}</span>` : "");
  $("chat").appendChild(d);
  $("chat").scrollTop = $("chat").scrollHeight;
}

async function sendText() {
  const input = $("chatInput");
  const content = input.value.trim();
  if (!content) return;
  input.value = "";
  addBubble("user", content);
  const cid = await ensureConversation();
  $("sendBtn").disabled = true;
  try {
    const j = await (await fetch(`/api/conversation/${cid}/say`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, lang })
    })).json();
    if (!j.ok) { $("talkError").innerHTML = `<div class="banner err">${esc(j.message)}</div>`; return; }
    $("talkError").innerHTML = "";
    addBubble("assistant", j.reply);
    speak(j.reply);
  } finally { $("sendBtn").disabled = false; }
}

let chatRec = null;
async function toggleChatRec() {
  const btn = $("micBtn");
  if (chatRec) {
    const blob = await chatRec.stop(); chatRec = null;
    btn.textContent = "🎤"; btn.className = "btn grey";
    if (!blob) return;
    const cid = await ensureConversation();
    try {
      const j = await (await fetch(`/api/conversation/${cid}/say_audio?lang=${lang}`,
        { method: "POST", body: blob })).json();
      if (!j.ok) { $("talkError").innerHTML = `<div class="banner err">${esc(j.message)}</div>`; return; }
      $("talkError").innerHTML = "";
      addBubble("user", j.transcript);
      addBubble("assistant", j.reply);
      speak(j.reply);
    } catch (e) { $("talkError").innerHTML = `<div class="banner err">${esc(String(e))}</div>`; }
  } else {
    try {
      chatRec = makeRecorder(); await chatRec.start();
      btn.textContent = "■"; btn.className = "btn red";
    } catch (e) { chatRec = null; $("talkError").innerHTML = `<div class="banner err">${t("micDenied")}</div>`; }
  }
}

function speak(text) { return say(text, lang); }   // from voice.js

/* ---------- hands-free conversation (Converse_2way's Pipecat pipeline) ---- */
let hfCall = null;

async function toggleHandsFree() {
  const btn = $("hfBtn");
  if (hfCall) {
    hfCall.stop(); hfCall = null; shutUp();
    btn.className = "btn"; btn.innerHTML = `<span>${t("btnHandsFree")}</span>`;
    $("hfStatus").textContent = t("hfIdle");
    $("hfLevel").style.width = "0";
    return;
  }

  const cid = await ensureConversation();
  $("talkError").innerHTML = "";
  $("hfStatus").textContent = t("hfConnecting");
  btn.disabled = true;
  try {
    hfCall = await startHandsFreeCall(cid, {
      lang,
      onTurn: (m) => {
        addBubble(m.role, m.text);
        if (m.role === "assistant") speak(m.text);
      },
      // The resident started talking: stop the assistant talking over them.
      onUserSpeaking: shutUp,
      onLevel: (v) => { $("hfLevel").style.width = `${Math.round(v * 100)}%`; },
    });
    btn.className = "btn red";
    btn.innerHTML = `<span>${t("btnHandsFreeStop")}</span>`;
    $("hfStatus").textContent = t("hfActive");
  } catch (e) {
    hfCall = null;
    $("hfStatus").textContent = t("hfIdle");
    $("talkError").innerHTML = `<div class="banner err">${esc(String(e.message || e))}</div>`;
  } finally { btn.disabled = false; }
}

async function analyzeVoice() {
  if (!state.conversationId) { $("voiceSummary").textContent = t("noRecordings"); return; }
  $("voiceSummary").innerHTML = `<span class="spinner"></span>${t("analysing")}`;
  const j = await (await fetch(`/api/conversation/${state.conversationId}/analyze_voice`,
    { method: "POST" })).json();
  if (!j.ok) { $("voiceSummary").innerHTML = `<span style="color:var(--warn)">${esc(j.message)}</span>`; return; }
  const s = j.summary;
  $("voiceSummary").innerHTML = s
    ? `<div class="banner info">${esc(t("analysed")(s.analyzed, s.dominant))}</div>`
    : esc(j.message || t("noRecordings"));
}

async function saveRecord() {
  if (!state.conversationId) return;
  $("talkRecord").innerHTML = `<span class="spinner"></span>${t("working")}`;
  const j = await (await fetch(`/api/conversation/${state.conversationId}/record?lang=${lang}`,
    { method: "POST" })).json();
  if (!j.ok) { $("talkRecord").innerHTML = `<div class="banner err">${esc(j.message)}</div>`; return; }
  $("talkRecord").innerHTML = `<div class="banner good">${t("recordSaved")}</div>
    <div class="c"><b>${esc(j.mood)}</b><div class="sub" style="margin-top:6px">${esc(j.summary)}</div>
    <div class="sub" style="margin-top:6px">${esc(j.notable_points)}</div></div>`;
}

/* ================= MEDS ================= */
async function loadMeds() {
  let m;
  try { m = await (await fetch("/api/medications/today")).json(); } catch (e) { return; }
  $("mTotal").textContent = m.total;
  $("mTaken").textContent = m.taken;
  $("mMissed").textContent = m.missed;
  $("mNext").textContent = m.next ? m.next.slot : "—";

  $("medsAlert").innerHTML = (m.due && m.due.length)
    ? `<div class="banner warn">⏰ ${m.due.map(d => esc(`${d.name} (${d.slot})`)).join(", ")}</div>` : "";

  $("medsList").innerHTML = m.doses.length ? m.doses.map(d => `
    <div class="dose ${d.status === "taken" ? "taken" : ""}">
      <div class="time">${d.slot}</div>
      <div style="flex:1;min-width:150px"><b>${esc(d.name)}</b>
        ${d.status === "taken" ? `<span class="pill taken">${t("taken")}</span>` : ""}
        <div class="sub">${esc([d.dose_amount, d.strength].filter(Boolean).join(" · "))}</div></div>
      ${d.status === "pending"
        ? `<button class="btn green" onclick="dose(${d.med_id},'${d.day}','${d.slot}','taken')">${t("taken")}</button>
           <button class="btn grey" onclick="dose(${d.med_id},'${d.day}','${d.slot}','skipped')">${t("skip")}</button>`
        : `<button class="btn grey" onclick="dose(${d.med_id},'${d.day}','${d.slot}','undo')">${t("undo")}</button>`}
    </div>`).join("") : `<p class="sub">${t("nothingToday")}</p>`;
}

async function dose(med_id, day, slot, status) {
  await fetch("/api/medications/dose", { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ med_id, day, slot, status }) });
  loadMeds();
}

$("rxFile").onchange = e => { if (e.target.files[0]) readRxPhoto(e.target.files[0]); };

async function readRx() {
  await runRx("/api/medications/extract_text", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("rxText").value })
  });
}
async function readRxPhoto(file) {
  await runRx("/api/medications/extract_photo", {
    method: "POST", headers: { "Content-Type": file.type || "image/jpeg" }, body: file });
}

async function runRx(url, opts) {
  $("rxStatus").innerHTML = `<span class="spinner"></span>${t("reading")}`;
  $("rxBtn").disabled = true; $("rxReview").innerHTML = "";
  try {
    const j = await (await fetch(url, opts)).json();
    if (!j.ok) { $("rxStatus").innerHTML = `<span style="color:var(--warn)">${esc(j.message)}</span>`; return; }
    $("rxStatus").textContent = "";
    state.rxDraft = j;
    renderRx();
  } catch (e) { $("rxStatus").innerHTML = `<span style="color:var(--warn)">${esc(String(e))}</span>`; }
  finally { $("rxBtn").disabled = false; }
}

function renderRx() {
  const d = state.rxDraft;
  if (!d || !d.medications.length) { $("rxReview").innerHTML = `<div class="banner warn">${t("noRx")}</div>`; return; }
  $("rxReview").innerHTML = `<div class="banner warn"><b>${t("reviewRx")}</b></div>` +
    (d.warnings || []).map(w => `<div class="banner warn">⚠ ${esc(w)}</div>`).join("") +
    d.medications.map((m, i) => `
      <div class="c" style="margin-bottom:12px">
        <b style="font-size:18px">${esc(m.name)}</b>
        <div class="opts" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-top:10px">
          <div><div class="sub">${t("name")}</div><input type="text" id="rx_n_${i}" value="${esc(m.name)}"></div>
          <div><div class="sub">${t("strength")}</div><input type="text" id="rx_s_${i}" value="${esc(m.strength||"")}"></div>
          <div><div class="sub">${t("dose")}</div><input type="text" id="rx_d_${i}" value="${esc(m.dose_amount||"")}"></div>
          <div><div class="sub">${t("times")}</div><input type="text" id="rx_t_${i}" value="${esc((m.times||[]).join(", "))}"></div>
          <div><div class="sub">${t("days")}</div><input type="text" id="rx_y_${i}" value="${esc(m.duration_days||"")}"></div>
        </div>
      </div>`).join("") +
    `<button class="btn green" onclick="saveRx()">${t("saveRx")}</button>
     <button class="btn grey" onclick="state.rxDraft=null;document.getElementById('rxReview').innerHTML=''">${t("cancel")}</button>`;
}

async function saveRx() {
  const meds = state.rxDraft.medications.map((m, i) => ({
    name: $(`rx_n_${i}`).value.trim() || m.name,
    strength: $(`rx_s_${i}`).value.trim() || null,
    dose_amount: $(`rx_d_${i}`).value.trim() || null,
    times: $(`rx_t_${i}`).value.split(",").map(s => s.trim()).filter(Boolean),
    duration_days: parseInt($(`rx_y_${i}`).value) || null,
    form: m.form, timing: m.timing, frequency_text: m.frequency_text, notes: m.notes
  }));
  const j = await (await fetch("/api/medications/save", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ medications: meds }) })).json();
  if (j.ok) {
    state.rxDraft = null;
    $("rxReview").innerHTML = `<div class="banner good">${t("savedN")(j.saved)}</div>`;
    $("rxText").value = "";
    loadMeds();
  }
}

/* ================= REPORT ================= */
async function makeReport() {
  $("repStatus").innerHTML = `<span class="spinner"></span>${t("thinking")}`;
  $("repBtn").disabled = true;
  try {
    const j = await (await fetch(`/api/report?resident_id=${state.residentId}&lang=${lang}`)).json();
    if (!j.ok) { $("repOut").innerHTML = `<div class="banner err">${esc(j.message)}</div>`; return; }
    if (j.empty) { $("repOut").innerHTML = `<div class="banner info">${t("emptyReport")}</div>`; return; }
    $("repOut").innerHTML = `<pre class="report">${esc(j.report)}</pre>`;
  } finally { $("repStatus").textContent = ""; $("repBtn").disabled = false; }
}
