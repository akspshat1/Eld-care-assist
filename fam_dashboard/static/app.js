/* Family dashboard front end. */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

let residentId = null;

const scoreColor = s => s == null ? "#9aa5b1"
  : s >= 60 ? "#12a150" : s < 40 ? "#dc2626" : "#d97706";

const scoreWord = s => s == null ? "No reading yet"
  : s >= 75 ? "Doing well" : s >= 60 ? "Doing all right"
  : s >= 40 ? "A bit low" : "Not doing well";

/* ---- tabs ---- */
document.querySelectorAll("nav button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach(x =>
      x.classList.toggle("on", x === b));
    document.querySelectorAll(".panel").forEach(x =>
      x.classList.toggle("on", x.id === b.dataset.tab));
    if (b.dataset.tab === "history") loadTimeline();
    if (b.dataset.tab === "contacts") { loadContacts(); loadCalls(); }
  };
});

/* ---- boot ---- */
(async function boot() {
  const h = await (await fetch("/api/health")).json();
  if (!h.sources.care_db) {
    $("banner").innerHTML = `<div class="alert warn"><span class="ic">⚠</span>
      <div>${esc(h.message)}</div></div>`;
  }
  const r = await (await fetch("/api/residents")).json();
  const sel = $("who");
  if (!r.residents.length) {
    sel.innerHTML = "<option>No residents</option>";
    return;
  }
  sel.innerHTML = r.residents.map(p =>
    `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  residentId = r.residents[0].id;
  sel.onchange = () => { residentId = Number(sel.value); loadAll(); };
  loadAll();
})();

function loadAll() {
  if (!residentId) return;
  loadOverview();
  loadDigest();
  $("exportLink").href = `/api/export?resident_id=${residentId}&days=30`;
}

/* ---- overview ---- */
async function loadOverview() {
  const j = await (await fetch(`/api/overview?resident_id=${residentId}`)).json();
  if (!j.ok) { $("hero").innerHTML = `<div class="sub">${esc(j.message)}</div>`; return; }

  const score = j.latest ? j.latest.wellbeing : null;
  $("hero").innerHTML = `
    <div class="ring" style="background:${scoreColor(score)}">${score ?? "—"}</div>
    <div style="flex:1;min-width:220px">
      <div class="who">${esc(j.resident.name)}</div>
      <div style="font-size:19px;font-weight:600;color:${scoreColor(score)};margin-top:3px">
        ${scoreWord(score)}</div>
      <div class="sub" style="margin-top:5px">
        ${j.latest ? `Last check-in ${esc(j.latest.day)} at ${esc(j.latest.time)}`
                   : "No check-ins yet"}
        ${j.hours_since_checkin != null ? ` · ${j.hours_since_checkin}h ago` : ""}
      </div>
      ${j.latest && j.latest.summary
        ? `<div style="margin-top:10px">${esc(j.latest.summary)}</div>` : ""}
    </div>
    ${j.trend.length > 1 ? `<div style="min-width:180px">
        <div class="sub">Last ${j.trend.length} days</div>
        <div class="bar">${j.trend.map(d =>
          `<div title="${d.day}: ${d.score}" style="height:${Math.max(4, d.score)}%;
             background:${scoreColor(d.score)}"></div>`).join("")}</div></div>` : ""}`;

  $("alerts").innerHTML = j.alerts.length
    ? j.alerts.map(a => `
        <div class="alert ${a.level}">
          <span class="ic">${a.level === "urgent" ? "🚨" : a.level === "warn" ? "⚠" : "ℹ"}</span>
          <div>${esc(a.text)}<small>${esc(a.when)}</small></div>
        </div>`).join("")
    : `<div class="ok">Nothing needs your attention right now.</div>`;

  const med = j.medication;
  $("cards").innerHTML = `
    <div class="c"><span class="label">CHECK-INS TODAY</span><b>${j.today_count}</b></div>
    <div class="c"><span class="label">MEDICINES TODAY</span>
      <b>${med ? `${med.today.taken}/${med.today.total}` : "—"}</b></div>
    <div class="c"><span class="label">MISSED TODAY</span>
      <b style="color:${med && med.today.missed ? "var(--warn)" : "inherit"}">
        ${med ? med.today.missed : "—"}</b></div>
    <div class="c"><span class="label">NEXT DOSE</span>
      <b>${med && med.next ? esc(med.next.slot) : "—"}</b></div>`;

  $("medBox").innerHTML = (med && med.missed_today.length) ? `
    <div class="alert warn"><span class="ic">💊</span><div>
      Missed today: ${med.missed_today.map(m =>
        esc(`${m.name} at ${m.slot}`)).join(", ")}
      <small>Week so far: ${med.week.taken} of ${med.week.total} taken
        ${med.week.adherence != null ? `(${med.week.adherence}%)` : ""}</small>
    </div></div>` : (med ? `<p class="sub">Medicines this week:
      ${med.week.taken} of ${med.week.total} taken
      ${med.week.adherence != null ? `(${med.week.adherence}%)` : ""}.</p>` : "");

  $("recent").innerHTML = j.recent.length ? `<table>
    <tr><th>When</th><th>Wellbeing</th><th>How they were</th></tr>
    ${j.recent.map(c => `<tr>
      <td>${esc(c.day)} ${esc(c.time)}</td>
      <td><b style="color:${scoreColor(c.wellbeing)}">${c.wellbeing ?? "—"}</b></td>
      <td>${esc(c.summary || "")}
        ${c.concerns.length ? `<br><span class="sub" style="color:var(--amber)">
          ⚠ ${c.concerns.map(esc).join(" · ")}</span>` : ""}</td></tr>`).join("")}
    </table>` : `<p class="sub">No check-ins recorded yet.</p>`;
}

async function loadDigest() {
  $("digest").innerHTML = `<span class="spinner"></span><span class="sub">Writing an update…</span>`;
  try {
    const j = await (await fetch(`/api/digest?resident_id=${residentId}`)).json();
    $("digest").innerHTML = j.ok
      ? `<div class="alert info"><span class="ic">💬</span><div>${esc(j.digest)}</div></div>`
      : "";
  } catch (e) { $("digest").innerHTML = ""; }
}

/* ---- timeline ---- */
async function loadTimeline() {
  const j = await (await fetch(`/api/timeline?resident_id=${residentId}&days=14`)).json();
  if (!j.ok) { $("timeline").innerHTML = `<p class="sub">${esc(j.message)}</p>`; return; }
  $("timeline").innerHTML = `<table>
    <tr><th>Day</th><th>Wellbeing</th><th>Check-ins</th><th>Medicines</th><th>Notes</th></tr>
    ${j.days.map(d => `<tr>
      <td>${esc(d.day)}</td>
      <td><b style="color:${scoreColor(d.wellbeing)}">${d.wellbeing ?? "—"}</b></td>
      <td>${d.checkins}</td>
      <td>${d.medication ? `${d.medication.taken}/${d.medication.total}
           ${d.medication.missed ? `<span class="pill" style="background:#fee2e2;color:#b91c1c">
             ${d.medication.missed} missed</span>` : ""}` : "—"}</td>
      <td>${esc(d.summary || "")}
        ${d.concerns.length ? `<br><span class="sub" style="color:var(--amber)">
          ${d.concerns.map(esc).join(" · ")}</span>` : ""}</td></tr>`).join("")}
  </table>`;
}

/* ---- contacts ---- */
async function loadContacts() {
  const j = await (await fetch(`/api/contacts?resident_id=${residentId}`)).json();
  $("contactList").innerHTML = j.contacts.length ? j.contacts.map(c => `
    <div class="contact">
      <div class="who"><b>${esc(c.name)}</b>
        ${c.is_primary ? `<span class="pill primary">Main contact</span>` : ""}
        <div class="sub">${esc(c.relationship || "")}${c.relationship ? " · " : ""}${esc(c.phone)}</div>
      </div>
      <a class="call" href="tel:${esc((c.phone || "").replace(/[^\d+]/g, ""))}"
         onclick="logCall(${c.id})">📞 Call</a>
      <button class="ghost" onclick="togglePrimary(${c.id}, ${c.is_primary ? 0 : 1})">
        ${c.is_primary ? "Unset main" : "Set as main"}</button>
      <button class="ghost" onclick="removeContact(${c.id}, '${esc(c.name)}')">Delete</button>
    </div>`).join("") : `<p class="sub">No contacts yet. Add one below.</p>`;
}

async function addContact() {
  const name = $("cName").value.trim(), phone = $("cPhone").value.trim();
  if (!name || !phone) { $("cStatus").textContent = "Name and phone are required."; return; }
  const j = await (await fetch("/api/contacts", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, phone, relationship: $("cRel").value.trim(),
                           email: $("cEmail").value.trim(),
                           is_primary: $("cPrimary").checked,
                           resident_id: residentId })
  })).json();
  if (!j.ok) { $("cStatus").textContent = j.message; return; }
  ["cName", "cRel", "cPhone", "cEmail"].forEach(id => $(id).value = "");
  $("cPrimary").checked = false;
  $("cStatus").textContent = "Added.";
  loadContacts();
}

async function togglePrimary(id, val) {
  await fetch(`/api/contacts/${id}`, { method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_primary: val }) });
  loadContacts();
}

async function removeContact(id, name) {
  if (!confirm(`Remove ${name}?`)) return;
  await fetch(`/api/contacts/${id}`, { method: "DELETE" });
  loadContacts();
}

async function logCall(id) {
  // Fire and forget: the tel: link opens regardless.
  fetch(`/api/contacts/${id}/call?resident_id=${residentId}`, { method: "POST" })
    .then(() => loadCalls()).catch(() => {});
}

async function loadCalls() {
  const j = await (await fetch(`/api/overview?resident_id=${residentId}`)).json();
  if (!j.ok) return;
  $("callLog").innerHTML = j.calls.length ? `<table>
    <tr><th>When</th><th>Who</th><th>Started from</th></tr>
    ${j.calls.map(c => `<tr><td>${esc(c.day)} ${esc(c.time)}</td>
      <td>${esc(c.name)}${c.relationship ? ` <span class="sub">(${esc(c.relationship)})</span>` : ""}</td>
      <td>${esc(c.source)}</td></tr>`).join("")}</table>`
    : `<p class="sub">No calls recorded yet.</p>`;
}
