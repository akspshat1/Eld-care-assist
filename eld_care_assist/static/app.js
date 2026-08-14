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
  tabMood:"Mood", moodTitle:"Mood check",
  moodSub:"Read mood from a photo, from the voice, or both. Nothing is saved unless you press Save.",
  moodFace:"From a photo", moodVoice:"From the voice",
  moodVoiceHelp:"Speak for a few seconds \u2014 anything at all.",
  btnUploadPhoto:"Upload a photo", btnSaveMood:"Save this reading", btnClear:"Clear",
  moodHistory:"Mood history", moodSaved:"Saved to today's record.",
  moodNothing:"Take a photo or record your voice first.",
  moodCombined:(s)=>`Overall mood reading: ${s}/100`,
  moodNoHistory:"No mood readings yet.",
  callOffer:(n)=>`Call ${n}?`, btnCallNow:"📞 Call now", btnNotNow:"Not now",
  tabFamily:"Family", familyTitle:"Family view",
  familySub:"What a relative sees: how they are, what needs attention, and who to call.",
  famAttention:"Needs attention", famContacts:"Contacts", famAddContact:"Add a contact",
  famHistory:"Last 14 days", famNothing:"Nothing needs attention right now.",
  fcName:"Name", fcRel:"Relationship", fcPhone:"Phone", fcMain:"Main contact",
  fcAdd:"Add contact", fcNeed:"Name and phone are required.", fcAdded:"Added.",
  fcCall:"\ud83d\udcde Call", fcSetMain:"Set as main", fcUnsetMain:"Unset main",
  fcDelete:"Delete", fcNone:"No contacts yet.", fcConfirm:n=>`Remove ${n}?`,
  famDoingWell:"Doing well", famAllRight:"Doing all right", famBitLow:"A bit low",
  famNotWell:"Not doing well", famNoReading:"No reading yet",
  famLastCheck:(d,t)=>`Last check-in ${d} at ${t}`, famNever:"No check-ins yet",
  modeResident:"Resident", modeCare:"Care team",
  tabHomeR:"Home", residentSub:"What would you like to do?",
  raTalk:"Have a chat", raTalkD:"Talk about anything. Just speak \u2014 no buttons.",
  raCheck:"Today's check-in", raCheckD:"A few gentle questions about how you feel.",
  trendTitle:"Wellbeing trend", famContactsHelp:"Saying \u201ccall my daughter\u201d in a conversation offers to ring them.",
  nextMed:(n,t)=>`Next medicine: ${n} at ${t}`,
  medDueNow:(n,t)=>`Time to take ${n} (due ${t})`,
  medGaveUp:(n)=>`${n} was not confirmed. Marked as not taken \u2014 please check with them.`, noNextMed:"No more medicines today.",
  greetMorning:n=>`Good morning, ${n}.`, greetAfternoon:n=>`Good afternoon, ${n}.`,
  greetEvening:n=>`Good evening, ${n}.`,
  medRemindTitle:"Time for your medicine",
  medAnnounce:(n,d)=>`It's time to take ${n}${d ? ", " + d : ""}. Have you taken it?`,
  medAsk:"Say \u201ctaken\u201d when you have had it.",
  medListening:"Listening\u2026", medThanks:n=>`Thank you. ${n} marked as taken.`,
  medUnclear:"I didn't catch that. I'll ask again in 5 minutes.",
  medAgainIn:"I'll remind you again in 5 minutes.",
  btnTaken:"\u2713 I've taken it", btnLater:"Not yet",
  medRemindersOn:"Voice reminders on", medRemindersOff:"Voice reminders off",
  dcReal:"Real time", dcDemo:"Demo time", dcClock:"Clock",
  dcHint:"Type 8:05, 0805 or 8", dcBadTime:"Use a time like 8:05",
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
  tabMood:"気分", moodTitle:"気分チェック",
  moodSub:"写真・声、またはその両方から気分を読み取ります。保存を押すまで記録されません。",
  moodFace:"写真から", moodVoice:"声から",
  moodVoiceHelp:"数秒間、何でもお話しください。",
  btnUploadPhoto:"写真をアップロード", btnSaveMood:"この結果を保存", btnClear:"クリア",
  moodHistory:"気分の記録", moodSaved:"今日の記録に保存しました。",
  moodNothing:"先に写真を撮るか、声を録音してください。",
  moodCombined:(s)=>`総合的な気分：${s}/100`,
  moodNoHistory:"まだ記録がありません。",
  callOffer:(n)=>`${n}さんに電話しますか？`, btnCallNow:"📞 今すぐ電話", btnNotNow:"やめておく",
  tabFamily:"家族", familyTitle:"家族向けの表示",
  familySub:"ご家族が見る画面です。ご様子、気になる点、連絡先。",
  famAttention:"気になる点", famContacts:"連絡先", famAddContact:"連絡先を追加",
  famHistory:"直近14日", famNothing:"今のところ心配な点はありません。",
  fcName:"お名前", fcRel:"ご関係", fcPhone:"電話番号", fcMain:"主な連絡先",
  fcAdd:"追加", fcNeed:"お名前と電話番号が必要です。", fcAdded:"追加しました。",
  fcCall:"\ud83d\udcde 電話", fcSetMain:"主にする", fcUnsetMain:"主を解除",
  fcDelete:"削除", fcNone:"まだ連絡先がありません。", fcConfirm:n=>`${n} を削除しますか？`,
  famDoingWell:"お元気です", famAllRight:"まずまずです", famBitLow:"少し元気がありません",
  famNotWell:"調子が良くありません", famNoReading:"記録がありません",
  famLastCheck:(d,t)=>`最終チェック ${d} ${t}`, famNever:"まだ記録がありません",
  modeResident:"ご本人", modeCare:"ケアチーム",
  tabHomeR:"ホーム", residentSub:"何をいたしましょうか？",
  raTalk:"お話しする", raTalkD:"何でもお話しください。ボタンは不要です。",
  raCheck:"今日の体調チェック", raCheckD:"かんたんな質問にお答えください。",
  trendTitle:"調子の推移", famContactsHelp:"会話中に「娘に電話」と言うとご案内します。",
  nextMed:(n,t)=>`次のお薬：${n}（${t}）`,
  medDueNow:(n,t)=>`${n}の時間です（${t}）`,
  medGaveUp:(n)=>`${n}の確認が取れませんでした。未服用として記録しました。ご確認ください。`, noNextMed:"今日のお薬は終わりました。",
  greetMorning:n=>`${n}さん、おはようございます。`,
  greetAfternoon:n=>`${n}さん、こんにちは。`,
  greetEvening:n=>`${n}さん、こんばんは。`,
  medRemindTitle:"お薬の時間です",
  medAnnounce:(n,d)=>`${n}${d ? "、" + d : ""}の時間です。飲みましたか？`,
  medAsk:"飲んだら「飲んだ」とお話しください。",
  medListening:"お聴きしています…", medThanks:n=>`ありがとうございます。${n}を服用済みにしました。`,
  medUnclear:"うまく聞き取れませんでした。5分後にまたお知らせします。",
  medAgainIn:"5分後にまたお知らせします。",
  btnTaken:"✓ 飲みました", btnLater:"まだです",
  medRemindersOn:"音声でお知らせ：オン", medRemindersOff:"音声でお知らせ：オフ",
  dcReal:"実時間", dcDemo:"デモ時間", dcClock:"時刻",
  dcHint:"8:05 / 0805 / 8 のように入力", dcBadTime:"8:05 のように入力してください",
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
  const mv = $("medVoiceBtn");
  if (mv) mv.textContent = medRemindersOn ? t("medRemindersOn") : t("medRemindersOff");
  loadQuestions();
  refreshTab();
}

/* ---------------- tabs ---------------- */
document.querySelectorAll("nav button").forEach(b => {
  b.onclick = () => go(b.dataset.tab);
});

/* Two audiences, one app: the resident gets a calm two-choice home, the care
   team gets the data. Tabs are filtered by mode rather than shown all at once. */
let mode = localStorage.getItem("eca_mode") || "resident";
// Declared here, not with the reminder code below: setLang() runs during
// boot and reads it, and a `let` further down the file would still be in
// its temporal dead zone -- which threw and aborted boot before the
// residents had loaded.
let medRemindersOn = localStorage.getItem("eca_med_voice") !== "off";

function setMode(m) {
  mode = m;
  localStorage.setItem("eca_mode", m);
  document.body.dataset.mode = m;
  $("modeResident").classList.toggle("on", m === "resident");
  $("modeCare").classList.toggle("on", m === "care");
  applyTabVisibility();

  // Always land on this mode's home. Switching mode is a deliberate change of
  // context, so carrying the previous tab over is more confusing than helpful.
  go(m === "resident" ? "residentHome" : "home");
}

function applyTabVisibility() {
  document.querySelectorAll("nav button").forEach(b => {
    const forMode = b.dataset.for;
    b.classList.toggle("hide", !(forMode === "both" || forMode === mode));
  });
}

function go(tab) {
  document.querySelectorAll("nav button").forEach(x =>
    x.classList.toggle("on", x.dataset.tab === tab));
  document.querySelectorAll(".panel").forEach(x =>
    x.classList.toggle("on", x.id === tab));
  window.scrollTo({ top: 0, behavior: "smooth" });
  refreshTab();
}
const currentTab = () => document.querySelector("nav button.on")?.dataset.tab || "";

function refreshTab() {
  const tab = currentTab();
  // Each loader talks to the network; one failing must not stop a tab or mode
  // switch from completing.
  try {
    if (tab === "home") loadHome();
    if (tab === "meds") loadMeds();
    if (tab === "mood") loadMoodHistory();
    if (tab === "family") loadFamily();
    if (tab === "residentHome") loadResidentHome();
  } catch (e) {
    console.error("refreshTab:", e);
  }
}

/* ---------------- boot ---------------- */
(async function boot() {
  setLang(lang);
  try {
    state.health = await (await fetch("/api/health")).json();
    if (!state.health.features.groq) {
      $("homeAlerts").innerHTML =
        `<div class="note bad">${esc(state.health.groq_message || "Groq key missing")}</div>`;
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
  // Applies the saved mode, filters the tabs and opens that mode's home.
  setMode(mode);
  clockPoll();
  medicineTick();          // check straight away, then every 30s
})();


/* ---------- resident home ---------- */
async function loadResidentHome() {
  const name = state.residents.find(p => p.id === state.residentId)?.name || "";
  const h = new Date().getHours();
  const greet = h < 12 ? t("greetMorning") : h < 18 ? t("greetAfternoon") : t("greetEvening");
  $("residentGreet").textContent = greet(name.split(" ")[0] || name);

  // One useful, non-nagging line: what is coming next.
  try {
    const m = await (await fetch("/api/medications/today")).json();
    // Only a dose near its scheduled time counts as "now"; older ones are
    // missed doses, shown to the care team rather than nagged about here.
    const due = (m.due || []).find(d => (d.late_minutes ?? 0) <= MED_GIVE_UP_MIN);
    const next = m.next;
    if (due) {
      $("residentNext").innerHTML =
        `<div class="note warn"><span class="ic">\u23f0</span><div>${esc(t("medDueNow")(due.name, due.slot))}</div></div>`;
    } else if (next) {
      $("residentNext").innerHTML =
        `<div class="note info"><span class="ic">\ud83d\udc8a</span><div>${esc(t("nextMed")(next.name, next.slot))}</div></div>`;
    } else {
      $("residentNext").innerHTML = "";
    }
  } catch (e) { $("residentNext").innerHTML = ""; }
}

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
      <div class="stat" style="margin-bottom:10px">
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
    $("ciFaceOut").innerHTML = `<div class="note info">${t("faceSeen")(j.face.emotion, Math.round(j.face.confidence))}</div>`;
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
      // Same reason as in voice.js: a suspended context never delivers audio.
      if (ctx.state === "suspended") { try { await ctx.resume(); } catch (e) {} }
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
        `<div class="note info">${esc(t("heard")(state.transcript))}` +
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
  if (!state.residentId) { $("ciError").innerHTML = `<div class="note bad">${t("needPerson")}</div>`; return; }
  if (!Object.keys(state.answers).length) {
    $("ciError").innerHTML = `<div class="note bad">${t("needAnswer")}</div>`; return; }

  const btn = $("ciSubmit");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${t("thinking")}`;
  try {
    const j = await (await fetch("/api/checkin/submit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resident_id: state.residentId, answers: state.answers,
                             face: state.face, voice: state.voice,
                             transcript: state.transcript, lang })
    })).json();
    if (!j.ok) { $("ciError").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
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
    <div class="note bad" style="font-size:17px">
      <b>⚠ ${t("urgentTitle")}</b><br>${t("urgentBody")}
    </div>` : "";
  $("ciResult").innerHTML = urgent + `
    <div class="stat">
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
    if (!j.ok) { $("talkError").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
    $("talkError").innerHTML = "";
    addBubble("assistant", j.reply);
    speak(j.reply);
    showCallOffer(j.call);
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
      if (!j.ok) { $("talkError").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
      $("talkError").innerHTML = "";
      addBubble("user", j.transcript);
      addBubble("assistant", j.reply);
      speak(j.reply);
      showCallOffer(j.call);
    } catch (e) { $("talkError").innerHTML = `<div class="note bad">${esc(String(e))}</div>`; }
  } else {
    try {
      chatRec = makeRecorder(); await chatRec.start();
      btn.textContent = "■"; btn.className = "btn red";
    } catch (e) { chatRec = null; $("talkError").innerHTML = `<div class="note bad">${t("micDenied")}</div>`; }
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
      // They asked out loud to phone someone; the backend spotted who.
      onCall: (c) => showCallOffer(c),
      onLevel: (v) => { $("hfLevel").style.width = `${Math.round(v * 100)}%`; },
    });
    btn.className = "btn red";
    btn.innerHTML = `<span>${t("btnHandsFreeStop")}</span>`;
    $("hfStatus").textContent = t("hfActive");
  } catch (e) {
    hfCall = null;
    $("hfStatus").textContent = t("hfIdle");
    $("talkError").innerHTML = `<div class="note bad">${esc(String(e.message || e))}</div>`;
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
    ? `<div class="note info">${esc(t("analysed")(s.analyzed, s.dominant))}</div>`
    : esc(j.message || t("noRecordings"));
}

async function saveRecord() {
  if (!state.conversationId) return;
  $("talkRecord").innerHTML = `<span class="spinner"></span>${t("working")}`;
  const j = await (await fetch(`/api/conversation/${state.conversationId}/record?lang=${lang}`,
    { method: "POST" })).json();
  if (!j.ok) { $("talkRecord").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
  $("talkRecord").innerHTML = `<div class="note good">${t("recordSaved")}</div>
    <div class="stat"><b>${esc(j.mood)}</b><div class="sub" style="margin-top:6px">${esc(j.summary)}</div>
    <div class="sub" style="margin-top:6px">${esc(j.notable_points)}</div></div>`;
}



/* ---------- call offer ----------
   The resident asked to phone someone. A person always confirms: the app
   never dials by itself. The tel: link opens the device dialler. */
function showCallOffer(call) {
  const box = $("callOffer");
  if (!call) { box.innerHTML = ""; return; }
  box.innerHTML = `
    <div class="note good" style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
      <div style="flex:1;min-width:180px">
        <b style="font-size:18px">${esc(t("callOffer")(call.name))}</b>
        <div class="sub">${esc(call.relationship || "")}${call.relationship ? " · " : ""}${esc(call.phone)}</div>
      </div>
      <a class="btn good" style="text-decoration:none" href="${esc(call.tel)}"
         onclick="logCall(${call.contact_id})">${t("btnCallNow")}</a>
      <button class="btn ghost" onclick="document.getElementById('callOffer').innerHTML=''">
        ${t("btnNotNow")}</button>
    </div>`;
  if (call.say) speak(call.say);
}

function logCall(contactId) {
  fetch(`/api/calls/${contactId}/log?resident_id=${state.residentId}`,
        { method: "POST" }).catch(() => {});
}

/* ================= MOOD ================= */
let moodFace = null, moodVoice = null, moodCam = null, moodRec = null;

async function moodOpenCam() {
  try { moodCam = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } }); }
  catch (e) { $("mFaceOut").innerHTML = `<div class="note bad">${t("camDenied")}</div>`; return; }
  const v = $("mVideo");
  v.srcObject = moodCam; v.classList.remove("hide");
  $("mCanvas").classList.add("hide");
  $("mSnapBtn").classList.remove("hide");
  $("mRetake").classList.add("hide");
  $("mCamBtn").classList.add("hide");
}

async function moodSnap() {
  const v = $("mVideo"), c = $("mCanvas");
  c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
  c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
  if (moodCam) { moodCam.getTracks().forEach(x => x.stop()); moodCam = null; }
  $("mVideo").classList.add("hide"); c.classList.remove("hide");
  $("mSnapBtn").classList.add("hide"); $("mRetake").classList.remove("hide");
  const blob = await new Promise(res => c.toBlob(res, "image/jpeg", 0.9));
  await analyseMoodPhoto(blob);
}

$("mFile").onchange = e => { if (e.target.files[0]) analyseMoodPhoto(e.target.files[0]); };

async function analyseMoodPhoto(blob) {
  $("mFaceOut").innerHTML = `<span class="spinner"></span>${t("working")}`;
  try {
    const j = await (await fetch("/api/checkin/photo", { method: "POST", body: blob })).json();
    if (!j.ok) { $("mFaceOut").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
    if (!j.found) { moodFace = null; $("mFaceOut").innerHTML = `<div class="note warn">${t("noFace")}</div>`; return; }
    moodFace = j.face;
    $("mFaceOut").innerHTML = `<div class="note info">${esc(t("faceSeen")(j.face.emotion, Math.round(j.face.confidence)))}</div>`;
    showCombined();
  } catch (e) { $("mFaceOut").innerHTML = `<div class="note bad">${esc(String(e))}</div>`; }
}

async function toggleMoodRec() {
  const btn = $("mRecBtn");
  if (moodRec) {
    const blob = await moodRec.stop(); moodRec = null;
    btn.textContent = t("btnRecord"); btn.className = "btn grey";
    $("mLevel").style.width = "0";
    if (!blob) return;
    $("mVoiceOut").innerHTML = `<span class="spinner"></span>${t("working")}`;
    try {
      const j = await (await fetch(`/api/checkin/voice?lang=${lang}`, { method: "POST", body: blob })).json();
      if (!j.ok) { $("mVoiceOut").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
      moodVoice = j.voice || null;
      const heard = j.transcript ? `<div class="sub" style="margin-top:6px">${esc(t("heard")(j.transcript))}</div>` : "";
      $("mVoiceOut").innerHTML = j.voice
        ? `<div class="note info">${esc(t("toneWas")(j.voice.emotion, Math.round(j.voice.confidence)))}${heard}</div>`
        : `<div class="note warn">${esc(j.transcript || "")}</div>`;
      showCombined();
    } catch (e) { $("mVoiceOut").innerHTML = `<div class="note bad">${esc(String(e))}</div>`; }
  } else {
    try {
      moodRec = makeRecorder(); await moodRec.start();
      btn.textContent = t("btnStop"); btn.className = "btn red";
    } catch (e) { moodRec = null; $("mVoiceOut").innerHTML = `<div class="note bad">${t("micDenied")}</div>`; }
  }
}

/* Face and voice valence are both -1..1; average whichever we have. */
function moodScore() {
  const vals = [];
  if (moodFace && moodFace.valence != null) vals.push(moodFace.valence);
  if (moodVoice && moodVoice.valence != null) vals.push(moodVoice.valence);
  if (!vals.length) return null;
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  return Math.round(50 + 50 * mean);
}

function showCombined() {
  const s = moodScore();
  $("mCombined").innerHTML = s == null ? "" : `
    <div class="stat" style="margin-top:6px;display:flex;align-items:center;gap:18px;flex-wrap:wrap">
      <div class="score" style="color:${scoreColor(s)}">${s}</div>
      <div><b>${esc(t("moodCombined")(s))}</b>
        <div class="sub">${moodFace ? `${esc(moodFace.emotion)} (photo)` : ""}
          ${moodFace && moodVoice ? " \u00b7 " : ""}
          ${moodVoice ? `${esc(moodVoice.emotion)} (voice)` : ""}</div></div>
    </div>`;
}

async function saveMood() {
  if (!moodFace && !moodVoice) { $("mSaved").innerHTML = `<div class="note warn">${t("moodNothing")}</div>`; return; }
  const btn = $("mSaveBtn"); btn.disabled = true;
  try {
    const j = await (await fetch("/api/checkin/submit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resident_id: state.residentId, answers: { mood_only: "yes" },
                             face: moodFace, voice: moodVoice, lang })
    })).json();
    $("mSaved").innerHTML = j.ok
      ? `<div class="note good">${t("moodSaved")}</div>`
      : `<div class="note bad">${esc(j.message)}</div>`;
    if (j.ok) { loadMoodHistory(); loadHome(); }
  } finally { btn.disabled = false; }
}

function clearMood() {
  moodFace = null; moodVoice = null;
  $("mFaceOut").innerHTML = ""; $("mVoiceOut").innerHTML = "";
  $("mCombined").innerHTML = ""; $("mSaved").innerHTML = "";
  $("mCanvas").classList.add("hide");
  $("mCamBtn").classList.remove("hide"); $("mRetake").classList.add("hide");
}

async function loadMoodHistory() {
  if (!state.residentId) return;
  const j = await (await fetch(`/api/checkin/history?resident_id=${state.residentId}&limit=20`)).json();
  const rows = j.checkins.filter(c => c.face_emotion || c.voice_emotion);
  $("mHistory").innerHTML = rows.length ? `<table style="width:100%;border-collapse:collapse">
    ${rows.map(c => `<tr style="border-bottom:1px solid var(--line)">
      <td style="padding:9px 6px">${esc(c.day)} ${esc(c.time)}</td>
      <td style="padding:9px 6px"><b style="color:${scoreColor(c.wellbeing)}">${c.wellbeing ?? "\u2014"}</b></td>
      <td style="padding:9px 6px">${c.face_emotion ? `\ud83d\ude42 ${esc(c.face_emotion)}` : ""}</td>
      <td style="padding:9px 6px">${c.voice_emotion ? `\ud83c\udfa4 ${esc(c.voice_emotion)}` : ""}</td>
    </tr>`).join("")}</table>` : `<p class="sub">${t("moodNoHistory")}</p>`;
}


/* ================= FAMILY ================= */
const famWord = s => s == null ? t("famNoReading")
  : s >= 75 ? t("famDoingWell") : s >= 60 ? t("famAllRight")
  : s >= 40 ? t("famBitLow") : t("famNotWell");

async function loadFamily() {
  if (!state.residentId) return;
  let j;
  try {
    j = await (await fetch(`/api/family/overview?resident_id=${state.residentId}`)).json();
  } catch (e) { return; }
  if (!j.ok) { $("famHero").innerHTML = `<div class="sub">${esc(j.message)}</div>`; return; }

  const score = j.latest ? j.latest.wellbeing : null;
  $("famHero").innerHTML = `
    <div style="width:96px;height:96px;border-radius:50%;display:grid;place-items:center;
                font-size:28px;font-weight:800;color:#fff;background:${scoreColor(score)}">
      ${score ?? "\u2014"}</div>
    <div style="flex:1;min-width:220px">
      <div style="font-size:20px;font-weight:700">${esc(j.resident.name)}</div>
      <div style="font-size:18px;font-weight:600;color:${scoreColor(score)}">${famWord(score)}</div>
      <div class="sub" style="margin-top:4px">
        ${j.latest ? esc(t("famLastCheck")(j.latest.day, j.latest.time)) : t("famNever")}</div>
      ${j.latest && j.latest.summary ? `<div style="margin-top:8px">${esc(j.latest.summary)}</div>` : ""}
    </div>
    ${j.trend.length > 1 ? `<div style="min-width:170px">
      <div class="sub">${esc(t("famHistory"))}</div>
      <div style="display:flex;align-items:flex-end;gap:3px;height:64px;margin-top:6px">
        ${j.trend.map(d => `<div title="${d.day}: ${d.score}" style="flex:1;border-radius:3px 3px 0 0;
          min-height:3px;height:${Math.max(4, d.score)}%;background:${scoreColor(d.score)}"></div>`).join("")}
      </div></div>` : ""}`;

  $("famAlerts").innerHTML = j.alerts.length
    ? j.alerts.map(a => `<div class="banner ${a.level === "urgent" ? "err" : a.level === "warn" ? "warn" : "info"}">
        ${a.level === "urgent" ? "\ud83d\udea8" : a.level === "warn" ? "\u26a0" : "\u2139"} ${esc(a.text)}
        <div class="sub" style="font-weight:400">${esc(a.when || "")}</div></div>`).join("")
    : `<div class="note good">${t("famNothing")}</div>`;

  const med = j.medication;
  $("famCards").innerHTML = `
    <div class="stat"><span class="label">${t("cMeds")}</span>
      <b>${med ? `${med.today.taken}/${med.today.total}` : "\u2014"}</b></div>
    <div class="stat"><span class="label">${t("mMissed")}</span>
      <b style="color:${med && med.today.missed ? "var(--warn)" : "inherit"}">
        ${med ? med.today.missed : "\u2014"}</b></div>
    <div class="stat"><span class="label">${t("mNext")}</span>
      <b>${med && med.next ? esc(med.next.slot) : "\u2014"}</b></div>
    <div class="stat"><span class="label">${t("cTalks")}</span><b>${j.today_count}</b></div>`;

  loadFamContacts();
  loadFamTimeline();
  loadFamDigest();
}

async function loadFamDigest() {
  $("famDigest").innerHTML = `<span class="spinner"></span><span class="sub">${t("working")}</span>`;
  try {
    const j = await (await fetch(`/api/family/digest?resident_id=${state.residentId}&lang=${lang}`)).json();
    $("famDigest").innerHTML = j.ok ? `<div class="note info">\ud83d\udcac ${esc(j.digest)}</div>` : "";
  } catch (e) { $("famDigest").innerHTML = ""; }
}

async function loadFamTimeline() {
  const j = await (await fetch(`/api/family/timeline?resident_id=${state.residentId}&days=14`)).json();
  if (!j.ok) return;
  $("famTimeline").innerHTML = `<table style="width:100%;border-collapse:collapse">
    ${j.days.map(d => `<tr style="border-bottom:1px solid var(--line)">
      <td style="padding:8px 6px">${esc(d.day)}</td>
      <td style="padding:8px 6px"><b style="color:${scoreColor(d.wellbeing)}">${d.wellbeing ?? "\u2014"}</b></td>
      <td style="padding:8px 6px">${d.medication ? `${d.medication.taken}/${d.medication.total}` : "\u2014"}</td>
      <td style="padding:8px 6px" class="sub">${esc(d.summary || "")}</td>
    </tr>`).join("")}</table>`;
}

async function loadFamContacts() {
  const j = await (await fetch(`/api/contacts?resident_id=${state.residentId}`)).json();
  $("famContactList").innerHTML = j.contacts.length ? j.contacts.map(c => `
    <div class="row-item">
      <div style="flex:1;min-width:170px">
        <b>${esc(c.name)}</b>${c.is_primary ? `<span class="pill good">${t("fcMain")}</span>` : ""}
        <div class="sub">${esc(c.relationship || "")}${c.relationship ? " \u00b7 " : ""}${esc(c.phone)}</div>
      </div>
      <a class="btn good" style="text-decoration:none"
         href="tel:${esc((c.phone || "").replace(/[^\d+]/g, ""))}"
         onclick="logCall(${c.id})">${t("fcCall")}</a>
      <button class="btn ghost" onclick="famTogglePrimary(${c.id}, ${c.is_primary ? 0 : 1})">
        ${c.is_primary ? t("fcUnsetMain") : t("fcSetMain")}</button>
      <button class="btn bad" onclick="famDeleteContact(${c.id}, '${esc(c.name)}')">${t("fcDelete")}</button>
    </div>`).join("") : `<p class="sub">${t("fcNone")}</p>`;
}

async function famAddContact() {
  const name = $("fcName").value.trim(), phone = $("fcPhone").value.trim();
  if (!name || !phone) { $("fcStatus").textContent = t("fcNeed"); return; }
  const j = await (await fetch("/api/contacts", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, phone, relationship: $("fcRel").value.trim(),
                           is_primary: $("fcPrimary").checked,
                           resident_id: state.residentId })
  })).json();
  if (!j.ok) { $("fcStatus").textContent = j.message; return; }
  ["fcName", "fcRel", "fcPhone"].forEach(id => $(id).value = "");
  $("fcPrimary").checked = false;
  $("fcStatus").textContent = t("fcAdded");
  loadFamContacts();
}

async function famTogglePrimary(id, val) {
  await fetch(`/api/contacts/${id}`, { method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_primary: val }) });
  loadFamContacts();
}

async function famDeleteContact(id, name) {
  if (!confirm(t("fcConfirm")(name))) return;
  await fetch(`/api/contacts/${id}`, { method: "DELETE" });
  loadFamContacts();
}



/* ================= DEMO CLOCK =================
   Shifts the server's idea of "now" so reminders can be triggered on cue.
   Everything time-based follows it, because the server decides what is due. */

let clockState = null;

async function clockPost(body) {
  try {
    const j = await (await fetch("/api/demo/clock", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) })).json();
    if (j.ok) {
      clockState = j;
      paintClock();
      // A jump usually means "fire the reminder now" -- re-check immediately
      // instead of waiting for the next poll, and allow a repeat ask.
      for (const k in medLastAsked) delete medLastAsked[k];
      medicineTick();
      refreshTab();
    }
  } catch (e) { /* server not reachable */ }
}

const clockShift = (secs) => clockPost({ shift_seconds: secs });
const clockReset = () => clockPost({ reset: true });

/* Forgiving time parsing: someone demoing should be able to type "8", "805",
   "8:5" or "08:05" and have it mean 08:05, not get an error. */
function parseClockInput(raw) {
  const txt = String(raw || "").trim();
  if (!txt) return null;
  let h, m;
  const withColon = txt.match(/^(\d{1,2})\s*[:.\uff1a]\s*(\d{1,2})$/);
  const digits = txt.replace(/\D/g, "");
  // No digits at all is a typo, not midnight -- "abc" must not set 00:00.
  if (!withColon && !digits) return null;
  if (withColon) {
    h = +withColon[1]; m = +withColon[2];
  } else if (digits.length <= 2) {
    h = +digits; m = 0;                       // "8" -> 08:00
  } else if (digits.length === 3) {
    h = +digits.slice(0, 1); m = +digits.slice(1);   // "805" -> 08:05
  } else if (digits.length === 4) {
    h = +digits.slice(0, 2); m = +digits.slice(2);   // "0805" -> 08:05
  } else {
    return null;
  }
  if (!(h >= 0 && h <= 23 && m >= 0 && m <= 59)) return null;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function clockSet(raw) {
  const hhmm = parseClockInput(raw);
  const hint = $("dcHint");
  if (!hhmm) {
    if (hint && String(raw || "").trim()) hint.textContent = t("dcBadTime");
    return;
  }
  if (hint) hint.textContent = t("dcHint");
  clockPost({ time: hhmm });
}

/* Open the panel and put the caret straight in the field, so the clock is
   writable in one click rather than two. */
function openClockEditor() {
  const box = $("demoClock");
  box.classList.toggle("open");
  if (box.classList.contains("open")) {
    const input = $("dcInput");
    input.value = clockState ? clockState.time : "";
    setTimeout(() => { input.focus(); input.select(); }, 30);
  }
}

function paintClock() {
  if (!clockState) return;
  const box = $("demoClock");
  $("dcTime").textContent = clockState.time;
  box.classList.toggle("shifted", !!clockState.shifted);
  const input = $("dcInput");
  if (input && document.activeElement !== input) input.value = clockState.time;
  $("dcTag").textContent = clockState.shifted ? t("dcDemo") : t("dcClock");
}

async function clockPoll() {
  try {
    const j = await (await fetch("/api/demo/clock")).json();
    if (j.ok) { clockState = j; paintClock(); }
  } catch (e) { /* ignore */ }
}
setInterval(clockPoll, 10000);

/* ================= MEDICINE VOICE REMINDERS =================
   Announces a dose when it falls due, listens for "taken", marks it, and
   otherwise repeats every 5 minutes.

   Runs app-wide rather than on the Medicines tab: the resident will be on the
   Home screen, not looking at a medication list. It only speaks when a dose is
   actually due, so it stays quiet the rest of the time. */

const MED_REPEAT_MS = 5 * 60 * 1000;   // ask again after 5 minutes
const MED_POLL_MS = 30 * 1000;         // how often we check for a due dose

/* Ask at most this many times, then stop and record it as not taken. Endless
   reminding is worse than useless: the resident tunes it out, and the record
   still claims the dose is merely "pending" when in truth nobody confirmed it.
   Five attempts five minutes apart is about twenty minutes of trying. */
const MED_MAX_ASKS = 5;

/* How long a dose is chased before it is written off.
   30 minutes past its time it is marked not taken and the reminders stop.
   Without a cutoff, due_now() keeps returning any pending dose for the rest of
   the day, so an 08:00 dose nobody marked would still be announcing at 8pm --
   and the record would still claim it was merely "pending". */
const MED_GIVE_UP_MIN = 30;

let medAsking = false;                  // one announcement at a time
const medLastAsked = {};                // dose key -> timestamp
const medAskCount = {};                 // dose key -> how many times asked
const medWrittenOff = {};               // dose key -> already marked missed

const doseKey = d => `${d.med_id}|${d.day}|${d.slot}`;

function medBanner(html) {
  const box = $("medReminder");
  if (box) box.innerHTML = html;
}

async function medicineTick() {
  if (!medRemindersOn || medAsking || !state.residentId) return;
  let m;
  try { m = await (await fetch("/api/medications/today")).json(); }
  catch (e) { return; }

  // Anything already past the cutoff is written off now, whether or not it was
  // ever announced -- the app may have been closed when it fell due.
  const expired = (m.due || []).filter(d => (d.late_minutes ?? 0) > MED_GIVE_UP_MIN);
  if (expired.length) {
    await Promise.all(expired.map(d => writeOffDose(d, false)));
    if (currentTab() === "meds") loadMeds();
    if (currentTab() === "residentHome") loadResidentHome();
  }

  const due = (m.due || []).filter(d => {
    const k = doseKey(d);
    if ((d.late_minutes ?? 0) > MED_GIVE_UP_MIN) return false;
    if ((medAskCount[k] || 0) >= MED_MAX_ASKS) return false;   // asked enough
    const last = medLastAsked[k];
    return !last || Date.now() - last >= MED_REPEAT_MS;
  });
  if (!due.length) { if (!medAsking) medBanner(""); return; }

  await askAboutDose(due[0]);
}

async function askAboutDose(dose) {
  medAsking = true;
  const key = doseKey(dose);
  medLastAsked[key] = Date.now();
  medAskCount[key] = (medAskCount[key] || 0) + 1;
  const lastAttempt = medAskCount[key] >= MED_MAX_ASKS;
  const label = [dose.dose_amount, dose.strength].filter(Boolean).join(" ");

  medBanner(`
    <div class="note warn" style="align-items:center">
      <span class="ic">\u23f0</span>
      <div style="flex:1">
        <b>${esc(t("medRemindTitle"))}</b>
        <div style="font-size:1.05rem;margin-top:2px">${esc(dose.name)} ${esc(label)} \u00b7 ${esc(dose.slot)}</div>
        <small id="medPrompt">${esc(t("medAsk"))}</small>
        <div class="meter" style="margin-top:6px"><i id="medLevel"></i></div>
      </div>
      <button class="btn good" onclick="confirmDoseTaken(${dose.med_id},'${dose.day}','${dose.slot}')">${t("btnTaken")}</button>
      <button class="btn ghost" onclick="dismissDose()">${t("btnLater")}</button>
    </div>`);

  try {
    await say(t("medAnnounce")(dose.name, label), lang);
    const prompt = $("medPrompt");
    if (prompt) prompt.textContent = t("medListening");

    const blob = await listenOnce(12000, (v) => {
      const bar = $("medLevel");
      if (bar) bar.style.width = `${Math.round(v * 100)}%`;
    });
    if (!blob) {                              // said nothing
      if (lastAttempt) { await giveUpOnDose(dose); return; }
      if (prompt) prompt.textContent = t("medAgainIn");
      return;
    }
    const url = `/api/medications/confirm_voice?med_id=${dose.med_id}`
              + `&day=${dose.day}&slot=${encodeURIComponent(dose.slot)}&lang=${lang}`;
    const j = await (await fetch(url, { method: "POST", body: blob })).json();

    if (j.ok && j.taken) {
      await say(t("medThanks")(dose.name), lang);
      medBanner(`<div class="note good"><span class="ic">\u2713</span><div>${esc(t("medThanks")(dose.name))}</div></div>`);
      setTimeout(() => medBanner(""), 6000);
      delete medAskCount[key];
      delete medWrittenOff[key];
      if (currentTab() === "meds") loadMeds();
      if (currentTab() === "residentHome") loadResidentHome();
    } else if (lastAttempt) {
      await giveUpOnDose(dose);
    } else {
      if (prompt) prompt.textContent = t("medUnclear");
      await say(t("medUnclear"), lang);
    }
  } catch (e) {
    /* leave the card up; the 5-minute repeat will try again */
  } finally {
    medAsking = false;
  }
}

/* After the last attempt, stop asking and record the truth: nobody confirmed
   this dose. It is marked "skipped" rather than "taken" so the care team and
   the family dashboard see it as missed -- assuming it was swallowed because
   the resident went quiet would be the dangerous choice. */
async function writeOffDose(dose, announce = true) {
  const k = doseKey(dose);
  if (medWrittenOff[k]) return;               // only once per dose
  medWrittenOff[k] = true;
  try {
    await fetch("/api/medications/dose", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ med_id: dose.med_id, day: dose.day,
                             slot: dose.slot, status: "skipped" }) });
  } catch (e) { medWrittenOff[k] = false; return; }   // let it retry later

  if (announce) {
    medBanner(`<div class="note bad"><span class="ic">\u26a0</span><div>${esc(t("medGaveUp")(dose.name))}</div></div>`);
    setTimeout(() => medBanner(""), 12000);
    if (currentTab() === "meds") loadMeds();
    if (currentTab() === "residentHome") loadResidentHome();
  }
}

/* Kept as the name the ask-loop calls, so the last failed attempt still
   explains itself out loud. */
const giveUpOnDose = (dose) => writeOffDose(dose, true);

/* Tapping the button is always available -- voice is an addition, not a
   requirement, and a resident may simply prefer to press it. */
async function confirmDoseTaken(med_id, day, slot) {
  await fetch("/api/medications/dose", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ med_id, day, slot, status: "taken" }) });
  shutUp();
  medBanner(`<div class="note good"><span class="ic">\u2713</span><div>${esc(t("medThanks")(""))}</div></div>`);
  setTimeout(() => medBanner(""), 5000);
  if (currentTab() === "meds") loadMeds();
  if (currentTab() === "residentHome") loadResidentHome();
}

function dismissDose() {
  shutUp();
  medBanner("");
}

function toggleMedReminders() {
  medRemindersOn = !medRemindersOn;
  localStorage.setItem("eca_med_voice", medRemindersOn ? "on" : "off");
  const b = $("medVoiceBtn");
  if (b) b.textContent = medRemindersOn ? t("medRemindersOn") : t("medRemindersOff");
  if (!medRemindersOn) { shutUp(); medBanner(""); }
}

setInterval(medicineTick, MED_POLL_MS);

/* ================= MEDS ================= */
async function loadMeds() {
  let m;
  try { m = await (await fetch("/api/medications/today")).json(); } catch (e) { return; }
  $("mTotal").textContent = m.total;
  $("mTaken").textContent = m.taken;
  $("mMissed").textContent = m.missed;
  $("mNext").textContent = m.next ? m.next.slot : "—";

  $("medsAlert").innerHTML = (m.due && m.due.length)
    ? `<div class="note warn">⏰ ${m.due.map(d => esc(`${d.name} (${d.slot})`)).join(", ")}</div>` : "";

  $("medsList").innerHTML = m.doses.length ? m.doses.map(d => `
    <div class="row-item ${d.status === "taken" ? "taken" : ""}">
      <div class="time">${d.slot}</div>
      <div style="flex:1;min-width:150px"><b>${esc(d.name)}</b>
        ${d.status === "taken" ? `<span class="pill good">${t("taken")}</span>` : ""}
        <div class="sub">${esc([d.dose_amount, d.strength].filter(Boolean).join(" · "))}</div></div>
      ${d.status === "pending"
        ? `<button class="btn good" onclick="dose(${d.med_id},'${d.day}','${d.slot}','taken')">${t("taken")}</button>
           <button class="btn ghost" onclick="dose(${d.med_id},'${d.day}','${d.slot}','skipped')">${t("skip")}</button>`
        : `<button class="btn ghost" onclick="dose(${d.med_id},'${d.day}','${d.slot}','undo')">${t("undo")}</button>`}
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
  if (!d || !d.medications.length) { $("rxReview").innerHTML = `<div class="note warn">${t("noRx")}</div>`; return; }
  $("rxReview").innerHTML = `<div class="note warn"><b>${t("reviewRx")}</b></div>` +
    (d.warnings || []).map(w => `<div class="note warn">⚠ ${esc(w)}</div>`).join("") +
    d.medications.map((m, i) => `
      <div class="stat" style="margin-bottom:12px">
        <b style="font-size:18px">${esc(m.name)}</b>
        <div class="opts" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-top:10px">
          <div><div class="sub">${t("name")}</div><input type="text" id="rx_n_${i}" value="${esc(m.name)}"></div>
          <div><div class="sub">${t("strength")}</div><input type="text" id="rx_s_${i}" value="${esc(m.strength||"")}"></div>
          <div><div class="sub">${t("dose")}</div><input type="text" id="rx_d_${i}" value="${esc(m.dose_amount||"")}"></div>
          <div><div class="sub">${t("times")}</div><input type="text" id="rx_t_${i}" value="${esc((m.times||[]).join(", "))}"></div>
          <div><div class="sub">${t("days")}</div><input type="text" id="rx_y_${i}" value="${esc(m.duration_days||"")}"></div>
        </div>
      </div>`).join("") +
    `<button class="btn good" onclick="saveRx()">${t("saveRx")}</button>
     <button class="btn ghost" onclick="state.rxDraft=null;document.getElementById('rxReview').innerHTML=''">${t("cancel")}</button>`;
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
    $("rxReview").innerHTML = `<div class="note good">${t("savedN")(j.saved)}</div>`;
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
    if (!j.ok) { $("repOut").innerHTML = `<div class="note bad">${esc(j.message)}</div>`; return; }
    if (j.empty) { $("repOut").innerHTML = `<div class="note info">${t("emptyReport")}</div>`; return; }
    $("repOut").innerHTML = `<pre class="report">${esc(j.report)}</pre>`;
  } finally { $("repStatus").textContent = ""; $("repBtn").disabled = false; }
}
