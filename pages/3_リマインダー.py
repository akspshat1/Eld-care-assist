"""Voice reminders page: set reminder times/content per resident.
A background thread (started here) speaks each reminder aloud when its time
comes, as long as this Streamlit app process keeps running."""
import streamlit as st

from core.database import (
    add_reminder,
    delete_reminder,
    get_reminders,
    get_residents,
    set_reminder_active,
)
from core.tts_client import speak
from features.reminders import start_scheduler

st.set_page_config(page_title="リマインダー", page_icon="⏰")
st.title("リマインダー")

start_scheduler()

residents = get_residents()
residents_by_id = {r["id"]: r for r in residents}

st.subheader("新しいリマインダーを追加")
with st.form("add_reminder_form"):
    resident_id = st.selectbox(
        "入居者",
        options=list(residents_by_id.keys()),
        format_func=lambda rid: residents_by_id[rid]["name"],
    )
    reminder_time = st.time_input("時刻")
    content = st.text_input("内容（例: お薬を飲む時間、水分補給、体操の時間）")
    submitted = st.form_submit_button("追加")
    if submitted:
        if not content:
            st.warning("内容を入力してください。")
        else:
            add_reminder(resident_id, reminder_time.strftime("%H:%M"), content)
            st.success("リマインダーを追加しました。")
            st.rerun()

st.subheader("リマインダー一覧")
reminders = get_reminders()
if not reminders:
    st.write("まだリマインダーがありません。")
else:
    for r in reminders:
        col1, col2, col3, col4, col5 = st.columns([2, 1, 3, 1, 1])
        col1.write(r["resident_name"])
        col2.write(r["time"])
        col3.write(r["content"])
        is_active = col4.checkbox("有効", value=bool(r["is_active"]), key=f"active_{r['id']}")
        if is_active != bool(r["is_active"]):
            set_reminder_active(r["id"], is_active)
            st.rerun()
        if col5.button("削除", key=f"delete_{r['id']}"):
            delete_reminder(r["id"])
            st.rerun()

st.subheader("テスト再生")
st.write("設定した時刻を待たずに、その場で音声を確認できます。")
if reminders:
    test_id = st.selectbox(
        "テストするリマインダー",
        options=[r["id"] for r in reminders],
        format_func=lambda rid: next(r for r in reminders if r["id"] == rid)["content"],
        key="test_select",
    )
    if st.button("今すぐ再生する"):
        target = next(r for r in reminders if r["id"] == test_id)
        speak(f"{target['resident_name']}さん、{target['content']}の時間です。")
        st.success("再生しました。")
