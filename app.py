from __future__ import annotations

import hmac

import streamlit as st

from stock_sync import StockReconciliationService
from stock_sync.bigquery_source import BigQuerySource
from stock_sync.config import AppConfig

st.set_page_config(page_title="Sincronización de stock", page_icon="📦", layout="wide")


def apply_design_system() -> None:
    """Apply the compact, border-first visual language used throughout the app."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --canvas: #ffffff;
            --paper: #f5f5f5;
            --border: #e5e5e5;
            --border-strong: #d4d4d4;
            --ink: #171717;
            --midnight: #0a0a0a;
            --muted: #737373;
            --blue: #2563eb;
            --blue-dark: #1e40af;
            --mint: #dcfce7;
        }

        html, body, [class*="css"] {
            font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
            color: var(--ink);
        }

        .stApp {
            background-color: var(--canvas);
            background-image: radial-gradient(#e5e5e5 0.65px, transparent 0.65px);
            background-size: 18px 18px;
        }

        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.92);
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(12px);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1200px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3, p, label { color: var(--ink); }

        .brand-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 4rem;
            font-size: 14px;
            font-weight: 600;
        }

        .brand-mark {
            display: grid;
            place-items: center;
            width: 32px;
            height: 32px;
            color: white;
            background: var(--midnight);
            border-radius: 9px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
            font-size: 16px;
        }

        .brand-name { font-size: 15px; }
        .brand-name span { color: var(--blue); }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            margin: 0 0 16px;
            padding: 6px 11px;
            color: var(--ink);
            background: var(--canvas);
            border: 1px solid var(--border);
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 500;
        }

        .eyebrow::before {
            width: 7px;
            height: 7px;
            background: var(--blue);
            border-radius: 50%;
            content: "";
        }

        .hero-title {
            max-width: 760px;
            margin: 0;
            color: var(--ink);
            font-family: "Inter", ui-sans-serif, sans-serif;
            font-size: clamp(38px, 5vw, 48px);
            font-weight: 500;
            line-height: 1.04;
            letter-spacing: -0.035em;
        }

        .hero-copy {
            max-width: 650px;
            margin: 16px 0 32px;
            color: var(--muted);
            font-size: 16px;
            line-height: 1.5;
        }

        .login-hero { max-width: 620px; margin: 4vh auto 24px; text-align: center; }
        .login-hero .hero-title { font-size: clamp(38px, 6vw, 48px); }
        .login-hero .hero-copy { margin-left: auto; margin-right: auto; }

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--canvas);
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            box-shadow: none;
        }

        div[data-testid="stForm"] {
            max-width: 520px;
            margin: 0 auto;
            padding: 20px 20px 10px;
        }

        [data-testid="stTextInput"] input,
        [data-baseweb="select"] > div {
            min-height: 42px;
            color: var(--ink) !important;
            background: var(--canvas) !important;
            border-color: var(--midnight) !important;
            border-radius: 6px !important;
        }

        [data-testid="stTextInput"] input:focus {
            border-color: var(--blue) !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            min-height: 40px;
            padding: 0.55rem 1rem;
            color: var(--ink) !important;
            background: var(--canvas) !important;
            border: 1px solid var(--border-strong) !important;
            border-radius: 8px !important;
            font-size: 14px;
            font-weight: 500 !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            transition: border-color 120ms ease, background 120ms ease;
        }

        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button {
            color: white !important;
            background: var(--midnight) !important;
            border-color: var(--midnight) !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            color: var(--ink) !important;
            background: var(--paper) !important;
            border-color: var(--ink) !important;
        }

        .stButton > button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            color: white !important;
            background: var(--blue-dark) !important;
            border-color: var(--blue-dark) !important;
        }

        .stButton > button:disabled {
            color: #a3a3a3 !important;
            background: var(--paper) !important;
            border-color: var(--border) !important;
            box-shadow: none;
        }

        .section-heading {
            margin: 40px 0 14px;
            font-size: 24px;
            font-weight: 600;
            line-height: 1.33;
            letter-spacing: -0.02em;
        }

        .run-chip {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            margin-top: 24px;
            padding: 6px 10px;
            color: var(--ink);
            background: var(--mint);
            border-radius: 9999px;
            font-family: "JetBrains Mono", ui-monospace, monospace;
            font-size: 12px;
            font-weight: 500;
        }

        .run-chip::before {
            width: 7px;
            height: 7px;
            background: #16a34a;
            border-radius: 50%;
            content: "";
        }

        [data-testid="stDataFrame"] {
            overflow: hidden;
            background: var(--canvas);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: none;
        }

        [data-testid="stExpander"] {
            overflow: hidden;
            margin-top: 20px;
            background: var(--canvas);
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
        }

        [data-testid="stAlert"] { border-radius: 8px; }
        [data-testid="stCaptionContainer"] { color: var(--muted); }

        [data-baseweb="tag"] {
            background: #dbeafe !important;
            border-radius: 9999px !important;
        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding-top: 1.5rem; }
            .brand-bar { margin-bottom: 2.5rem; }
            .hero-copy { font-size: 15px; }
            div[data-testid="stForm"] { padding: 16px 14px 6px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand() -> None:
    st.markdown(
        """
        <div class="brand-bar">
            <span class="brand-mark">↔</span>
            <span class="brand-name">forus <span>stock</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


apply_design_system()


def authenticated() -> bool:
    if st.session_state.get("authenticated"):
        return True
    brand()
    st.markdown(
        """
        <div class="login-hero">
            <p class="eyebrow">Control de inventario</p>
            <h1 class="hero-title">Tu stock, siempre en sintonía.</h1>
            <p class="hero-copy">
                Compara el inventario de ERP y Shopify en un solo lugar,
                con resultados claros y listos para actuar.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", use_container_width=True)
    if submitted:
        auth = st.secrets["app_auth"]
        users = auth.get("users", {auth.get("username"): auth.get("password")})
        expected = users.get(username)
        if expected and hmac.compare_digest(str(password), str(expected)):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        st.error("Credenciales incorrectas")
    return False


if authenticated():
    brand()
    st.markdown(
        """
        <p class="eyebrow">Centro de conciliación</p>
        <h1 class="hero-title">ERP y Shopify, en perfecto balance.</h1>
        <p class="hero-copy">
            Elige los sitios que quieres revisar. Compararemos ambas fuentes y
            destacaremos las diferencias que necesitan tu atención.
        </p>
        """,
        unsafe_allow_html=True,
    )
    try:
        config = AppConfig.from_mapping(st.secrets)
    except (KeyError, ValueError) as exc:
        st.error(f"Configuración inválida: {exc}")
        st.stop()

    with st.container(border=True):
        st.markdown("### Prepara la revisión")
        st.caption("Selecciona una o más tiendas para comenzar la comparación.")
        sites = st.multiselect(
            "Sitios a conciliar",
            options=list(config.shopify_sites),
            default=list(config.shopify_sites),
        )

        if st.button(
            "Ejecutar conciliación",
            type="primary",
            disabled=not sites,
            use_container_width=True,
        ):
            with st.spinner("Consultando BigQuery y Shopify…"):
                try:
                    result = StockReconciliationService(config).run(
                        sites,
                        trigger="streamlit",
                        actor=st.session_state.get("username", "unknown"),
                    )
                except Exception as exc:  # noqa: BLE001 - límite de presentación
                    st.exception(exc)
                    st.stop()
            st.session_state["result"] = result

    if result := st.session_state.get("result"):
        st.markdown(
            f'<span class="run-chip">Corrida {result.run_id}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<h2 class="section-heading">Resumen de resultados</h2>',
            unsafe_allow_html=True,
        )
        st.dataframe(result.summary, use_container_width=True, hide_index=True)
        mostrar_todo = st.checkbox(
            "Mostrar todos los registros (sincronizados y desincronizados)"
        )
        titulo_detalle = "Detalle completo" if mostrar_todo else "Diferencias encontradas"
        st.markdown(
            f'<h2 class="section-heading">{titulo_detalle}</h2>',
            unsafe_allow_html=True,
        )
        if mostrar_todo:
            tabla = result.detail
        else:
            tabla = result.detail[
                result.detail["estado_sincronizacion"] != "SINCRONIZADO"
            ]
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar Excel",
            data=result.excel_bytes,
            file_name="desincronizacion_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        if result.warnings:
            with st.expander(f"Advertencias ({len(result.warnings)})"):
                st.write("\n".join(f"- {warning}" for warning in result.warnings))

    with st.expander("Diagnóstico ERP · solo lectura"):
        st.caption(
            "Consultas de conteo sobre las tablas configuradas en [bigquery], "
            "para verificar rápidamente qué hay realmente en BigQuery."
        )
        if st.button("Ejecutar diagnóstico"):
            with st.spinner("Consultando BigQuery…"):
                try:
                    diag = BigQuerySource(
                        config.bigquery, config.service_account
                    ).diagnostics()
                except Exception as exc:  # noqa: BLE001 - límite de presentación
                    st.exception(exc)
                    st.stop()
            st.write("Filas en `stock_table`:")
            st.dataframe(diag["stock_table_filas"], hide_index=True)
            st.write("Valores de `estado` en `warehouses_table`:")
            st.dataframe(diag["warehouses_estado"], hide_index=True)
            st.write(
                f"Valores de `{config.bigquery.warehouse_sites_site_column}` "
                "en `warehouse_sites_table`:"
            )
            st.dataframe(diag["sitios_disponibles"], hide_index=True)
            if "marcas_disponibles" in diag:
                st.write(
                    f"Valores de `{config.bigquery.product_master_brand_column}` "
                    "en `product_master_table`:"
                )
                st.dataframe(diag["marcas_disponibles"], hide_index=True)
