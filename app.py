from __future__ import annotations

import hmac

import streamlit as st

from stock_sync import StockReconciliationService
from stock_sync.config import AppConfig

st.set_page_config(page_title="Sincronización de stock", page_icon="📦", layout="wide")


def authenticated() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title("Acceso")
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")
    if submitted:
        auth = st.secrets["app_auth"]
        users = auth.get("users", {auth.get("username"): auth.get("password")})
        expected = users.get(username)
        if expected and hmac.compare_digest(str(password), str(expected)):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Credenciales incorrectas")
    return False


if authenticated():
    st.title("Conciliación ERP ↔ Shopify")
    try:
        config = AppConfig.from_mapping(st.secrets)
    except (KeyError, ValueError) as exc:
        st.error(f"Configuración inválida: {exc}")
        st.stop()

    sites = st.multiselect(
        "Sitios",
        options=list(config.shopify_sites),
        default=list(config.shopify_sites),
    )

    if st.button("Ejecutar conciliación", type="primary", disabled=not sites):
        with st.spinner("Consultando BigQuery y Shopify…"):
            try:
                result = StockReconciliationService(config).run(sites)
            except Exception as exc:
                st.exception(exc)
                st.stop()
        st.session_state["result"] = result

    if result := st.session_state.get("result"):
        st.subheader("Resumen")
        st.dataframe(result.summary, use_container_width=True, hide_index=True)
        st.subheader("Detalle desincronizado")
        mismatches = result.detail[
            result.detail["estado_sincronizacion"] != "SINCRONIZADO"
        ]
        st.dataframe(mismatches, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar Excel",
            data=result.excel_bytes,
            file_name="desincronizacion_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        if result.warnings:
            with st.expander(f"Advertencias ({len(result.warnings)})"):
                st.write("\n".join(f"- {warning}" for warning in result.warnings))
