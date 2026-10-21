from __future__ import annotations

from pathlib import Path

import streamlit as st

from stock_sync import StockReconciliationService
from stock_sync.bigquery_source import BigQuerySource
from stock_sync.config import AppConfig

st.set_page_config(page_title="eOM", page_icon="📦", layout="wide")

LOGO_SVG = (Path(__file__).parent / "assets" / "eom-logo.svg").read_text(encoding="utf-8")


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
            --blue: #00269a;
            --blue-dark: #001e78;
            --cyan: #009ee2;
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
            margin-bottom: 4rem;
        }

        .brand-logo {
            display: block;
            width: 150px;
            line-height: 0;
        }

        .brand-logo svg { display: block; width: 100%; height: auto; }

        .brand-bar.centered {
            justify-content: center;
            margin: 4vh auto 18px;
            text-align: center;
        }

        .brand-bar.centered .brand-logo { width: 190px; }

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
            background: var(--cyan);
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

        .login-hero { max-width: 520px; margin: 0 auto 24px; text-align: center; }
        .login-hero .hero-title { font-size: clamp(30px, 5vw, 40px); }
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


def apply_dashboard_layout() -> None:
    """Switch the authenticated experience to the framed dashboard layout."""
    st.markdown(
        """
        <style>
        .stApp { background: #f3f4f6; background-image: none; }

        [data-testid="stHeader"] {
            background: transparent;
            border-bottom: 0;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: none;
            min-height: calc(100vh - 20px);
            margin: 10px 10px 10px 0;
            padding: 28px 32px 48px;
            background: #ffffff;
            border: 1px solid rgba(229, 231, 235, 0.9);
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }

        section[data-testid="stSidebar"] {
            width: 270px !important;
            min-width: 270px !important;
            margin: 10px;
            background: #ffffff;
            border: 1px solid rgba(229, 231, 235, 0.9);
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }

        section[data-testid="stSidebar"] > div {
            background: transparent;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 18px 12px;
        }

        .sidebar-brand {
            padding: 2px 10px 18px;
            border-bottom: 1px solid #f1f5f9;
        }

        .sidebar-brand .brand-logo {
            width: 112px;
            margin-bottom: 13px;
        }

        .sidebar-product {
            color: #0f172a;
            font-size: 14px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }

        .nav-section {
            margin: 22px 8px 7px;
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        section[data-testid="stSidebar"] .stButton {
            margin-bottom: 3px;
        }

        section[data-testid="stSidebar"] .stButton > button {
            min-height: 36px;
            justify-content: flex-start;
            padding: 7px 10px;
            color: #475569 !important;
            background: transparent !important;
            border: 0 !important;
            border-radius: 8px !important;
            box-shadow: none;
            font-size: 13px;
            font-weight: 500 !important;
            text-align: left;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            color: #0f172a !important;
            background: #f8fafc !important;
        }

        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            color: #3730a3 !important;
            background: #eef2ff !important;
            font-weight: 600 !important;
        }

        .dashboard-page-header {
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid #f1f5f9;
        }

        .dashboard-page-title {
            margin: 0;
            color: #0f172a;
            font-size: 22px;
            font-weight: 600;
            line-height: 1.3;
            letter-spacing: -0.025em;
        }

        .dashboard-page-copy {
            max-width: 680px;
            margin: 6px 0 0;
            color: #64748b;
            font-size: 13px;
            line-height: 1.5;
        }

        .empty-page {
            min-height: 62vh;
        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] {
                min-height: auto;
                margin: 6px;
                padding: 22px 18px 36px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand(*, centered: bool = False) -> None:
    alignment = " centered" if centered else ""
    st.markdown(
        f"""
        <div class="brand-bar{alignment}">
            <span class="brand-logo">{LOGO_SVG}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_navigation() -> str:
    pages = {
        "Overview": "◎  Overview",
        "Sincronización de Stock": "↻  Sincronización de Stock",
        "Reasignación de pedidos": "⇄  Reasignación de pedidos",
        "Analytics": "▥  Analytics",
        "Configuración": "⚙  Configuración",
    }
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Sincronización de Stock"

    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="brand-logo">{LOGO_SVG}</div>
            <div class="sidebar-product">Ecommerce Manager</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown('<p class="nav-section">General</p>', unsafe_allow_html=True)
    if st.sidebar.button(
        pages["Overview"],
        key="nav_overview",
        type="primary" if st.session_state["active_page"] == "Overview" else "tertiary",
        use_container_width=True,
    ):
        st.session_state["active_page"] = "Overview"
        st.rerun()

    st.sidebar.markdown(
        '<p class="nav-section">Operaciones ecommerce</p>',
        unsafe_allow_html=True,
    )
    for page, key in (
        ("Sincronización de Stock", "nav_stock"),
        ("Reasignación de pedidos", "nav_orders"),
    ):
        if st.sidebar.button(
            pages[page],
            key=key,
            type="primary" if st.session_state["active_page"] == page else "tertiary",
            use_container_width=True,
        ):
            st.session_state["active_page"] = page
            st.rerun()

    st.sidebar.markdown('<p class="nav-section">Insights</p>', unsafe_allow_html=True)
    if st.sidebar.button(
        pages["Analytics"],
        key="nav_analytics",
        type="primary" if st.session_state["active_page"] == "Analytics" else "tertiary",
        use_container_width=True,
    ):
        st.session_state["active_page"] = "Analytics"
        st.rerun()

    st.sidebar.markdown('<p class="nav-section">Settings</p>', unsafe_allow_html=True)
    if st.sidebar.button(
        pages["Configuración"],
        key="nav_settings",
        type="primary" if st.session_state["active_page"] == "Configuración" else "tertiary",
        use_container_width=True,
    ):
        st.session_state["active_page"] = "Configuración"
        st.rerun()

    st.sidebar.divider()
    user_name = (
        st.user.get("name")
        or st.user.get("preferred_username")
        or st.user.get("email")
        or "Usuario Microsoft"
    )
    st.sidebar.caption(f"Sesión iniciada como {user_name}")
    if st.sidebar.button(
        "Cerrar sesión",
        key="logout",
        use_container_width=True,
    ):
        st.logout()

    return str(st.session_state["active_page"])


def page_header(title: str, copy: str | None = None) -> None:
    description = f'<p class="dashboard-page-copy">{copy}</p>' if copy else ""
    st.markdown(
        f"""
        <header class="dashboard-page-header">
            <h1 class="dashboard-page-title">{title}</h1>
            {description}
        </header>
        """,
        unsafe_allow_html=True,
    )


apply_design_system()


def authenticated() -> bool:
    if st.user.is_logged_in:
        username = (
            st.user.get("preferred_username")
            or st.user.get("email")
            or st.user.get("name")
            or st.user.get("sub")
            or "unknown"
        )
        st.session_state["username"] = str(username)
        return True

    brand(centered=True)
    st.markdown(
        """
        <div class="login-hero">
            <h1 class="hero-title">Inicia sesión en eOM</h1>
            <p class="hero-copy">
                Accede con tu cuenta corporativa al centro de operaciones y
                conciliación de inventario.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "Ingresar con Microsoft",
        type="primary",
        use_container_width=True,
    ):
        st.login("microsoft")
    return False


def render_stock_sync() -> None:
    page_header(
        "Sincronización de Stock",
        "Compara el inventario del ERP con Shopify y revisa las diferencias que "
        "necesitan atención.",
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


def render_empty_page(title: str) -> None:
    page_header(title)
    st.markdown('<div class="empty-page"></div>', unsafe_allow_html=True)


if authenticated():
    apply_dashboard_layout()
    active_page = sidebar_navigation()
    if active_page == "Sincronización de Stock":
        render_stock_sync()
    else:
        render_empty_page(active_page)
