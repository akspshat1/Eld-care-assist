"""Streamlit entry point.

Feature pages (conversation, report, reminders) will be added under pages/
in later steps. For now this page just verifies the project setup.
"""
import streamlit as st

from config import GROQ_API_KEY
from core.database import init_db, list_tables

st.set_page_config(page_title="会話×記録自動化AI", page_icon="🧓")

init_db()

st.title("高齢者施設向け 会話×記録自動化AI")
st.write("左のサイドバーから各機能のページに移動します（機能はステップごとに追加されます）。")

st.subheader("セットアップ状況の確認")

tables = list_tables()
st.write(f"DBに作成されたテーブル: {', '.join(tables) if tables else 'なし'}")

if GROQ_API_KEY:
    st.success("GROQ_API_KEY が読み込まれています。")
else:
    st.warning("GROQ_API_KEY が未設定です。.env ファイルを作成して設定してください。")
