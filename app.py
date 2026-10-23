from __future__ import annotations

from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from stock_sync import StockReconciliationService
from stock_sync.bigquery_source import BigQuerySource
from stock_sync.config import AppConfig

st.set_page_config(page_title="eOM · Forus", page_icon="📦", layout="wide")

LOGO_SVG = (
    (Path(__file__).parent / "assets" / "forus-logo.svg")
    .read_text(encoding="utf-8")
    .split("?>", 1)[-1]
)

# Paleta de marca: primario, profundos, acento cian y tinta.
PRIMARY = "#0511F2"
NAVY = "#030BA6"
COBALT = "#0339A6"
CYAN = "#049DD9"
INK = "#0D0D0D"
SITE_COLORS = (PRIMARY, CYAN, COBALT, NAVY, INK)

STATUS_LABELS = {
    "SINCRONIZADO": ("Sincronizado", CYAN),
    "DESINCRONIZADO": ("Desincronizado", PRIMARY),
    "NO_CREADO": ("No creado", INK),
}

NAVIGATION = (
    ("General", (("Overview", ":material/space_dashboard:"),)),
    (
        "Operaciones ecommerce",
        (
            ("Sincronización de Stock", ":material/sync_alt:"),
            ("Reasignación de pedidos", ":material/swap_horiz:"),
        ),
    ),
    ("Insights", (("Analytics", ":material/insights:"),)),
    ("Settings", (("Configuración", ":material/settings:"),)),
)

DETAIL_COLUMN_CONFIG = {
    "sitio": st.column_config.TextColumn("Sitio"),
    "id_producto": st.column_config.TextColumn("SKU ERP"),
    "variant_sku": st.column_config.TextColumn("SKU Shopify"),
    "talla": st.column_config.TextColumn("Talla"),
    "codigo_tienda": st.column_config.TextColumn("Bodega ERP"),
    "nombrebodega": st.column_config.TextColumn("Bodega"),
    "stock_erp_sitio": st.column_config.NumberColumn("Stock ERP", format="%d"),
    "stock_disponible_ecommerce": st.column_config.NumberColumn("Stock Shopify", format="%d"),
    "diferencia_stock": st.column_config.NumberColumn("Diferencia", format="%d"),
    "estado_sincronizacion": st.column_config.TextColumn("Estado"),
}
KEY_DETAIL_COLUMNS = list(DETAIL_COLUMN_CONFIG)


def apply_design_system() -> None:
    """Tokens y estilos base: lienzo gris claro, tarjetas blancas y acentos de la paleta."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --primary: {PRIMARY};
            --navy: {NAVY};
            --cobalt: {COBALT};
            --cyan: {CYAN};
            --ink: {INK};
            --primary-50: #EEF0FF;
            --primary-100: #DCE0FF;
            --cyan-50: #E6F5FB;
            --canvas: #F4F6FA;
            --surface: #FFFFFF;
            --border: #E4E7EE;
            --muted: #5B6275;
            --subtle: #8A90A2;
        }}

        html, body, [class*="css"], .stApp {{
            font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
            color: var(--ink);
        }}

        .stApp {{ background: var(--canvas); }}

        [data-testid="stHeader"] {{ background: transparent; }}

        [data-testid="stMainBlockContainer"] {{
            max-width: 1280px;
            padding: 1.5rem 2rem 4rem;
        }}

        /* Tarjetas */
        [data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stVerticalBlock"][class*="border"] {{
            background: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 2px rgba(13, 13, 13, 0.04);
        }}

        .card-title {{
            margin: 0;
            color: var(--ink);
            font-size: 15px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}

        .card-sub {{
            margin: 2px 0 12px;
            color: var(--subtle);
            font-size: 12px;
        }}

        /* Botones */
        .stButton > button, .stDownloadButton > button {{
            min-height: 38px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
        }}

        button[data-testid="stBaseButton-primary"] {{
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 1px 2px rgba(5, 17, 242, 0.25);
        }}

        button[data-testid="stBaseButton-primary"]:hover {{
            background: var(--navy);
            border-color: var(--navy);
        }}

        button[data-testid="stBaseButton-secondary"] {{
            background: var(--surface);
            border: 1px solid var(--border);
        }}

        /* Pestañas subrayadas */
        [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid var(--border);
        }}

        button[data-baseweb="tab"] {{
            padding: 10px 12px;
            color: var(--muted);
            font-weight: 500;
        }}

        button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--primary); }}
        [data-baseweb="tab-highlight"] {{ background-color: var(--primary); height: 2px; }}
        [data-baseweb="tab-border"] {{ display: none; }}

        [data-baseweb="tag"] {{
            color: var(--navy) !important;
            background: var(--primary-50) !important;
            border-radius: 6px !important;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }}

        [data-testid="stExpander"] details {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
        }}

        @media (max-width: 700px) {{
            [data-testid="stMainBlockContainer"] {{ padding: 1rem 1rem 3rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_dashboard_layout() -> None:
    """Barra lateral blanca con navegación tipo riel y barra superior de página."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            width: 248px !important;
            min-width: 248px !important;
            background: var(--surface);
            border-right: 1px solid var(--border);
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 4px 8px 16px;
        }

        .sidebar-brand { padding: 0 10px 18px; border-bottom: 1px solid var(--border); }
        .sidebar-brand .brand-logo { width: 104px; line-height: 0; }
        .sidebar-brand .brand-logo svg { width: 100%; height: auto; display: block; }

        .sidebar-product {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
            color: var(--ink);
            font-size: 13px;
            font-weight: 600;
        }

        .sidebar-product .product-badge {
            padding: 2px 7px;
            color: #fff;
            background: linear-gradient(135deg, var(--primary), var(--cyan));
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .nav-section {
            margin: 18px 10px 6px;
            color: var(--subtle);
            font-size: 10.5px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        section[data-testid="stSidebar"] .stButton { margin-bottom: 2px; }

        section[data-testid="stSidebar"] .stButton > button {
            justify-content: flex-start;
            min-height: 36px;
            padding: 6px 10px;
            color: var(--muted);
            background: transparent;
            border: 0;
            border-radius: 8px;
            box-shadow: none;
            font-size: 13.5px;
            font-weight: 500;
        }

        section[data-testid="stSidebar"] .stButton > button > div {
            justify-content: flex-start;
            width: 100%;
        }

        section[data-testid="stSidebar"] .stButton > button p { font-size: 13.5px; }

        section[data-testid="stSidebar"] .stButton > button:hover {
            color: var(--ink);
            background: var(--canvas);
        }

        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
            color: var(--primary);
            background: var(--primary-50);
            font-weight: 600;
        }

        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
            color: var(--primary);
            background: var(--primary-100);
        }

        .sidebar-user {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 6px 4px 8px;
        }

        .sidebar-user .who { min-width: 0; }
        .sidebar-user .name {
            overflow: hidden;
            color: var(--ink);
            font-size: 13px;
            font-weight: 600;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .sidebar-user .role { color: var(--subtle); font-size: 11.5px; }

        .avatar {
            display: inline-flex;
            flex: none;
            align-items: center;
            justify-content: center;
            width: 34px;
            height: 34px;
            color: var(--navy);
            background: var(--primary-50);
            border-radius: 50%;
            font-size: 12px;
            font-weight: 700;
        }

        .topbar {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            justify-content: space-between;
            margin: -0.5rem 0 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .topbar-title {
            margin: 0;
            padding: 0;
            color: var(--ink);
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .topbar-copy { margin: 4px 0 0; color: var(--muted); font-size: 13px; }

        .topbar-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

        .chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 10px;
            color: var(--muted);
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 500;
            white-space: nowrap;
        }

        .chip b { color: var(--ink); font-weight: 600; }
        .chip .dot { width: 7px; height: 7px; background: var(--cyan); border-radius: 50%; }

        /* KPIs */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin: 4px 0 16px;
        }

        .kpi {
            position: relative;
            overflow: hidden;
            padding: 16px 18px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
        }

        .kpi::before {
            position: absolute;
            inset: 0 auto 0 0;
            width: 3px;
            background: var(--accent);
            content: "";
        }

        .kpi-label { color: var(--muted); font-size: 12.5px; font-weight: 500; }

        .kpi-value {
            margin-top: 6px;
            color: var(--ink);
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.02em;
            font-variant-numeric: tabular-nums;
        }

        .kpi-foot {
            display: inline-block;
            margin-top: 8px;
            padding: 2px 8px;
            color: var(--accent);
            background: var(--accent-bg);
            border-radius: 6px;
            font-size: 11.5px;
            font-weight: 600;
        }

        /* Lista de sitios */
        .site-row {
            display: flex;
            gap: 12px;
            align-items: center;
            padding: 11px 2px;
            border-top: 1px solid var(--border);
        }

        .site-row:first-child { border-top: 0; }

        .tile {
            display: inline-flex;
            flex: none;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            color: #fff;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
        }

        .site-main { flex: 1; min-width: 0; }
        .site-name { color: var(--ink); font-size: 13.5px; font-weight: 600; }
        .site-sub { color: var(--subtle); font-size: 12px; }

        .bar {
            height: 6px;
            margin-top: 7px;
            overflow: hidden;
            background: var(--cyan-50);
            border-radius: 9999px;
        }

        .bar span {
            display: block;
            height: 100%;
            background: linear-gradient(90deg, var(--cyan), var(--primary));
            border-radius: 9999px;
        }

        .site-pct {
            min-width: 58px;
            color: var(--ink);
            font-size: 14px;
            font-weight: 700;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        /* Leyenda del donut */
        .legend-item { display: flex; gap: 10px; align-items: flex-start; margin: 14px 0; }
        .legend-dot { width: 10px; height: 10px; margin-top: 4px; border-radius: 50%; }
        .legend-label { color: var(--muted); font-size: 12.5px; }
        .legend-value {
            color: var(--ink);
            font-size: 15px;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }

        .empty-state { padding: 40px 16px; text-align: center; }

        .empty-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 56px;
            height: 56px;
            margin-bottom: 14px;
            background: linear-gradient(135deg, var(--primary-50), var(--cyan-50));
            border-radius: 16px;
        }

        .empty-icon span {
            width: 22px;
            height: 22px;
            background: linear-gradient(135deg, var(--primary), var(--cyan));
            border-radius: 7px;
        }

        .empty-title { color: var(--ink); font-size: 15px; font-weight: 600; }
        .empty-copy {
            max-width: 440px;
            line-height: 1.5;
            margin: 6px auto 0;
            color: var(--muted);
            font-size: 13px;
        }

        .warning-list { margin: 8px 0 0; padding-left: 18px; color: var(--muted); font-size: 13px; }
        .warning-list li { margin: 4px 0; }

        @media (max-width: 900px) {
            .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_login_layout() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] { max-width: 1120px; padding-top: 6vh; }

        .login-hero {
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 520px;
            overflow: hidden;
            padding: 36px;
            color: #fff;
            background: linear-gradient(150deg, var(--navy) 0%, var(--primary) 58%, var(--cyan) 130%);
            border-radius: 20px;
        }

        .login-hero::after {
            position: absolute;
            top: -90px;
            right: -90px;
            width: 280px;
            height: 280px;
            border: 44px solid rgba(4, 157, 217, 0.35);
            border-radius: 50%;
            content: "";
        }

        .login-hero .eyebrow {
            display: inline-block;
            padding: 5px 11px;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }

        .login-hero .hero-title {
            max-width: 420px;
            margin: 22px 0 12px;
            padding: 0;
            color: #fff;
            font-size: 34px;
            font-weight: 700;
            line-height: 1.12;
            letter-spacing: -0.03em;
        }

        .login-hero .hero-copy { max-width: 400px; margin: 0; color: rgba(255, 255, 255, 0.82); font-size: 15px; }

        .hero-points { margin: 26px 0 0; padding: 0; list-style: none; }
        .hero-points li {
            display: flex;
            gap: 10px;
            align-items: center;
            margin: 10px 0;
            color: rgba(255, 255, 255, 0.92);
            font-size: 14px;
        }
        .hero-points li::before {
            width: 8px;
            height: 8px;
            background: var(--cyan);
            border-radius: 2px;
            content: "";
        }

        .palette-strip {
            display: flex;
            height: 10px;
            overflow: hidden;
            border-radius: 9999px;
            box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.35);
        }
        .palette-strip span { flex: 1; }

        .login-panel { padding: 56px 8px 12px; }
        .login-panel .brand-logo { width: 150px; line-height: 0; }
        .login-panel .brand-logo svg { width: 100%; height: auto; display: block; }

        .login-panel .login-title {
            margin: 40px 0 8px;
            padding: 0;
            color: var(--ink);
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .login-panel .login-copy { margin: 0 0 28px; color: var(--muted); font-size: 14.5px; }

        .login-note { margin-top: 18px; color: var(--subtle); font-size: 12px; }

        @media (max-width: 700px) {
            .login-hero { min-height: auto; padding: 28px 22px; }
            .login-hero .hero-title { font-size: 27px; }
            .login-panel { padding-top: 16px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _initials(name: str) -> str:
    parts = [part for part in name.replace(".", " ").split() if part[:1].isalpha()]
    return "".join(part[0] for part in parts[:2]).upper() or "U"


def _site_label(site: str) -> str:
    return site.replace("_", " ").title()


def sidebar_navigation() -> str:
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Sincronización de Stock"
    active = st.session_state["active_page"]

    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="brand-logo">{LOGO_SVG}</div>
            <div class="sidebar-product">
                <span class="product-badge">eOM</span> Ecommerce Manager
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for section, pages in NAVIGATION:
        st.sidebar.markdown(f'<div class="nav-section">{section}</div>', unsafe_allow_html=True)
        for page, icon in pages:
            if st.sidebar.button(
                page,
                key=f"nav_{page}",
                icon=icon,
                type="primary" if active == page else "tertiary",
                use_container_width=True,
            ):
                st.session_state["active_page"] = page
                st.rerun()

    st.sidebar.divider()
    user_name = str(
        st.user.get("name")
        or st.user.get("preferred_username")
        or st.user.get("email")
        or "Usuario Microsoft"
    )
    email = str(st.user.get("email") or st.user.get("preferred_username") or "")
    st.sidebar.markdown(
        f"""
        <div class="sidebar-user">
            <span class="avatar">{escape(_initials(user_name))}</span>
            <div class="who">
                <div class="name">{escape(user_name)}</div>
                <div class="role">{escape(email)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button(
        "Cerrar sesión",
        key="logout",
        icon=":material/logout:",
        type="tertiary",
        use_container_width=True,
    ):
        st.logout()

    return str(st.session_state["active_page"])


def page_header(title: str, copy: str | None = None, chips: list[str] | None = None) -> None:
    description = f'<div class="topbar-copy">{escape(copy)}</div>' if copy else ""
    meta = "".join(chips or [])
    st.markdown(
        f"""
        <header class="topbar">
            <div><div class="topbar-title">{escape(title)}</div>{description}</div>
            <div class="topbar-meta">{meta}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _chip(label: str, value: str, *, dot: bool = False) -> str:
    marker = '<span class="dot"></span>' if dot else ""
    return f'<span class="chip">{marker}{escape(label)} <b>{escape(value)}</b></span>'


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

    apply_login_layout()
    hero, panel = st.columns([1.1, 1], gap="large")
    with hero:
        strip = "".join(
            f'<span style="background:{color}"></span>'
            for color in (PRIMARY, NAVY, COBALT, CYAN, INK)
        )
        st.markdown(
            f"""
            <section class="login-hero">
                <div>
                    <span class="eyebrow">eOM · Ecommerce Manager</span>
                    <div class="hero-title">Inventario ERP y Shopify, en una sola vista.</div>
                    <div class="hero-copy">Concilia el stock publicable de cada tienda y detecta a
                    tiempo las diferencias que afectan la venta online.</div>
                    <ul class="hero-points">
                        <li>Conciliación diaria por SKU, bodega y sitio</li>
                        <li>Resumen por marca y detalle exportable a Excel</li>
                        <li>Registro de cada corrida para auditoría</li>
                    </ul>
                </div>
                <div class="palette-strip">{strip}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with panel:
        st.markdown(
            f"""
            <div class="login-panel">
                <div class="brand-logo">{LOGO_SVG}</div>
                <div class="login-title">Inicia sesión</div>
                <div class="login-copy">Accede con tu cuenta corporativa al centro de operaciones
                y conciliación de inventario.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Ingresar con Microsoft",
            type="primary",
            icon=":material/login:",
            use_container_width=True,
        ):
            st.login("microsoft")
        st.markdown(
            '<div class="login-note">Acceso restringido a usuarios autorizados en '
            "Microsoft Entra ID.</div>",
            unsafe_allow_html=True,
        )
    return False


def _kpi(label: str, value: str, foot: str, accent: str, accent_bg: str) -> str:
    return (
        f'<div class="kpi" style="--accent:{accent};--accent-bg:{accent_bg}">'
        f'<div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div>'
        f'<span class="kpi-foot">{escape(foot)}</span></div>'
    )


def render_kpis(summary: pd.DataFrame) -> None:
    total = summary[summary["sitio"] == "GLOBAL"].iloc[0]
    compared = int(total["combinaciones_comparadas"])
    mismatched = int(total["combinaciones_desincronizadas"])
    synced = compared - mismatched
    pct_synced = 100 * synced / compared if compared else 0
    cards = [
        _kpi("Combinaciones comparadas", f"{compared:,}",
             f"{int(total['skus_unicos']):,} SKUs únicos", NAVY, "#E8E9FB"),
        _kpi("Sincronizadas", f"{synced:,}",
             f"{pct_synced:.1f}% del total", CYAN, "#E6F5FB"),
        _kpi("Desincronizadas", f"{mismatched:,}",
             f"{float(total['porcentaje_desincronizacion']):.1f}% del total",
             PRIMARY, "#EEF0FF"),
        _kpi("Diferencia absoluta", f"{float(total['diferencia_absoluta_unidades']):,.0f}",
             f"{int(total['no_creado']):,} SKUs no creados", COBALT, "#E6ECF6"),
    ]
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_sites(summary: pd.DataFrame) -> None:
    sites = summary[summary["sitio"] != "GLOBAL"].sort_values(
        "porcentaje_desincronizacion", ascending=False
    )
    rows = []
    for index, site in enumerate(sites.itertuples(index=False)):
        pct = float(site.porcentaje_desincronizacion)
        label = _site_label(str(site.sitio))
        rows.append(
            f"""
            <div class="site-row">
                <span class="tile" style="background:{SITE_COLORS[index % len(SITE_COLORS)]}">
                    {escape(label[:1])}
                </span>
                <div class="site-main">
                    <div class="site-name">{escape(label)}</div>
                    <div class="site-sub">{int(site.combinaciones_desincronizadas):,} de
                    {int(site.combinaciones_comparadas):,} combinaciones</div>
                    <div class="bar"><span style="width:{min(pct, 100):.1f}%"></span></div>
                </div>
                <div class="site-pct">{pct:.1f}%</div>
            </div>
            """.strip()
        )
    with st.container(border=True):
        st.markdown(
            '<div class="card-title">Desincronización por sitio</div>'
            '<div class="card-sub">Porcentaje de combinaciones SKU-bodega con diferencias</div>'
            + "".join(rows),
            unsafe_allow_html=True,
        )


def render_status_breakdown(detail: pd.DataFrame) -> None:
    counts = detail["estado_sincronizacion"].value_counts()
    data = pd.DataFrame(
        [
            {"estado": label, "combinaciones": int(counts.get(status, 0)), "color": color}
            for status, (label, color) in STATUS_LABELS.items()
        ]
    )
    with st.container(border=True):
        st.markdown(
            '<div class="card-title">Estado de sincronización</div>'
            '<div class="card-sub">Distribución de combinaciones comparadas</div>',
            unsafe_allow_html=True,
        )
        chart_col, legend_col = st.columns([1.1, 1], vertical_alignment="center")
        with chart_col:
            chart = (
                alt.Chart(data)
                .mark_arc(innerRadius=58, outerRadius=96, padAngle=0.01)
                .encode(
                    theta=alt.Theta("combinaciones:Q"),
                    color=alt.Color(
                        "estado:N",
                        scale=alt.Scale(domain=list(data["estado"]), range=list(data["color"])),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("estado:N", title="Estado"),
                        alt.Tooltip("combinaciones:Q", title="Combinaciones", format=","),
                    ],
                )
                .properties(height=210)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, use_container_width=True)
        with legend_col:
            total = max(int(data["combinaciones"].sum()), 1)
            st.markdown(
                "".join(
                    f'<div class="legend-item"><span class="legend-dot" '
                    f'style="background:{row.color}"></span><div>'
                    f'<div class="legend-label">{escape(row.estado)} · '
                    f"{100 * row.combinaciones / total:.1f}%</div>"
                    f'<div class="legend-value">{row.combinaciones:,}</div></div></div>'
                    for row in data.itertuples(index=False)
                ),
                unsafe_allow_html=True,
            )


def render_detail(result) -> None:
    detail = result.detail
    mismatches = detail[detail["estado_sincronizacion"] != "SINCRONIZADO"]
    with st.container(border=True):
        title_col, action_col = st.columns([3, 1], vertical_alignment="center")
        with title_col:
            st.markdown(
                '<div class="card-title">Detalle por SKU y bodega</div>'
                '<div class="card-sub">Ordenado por mayor diferencia absoluta</div>',
                unsafe_allow_html=True,
            )
        with action_col:
            st.download_button(
                "Descargar Excel",
                data=result.excel_bytes,
                file_name="desincronizacion_stock.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                use_container_width=True,
            )
        diff_tab, all_tab, warnings_tab = st.tabs(
            [
                f"Diferencias ({len(mismatches):,})",
                f"Detalle completo ({len(detail):,})",
                f"Advertencias ({len(result.warnings):,})",
            ]
        )
        with diff_tab:
            st.dataframe(
                mismatches,
                use_container_width=True,
                hide_index=True,
                column_config=DETAIL_COLUMN_CONFIG,
                column_order=KEY_DETAIL_COLUMNS
                + [c for c in detail.columns if c not in DETAIL_COLUMN_CONFIG],
            )
        with all_tab:
            st.dataframe(
                detail,
                use_container_width=True,
                hide_index=True,
                column_config=DETAIL_COLUMN_CONFIG,
                column_order=KEY_DETAIL_COLUMNS
                + [c for c in detail.columns if c not in DETAIL_COLUMN_CONFIG],
            )
        with warnings_tab:
            if result.warnings:
                shown = result.warnings[:500]
                items = "".join(f"<li>{escape(warning)}</li>" for warning in shown)
                st.markdown(f'<ul class="warning-list">{items}</ul>', unsafe_allow_html=True)
                if len(result.warnings) > len(shown):
                    st.caption(
                        f"Se muestran {len(shown)} de {len(result.warnings):,}; "
                        "el registro completo está en el JSON de auditoría."
                    )
            else:
                st.caption("La corrida no generó advertencias.")


def render_empty_state(title: str, copy: str) -> None:
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="empty-state">
                <div class="empty-icon"><span></span></div>
                <div class="empty-title">{escape(title)}</div>
                <div class="empty-copy">{escape(copy)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_stock_sync() -> None:
    result = st.session_state.get("result")
    chips = []
    if result:
        chips = [
            _chip("Corte ERP", result.expected_stock_date, dot=True),
            _chip("Corrida", result.run_id[:8]),
        ]
    page_header(
        "Sincronización de Stock",
        "Compara el stock publicable del ERP con el inventario disponible en Shopify.",
        chips,
    )
    try:
        config = AppConfig.from_mapping(st.secrets)
    except (KeyError, ValueError) as exc:
        st.error(f"Configuración inválida: {exc}")
        st.stop()

    with st.container(border=True):
        sites_col, action_col = st.columns([4, 1.2], vertical_alignment="bottom")
        with sites_col:
            sites = st.multiselect(
                "Sitios a conciliar",
                options=list(config.shopify_sites),
                default=list(config.shopify_sites),
                format_func=_site_label,
            )
        with action_col:
            run = st.button(
                "Ejecutar conciliación",
                type="primary",
                icon=":material/sync:",
                disabled=not sites,
                use_container_width=True,
            )
    if run:
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
        st.rerun()

    if result:
        render_kpis(result.summary)
        sites_col, status_col = st.columns([1.15, 1])
        with sites_col:
            render_sites(result.summary)
        with status_col:
            render_status_breakdown(result.detail)
        render_detail(result)
    else:
        render_empty_state(
            "Aún no hay resultados",
            "Selecciona uno o más sitios y ejecuta la conciliación para ver el resumen, "
            "la distribución por estado y el detalle por SKU.",
        )

    with st.expander("Diagnóstico ERP · solo lectura", icon=":material/troubleshoot:"):
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
    render_empty_state(
        "Próximamente",
        "Esta sección todavía no está disponible. Mientras tanto puedes usar "
        "Sincronización de Stock.",
    )


if authenticated():
    apply_dashboard_layout()
    active_page = sidebar_navigation()
    if active_page == "Sincronización de Stock":
        render_stock_sync()
    else:
        render_empty_page(active_page)
