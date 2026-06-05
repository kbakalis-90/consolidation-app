"""Setup page: configure the group currency and manage entities."""

from __future__ import annotations

import streamlit as st

from consol.persistence import config_repo, entity_repo
from consol.services import ingestion_service
from ui.bootstrap import get_conn

st.title("⚙️ Setup")

conn = get_conn()

st.header("Group settings")
current_ccy = config_repo.group_currency(conn)
with st.form("group_settings"):
    group_ccy = st.text_input("Group reporting currency (ISO 4217)", value=current_ccy, max_chars=3)
    if st.form_submit_button("Save group settings"):
        config_repo.set(conn, "group_currency", group_ccy.strip().upper())
        conn.commit()
        st.success(f"Group currency set to {group_ccy.strip().upper()}.")

st.header("Entities")
with st.form("add_entity", clear_on_submit=True):
    cols = st.columns(3)
    code = cols[0].text_input("Code", placeholder="UK01")
    name = cols[1].text_input("Name", placeholder="Acme UK Ltd")
    currency = cols[2].text_input("Local currency", placeholder="GBP", max_chars=3)
    if st.form_submit_button("Add / update entity"):
        if code and name and currency:
            ingestion_service.save_entity(conn, code, name, currency)
            st.success(f"Saved entity {code.strip().upper() if False else code.strip()}.")
        else:
            st.error("Code, name and currency are all required.")

entities = entity_repo.list_all(conn)
if entities:
    st.dataframe(
        [
            {"Code": e.code, "Name": e.name, "Currency": e.local_currency, "Active": e.is_active}
            for e in entities
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("No entities yet. Add one above.")
