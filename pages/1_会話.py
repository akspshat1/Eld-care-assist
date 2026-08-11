"""Conversation page: chat with a resident persona and log it to the DB."""
import streamlit as st

from core.database import (
    add_message,
    create_conversation,
    get_extraction,
    get_messages,
    get_residents,
    save_extraction,
    seed_residents_from_personas,
)
from core.llm_client import transcribe_audio
from features.conversation import build_system_prompt, get_ai_reply, load_personas
from features.extraction import extract_conversation

st.set_page_config(page_title="会話", page_icon="💬")
st.title("会話")

seed_residents_from_personas(load_personas())
residents = get_residents()
residents_by_id = {r["id"]: r for r in residents}

selected_id = st.sidebar.selectbox(
    "入居者を選択",
    options=list(residents_by_id.keys()),
    format_func=lambda rid: residents_by_id[rid]["name"],
)
selected_resident = residents_by_id[selected_id]

st.sidebar.write(f"性格: {selected_resident['personality']}")
st.sidebar.write(f"好きな話題: {selected_resident['favorite_topics']}")

# Start a new conversation session when the resident changes, or on first load.
if st.session_state.get("resident_id") != selected_id:
    st.session_state.resident_id = selected_id
    st.session_state.conversation_id = create_conversation(selected_id)

if st.sidebar.button("新しい会話を始める"):
    st.session_state.conversation_id = create_conversation(selected_id)

conversation_id = st.session_state.conversation_id

# Show the conversation so far (persisted in the DB, not just this session).
history = get_messages(conversation_id)
for msg in history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

audio_value = st.audio_input("音声で話しかける（録音して送信）")
user_input = st.chat_input("または、メッセージを入力してください")

# audio_input keeps returning the same recording across reruns, so only
# transcribe it once per new recording (tracked by its file_id).
if audio_value is not None and audio_value.file_id != st.session_state.get("last_audio_id"):
    st.session_state.last_audio_id = audio_value.file_id
    with st.spinner("音声を認識中..."):
        user_input = transcribe_audio(audio_value.getvalue())

if user_input:
    add_message(conversation_id, "user", user_input)
    with st.chat_message("user"):
        st.write(user_input)

    system_prompt = build_system_prompt(selected_resident)
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in get_messages(conversation_id):
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    with st.chat_message("assistant"):
        with st.spinner("考え中..."):
            reply = get_ai_reply(api_messages)
        st.write(reply)
    add_message(conversation_id, "assistant", reply)

st.sidebar.divider()
if st.sidebar.button("この会話の記録を保存"):
    current_history = get_messages(conversation_id)
    if not current_history:
        st.sidebar.warning("まだ会話がありません。")
    else:
        with st.spinner("記録を作成中..."):
            result = extract_conversation(current_history)
        save_extraction(
            conversation_id, result["mood"], result["summary"], result["notable_points"]
        )
        st.sidebar.success("記録を保存しました。")

extraction = get_extraction(conversation_id)
if extraction:
    st.sidebar.subheader("この会話の記録")
    st.sidebar.write(f"気分: {extraction['mood']}")
    st.sidebar.write(f"要約: {extraction['summary']}")
    st.sidebar.write(f"特記事項: {extraction['notable_points']}")
