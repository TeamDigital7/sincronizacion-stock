from __future__ import annotations

import hmac

import streamlit as st

from stock_sync import StockReconciliationService
from stock_sync.bigquery_source import BigQuerySource
from stock_sync.config import AppConfig

st.set_page_config(page_title="Sincronización de stock", page_icon="📦", layout="wide")


def apply_design_system() -> None:
    """Apply the warm, editorial visual language used throughout the app."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap');

        :root {
            --flame: #fa5d00;
            --flame-dark: #d94f00;
            --glow: #fee3b5;
            --ink: #1d1e1c;
            --stone: #615f5c;
            --driftwood: #8e8b87;
            --bone: #c0bbb6;
            --mist: #e8ded3;
            --cream: #fff8f1;
            --paper: #ffffff;
            --warm-shadow: 6px 4px 24px rgba(250, 166, 0, 0.18);
        }

        html, body, [class*="css"] {
            font-family: "DM Sans", ui-sans-serif, system-ui, sans-serif;
            color: var(--ink);
            letter-spacing: 0.015em;
        }

        .stApp {
            background:
                radial-gradient(circle at 88% 7%, rgba(254, 227, 181, 0.65), transparent 25rem),
                var(--cream);
        }

        [data-testid="stHeader"] {
            background: rgba(255, 248, 241, 0.86);
            border-bottom: 1px solid rgba(227, 214, 197, 0.7);
            backdrop-filter: blur(14px);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1200px;
            padding-top: 3.5rem;
            padding-bottom: 5rem;
        }

        h1, h2, h3, p, label { color: var(--ink); }
        h1, h2, h3 { letter-spacing: 0.01em !important; }

        .brand-bar {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 3.5rem;
            font-size: 15px;
            font-weight: 700;
        }

        .brand-mark {
            display: grid;
            place-items: center;
            width: 38px;
            height: 38px;
            color: white;
            background: var(--flame);
            border-radius: 13px;
            box-shadow: 0 4px 14px rgba(250, 93, 0, 0.22);
            font-size: 20px;
        }

        .brand-name { font-size: 16px; }
        .brand-name span { color: var(--flame); }

        .eyebrow {
            margin: 0 0 10px;
            color: var(--flame);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .hero-title {
            max-width: 820px;
            margin: 0;
            color: var(--ink);
            font-family: "DM Serif Display", Georgia, serif;
            font-size: clamp(42px, 6vw, 72px);
            font-weight: 400;
            line-height: 1.04;
            letter-spacing: -0.025em;
        }

        .hero-copy {
            max-width: 680px;
            margin: 18px 0 34px;
            color: var(--stone);
            font-size: 18px;
            line-height: 1.55;
        }

        .login-hero { max-width: 620px; margin: 3vh auto 28px; text-align: center; }
        .login-hero .hero-title { font-size: clamp(42px, 7vw, 68px); }
        .login-hero .hero-copy { margin-left: auto; margin-right: auto; }

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(227, 214, 197, 0.85) !important;
            border-radius: 20px !important;
            box-shadow: var(--warm-shadow);
        }

        div[data-testid="stForm"] {
            max-width: 520px;
            margin: 0 auto;
            padding: 22px 24px 12px;
        }

        [data-testid="stTextInput"] input,
        [data-baseweb="select"] > div {
            min-height: 48px;
            color: var(--ink) !important;
            background: var(--paper) !important;
            border-color: var(--bone) !important;
            border-radius: 16px !important;
        }

        [data-testid="stTextInput"] input:focus {
            border-color: var(--flame) !important;
            box-shadow: 0 0 0 3px rgba(250, 93, 0, 0.14) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            min-height: 46px;
            padding: 0.7rem 1.35rem;
            border: 1px solid var(--flame) !important;
            border-radius: 16px !important;
            font-weight: 700 !important;
            letter-spacing: 0.015em;
            transition: transform 150ms ease, box-shadow 150ms ease, background 150ms ease;
        }

        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button {
            color: white !important;
            background: var(--flame) !important;
            box-shadow: 0 4px 12px rgba(250, 93, 0, 0.23);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            color: white !important;
            background: var(--flame-dark) !important;
            border-color: var(--flame-dark) !important;
            transform: translateY(-1px);
            box-shadow: 0 7px 16px rgba(250, 93, 0, 0.22);
        }

        .stButton > button:disabled {
            color: var(--driftwood) !important;
            background: #eee7df !important;
            border-color: #ddd2c7 !important;
            box-shadow: none;
        }

        .section-heading {
            margin: 48px 0 18px;
            font-size: 28px;
            font-weight: 650;
            line-height: 1.2;
        }

        .run-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 26px;
            padding: 8px 13px;
            color: var(--stone);
            background: rgba(255,255,255,.7);
            border: 1px solid var(--mist);
            border-radius: 999px;
            font-size: 13px;
        }

        .run-chip::before {
            width: 8px;
            height: 8px;
            background: var(--flame);
            border-radius: 50%;
            content: "";
        }

        [data-testid="stDataFrame"] {
            overflow: hidden;
            background: var(--paper);
            border: 1px solid var(--mist);
            border-radius: 20px;
            box-shadow: 3px 3px 18px rgba(227, 214, 197, 0.5);
        }

        [data-testid="stExpander"] {
            overflow: hidden;
            margin-top: 22px;
            background: rgba(255,255,255,.72);
            border: 1px solid var(--mist) !important;
            border-radius: 16px !important;
        }

        [data-testid="stAlert"] { border-radius: 16px; }
        [data-testid="stCaptionContainer"] { color: var(--driftwood); }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding-top: 2rem; }
            .brand-bar { margin-bottom: 2.5rem; }
            .hero-copy { font-size: 16px; }
            div[data-testid="stForm"] { padding: 18px 16px 8px; }
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
