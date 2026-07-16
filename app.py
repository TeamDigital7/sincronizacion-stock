from __future__ import annotations

import hmac

import pandas as pd
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


def read_uploaded_snapshot(uploaded) -> pd.DataFrame:
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded, dtype=str)
    return pd.read_excel(uploaded, dtype=str)


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

    erp_snapshot = None
    if config.bigquery.mode == "uploaded_snapshot":
        st.info(
            "Modo snapshot cargado: sube un CSV/XLSX con el stock ERP ya calculado. "
            "La app no consultará BigQuery."
        )
        uploaded = st.file_uploader(
            "Archivo ERP snapshot",
            type=["csv", "xlsx", "xls"],
        )
        if uploaded is not None:
            erp_snapshot = read_uploaded_snapshot(uploaded)
            required_columns = {"sitio", "id_producto", "codigo_tienda", "stock_erp_sitio"}
            missing = required_columns - set(erp_snapshot.columns)
            if missing:
                st.error(
                    "El archivo ERP snapshot no tiene estas columnas obligatorias: "
                    + ", ".join(sorted(missing))
                )
                st.stop()
            st.success(f"Archivo cargado: {len(erp_snapshot):,} filas")

    if st.button("Ejecutar conciliación", type="primary", disabled=not sites):
        if config.bigquery.mode == "uploaded_snapshot" and erp_snapshot is None:
            st.error("Debes subir el archivo ERP snapshot antes de ejecutar.")
            st.stop()
        with st.spinner("Consultando fuentes y Shopify…"):
            try:
                result = StockReconciliationService(config).run(
                    sites,
                    erp_snapshot=erp_snapshot,
                )
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
