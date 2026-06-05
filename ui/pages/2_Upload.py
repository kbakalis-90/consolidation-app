"""Upload page: account mappings and trial balances."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from consol.checks.registry import summarize
from consol.ingestion.readers import IngestionError
from consol.persistence import entity_repo, mapping_repo
from consol.services import ingestion_service
from ui.bootstrap import get_conn
from ui.components.check_badge import render_check_summary

st.title("📤 Upload")

conn = get_conn()
entities = entity_repo.list_all(conn)
if not entities:
    st.warning("Add at least one entity on the Setup page first.")
    st.stop()

entity_by_label = {f"{e.code} — {e.name}": e for e in entities}
label = st.selectbox("Entity", list(entity_by_label.keys()))
entity = entity_by_label[label]

tab_map, tab_tb = st.tabs(["Account mapping", "Trial balance"])

with tab_map:
    st.caption(
        "Columns: account_code, statement (BS/PL), caption, normal_sign (debit/credit); "
        "optional: account_desc, caption_order, cf_category, wc_class, is_equity, is_cash."
    )
    has = mapping_repo.has_mapping(conn, entity.entity_id)
    st.info(f"Mapping currently {'loaded' if has else 'NOT loaded'} for {entity.code}.")
    mfile = st.file_uploader("Mapping file (.csv/.xlsx)", type=["csv", "xlsx", "xls"], key="map")
    if mfile is not None and st.button("Load mapping"):
        try:
            res = ingestion_service.ingest_mapping(
                conn, entity.entity_id, mfile.getvalue(), mfile.name
            )
            render_check_summary(summarize(res.checks))
            if res.rows:
                st.success(f"Loaded {res.rows} mapping rows for {entity.code}.")
        except IngestionError as exc:
            st.error(str(exc))

with tab_tb:
    st.caption("Columns: account_code (+ debit/credit OR signed amount); optional account_desc.")
    cols = st.columns(2)
    year = cols[0].number_input("Year", min_value=2000, max_value=2100, value=dt.date.today().year)
    month = cols[1].number_input("Month", min_value=1, max_value=12, value=dt.date.today().month)
    tfile = st.file_uploader("Trial balance (.csv/.xlsx)", type=["csv", "xlsx", "xls"], key="tb")
    if tfile is not None and st.button("Load trial balance"):
        try:
            res = ingestion_service.ingest_tb(
                conn, entity.entity_id, int(year), int(month), tfile.getvalue(), tfile.name
            )
            render_check_summary(summarize(res.checks))
            if res.rows:
                st.success(
                    f"Loaded {res.rows} TB rows for {entity.code} {int(year)}-{int(month):02d}."
                )
        except IngestionError as exc:
            st.error(str(exc))

st.divider()
st.subheader("Recent uploads")
st.dataframe(ingestion_service.upload_history(conn), hide_index=True, use_container_width=True)
