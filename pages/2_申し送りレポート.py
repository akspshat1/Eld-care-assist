"""Handoff report page: aggregate a day's conversation records into a report."""
from datetime import date

import streamlit as st

from core.database import get_daily_records, get_residents
from features.report import generate_report

st.set_page_config(page_title="申し送りレポート", page_icon="📋")
st.title("申し送りレポート")

residents = get_residents()
residents_by_id = {r["id"]: r for r in residents}
resident_options = {0: "全員"}
resident_options.update({r["id"]: r["name"] for r in residents})

col1, col2 = st.columns(2)
with col1:
    target_date = st.date_input("対象日", value=date.today())
with col2:
    selected_id = st.selectbox(
        "入居者", options=list(resident_options.keys()), format_func=lambda k: resident_options[k]
    )

if st.button("レポートを生成"):
    date_str = target_date.isoformat()
    resident_id = None if selected_id == 0 else selected_id
    records = get_daily_records(date_str, resident_id)

    if not records:
        st.warning(
            "この日の会話記録が見つかりません。会話ページで「この会話の記録を保存」を"
            "実行してから、もう一度お試しください。"
        )
    else:
        records_by_resident = {}
        for rec in records:
            records_by_resident.setdefault(rec["resident_id"], []).append(rec)

        for rid, resident_records in records_by_resident.items():
            resident_name = resident_records[0]["resident_name"]
            with st.spinner(f"{resident_name}さんのレポートを作成中..."):
                report_text = generate_report(resident_name, resident_records)
            st.subheader(resident_name)
            st.text_area(
                f"{resident_name}さんのレポート（コピーして使えます）",
                report_text,
                height=220,
                key=f"report_{rid}",
            )
