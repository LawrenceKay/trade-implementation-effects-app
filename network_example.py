"""
network_example.py — Trade Partner Intelligence
================================================
Streamlit app with two analytical lenses:
  1. Trade agreement network centrality  (3D force-directed graph)
  2. Economic complexity                 (ECI dashboard)

Run:
    conda activate trade-app && streamlit run network_example.py
"""

import base64
import html as _html
import json
import math
import os
import statistics
from io import BytesIO
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="FaDalgo",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

COLOR_GREEN  = "#00A651"
COLOR_BLUE   = "#004B87"   # solid fills only (badges, active pills) — dark navy, white text on top
COLOR_CYAN   = "#4DD8E8"   # accent pulled from the backdrop image's particle wave;
                            # used wherever text needs to read against a dark glass panel
COLOR_ORANGE = "#F7941D"
COLOR_RED    = "#E8564B"   # brightened from the original #C0392B for legibility on dark panels
COLOR_TEAL   = "#85D6E9"   # sampled directly from the backdrop image's brightest dot pixels
                            # (avg of top 5% brightness); used for the country-selection and
                            # trade-partners boxes, which were previously brand green

PROJECT_ROOT = Path(__file__).parent


@st.cache_data(show_spinner=False)
def _load_backdrop_b64() -> str:
    """Down-scale and base64-encode the app's backdrop image, once per server process.

    The source file in assets/ is a huge 8750x12667px original (2.3MB) — a
    browser background only ever needs to be as wide as the viewport, so we
    resize before embedding it as a CSS data URI (avoids needing a separate
    static-file server, and keeps the page payload reasonable).
    """
    img_path = PROJECT_ROOT / "assets" / "visax-FpkeKQlgJtI-unsplash.jpg"
    img = Image.open(img_path)
    max_w = 1920
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, round(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=78)
    return base64.b64encode(buf.getvalue()).decode("ascii")


BACKDROP_B64 = _load_backdrop_b64()

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<style>
  :root {{
    --panel-bg: rgba(11, 17, 25, 0.70);
    --panel-bg-solid: #0e161f;
    --panel-border: {COLOR_TEAL};
    --divider: rgba(255,255,255,0.10);
    --text-primary: #EAF1F7;
    --text-secondary: #A9BAC8;
    --text-muted: #7C8FA0;
  }}

  /* ── Global ──────────────────────────────────────────────────────────────── */
  header[data-testid="stHeader"], [data-testid="stHeader"] {{ display:none !important; }}
  .stAppDeployButton {{ display:none !important; }}
  [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}

  /* Backdrop image — fixed, covers the viewport, dark scrim for legibility.
     background-attachment:fixed means whatever crop shows here is what's
     visible behind the page at every scroll depth, so the vertical position
     is tuned to keep the source photo's particle-wave feature in frame
     rather than cropping to its (mostly black) top band. */
  .stApp {{
    background-image:
      linear-gradient(180deg, rgba(3,6,10,.55) 0%, rgba(3,6,10,.30) 35%, rgba(3,6,10,.38) 70%, rgba(3,6,10,.70) 100%),
      url("data:image/jpeg;base64,{BACKDROP_B64}");
    background-size: cover;
    background-position: center 38%;
    background-attachment: fixed;
    background-repeat: no-repeat;
  }}
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewBlockContainer"], .main,
  .block-container {{ background-color: transparent !important; }}
  .block-container {{ padding-top:1.5rem; padding-bottom:2rem; }}
  .block-container, .block-container p, .block-container span,
  .block-container div, .block-container label {{ color: var(--text-primary); }}
  hr {{ border-color:{COLOR_TEAL} !important; }}

  /* ── Bordered containers (st.container(border=True)) — dark glass panels ──── */
  /* This Streamlit version has no data-testid="stVerticalBlockBorderWrapper" —
     border=True containers render as a plain [data-testid="stVerticalBlock"]
     with Streamlit's own default border. [height="420px"] scopes this to
     just the two bordered containers on the analysis page (both explicitly
     use that height) without also styling every other stVerticalBlock. */
  [data-testid="stVerticalBlock"][height="420px"] {{
    background: var(--panel-bg) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--panel-border) !important;
    border-radius: 10px !important;
  }}

  /* ── Sidebar (currently hidden via display:none above; kept in step with the
       dark theme in case it's re-enabled) ─────────────────────────────────── */
  [data-testid="stSidebar"],
  [data-testid="stSidebarContent"] {{ background-color: var(--panel-bg-solid) !important; }}

  /* Nav section buttons */
  section[data-testid="stSidebar"] .stButton > button {{
    text-align: left !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    padding: 10px 14px !important;
    border-radius: 6px !important;
    height: auto !important;
    min-height: 44px !important;
    white-space: normal !important;
    line-height: 1.4 !important;
    width: 100% !important;
    background-color: var(--panel-bg-solid) !important;
    color: {COLOR_GREEN} !important;
    border: 2px solid {COLOR_GREEN} !important;
    box-shadow: none !important;
    transition: all .15s !important;
  }}
  section[data-testid="stSidebar"] .stButton > button:hover {{
    background-color: {COLOR_GREEN}18 !important;
  }}

  /* Sidebar description text */
  .sidebar-desc {{
    font-size: 11.5px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 6px 0 16px 2px;
    padding-left: 2px;
  }}

  /* Selected country badge */
  .country-badge {{
    background: {COLOR_BLUE};
    color: white;
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 4px;
    text-align: center;
  }}
  .country-region {{
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
    margin-bottom: 10px;
  }}

  /* ── Home page ───────────────────────────────────────────────────────────── */
  /* !important on color: the generic .block-container div default-text rule
     earlier in this block outranks a bare single-class selector like .page-title
     on specificity, and would otherwise silently win regardless of source order. */
  .page-title  {{ font-size:48px; font-weight:700; color:{COLOR_TEAL} !important; margin-bottom:4px;
    text-shadow: 0 2px 14px rgba(0,0,0,.6); }}
  .page-sub    {{ font-size:15px; color:var(--text-primary); margin-bottom:28px; }}

  .concept-card {{
    border-top: 4px solid {COLOR_GREEN};
    background: var(--panel-bg);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-radius: 0 0 6px 6px;
    padding: 20px 18px 18px;
    height: 100%;
  }}
  .concept-card h3 {{
    font-size: 14px;
    font-weight: 700;
    color: {COLOR_CYAN};
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: .04em;
  }}
  .concept-card p {{
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.7;
  }}

  /* ── Metric tabs (centrality page) ───────────────────────────────────────── */
  .metric-tab-row {{ display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; }}
  .metric-tab {{
    padding: 6px 18px;
    border-radius: 20px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    border: 2px solid {COLOR_GREEN};
    background: var(--panel-bg-solid);
    color: {COLOR_GREEN};
    transition: all .15s;
  }}
  .metric-tab.active {{
    background: {COLOR_BLUE};
    color: white;
    border-color: {COLOR_BLUE};
  }}

  /* Main area metric buttons (non-sidebar) */
  .main-metric-btn > div > .stButton > button {{
    border-radius: 20px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    padding: 6px 18px !important;
    background: var(--panel-bg-solid) !important;
    color: {COLOR_GREEN} !important;
    border: 2px solid {COLOR_GREEN} !important;
    box-shadow: none !important;
    transition: all .15s !important;
  }}

  /* ── Primary button — green fill, white text ────────────────────────────── */
  [data-testid="baseButton-primary"] {{
    background-color: {COLOR_GREEN} !important;
    border-color:     {COLOR_GREEN} !important;
    color: white !important;
    font-weight: 700 !important;
  }}
  [data-testid="baseButton-primary"]:hover {{
    background-color: #008a44 !important;
    border-color:     #008a44 !important;
  }}
  /* Sidebar active nav buttons — beats generic sidebar rule on all properties */
  body section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {{
    background-color: {COLOR_GREEN} !important;
    border-color:     {COLOR_GREEN} !important;
    color: white !important;
    font-weight: 700 !important;
  }}
  body section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {{
    background-color: #008a44 !important;
    border-color:     #008a44 !important;
  }}
  /* Sidebar inactive nav buttons — dark glass with green border */
  body section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-secondary"] {{
    background-color: var(--panel-bg-solid) !important;
    border-color:     {COLOR_GREEN} !important;
    color: {COLOR_GREEN} !important;
    font-weight: 600 !important;
  }}
  body section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-secondary"]:hover {{
    background-color: {COLOR_GREEN}22 !important;
  }}

  /* ── Sidebar selectbox control — white text on green ────────────────────── */
  section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    border-color: {COLOR_GREEN} !important;
    border-width: 2px !important;
    border-radius: 6px !important;
    background-color: {COLOR_GREEN} !important;
  }}
  section[data-testid="stSidebar"] [data-baseweb="select"] > div * {{
    color: white !important;
    background-color: transparent !important;
  }}
  section[data-testid="stSidebar"] [data-baseweb="select"] svg {{
    fill: white !important;
  }}

  /* ── Dropdown menu portal — teal text on dark glass ───────────────────────── */
  /* Streamlit's BaseWeb select popover in this version carries no
     data-baseweb="menu" attribute — the real, stable hook is the testid on
     the virtualized option list. Kept the old data-baseweb="menu" selectors
     alongside it in case a future Streamlit version restores that markup. */
  body [data-testid="stSelectboxVirtualDropdown"],
  body [data-baseweb="menu"],
  [data-baseweb="popover"] [data-baseweb="menu"] {{
    background-color: var(--panel-bg-solid) !important;
    color: {COLOR_TEAL} !important;
  }}
  body [data-testid="stSelectboxVirtualDropdown"] li,
  body [data-testid="stSelectboxVirtualDropdown"] [role="option"],
  body [data-baseweb="menu"] li,
  body [data-baseweb="menu"] [role="option"],
  body [data-baseweb="menu"] ul > * {{
    background-color: var(--panel-bg-solid) !important;
    color: {COLOR_TEAL} !important;
  }}
  body [data-testid="stSelectboxVirtualDropdown"] li *,
  body [data-testid="stSelectboxVirtualDropdown"] [role="option"] *,
  body [data-baseweb="menu"] li *,
  body [data-baseweb="menu"] [role="option"] * {{
    color: {COLOR_TEAL} !important;
    background-color: transparent !important;
  }}
  body [data-testid="stSelectboxVirtualDropdown"] li:hover,
  body [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
  body [data-testid="stSelectboxVirtualDropdown"] [aria-selected="true"],
  body [data-baseweb="menu"] li:hover,
  body [data-baseweb="menu"] [role="option"]:hover,
  body [data-baseweb="menu"] [aria-selected="true"] {{
    background-color: {COLOR_TEAL} !important;
    color: #0B1C24 !important;
  }}
  body [data-testid="stSelectboxVirtualDropdown"] li:hover *,
  body [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover *,
  body [data-testid="stSelectboxVirtualDropdown"] [aria-selected="true"] *,
  body [data-baseweb="menu"] li:hover *,
  body [data-baseweb="menu"] [role="option"]:hover *,
  body [data-baseweb="menu"] [aria-selected="true"] * {{
    color: #0B1C24 !important;
    background-color: transparent !important;
  }}

  /* ── Analysis page country heading selectbox — green banner ─────────────── */
  /* Scoped to stSelectbox only — stMultiSelect (Assess a group) keeps normal   */
  /* sizing, since giant text made its dropdown hard to browse/add from.       */
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    font-size: 28px !important;
    font-weight: 700 !important;
    min-height: 56px !important;
    border-color: {COLOR_TEAL} !important;
    border-width: 2px !important;
    border-radius: 6px !important;
    background-color: {COLOR_TEAL} !important;
    padding-left: 14px !important;
  }}
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-value"],
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-value"] * {{
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #0B1C24 !important;
  }}
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-placeholder"] {{
    font-size: 28px !important;
    font-weight: 700 !important;
    color: rgba(11,28,36,0.65) !important;
  }}
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] input {{
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #0B1C24 !important;
  }}
  .block-container [data-testid="stSelectbox"] [data-baseweb="select"] svg {{
    width: 22px !important;
    height: 22px !important;
    fill: #0B1C24 !important;
  }}

  /* ── Assess a group multiselect — compact, easy to browse and add from ────── */
  .block-container [data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    min-height: 38px !important;
    border-color: {COLOR_TEAL} !important;
    background-color: var(--panel-bg) !important;
  }}
  .block-container [data-testid="stMultiSelect"] [data-baseweb="select"] input {{
    font-size: 14px !important;
    color: var(--text-primary) !important;
  }}

  /* ── Data note ───────────────────────────────────────────────────────────── */
  .data-note {{
    background: rgba(247,148,29,0.12); border-left:4px solid {COLOR_ORANGE};
    padding:.7rem 1rem; border-radius:4px; font-size:.82rem;
    color: var(--text-secondary); margin-top:1rem;
  }}

  /* ── Stat cards ──────────────────────────────────────────────────────────── */
  .stat-card {{
    background: var(--panel-bg);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-left: 4px solid {COLOR_CYAN};
    border-radius: 0 6px 6px 0;
    padding: 14px 18px;
    margin-bottom: 10px;
  }}
  .stat-card .stat-label {{ font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.05em; }}
  .stat-card .stat-value {{ font-size:28px; font-weight:700; color:{COLOR_CYAN}; line-height:1.2; }}
  .stat-card .stat-sub   {{ font-size:12px; color:var(--text-secondary); margin-top:2px; }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# METRICS (used on centrality page)
# ══════════════════════════════════════════════════════════════════════════════

METRICS = {
    "Agreements":      {"key": "n_agreements",       "label": "AG", "desc": "Total preferential trade agreements in force"},
    "Avg. provisions": {"key": "avg_enforceable",    "label": "AV", "desc": "Average legally enforceable provisions across all agreements"},
    "Max. provisions": {"key": "max_enforceable",    "label": "MX", "desc": "Maximum legally enforceable provisions in any single agreement"},
    "Partners":        {"key": "n_partners",          "label": "PT", "desc": "Number of partner countries covered by at least one agreement"},
    "Centrality":      {"key": "overall_centrality", "label": "CT", "desc": "Eigenvector centrality in FTA network — Fan et al. (2025)"},
    "Complexity":      {"key": "eci_score",           "label": "EC", "desc": "Economic Complexity Index (Harvard Atlas 2012)"},
}
METRIC_LABELS = list(METRICS.keys())

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

# Centrality + real agreement/provision-depth stats (from centrality_pipeline.py,
# sourced entirely from WB DTA 2.0 — see Section 5 of CLAUDE.md for provenance)
_centrality_index      = {}
_n_agreements_index    = {}
_n_partners_index      = {}
_avg_enforceable_index = {}
_max_enforceable_index = {}
DEPTH_MAX = 1.0  # dynamic max avg_enforceable, used to scale depth to a 0-100 score
CENTRALITY_LOADED = False
_cent_path = PROJECT_ROOT / "data" / "processed" / "centrality_scores.csv"
if _cent_path.exists():
    try:
        _cent_df = pd.read_csv(_cent_path).set_index("iso3")
        _centrality_index      = _cent_df["overall_centrality"].to_dict()
        _n_agreements_index    = _cent_df["n_agreements"].to_dict()
        _n_partners_index      = _cent_df["n_partners"].to_dict()
        _avg_enforceable_index = _cent_df["avg_enforceable"].to_dict()
        _max_enforceable_index = _cent_df["max_enforceable"].to_dict()
        _positive_avg_enf = [v for v in _avg_enforceable_index.values() if v and v > 0]
        DEPTH_MAX = max(_positive_avg_enf) if _positive_avg_enf else 1.0
        CENTRALITY_LOADED = True
    except Exception:
        pass

# FTA network graph for what-if centrality simulation
_FTA_GRAPH: nx.Graph | None = None
_FTA_MEAN_WEIGHT: float = 1.0
_edges_path = PROJECT_ROOT / "data" / "processed" / "fta_network_edges.csv"
if _edges_path.exists():
    try:
        _edges_df = pd.read_csv(_edges_path)
        _FTA_GRAPH = nx.Graph()
        for _, _er in _edges_df.iterrows():
            _FTA_GRAPH.add_edge(str(_er["iso1"]), str(_er["iso2"]), weight=float(_er["weight"]))
        _FTA_MEAN_WEIGHT = float(_edges_df["weight"].mean())
    except Exception:
        pass


def simulate_centrality(country_iso: str, new_partners: list[str]) -> float | None:
    """
    Returns the simulated eigenvector centrality score (0–100) for country_iso
    after adding hypothetical FTA edges to each country in new_partners.

    New edges are assigned the mean depth weight of the existing network,
    representing a typical new agreement. Returns None if the graph is unavailable
    or the computation fails.
    """
    if _FTA_GRAPH is None or not new_partners:
        return None

    G_sim = _FTA_GRAPH.copy()
    for partner in new_partners:
        if not G_sim.has_edge(country_iso, partner):
            G_sim.add_edge(country_iso, partner, weight=_FTA_MEAN_WEIGHT)

    try:
        cent = nx.eigenvector_centrality_numpy(G_sim, weight="weight")
    except Exception:
        try:
            cent = nx.eigenvector_centrality(G_sim, weight="weight", max_iter=1000, tol=1e-6)
        except Exception:
            return None

    vals = list(cent.values())
    if vals and min(vals) < 0:
        cent = {k: abs(v) for k, v in cent.items()}

    new_max = max(cent.values()) if cent else 1.0
    score = cent.get(country_iso, 0.0)
    return round(score / new_max * 100, 1) if new_max > 0 else None


def simulate_depth(country_iso: str, new_partners: list[str], depth_max: float = DEPTH_MAX) -> tuple[float, float] | None:
    """
    Returns (simulated_avg_enforceable, simulated_depth_pct2) for country_iso
    after hypothetically signing agreements with each country in new_partners.

    The depth of each new agreement is assumed to equal that partner's own
    avg_enforceable (from COUNTRY_DATA). Returns None if the selected country
    has no depth data or no new partners have depth data.
    """
    n_current  = COUNTRY_DATA.get(country_iso, {}).get("n_agreements")
    avg_current = COUNTRY_DATA.get(country_iso, {}).get("avg_enforceable")
    if n_current is None or avg_current is None or not new_partners:
        return None

    new_depths = [
        COUNTRY_DATA[p]["avg_enforceable"]
        for p in new_partners
        if p in COUNTRY_DATA and COUNTRY_DATA[p].get("avg_enforceable") is not None
    ]
    if not new_depths:
        return None

    sim_avg = (avg_current * n_current + sum(new_depths)) / (n_current + len(new_depths))
    sim_pct = round(min(sim_avg / depth_max * 100, 100), 1)
    return sim_avg, sim_pct


def compute_additionality(own_eci: float | None, partner_ecis: list[float]) -> float | None:
    """
    Returns the complexity additionality a country receives from its trade partners.

    Defined as: mean([own_eci] + [p for p in partner_ecis if p > own_eci]) - own_eci

    Only partners more complex than the country count — less-complex partners add nothing.
    Returns None if own_eci is unknown; 0.0 if no partners are more complex.
    """
    if own_eci is None:
        return None
    more_complex = [p for p in partner_ecis if p > own_eci]
    if not more_complex:
        return 0.0
    group_mean = (own_eci + sum(more_complex)) / (1 + len(more_complex))
    return round(group_mean - own_eci, 3)


# ECI scores (Harvard Atlas via CID GitHub, 2012)
_eci_index = {}
_eci_rank  = {}
ECI_LOADED = False
_eci_path  = PROJECT_ROOT / "data" / "processed" / "eci_scores.csv"
if _eci_path.exists():
    try:
        _eci_df   = pd.read_csv(_eci_path).set_index("iso3")
        _eci_index = _eci_df["eci_score"].to_dict()
        _eci_rank  = _eci_df["eci_rank"].to_dict()
        ECI_LOADED = True
    except Exception:
        pass

# FTA partner map and agreements list — built from WB DTA 2.0 via
# centrality_pipeline.py's load_wb_dta() / data/processed/agreements.csv
# (see CLAUDE.md Section 5, "Base network source mismatch")
PARTNER_MAP: dict[str, set] = {}
AGREEMENTS_MAP: dict[str, list] = {}   # iso3 → [{"name": str, "year": int|None}]
PAIR_AGREEMENTS: dict[str, list] = {}  # "iso3_a|iso3_b" (sorted) → [agreement_names]
_agreements_path = PROJECT_ROOT / "data" / "processed" / "agreements.csv"
if _agreements_path.exists():
    try:
        _agr_df = pd.read_csv(_agreements_path)
        # Partner map (deduplicated pairs)
        for _a, _b in zip(_agr_df["iso1"], _agr_df["iso2"]):
            PARTNER_MAP.setdefault(_a, set()).add(_b)
            PARTNER_MAP.setdefault(_b, set()).add(_a)
        # Agreements map — unique agreement names per country, sorted by year
        for _, _row in _agr_df.iterrows():
            _agr = str(_row["agreement"]).strip() if pd.notna(_row["agreement"]) else "Unknown"
            _yr  = int(_row["entry_year"]) if pd.notna(_row["entry_year"]) else None
            for _iso in [_row["iso1"], _row["iso2"]]:
                _seen = {d["name"] for d in AGREEMENTS_MAP.get(_iso, [])}
                if _agr not in _seen:
                    AGREEMENTS_MAP.setdefault(_iso, []).append({"name": _agr, "year": _yr})
        for _iso in AGREEMENTS_MAP:
            AGREEMENTS_MAP[_iso].sort(key=lambda d: d["year"] or 0)
        # Pair agreements — which agreements directly connect each country pair
        for _, _row in _agr_df.iterrows():
            _key = "|".join(sorted([_row["iso1"], _row["iso2"]]))
            _agr = str(_row["agreement"]).strip() if pd.notna(_row["agreement"]) else "Unknown"
            if _agr not in PAIR_AGREEMENTS.get(_key, []):
                PAIR_AGREEMENTS.setdefault(_key, []).append(_agr)
    except Exception:
        pass

# All unique FTA links for full-network display (deduplicated country pairs)
ALL_LINKS: list[dict] = []
if PARTNER_MAP:
    _seen_pairs: set = set()
    for _a, _partners in PARTNER_MAP.items():
        for _b in _partners:
            _pair = tuple(sorted([_a, _b]))
            if _pair not in _seen_pairs:
                _seen_pairs.add(_pair)
                ALL_LINKS.append({"source": _pair[0], "target": _pair[1]})

# ══════════════════════════════════════════════════════════════════════════════
# WB REGIONS
# ══════════════════════════════════════════════════════════════════════════════

WB_REGIONS = {
    "East Asia and Pacific":        "#2F8FDB",  # strong blue
    "Europe and Central Asia":      "#B07CE0",  # purple
    "Latin America and Caribbean":  "#F0813C",  # burnt orange
    "Middle East and North Africa": "#E0C23A",  # gold
    "North America":                "#6E93BE",  # steel blue — distinct from the brighter East Asia blue
    "South Asia":                   "#E056A0",  # magenta — was red, changed to avoid clashing with red status colours
    "Sub-Saharan Africa":           "#28B79A",  # teal
}
# Brightened from the original set (dark navy/dark teal/muted brick red) which
# was tuned for a white background — see "Consider how to recolour the app" /
# the backdrop-image styling task in CLAUDE.md Section 5.

# ══════════════════════════════════════════════════════════════════════════════
# COUNTRIES  (~180 WB members)
# ══════════════════════════════════════════════════════════════════════════════

COUNTRIES = [
    # North America
    {"iso3":"USA","name":"United States",        "lat": 39,"lon":-98,  "region":"North America",              "tier":4},
    {"iso3":"CAN","name":"Canada",               "lat": 60,"lon":-95,  "region":"North America",              "tier":4},
    # Europe & Central Asia
    {"iso3":"DEU","name":"Germany",              "lat": 51,"lon": 10,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"FRA","name":"France",               "lat": 46,"lon":  2,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"GBR","name":"United Kingdom",       "lat": 55,"lon": -3,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"ITA","name":"Italy",                "lat": 42,"lon": 12,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"ESP","name":"Spain",                "lat": 40,"lon": -4,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"NLD","name":"Netherlands",          "lat": 52,"lon":  5,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"BEL","name":"Belgium",              "lat": 50,"lon":  4,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"CHE","name":"Switzerland",          "lat": 47,"lon":  8,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"AUT","name":"Austria",              "lat": 47,"lon": 14,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"SWE","name":"Sweden",               "lat": 60,"lon": 15,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"NOR","name":"Norway",               "lat": 65,"lon": 15,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"DNK","name":"Denmark",              "lat": 56,"lon": 10,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"FIN","name":"Finland",              "lat": 64,"lon": 26,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"GRC","name":"Greece",               "lat": 38,"lon": 22,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"PRT","name":"Portugal",             "lat": 39,"lon": -8,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"CZE","name":"Czech Republic",       "lat": 50,"lon": 15,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"HUN","name":"Hungary",              "lat": 47,"lon": 19,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"ROU","name":"Romania",              "lat": 46,"lon": 25,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"BGR","name":"Bulgaria",             "lat": 43,"lon": 25,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"HRV","name":"Croatia",              "lat": 45,"lon": 16,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"SVK","name":"Slovakia",             "lat": 48,"lon": 19,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"SVN","name":"Slovenia",             "lat": 46,"lon": 15,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"LTU","name":"Lithuania",            "lat": 56,"lon": 24,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"LVA","name":"Latvia",               "lat": 57,"lon": 25,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"EST","name":"Estonia",              "lat": 59,"lon": 25,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"IRL","name":"Ireland",              "lat": 53,"lon": -8,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"LUX","name":"Luxembourg",           "lat": 49,"lon":  6,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"MLT","name":"Malta",                "lat": 36,"lon": 14,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"CYP","name":"Cyprus",               "lat": 35,"lon": 33,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"ISL","name":"Iceland",              "lat": 65,"lon":-18,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"LIE","name":"Liechtenstein",        "lat": 47,"lon":  9,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"POL","name":"Poland",               "lat": 52,"lon": 20,  "region":"Europe and Central Asia",      "tier":5},
    {"iso3":"TUR","name":"Turkey",               "lat": 38,"lon": 35,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"ALB","name":"Albania",              "lat": 41,"lon": 20,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"SRB","name":"Serbia",               "lat": 44,"lon": 21,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"BIH","name":"Bosnia & Herzegovina", "lat": 44,"lon": 17,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"MKD","name":"North Macedonia",      "lat": 41,"lon": 22,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"MNE","name":"Montenegro",           "lat": 43,"lon": 19,  "region":"Europe and Central Asia",      "tier":4},
    {"iso3":"UKR","name":"Ukraine",              "lat": 49,"lon": 32,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"BLR","name":"Belarus",              "lat": 53,"lon": 28,  "region":"Europe and Central Asia",      "tier":2},
    {"iso3":"MDA","name":"Moldova",              "lat": 47,"lon": 29,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"RUS","name":"Russia",               "lat": 60,"lon":100,  "region":"Europe and Central Asia",      "tier":2},
    {"iso3":"KAZ","name":"Kazakhstan",           "lat": 48,"lon": 68,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"UZB","name":"Uzbekistan",           "lat": 41,"lon": 64,  "region":"Europe and Central Asia",      "tier":2},
    {"iso3":"AZE","name":"Azerbaijan",           "lat": 40,"lon": 47,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"GEO","name":"Georgia",              "lat": 42,"lon": 43,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"ARM","name":"Armenia",              "lat": 40,"lon": 45,  "region":"Europe and Central Asia",      "tier":3},
    {"iso3":"TKM","name":"Turkmenistan",         "lat": 40,"lon": 58,  "region":"Europe and Central Asia",      "tier":1},
    {"iso3":"KGZ","name":"Kyrgyz Republic",      "lat": 41,"lon": 74,  "region":"Europe and Central Asia",      "tier":2},
    {"iso3":"TJK","name":"Tajikistan",           "lat": 39,"lon": 71,  "region":"Europe and Central Asia",      "tier":2},
    # East Asia & Pacific
    {"iso3":"CHN","name":"China",                "lat": 35,"lon":105,  "region":"East Asia and Pacific",        "tier":4},
    {"iso3":"JPN","name":"Japan",                "lat": 36,"lon":138,  "region":"East Asia and Pacific",        "tier":4},
    {"iso3":"KOR","name":"South Korea",          "lat": 37,"lon":127,  "region":"East Asia and Pacific",        "tier":4},
    {"iso3":"AUS","name":"Australia",            "lat":-27,"lon":133,  "region":"East Asia and Pacific",        "tier":5},
    {"iso3":"IDN","name":"Indonesia",            "lat": -5,"lon":120,  "region":"East Asia and Pacific",        "tier":3},
    {"iso3":"THA","name":"Thailand",             "lat": 15,"lon":101,  "region":"East Asia and Pacific",        "tier":3},
    {"iso3":"VNM","name":"Vietnam",              "lat": 16,"lon":108,  "region":"East Asia and Pacific",        "tier":3},
    {"iso3":"MYS","name":"Malaysia",             "lat":  3,"lon":113,  "region":"East Asia and Pacific",        "tier":4},
    {"iso3":"PHL","name":"Philippines",          "lat": 13,"lon":122,  "region":"East Asia and Pacific",        "tier":3},
    {"iso3":"NZL","name":"New Zealand",          "lat":-41,"lon":174,  "region":"East Asia and Pacific",        "tier":5},
    {"iso3":"SGP","name":"Singapore",            "lat":  1,"lon":104,  "region":"East Asia and Pacific",        "tier":5},
    {"iso3":"MMR","name":"Myanmar",              "lat": 19,"lon": 96,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"KHM","name":"Cambodia",             "lat": 12,"lon":105,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"LAO","name":"Lao PDR",              "lat": 18,"lon":103,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"MNG","name":"Mongolia",             "lat": 46,"lon":105,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"PNG","name":"Papua New Guinea",     "lat": -6,"lon":147,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"FJI","name":"Fiji",                 "lat":-18,"lon":178,  "region":"East Asia and Pacific",        "tier":2},
    {"iso3":"BRN","name":"Brunei",               "lat":  4,"lon":115,  "region":"East Asia and Pacific",        "tier":3},
    {"iso3":"TLS","name":"Timor-Leste",          "lat": -9,"lon":126,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"WSM","name":"Samoa",                "lat":-14,"lon":-172, "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"TON","name":"Tonga",                "lat":-21,"lon":-175, "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"VUT","name":"Vanuatu",              "lat":-16,"lon":167,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"SLB","name":"Solomon Islands",      "lat": -9,"lon":160,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"KIR","name":"Kiribati",             "lat":  1,"lon":173,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"MHL","name":"Marshall Islands",     "lat":  7,"lon":171,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"FSM","name":"Micronesia",           "lat":  6,"lon":158,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"PLW","name":"Palau",                "lat":  8,"lon":134,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"NRU","name":"Nauru",                "lat": -1,"lon":167,  "region":"East Asia and Pacific",        "tier":1},
    {"iso3":"TUV","name":"Tuvalu",               "lat": -8,"lon":179,  "region":"East Asia and Pacific",        "tier":1},
    # Latin America & Caribbean
    {"iso3":"BRA","name":"Brazil",               "lat":-15,"lon":-47,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"ARG","name":"Argentina",            "lat":-38,"lon":-63,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"MEX","name":"Mexico",               "lat": 24,"lon":-102, "region":"Latin America and Caribbean",  "tier":4},
    {"iso3":"COL","name":"Colombia",             "lat":  4,"lon":-73,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"CHL","name":"Chile",                "lat":-30,"lon":-71,  "region":"Latin America and Caribbean",  "tier":4},
    {"iso3":"PER","name":"Peru",                 "lat": -9,"lon":-75,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"VEN","name":"Venezuela",            "lat":  8,"lon":-66,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"ECU","name":"Ecuador",              "lat": -2,"lon":-78,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"BOL","name":"Bolivia",              "lat":-17,"lon":-65,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"PRY","name":"Paraguay",             "lat":-23,"lon":-58,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"URY","name":"Uruguay",              "lat":-33,"lon":-56,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"GTM","name":"Guatemala",            "lat": 15,"lon":-90,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"CUB","name":"Cuba",                 "lat": 22,"lon":-80,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"DOM","name":"Dominican Republic",   "lat": 19,"lon":-70,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"HND","name":"Honduras",             "lat": 15,"lon":-86,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"SLV","name":"El Salvador",          "lat": 14,"lon":-89,  "region":"Latin America and Caribbean",  "tier":3},
    {"iso3":"NIC","name":"Nicaragua",            "lat": 13,"lon":-85,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"CRI","name":"Costa Rica",           "lat": 10,"lon":-84,  "region":"Latin America and Caribbean",  "tier":4},
    {"iso3":"PAN","name":"Panama",               "lat":  9,"lon":-80,  "region":"Latin America and Caribbean",  "tier":4},
    {"iso3":"JAM","name":"Jamaica",              "lat": 18,"lon":-77,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"TTO","name":"Trinidad & Tobago",    "lat": 11,"lon":-61,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"GUY","name":"Guyana",               "lat":  5,"lon":-59,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"SUR","name":"Suriname",             "lat":  4,"lon":-56,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"BLZ","name":"Belize",               "lat": 17,"lon":-88,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"HTI","name":"Haiti",                "lat": 19,"lon":-73,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"BRB","name":"Barbados",             "lat": 13,"lon":-59,  "region":"Latin America and Caribbean",  "tier":2},
    {"iso3":"LCA","name":"Saint Lucia",          "lat": 14,"lon":-61,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"VCT","name":"St Vincent & Grenadines","lat":13,"lon":-61, "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"GRD","name":"Grenada",              "lat": 12,"lon":-62,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"ATG","name":"Antigua & Barbuda",    "lat": 17,"lon":-62,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"DMA","name":"Dominica",             "lat": 15,"lon":-61,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"KNA","name":"St Kitts & Nevis",     "lat": 17,"lon":-63,  "region":"Latin America and Caribbean",  "tier":1},
    {"iso3":"BHS","name":"Bahamas",              "lat": 25,"lon":-77,  "region":"Latin America and Caribbean",  "tier":2},
    # Middle East & North Africa
    {"iso3":"SAU","name":"Saudi Arabia",         "lat": 25,"lon": 45,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"ARE","name":"United Arab Emirates", "lat": 24,"lon": 54,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"IRN","name":"Iran",                 "lat": 32,"lon": 53,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"IRQ","name":"Iraq",                 "lat": 33,"lon": 44,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"ISR","name":"Israel",               "lat": 31,"lon": 35,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"JOR","name":"Jordan",               "lat": 31,"lon": 37,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"KWT","name":"Kuwait",               "lat": 29,"lon": 48,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"LBN","name":"Lebanon",              "lat": 34,"lon": 36,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"LBY","name":"Libya",                "lat": 27,"lon": 17,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"MAR","name":"Morocco",              "lat": 32,"lon": -6,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"OMN","name":"Oman",                 "lat": 22,"lon": 57,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"QAT","name":"Qatar",                "lat": 25,"lon": 51,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"SYR","name":"Syria",                "lat": 35,"lon": 38,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"TUN","name":"Tunisia",              "lat": 34,"lon":  9,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"YEM","name":"Yemen",                "lat": 16,"lon": 48,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"DZA","name":"Algeria",              "lat": 28,"lon":  3,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"EGY","name":"Egypt",                "lat": 27,"lon": 30,  "region":"Middle East and North Africa", "tier":3},
    {"iso3":"BHR","name":"Bahrain",              "lat": 26,"lon": 50,  "region":"Middle East and North Africa", "tier":2},
    {"iso3":"DJI","name":"Djibouti",             "lat": 12,"lon": 43,  "region":"Middle East and North Africa", "tier":1},
    {"iso3":"PSE","name":"West Bank & Gaza",     "lat": 32,"lon": 35,  "region":"Middle East and North Africa", "tier":1},
    # South Asia
    {"iso3":"IND","name":"India",                "lat": 21,"lon": 78,  "region":"South Asia",                 "tier":2},
    {"iso3":"PAK","name":"Pakistan",             "lat": 30,"lon": 69,  "region":"South Asia",                 "tier":2},
    {"iso3":"BGD","name":"Bangladesh",           "lat": 24,"lon": 90,  "region":"South Asia",                 "tier":2},
    {"iso3":"LKA","name":"Sri Lanka",            "lat":  8,"lon": 81,  "region":"South Asia",                 "tier":2},
    {"iso3":"NPL","name":"Nepal",                "lat": 28,"lon": 84,  "region":"South Asia",                 "tier":1},
    {"iso3":"AFG","name":"Afghanistan",          "lat": 33,"lon": 65,  "region":"South Asia",                 "tier":1},
    {"iso3":"BTN","name":"Bhutan",               "lat": 27,"lon": 90,  "region":"South Asia",                 "tier":1},
    {"iso3":"MDV","name":"Maldives",             "lat":  4,"lon": 73,  "region":"South Asia",                 "tier":1},
    # Sub-Saharan Africa
    {"iso3":"NGA","name":"Nigeria",              "lat": 10,"lon":  8,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"ZAF","name":"South Africa",         "lat":-30,"lon": 25,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"ETH","name":"Ethiopia",             "lat":  9,"lon": 40,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"TZA","name":"Tanzania",             "lat": -6,"lon": 35,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"KEN","name":"Kenya",                "lat":  0,"lon": 38,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"GHA","name":"Ghana",                "lat":  8,"lon": -2,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"AGO","name":"Angola",               "lat":-12,"lon": 18,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"MOZ","name":"Mozambique",           "lat":-18,"lon": 35,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"MDG","name":"Madagascar",           "lat":-20,"lon": 47,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"CMR","name":"Cameroon",             "lat":  5,"lon": 12,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"ZMB","name":"Zambia",               "lat":-14,"lon": 28,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"ZWE","name":"Zimbabwe",             "lat":-20,"lon": 30,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"MWI","name":"Malawi",               "lat":-13,"lon": 34,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SEN","name":"Senegal",              "lat": 14,"lon":-14,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"MLI","name":"Mali",                 "lat": 17,"lon": -4,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"BFA","name":"Burkina Faso",         "lat": 12,"lon": -2,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"GIN","name":"Guinea",               "lat": 11,"lon":-11,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"RWA","name":"Rwanda",               "lat": -2,"lon": 30,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"BEN","name":"Benin",                "lat": 10,"lon":  2,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"TCD","name":"Chad",                 "lat": 15,"lon": 19,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SSD","name":"South Sudan",          "lat":  7,"lon": 30,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SOM","name":"Somalia",              "lat":  6,"lon": 46,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"UGA","name":"Uganda",               "lat":  1,"lon": 32,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"CIV","name":"Côte d'Ivoire",        "lat":  7,"lon": -6,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"COG","name":"Republic of Congo",    "lat": -1,"lon": 15,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"COD","name":"DR Congo",             "lat": -4,"lon": 24,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"TGO","name":"Togo",                 "lat":  8,"lon":  1,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"ERI","name":"Eritrea",              "lat": 15,"lon": 39,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SLE","name":"Sierra Leone",         "lat":  8,"lon":-12,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"LBR","name":"Liberia",              "lat":  6,"lon":-10,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"MRT","name":"Mauritania",           "lat": 20,"lon":-12,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"NAM","name":"Namibia",              "lat":-22,"lon": 17,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"BWA","name":"Botswana",             "lat":-22,"lon": 24,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"LSO","name":"Lesotho",              "lat":-29,"lon": 28,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SWZ","name":"Eswatini",             "lat":-26,"lon": 31,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"GAB","name":"Gabon",                "lat": -1,"lon": 12,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"GNB","name":"Guinea-Bissau",        "lat": 12,"lon":-15,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"GNQ","name":"Equatorial Guinea",    "lat":  2,"lon": 10,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"CPV","name":"Cabo Verde",           "lat": 16,"lon":-24,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"COM","name":"Comoros",              "lat":-12,"lon": 44,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"MUS","name":"Mauritius",            "lat":-20,"lon": 57,  "region":"Sub-Saharan Africa",         "tier":3},
    {"iso3":"SYC","name":"Seychelles",           "lat": -5,"lon": 56,  "region":"Sub-Saharan Africa",         "tier":2},
    {"iso3":"STP","name":"São Tomé & Príncipe",  "lat":  1,"lon":  7,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"GMB","name":"Gambia",               "lat": 13,"lon":-16,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"NER","name":"Niger",                "lat": 17,"lon":  8,  "region":"Sub-Saharan Africa",         "tier":1},
    {"iso3":"SDN","name":"Sudan",                "lat": 15,"lon": 30,  "region":"Sub-Saharan Africa",         "tier":1},
]

COUNTRY_LOOKUP = {c["iso3"]: c for c in COUNTRIES}
NAME_TO_REGION_COLOR = {c["name"]: WB_REGIONS[c["region"]] for c in COUNTRIES}

# ══════════════════════════════════════════════════════════════════════════════
# COUNTRY DATA (real: n_agreements/n_partners/avg_enforceable/max_enforceable
# all sourced from WB DTA 2.0 — see centrality_pipeline.py and CLAUDE.md Section 5)
# ══════════════════════════════════════════════════════════════════════════════

COUNTRY_DATA = {}
for c in COUNTRIES:
    iso3 = c["iso3"]
    COUNTRY_DATA[iso3] = {
        "n_agreements":    int(_n_agreements_index.get(iso3, 0)),
        "avg_enforceable": round(float(_avg_enforceable_index.get(iso3, 0.0)), 1),
        "max_enforceable": round(float(_max_enforceable_index.get(iso3, 0.0)), 1),
        "n_partners":      int(_n_partners_index.get(iso3, 0)),
    }
    COUNTRY_DATA[iso3]["overall_centrality"] = round(_centrality_index.get(iso3, 0.0), 6)
    COUNTRY_DATA[iso3]["eci_score"] = round(_eci_index[iso3], 3) if iso3 in _eci_index else None
    COUNTRY_DATA[iso3]["eci_rank"]  = int(_eci_rank[iso3])       if iso3 in _eci_rank  else None

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

_sorted_countries = sorted([(c["name"], c["iso3"]) for c in COUNTRIES], key=lambda x: x[0])
_all_names  = [n for n, _ in _sorted_countries]
_all_iso3s  = [i for _, i in _sorted_countries]

if "view"           not in st.session_state: st.session_state["view"]           = "analysis"
if "country"        not in st.session_state: st.session_state["country"]        = None
if "metric"         not in st.session_state: st.session_state["metric"]         = "Centrality"
if "country_group"  not in st.session_state: st.session_state["country_group"]  = []
if "strategy_text"  not in st.session_state: st.session_state["strategy_text"]  = None

# JS: style selectbox control + watch for dropdown menu and apply green-on-white
components.html(f"""
<script>
(function() {{
  const GREEN = '{COLOR_GREEN}';
  const ACCENT = '{COLOR_TEAL}';  // country-selection / partners dropdown accent
  const doc = window.parent.document;

  // Inject a <style> tag directly into the parent document so it
  // reaches the BaseWeb menu portal regardless of Streamlit's CSS pipeline.
  if (!doc.getElementById('app-menu-style')) {{
    const s = doc.createElement('style');
    s.id = 'app-menu-style';
    s.textContent = `
      [data-baseweb="menu"] {{ background: #0e161f !important; }}
      [data-baseweb="menu"] * {{ color: ${{ACCENT}} !important; background: transparent !important; }}
      [data-baseweb="menu"] li,
      [data-baseweb="menu"] [role="option"] {{ background: #0e161f !important; color: ${{ACCENT}} !important; }}
      [data-baseweb="menu"] li:hover,
      [data-baseweb="menu"] [role="option"]:hover {{
        background: ${{ACCENT}} !important; color: #0B1C24 !important;
      }}
      [data-baseweb="menu"] li:hover *,
      [data-baseweb="menu"] [role="option"]:hover * {{ color: #0B1C24 !important; background: transparent !important; }}
    `;
    doc.head.appendChild(s);
  }}

  function styleSelectControl() {{
    try {{
      const sidebar = doc.querySelector('[data-testid="stSidebar"]');
      if (!sidebar) return;
      sidebar.querySelectorAll('[data-baseweb="select"]').forEach(sel => {{
        // Control box — green background, white text
        const ctrl = sel.querySelector(':scope > div');
        if (ctrl) {{
          ctrl.style.backgroundColor = GREEN;
          ctrl.style.borderColor     = GREEN;
          ctrl.style.borderWidth     = '2px';
        }}
        // Selected value text — white on green
        sel.querySelectorAll('span, div, input').forEach(el => {{
          el.style.color = 'white';
          el.style.backgroundColor = 'transparent';
        }});
        // Chevron svg — white
        sel.querySelectorAll('svg').forEach(s => s.style.fill = 'white');
      }});
    }} catch(e) {{}}
  }}

  function applyMenuStyles(menu) {{
    menu.style.setProperty('background', '#0e161f', 'important');
    menu.querySelectorAll('*').forEach(el => {{
      el.style.setProperty('background', 'transparent', 'important');
      el.style.setProperty('color', ACCENT, 'important');
    }});
  }}

  function styleMenu(menu) {{
    // Poll every 40ms while the menu is in the DOM — beats BaseWeb re-applying inline styles
    applyMenuStyles(menu);
    const iv = setInterval(() => {{
      if (!doc.contains(menu)) {{ clearInterval(iv); return; }}
      applyMenuStyles(menu);
    }}, 40);

    menu.querySelectorAll('li, [role="option"]').forEach(opt => {{
      opt.addEventListener('mouseenter', () => {{
        opt.style.setProperty('background', ACCENT, 'important');
        opt.querySelectorAll('*').forEach(el => {{
          el.style.setProperty('background', 'transparent', 'important');
          el.style.setProperty('color', '#0B1C24', 'important');
        }});
      }});
      opt.addEventListener('mouseleave', () => {{
        opt.style.setProperty('background', '#0e161f', 'important');
        opt.querySelectorAll('*').forEach(el => {{
          el.style.setProperty('background', 'transparent', 'important');
          el.style.setProperty('color', ACCENT, 'important');
        }});
      }});
    }});
  }}

  // Run on load
  styleSelectControl();

  // Watch for dropdown menus being inserted into the DOM
  const observer = new MutationObserver(mutations => {{
    styleSelectControl();
    mutations.forEach(m => m.addedNodes.forEach(node => {{
      if (node.nodeType !== 1) return;
      if (node.dataset && (node.dataset.baseweb === 'menu' || node.dataset.testid === 'stSelectboxVirtualDropdown')) styleMenu(node);
      node.querySelectorAll && node.querySelectorAll('[data-baseweb="menu"], [data-testid="stSelectboxVirtualDropdown"]').forEach(styleMenu);
    }}));
  }});
  observer.observe(doc.body, {{ childList: true, subtree: true }});
}})();
</script>
""", height=1)

# ══════════════════════════════════════════════════════════════════════════════
# SINGLE PAGE
# ══════════════════════════════════════════════════════════════════════════════

def _build_globe_html(sel, sel_partners, intro_mode=False,
                      all_eci=None, all_centrality=None, pair_agreements=None,
                      group_isos=None):
    """Return the HTML string for the 3D globe component."""
    all_eci        = all_eci        or {}
    all_centrality = all_centrality or {}
    pair_agreements = pair_agreements or {}
    group_isos     = set(group_isos or [])

    SPHERE_R   = 180
    metric_key = "overall_centrality"
    all_vals   = [COUNTRY_DATA[c["iso3"]][metric_key] or 0 for c in COUNTRIES]
    min_val, max_val = min(all_vals), max(all_vals)
    val_range  = max(max_val - min_val, 1)
    NODE_MIN, NODE_MAX = 1.0, 28.0

    nodes = []
    for c in COUNTRIES:
        iso3  = c["iso3"]
        raw   = COUNTRY_DATA[iso3][metric_key] or 0
        size  = NODE_MIN + ((raw - min_val) / val_range) * (NODE_MAX - NODE_MIN)
        lat_r = math.radians(c["lat"])
        lon_r = math.radians(c["lon"])
        nodes.append({
            "id":          iso3,
            "name":        c["name"],
            "region":      c["region"],
            "regionColor": WB_REGIONS[c["region"]],
            "fx":          round(SPHERE_R * math.cos(lat_r) * math.cos(lon_r), 2),
            "fy":          round(SPHERE_R * math.sin(lat_r), 2),
            "fz":          round(SPHERE_R * math.cos(lat_r) * math.sin(lon_r), 2),
            "val":         round(size * 2.5 if iso3 == sel else size, 2),
            "selected":    iso3 == sel,
            "data":        COUNTRY_DATA[iso3],
        })

    node_isos     = {c["iso3"] for c in COUNTRIES}
    links_to_show = [l for l in ALL_LINKS if l["source"] in node_isos and l["target"] in node_isos]
    graph_data    = {"nodes": nodes, "links": links_to_show}

    # Normalise centrality scores to 0-100 for display
    _cent_vals = [v for v in all_centrality.values() if v > 0]
    _cent_max  = max(_cent_vals) if _cent_vals else 1.0
    all_cent_pct = {k: round(v / _cent_max * 100, 1) for k, v in all_centrality.items()}

    container_h = 480 if intro_mode else 720
    graph_h     = 460 if intro_mode else 700

    legend_items_html = "".join(
        f'<span class="leg-item"><span class="leg-dot" style="background:{colour};"></span>{region}</span>'
        for region, colour in WB_REGIONS.items()
    )
    # Light orange — matches the groupNeighbours node colour below (countries
    # reached via an extended/second-degree link through the simulated group,
    # not a WB region, so kept out of WB_REGIONS itself).
    legend_items_html += (
        '<span class="leg-item"><span class="leg-dot" style="background:#fbd49c;">'
        '</span>Extended connections</span>'
    )
    legend_display = "none" if intro_mode else "flex"
    show_panel     = "false" if intro_mode else "true"

    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="https://unpkg.com/3d-force-graph@1/dist/3d-force-graph.min.js"></script>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:#05080c; font-family:Arial,sans-serif; }}
  #graph-container {{ width:100%; height:{container_h}px; position:relative;
    border:1px solid {COLOR_TEAL}; border-radius:4px; overflow:hidden; }}
  #left-panels {{
    position:absolute; top:12px; left:12px;
    display:flex; flex-direction:column; gap:10px;
    max-width:280px; pointer-events:none;
  }}
  #legend {{
    display:{legend_display}; flex-direction:column; gap:10px;
    background:rgba(14,22,31,0.85); border:1px solid {COLOR_TEAL};
    border-radius:4px;
    padding:14px 20px;
    font-size:17px; color:#EAF1F7; font-weight:500;
  }}
  #node-panel {{
    background:rgba(14,22,31,0.92);
    border:1px solid {COLOR_TEAL};
    border-left:4px solid {COLOR_GREEN};
    border-radius:0 4px 4px 0;
    box-shadow:0 2px 14px rgba(0,0,0,.4);
    padding:14px 18px; min-width:200px;
    font-size:12.5px; line-height:1.6; display:none;
    pointer-events:auto;
  }}
  #node-panel h3 {{ font-size:13px; font-weight:700; color:{COLOR_CYAN};
    text-transform:uppercase; letter-spacing:.04em; margin-bottom:10px; }}
  .np-row {{ display:flex; justify-content:space-between; gap:12px;
    border-bottom:1px solid rgba(255,255,255,0.10); padding:4px 0; }}
  .np-row span:first-child {{ color:#A9BAC8; }}
  .np-row span:last-child {{ font-weight:700; color:{COLOR_CYAN}; }}
  .np-agr {{ margin-top:8px; }}
  .np-agr-title {{ font-size:11px; font-weight:700; color:#7C8FA0;
    text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }}
  .np-agr-item {{ font-size:11.5px; color:#D7E2EA; padding:2px 0;
    border-bottom:1px solid rgba(255,255,255,0.06); }}
  .scene-nav-info {{ display:none !important; }}
  .leg-item {{ display:flex; align-items:center; gap:10px; white-space:nowrap; }}
  .leg-dot {{ width:16px; height:16px; border-radius:50%; flex-shrink:0; }}
</style></head><body>
<div id="graph-container">
  <div id="graph"></div>
  <div id="left-panels">
    <div id="legend">{legend_items_html}</div>
    <div id="node-panel"></div>
  </div>
</div>
<script>
const graphData      = {json.dumps(graph_data)};
const selectedIso    = {json.dumps(sel or "")};
const partnerIsos    = new Set({json.dumps(list(sel_partners))});
const groupIsos      = new Set({json.dumps(list(group_isos))});
const allEci         = {json.dumps({k: round(float(v), 3) for k, v in all_eci.items()})};
const allCentPct     = {json.dumps(all_cent_pct)};
const pairAgreements = {json.dumps(pair_agreements)};
const showPanel      = {show_panel};

function nodeId(n) {{ return typeof n === 'object' ? n.id : n; }}

// Pre-compute nodes that are neighbours of group countries (but not already
// the selected country, an existing partner, or a group country itself).
const groupNeighbours = new Set();
graphData.links.forEach(link => {{
  const s = nodeId(link.source), t = nodeId(link.target);
  if (groupIsos.has(s) && !groupIsos.has(t) && t !== selectedIso && !partnerIsos.has(t))
    groupNeighbours.add(t);
  if (groupIsos.has(t) && !groupIsos.has(s) && s !== selectedIso && !partnerIsos.has(s))
    groupNeighbours.add(s);
}});

function showNodePanel(node) {{
  if (!showPanel || !node || node.id === selectedIso) return;
  const panel = document.getElementById('node-panel');
  const eci  = allEci[node.id];
  const cent = allCentPct[node.id];
  const pairKey = [selectedIso, node.id].sort().join('|');
  const agrs = pairAgreements[pairKey] || [];

  const eciStr  = eci  !== undefined ? (eci  >= 0 ? '+' : '') + eci.toFixed(3)  : 'N/A';
  const centStr = cent !== undefined ? cent.toFixed(1) + ' / 100' : 'N/A';

  const agrHtml = agrs.length
    ? '<div class="np-agr"><div class="np-agr-title">Shared trade agreements</div>'
      + agrs.map(a => `<div class="np-agr-item">${{a}}</div>`).join('')
      + '</div>'
    : '<div class="np-agr"><div class="np-agr-title">Shared trade agreements</div>'
      + '<div style="font-size:11.5px;color:#7C8FA0;">No direct agreement</div></div>';

  panel.innerHTML =
    `<h3>${{node.name}}</h3>`
    + `<div class="np-row"><span>Economic complexity (ECI)</span><span>${{eciStr}}</span></div>`
    + `<div class="np-row"><span>Network centrality</span><span>${{centStr}}</span></div>`
    + agrHtml;
  panel.style.display = 'block';
  panel.style.borderLeftColor = node.regionColor || '{COLOR_GREEN}';
}}

const Graph = ForceGraph3D()(document.getElementById('graph'))
  .width(document.getElementById('graph-container').clientWidth)
  .height({graph_h})
  .backgroundColor('#05080c')
  .graphData(graphData)
  .nodeId('id').nodeLabel('name').nodeVal('val')
  .nodeOpacity(0.92).nodeResolution(16)
  .nodeColor(node => {{
    if (!selectedIso) return '#8a97a3';
    if (node.id === selectedIso) return '{COLOR_GREEN}';
    if (partnerIsos.has(node.id)) return node.regionColor;
    if (groupIsos.has(node.id)) return '{COLOR_ORANGE}';
    if (groupNeighbours.has(node.id)) return '#fbd49c';
    return '#8a97a3';
  }})
  .nodeVal(node => {{
    if (node.id === selectedIso) return node.val;
    if (groupIsos.has(node.id)) return node.val * 1.8;
    return node.val;
  }})
  .linkWidth(link => {{
    const s = nodeId(link.source), t = nodeId(link.target);
    const sIsSel   = s === selectedIso || t === selectedIso;
    const sIsGroup = groupIsos.has(s)  || groupIsos.has(t);
    if (!selectedIso) return 0.15;
    if (sIsSel && sIsGroup)   return 2.4;   // selected ↔ group country
    if (sIsSel)               return 1.8;   // selected ↔ FTA partner
    if (sIsGroup)             return 0.5;   // group country's own network
    return 0.1;
  }})
  .linkColor(link => {{
    const s = nodeId(link.source), t = nodeId(link.target);
    const sIsSel   = s === selectedIso || t === selectedIso;
    const sIsGroup = groupIsos.has(s)  || groupIsos.has(t);
    if (!selectedIso) return '#4a5865';
    if (sIsSel && sIsGroup) return '{COLOR_ORANGE}';  // selected ↔ group
    if (sIsSel)             return '{COLOR_GREEN}';   // selected ↔ FTA partner
    if (sIsGroup)           return '#f5c07a';        // group country's network
    return '#414c57';
  }})
  .onNodeClick(node => showNodePanel(node))
  .onNodeHover(node => {{ document.body.style.cursor = node ? 'pointer' : 'default'; }});

let angle = 0;
const timer = setInterval(() => {{
  Graph.cameraPosition({{ x:500*Math.sin(angle), z:500*Math.cos(angle) }});
  angle += 0.003;
}}, 20);
document.getElementById('graph').addEventListener('mousedown',
  () => clearInterval(timer), {{ once:true }});
</script></body></html>
"""


def render_home():
    sel          = st.session_state["country"]
    sel_partners = PARTNER_MAP.get(sel, set()) if sel else set()

    st.markdown(
        '<div class="page-title">FaDalgo</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:17px;color:#EAF1F7;margin-top:2px;text-shadow:0 1px 6px rgba(0,0,0,.5);">'
        "The higher a country's exposure to production complexity in its network of trade agreements, "
        'the more likely it is to learn how to make new things and grow.'
        '</div>'
        '<div style="font-size:17px;color:#EAF1F7;margin-top:10px;text-shadow:0 1px 6px rgba(0,0,0,.5);">'
        'Use FaDalgo to see the complexity exposure that countries gain from the trade agreements they '
        'have signed, and how they could gain more by signing extra ones with further countries and '
        'trading blocs.'
        '</div>'
        '<div style="font-size:17px;color:#EAF1F7;margin-top:10px;text-shadow:0 1px 6px rgba(0,0,0,.5);">'
        'FaDalgo is an implementation of Fan et al.\'s 2025 paper <a href="https://www.sciencedirect.com/'
        'science/article/pii/S1059056025000553#sec3" target="_blank" style="color:#4DD8E8;"><em>Does '
        'centrality within trade agreements networks matter to economic complexity? The conditioning '
        'effects of network structure</em></a>, which builds on the work of Cesar Hidalgo and colleagues '
        'into economic complexity. The Fan et al. paper shows that countries gain complexity exposure '
        'through being more central in their network of trade agreements, signing deeper agreements with '
        'partners that have more domestic complexity, and prioritising agreements with partners that are '
        'outside their immediate region and have dissimilar production profiles. Hausmann and Hidalgo '
        '(2009) show in <a href="https://www.pnas.org/doi/10.1073/pnas.0900943106" target="_blank" '
        'style="color:#4DD8E8;"><em>The building blocks of economic complexity</em></a> that greater '
        'complexity in an economy is significantly linked to economic growth.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    sel_name = COUNTRY_LOOKUP[sel]["name"] if sel in COUNTRY_LOOKUP else (sel or "")

    # ── Country group (read from session state) ───────────────────────────────
    _grp_names  = st.session_state.get("country_group", [])
    _grp_iso3s  = [_all_iso3s[_all_names.index(n)] for n in _grp_names if n in _all_names]
    _grp_ecis   = [_eci_index[i] for i in _grp_iso3s if i in _eci_index]
    _grp_avg_eci = sum(_grp_ecis) / len(_grp_ecis) if _grp_ecis else None
    _all_cent_b = [v for v in _centrality_index.values() if v > 0]
    _cmax_b     = max(_all_cent_b) if _all_cent_b else 1.0
    _grp_cents  = [round(_centrality_index[i] / _cmax_b * 100, 1)
                   for i in _grp_iso3s if i in _centrality_index]
    _grp_avg_cent = sum(_grp_cents) / len(_grp_cents) if _grp_cents else None
    _grp_already  = [i for i in _grp_iso3s if i in sel_partners]
    _grp_new      = [i for i in _grp_iso3s if i not in sel_partners]
    _sim_cent     = simulate_centrality(sel, _grp_new) if sel and _grp_new else None
    _sim_depth    = simulate_depth(sel, _grp_new) if sel and _grp_new else None

    # cent_pct2 and depth_pct2 computed early — needed by group summary panel and additionality multiplier
    _all_cent2_early = [v for v in _centrality_index.values() if v > 0]
    _cmax2_early     = max(_all_cent2_early) if _all_cent2_early else 1.0
    _centrality_sel  = _centrality_index.get(sel)
    cent_pct2        = round((_centrality_sel / _cmax2_early) * 100, 1) if _centrality_sel and _all_cent2_early else None
    _avg_depth_early = COUNTRY_DATA.get(sel, {}).get("avg_enforceable")
    depth_pct2       = round(min(_avg_depth_early / DEPTH_MAX * 100, 100), 1) if _avg_depth_early is not None else None

    # Complexity additionality — current partners, then simulated with new group partners
    # When centrality rises, the additionality is scaled by the centrality gain ratio:
    # a more central country can access more of the network's complexity, multiplying
    # the direct-exposure additionality by (sim_centrality / current_centrality).
    _own_eci_early      = _eci_index.get(sel) if sel else None
    _partner_ecis_early = [_eci_index[p] for p in sel_partners if p in _eci_index]
    _avg_peci_base      = compute_additionality(_own_eci_early, _partner_ecis_early)
    _grp_new_ecis       = [_eci_index[p] for p in _grp_new if p in _eci_index]
    if _grp_new:
        _raw_sim_add = compute_additionality(_own_eci_early, _partner_ecis_early + _grp_new_ecis)
        if (_raw_sim_add is not None and _sim_cent is not None
                and cent_pct2 is not None and cent_pct2 > 0):
            _cent_mult    = _sim_cent / cent_pct2
            _sim_exp_peci = round(_raw_sim_add * _cent_mult, 3)
        else:
            _sim_exp_peci = _raw_sim_add
    else:
        _sim_exp_peci = None

    # ── Typology calculations ─────────────────────────────────────────────────────
    _centrality    = _centrality_index.get(sel)
    _avg_depth     = COUNTRY_DATA.get(sel, {}).get("avg_enforceable")
    _partner_ecis  = [_eci_index[p] for p in sel_partners if p in _eci_index]
    _own_eci_calc  = _eci_index.get(sel) if sel else None
    _avg_peci      = compute_additionality(_own_eci_calc, _partner_ecis)

    if _grp_iso3s and _grp_new_ecis:
        _raw_eff = compute_additionality(_own_eci_calc, _partner_ecis + _grp_new_ecis)
        if (_raw_eff is not None and _sim_cent is not None
                and cent_pct2 is not None and cent_pct2 > 0):
            _eff_peci = round(_raw_eff * (_sim_cent / cent_pct2), 3)
        else:
            _eff_peci = _raw_eff
    else:
        _eff_peci = _avg_peci

    _all_cent = [v for v in _centrality_index.values() if v > 0]
    _cent_pct = round((_centrality / max(_all_cent)) * 100, 1) if _centrality and _all_cent else None
    _breadth_high = (_cent_pct >= 40) if _cent_pct is not None else (COUNTRY_DATA.get(sel, {}).get("n_agreements", 0) >= 10)

    _depth_pct = round(min(_avg_depth / DEPTH_MAX * 100, 100), 1) if _avg_depth is not None else None
    _depth_high = (_depth_pct >= 45) if _depth_pct is not None else False

    if _eff_peci is None:
        _cx_label = "unknown complexity additionality"
    elif _eff_peci >= 0.8:
        _cx_label = "high complexity additionality"
    elif _eff_peci >= 0.3:
        _cx_label = "moderate complexity additionality"
    else:
        _cx_label = "low complexity additionality"

    if _breadth_high and _depth_high:
        _type_label = "Deep integrator"
    elif _breadth_high and not _depth_high:
        _type_label = "Broadly connected, shallow commitments"
    elif not _breadth_high and _depth_high:
        _type_label = "Selective but deep integrator"
    else:
        _type_label = "Early-stage integrator"

    # ── Recommended partners — computed here (rather than down by the section
    # that displays them) so the analysis paragraph above can also name each
    # metric's top pick. ───────────────────────────────────────────────────
    _depth_cands, _cent_cands, _eci_cands = [], [], []
    if sel:
        _non_partners = [
            iso for iso in _all_iso3s
            if iso != sel and iso not in sel_partners
        ]
        _all_cent_r = [v for v in _centrality_index.values() if v > 0]
        _cmax_r     = max(_all_cent_r) if _all_cent_r else 1.0
        for _iso in _non_partners:
            _name = COUNTRY_LOOKUP.get(_iso, {}).get("name", _iso)
            _n_agr = len(AGREEMENTS_MAP.get(_iso, []))
            if _n_agr:
                _depth_cands.append((_name, _n_agr))
            _c = _centrality_index.get(_iso)
            if _c is not None:
                _cent_cands.append((_name, round(_c / _cmax_r * 100, 1)))
            _e = _eci_index.get(_iso)
            if _e is not None:
                _eci_cands.append((_name, _e))
        _depth_cands.sort(key=lambda x: x[1], reverse=True)
        _cent_cands.sort(key=lambda x: x[1],  reverse=True)
        _eci_cands.sort(key=lambda x: x[1],   reverse=True)

    _top_depth_name = _depth_cands[0][0] if _depth_cands else None
    _top_cent_name  = _cent_cands[0][0]  if _cent_cands  else None
    _top_eci_name   = _eci_cands[0][0]   if _eci_cands   else None

    # ── Full-width: selectbox + integration profile ───────────────────────────
    cur_idx = _all_iso3s.index(sel) if sel in _all_iso3s else None
    st.markdown(
        f'<p style="font-size:15px;font-weight:700;color:{COLOR_TEAL};'
        f'letter-spacing:.02em;margin:0 0 4px 2px;">'
        f'Country selection</p>',
        unsafe_allow_html=True,
    )
    _chosen_name = st.selectbox(
        "Country selection",
        options=_all_names,
        index=cur_idx,
        placeholder="Choose a country…",
        key="analysis_country",
        label_visibility="collapsed",
    )
    if _chosen_name:
        _new_iso3 = _all_iso3s[_all_names.index(_chosen_name)]
        if _new_iso3 != st.session_state["country"]:
            st.session_state["country"] = _new_iso3
            _new_partners = PARTNER_MAP.get(_new_iso3, set())
            _partner_names = sorted(
                COUNTRY_LOOKUP[_p]["name"] for _p in _new_partners if _p in COUNTRY_LOOKUP
            )
            st.session_state["country_group"] = _partner_names
            # The multiselect widget's own key overrides `default=` after its first
            # render, so it must be set directly for the box to actually show these.
            st.session_state["country_group_widget"] = _partner_names
            st.rerun()

    # Pre-compute summary values needed inside col_grp
    _sum_agrs   = AGREEMENTS_MAP.get(sel, [])
    _sum_eci    = _eci_index.get(sel)
    _sum_rank   = int(_eci_rank[sel]) if sel in _eci_rank else None
    _sum_total  = len(_eci_index)
    _all_cent2b = [v for v in _centrality_index.values() if v > 0]
    _cmax2b     = max(_all_cent2b) if _all_cent2b else 1.0
    _sum_cent   = round((_centrality_index.get(sel, 0) / _cmax2b) * 100, 1) if sel and _centrality_index.get(sel) else None

    # ── Analysis + current trade agreement partners (equal columns) ──────────
    col_analysis, col_grp = st.columns(2, gap="small")

    with col_analysis:
        with st.container(border=True, height=420):
            if sel:
                _n_agrs = len(_sum_agrs)
                _agr_s  = "" if _n_agrs == 1 else "s"

                # Depth qualifier
                if depth_pct2 is None:
                    _depth_qual = ""
                elif depth_pct2 >= 60:
                    _depth_qual = ", mostly of high agreement depth"
                elif depth_pct2 >= 30:
                    _depth_qual = ", mostly of moderate agreement depth"
                else:
                    _depth_qual = ", mostly of low agreement depth"

                # Centrality qualifier
                if _sum_cent is None:
                    _cent_qual = "Its centrality in the global network of trade agreements is not available."
                elif _sum_cent >= 60:
                    _cent_qual = f"It has high centrality in the global network of trade agreements, ranking among the most connected countries."
                elif _sum_cent >= 25:
                    _cent_qual = f"It has moderate centrality in the global network of trade agreements, comparable to mid-tier trading nations."
                else:
                    _cent_qual = f"It has low centrality in its network of trade agreements, compared to leading countries."

                # Complexity additionality qualifier
                if _avg_peci is None:
                    _peci_qual = "Complexity additionality data is not available."
                elif _avg_peci == 0.0:
                    _peci_qual = f"None of {sel_name}'s current trade partners are more economically complex, so existing agreements provide no complexity additionality."
                elif _avg_peci >= 0.8:
                    _peci_qual = f"Exposure to more complex trade partners provides high complexity additionality (score: {_avg_peci:.2f}), with strong potential for knowledge transfer and upgrading."
                elif _avg_peci >= 0.3:
                    _peci_qual = f"Exposure to more complex trade partners provides moderate complexity additionality (score: {_avg_peci:.2f})."
                else:
                    _peci_qual = f"Exposure to more complex trade partners provides limited complexity additionality (score: {_avg_peci:.2f})."

                _agr_sent  = f"{sel_name} has {_n_agrs} FTA{_agr_s} on record{_depth_qual}."
                _cent_sent = _cent_qual
                _peci_sent = _peci_qual
                _type_sent = f"This makes {sel_name} a {_type_label.lower()}, with {_cx_label}."

                def _red(name):
                    return (
                        f'<span style="color:{COLOR_RED};font-weight:700;">'
                        f'{_html.escape(name)}</span>'
                    )

                _reco_sent_parts = []
                if _top_depth_name:
                    _reco_sent_parts.append(
                        f"If {_html.escape(sel_name)} wanted to make deeper additional agreements, "
                        f"it should consider {_red(_top_depth_name)}."
                    )
                if _top_cent_name:
                    _reco_sent_parts.append(
                        f"For network centrality, {_red(_top_cent_name)} would be the strongest option."
                    )
                if _top_eci_name:
                    _reco_sent_parts.append(
                        f"For economic complexity, {_red(_top_eci_name)} would be the strongest option."
                    )
                # Built from already-escaped pieces plus literal <span> tags — do
                # NOT run this back through _html.escape() below, that would
                # neuter the span tags into visible text instead of red styling.
                _reco_sent = " ".join(_reco_sent_parts)

                st.markdown(
                    f'<div style="font-size:15px;font-weight:700;color:{COLOR_CYAN};'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">'
                    f'Analysis of current trade agreements position</div>'
                    f'<div style="font-size:17px;color:#EAF1F7;line-height:1.8;">'
                    f'{_html.escape(_agr_sent)} '
                    f'{_html.escape(_cent_sent)} '
                    f'{_html.escape(_peci_sent)} '
                    f'{_html.escape(_type_sent)} '
                    f'{_reco_sent}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="color:#7C8FA0;font-size:12px;">'
                    f'Select a country to see its analysis.</div>',
                    unsafe_allow_html=True,
                )

    with col_grp:
        with st.container(border=True, height=420):
            st.markdown(
                f'<div style="font-size:15px;font-weight:700;color:{COLOR_CYAN};'
                f'letter-spacing:.02em;margin:0 0 4px 2px;">'
                f'Trade agreements</div>',
                unsafe_allow_html=True,
            )
            _grp_widget = st.multiselect(
                "Trade agreements",
                options=_all_names,
                default=st.session_state["country_group"],
                placeholder="Select additional countries to sign trade agreements with",
                key="country_group_widget",
                label_visibility="collapsed",
            )
            if _grp_widget != st.session_state["country_group"]:
                st.session_state["country_group"] = _grp_widget
                st.session_state["strategy_text"] = None
                st.rerun()

            # Colour the selected-country tags inside the multiselect by geographic
            # region, matching the region colours used next to the globe.
            _region_colors_json = json.dumps(NAME_TO_REGION_COLOR)
            components.html(f"""
<script>
(function() {{
  const REGION_COLORS = {_region_colors_json};
  const doc = window.parent.document;

  function styleTags() {{
    doc.querySelectorAll('[data-baseweb="tag"]').forEach(tag => {{
      const textEl = tag.querySelector('span') || tag;
      const text = (textEl.textContent || '').trim();
      const color = REGION_COLORS[text];
      if (color) {{
        tag.style.setProperty('background-color', color, 'important');
        tag.style.setProperty('border-color', color, 'important');
        tag.querySelectorAll('*').forEach(el => {{
          el.style.setProperty('color', 'white', 'important');
        }});
      }}
    }});
  }}

  styleTags();
  const observer = new MutationObserver(styleTags);
  observer.observe(doc.body, {{ childList: true, subtree: true }});
}})();
</script>
""", height=1)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Globe (full width) ────────────────────────────────────────────────────
    # height must match _build_globe_html's container_h (720 for non-intro
    # mode) — a shorter iframe clips the bottom of #graph-container, hiding
    # its bottom border.
    components.html(
        _build_globe_html(sel=sel, sel_partners=sel_partners, intro_mode=False,
                          all_eci=_eci_index, all_centrality=_centrality_index,
                          pair_agreements=PAIR_AGREEMENTS,
                          group_isos=_grp_new),
        height=720,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    agreements = AGREEMENTS_MAP.get(sel, [])

    # ── Score cards — 5 across, full width below globe ────────────────────
    own_eci    = _eci_index.get(sel)
    own_rank   = int(_eci_rank[sel]) if sel in _eci_rank else None
    total_eci  = len(_eci_index)
    centrality = _centrality_index.get(sel)
    avg_depth  = COUNTRY_DATA.get(sel, {}).get("avg_enforceable")
    has_dta_coverage = bool(avg_depth)  # False for countries with no WB DTA 2.0 agreement coverage

    _all_cent2 = [v for v in _centrality_index.values() if v > 0]
    _cmax2     = max(_all_cent2) if _all_cent2 else 1.0
    cent_pct2  = round((centrality / _cmax2) * 100, 1) if centrality and _all_cent2 else None
    cc = COLOR_GREEN if cent_pct2 and cent_pct2 >= 60 else (COLOR_ORANGE if cent_pct2 and cent_pct2 >= 25 else COLOR_RED)

    depth_pct2 = round(min(avg_depth / DEPTH_MAX * 100, 100), 1) if avg_depth is not None else None
    dc = COLOR_GREEN if depth_pct2 and depth_pct2 >= 60 else (COLOR_ORANGE if depth_pct2 and depth_pct2 >= 30 else COLOR_RED)

    ec = COLOR_GREEN if own_eci and own_eci > 0.5 else (COLOR_ORANGE if own_eci and own_eci > -0.5 else COLOR_RED)
    pc = COLOR_GREEN if _avg_peci is not None and _avg_peci >= 0.8 else (COLOR_ORANGE if _avg_peci is not None and _avg_peci >= 0.3 else COLOR_RED)

    # ── When a group is selected, override displayed card values ──────────
    _grp_mode = bool(_grp_iso3s)
    if _grp_mode:
        if _sim_cent is not None:
            _delta = round(_sim_cent - (cent_pct2 or 0), 1)
            _delta_str = f"+{_delta}" if _delta >= 0 else str(_delta)
            _disp_cent_val = f"{_sim_cent} / 100"
            _disp_cent_note = f"simulated centrality · {_delta_str} vs current · assuming avg depth"
        elif cent_pct2 is not None:
            _disp_cent_val = f"{cent_pct2} / 100"
            _disp_cent_note = "current centrality · no new partners to simulate"
        else:
            _disp_cent_val = "N/A"
            _disp_cent_note = "centrality unavailable"
        _cc2 = (COLOR_GREEN if _sim_cent and _sim_cent >= 60 else
                (COLOR_ORANGE if _sim_cent and _sim_cent >= 25 else
                 (COLOR_GREEN if cent_pct2 and cent_pct2 >= 60 else
                  (COLOR_ORANGE if cent_pct2 and cent_pct2 >= 25 else COLOR_RED))))
        if _sim_depth is not None:
            _sim_depth_avg, _sim_depth_pct = _sim_depth
            _ddelta = round(_sim_depth_pct - (depth_pct2 or 0), 1)
            _ddelta_str = f"+{_ddelta}" if _ddelta >= 0 else str(_ddelta)
            _disp_depth_val = f"{_sim_depth_pct} / 100"
            _disp_depth_note = f"simulated depth · {_ddelta_str} vs current · partners' avg depth"
            dc = (COLOR_GREEN if _sim_depth_pct >= 60 else
                  (COLOR_ORANGE if _sim_depth_pct >= 30 else COLOR_RED))
        elif depth_pct2 is not None:
            _disp_depth_val = f"{depth_pct2} / 100"
            _disp_depth_note = "current depth · no new partners to simulate"
        else:
            _disp_depth_val = "N/A"
            _disp_depth_note = "depth unavailable"
        if _sim_exp_peci is not None:
            _base_for_delta = _avg_peci_base if _avg_peci_base is not None else 0.0
            _exp_delta = round(_sim_exp_peci - _base_for_delta, 2)
            _exp_delta_str = f"+{_exp_delta:.2f}" if _exp_delta >= 0 else f"{_exp_delta:.2f}"
            _disp_exp_val  = f"{_sim_exp_peci:.2f}"
            _pc2 = (COLOR_GREEN if _sim_exp_peci >= 0.8 else
                    (COLOR_ORANGE if _sim_exp_peci >= 0.3 else COLOR_RED))
            _cent_mult_disp = (round(_sim_cent / cent_pct2, 2)
                               if _sim_cent is not None and cent_pct2 and cent_pct2 > 0 else 1.0)
            _disp_exp_note = f"simulated additionality · {_exp_delta_str} vs current · centrality multiplier ×{_cent_mult_disp:.2f}"
        elif _avg_peci_base is not None:
            _disp_exp_val  = f"{_avg_peci_base:.2f}"
            _pc2 = (COLOR_GREEN if _avg_peci_base >= 0.8 else
                    (COLOR_ORANGE if _avg_peci_base >= 0.3 else COLOR_RED))
            _disp_exp_note = "current additionality · no new partners to simulate"
        else:
            _disp_exp_val  = "N/A"
            _pc2 = COLOR_RED
            _disp_exp_note = "additionality unavailable"
    else:
        _disp_cent_val = f"{cent_pct2} / 100" if cent_pct2 is not None else "N/A"
        _cc2 = cc
        _disp_cent_note = (
            "hover for detail · % of max eigenvector centrality" if sel
            else "select a country above"
        )
        _disp_depth_val = f"{depth_pct2} / 100" if depth_pct2 is not None else "N/A"
        _disp_depth_note = (
            "hover for detail · " + ("WB DTA 2.0" if has_dta_coverage else "no WB DTA 2.0 match") if sel
            else "select a country above"
        )
        _disp_exp_val  = f"{_avg_peci:.2f}" if _avg_peci is not None else "N/A"
        _pc2 = pc
        _disp_exp_note = (
            "hover for detail · complexity additionality from more complex partners" if sel
            else "select a country above"
        )

    # ── Hover panel data ───────────────────────────────────────────────────

    # Card 2 — centrality: FTA partners ranked by their own centrality
    _cent_partners = []
    if _all_cent2:
        _cmax = max(_all_cent2)
        for _p in sel_partners:
            _pc = _centrality_index.get(_p)
            if _pc is not None:
                _pn = COUNTRY_LOOKUP.get(_p, {}).get("name", _p)
                _pct_v = round(_pc / _cmax * 100, 1)
                _pk = "|".join(sorted([sel, _p]))
                _ag = (PAIR_AGREEMENTS.get(_pk) or ["—"])[0]
                _ag = (_ag[:32] + "…") if len(_ag) > 32 else _ag
                _cent_partners.append((_pn, _pct_v, _ag))
    _cent_partners.sort(key=lambda x: x[1], reverse=True)
    _cent_top = _cent_partners[:5]
    _cent_bot = _cent_partners[-5:][::-1] if len(_cent_partners) > 5 else []

    # Card 3 — depth: agreements sorted by entry-into-force year as proxy
    _dated = sorted(
        [(a["name"], a["year"]) for a in agreements if a["year"]],
        key=lambda x: x[1]
    )
    _newest = list(reversed(_dated[-5:])) if _dated else []
    _oldest = _dated[:5] if _dated else []

    # Card 4 — ECI: neighbouring countries in the ranking
    _eci_nbrs = []
    if own_rank:
        for _iso, _rv in _eci_rank.items():
            _d = int(_rv) - own_rank
            if 0 < abs(_d) <= 3:
                _eci_nbrs.append((
                    COUNTRY_LOOKUP.get(_iso, {}).get("name", _iso),
                    int(_rv),
                    _eci_index.get(_iso, 0)
                ))
        _eci_nbrs.sort(key=lambda x: x[1])

    # Card 5 — exposure: FTA partners sorted by ECI
    _peci_data = []
    for _p in sel_partners:
        _pe = _eci_index.get(_p)
        if _pe is not None:
            _pn = COUNTRY_LOOKUP.get(_p, {}).get("name", _p)
            _pk = "|".join(sorted([sel, _p]))
            _ag = (PAIR_AGREEMENTS.get(_pk) or ["—"])[0]
            _ag = (_ag[:28] + "…") if len(_ag) > 28 else _ag
            _peci_data.append((_pn, _pe, _ag))
    _peci_data.sort(key=lambda x: x[1], reverse=True)
    _peci_top = _peci_data[:5]
    _peci_bot = _peci_data[-5:][::-1] if len(_peci_data) > 5 else []

    # ── Panel HTML helpers ─────────────────────────────────────────────────

    def _ph(title):
        return (
            f'<div style="padding:10px 12px 8px;font-size:11px;font-weight:700;'
            f'color:{COLOR_CYAN};text-transform:uppercase;letter-spacing:.05em;'
            f'border-bottom:1px solid rgba(255,255,255,0.10);position:sticky;top:0;background:#0e161f;">'
            f'{title}</div>'
        )

    def _ps(label):
        return (
            f'<div style="padding:5px 12px 3px;font-size:10px;font-weight:700;'
            f'color:#7C8FA0;text-transform:uppercase;letter-spacing:.05em;background:#121b26;">'
            f'{label}</div>'
        )

    def _pr(left, right, col=None):
        _c = col or COLOR_CYAN
        return (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:6px 12px;border-bottom:1px solid rgba(255,255,255,0.07);font-size:12px;">'
            f'<span style="color:#D7E2EA;flex:1;margin-right:8px;">{left}</span>'
            f'<span style="font-weight:700;color:{_c};white-space:nowrap;">{right}</span>'
            f'</div>'
        )

    def _pnote(text):
        return (
            f'<div style="padding:8px 12px;font-size:10.5px;color:#7C8FA0;'
            f'font-style:italic;border-top:1px solid rgba(255,255,255,0.10);">{text}</div>'
        )

    def _ccol(v):
        return COLOR_GREEN if v >= 60 else (COLOR_ORANGE if v >= 25 else COLOR_RED)

    _PS = (
        f'position:absolute;top:calc(100% + 6px);left:0;background:#0e161f;'
        f'border:1px solid {COLOR_TEAL};border-radius:6px;'
        f'box-shadow:0 8px 28px rgba(0,0,0,.55);z-index:999;'
        f'max-height:380px;overflow-y:auto;display:none;'
    )

    # ── Build panel bodies ─────────────────────────────────────────────────

    cent_panel = (
        _ph(f"Connections by centrality · {len(_cent_partners)} partners with data")
        + (_ps("Highest centrality links") + "".join(
            _pr(n, f"{p} / 100", _ccol(p)) for n, p, _ in _cent_top
        ) if _cent_top else _pr("No centrality data available", "—"))
        + (_ps("Lowest centrality links") + "".join(
            _pr(n, f"{p} / 100", _ccol(p)) for n, p, _ in _cent_bot
        ) if _cent_bot else "")
        + _pnote("Partner centrality scores proxy their contribution to your eigenvector centrality.")
    )

    depth_panel = (
        _ph(f"Agreements by era · {len(_dated)} dated records")
        + (_ps("Most recent — likely deepest") + "".join(
            _pr((n[:42] + "…") if len(n) > 42 else n, str(y), COLOR_GREEN)
            for n, y in _newest
        ) if _newest else _pr("No dated records found", "—"))
        + (_ps("Oldest — likely shallowest") + "".join(
            _pr((n[:42] + "…") if len(n) > 42 else n, str(y), COLOR_RED)
            for n, y in _oldest
        ) if _oldest else "")
        + _pnote("Entry-into-force year used as depth proxy. True depth scores require WB DTA 2.0.")
    )

    _eci_interp = (
        "World-class industrial base — exports highly sophisticated products"
        if own_eci and own_eci > 1.5 else
        "Complex economy — significant high-value manufacturing and services"
        if own_eci and own_eci > 0.5 else
        "Moderate complexity — mix of industrial and commodity exports"
        if own_eci and own_eci > -0.5 else
        "Lower complexity — exports concentrated in commodities and basic goods"
        if own_eci is not None else "ECI data not available"
    )

    eci_panel = (
        _ph(f"Economic complexity — {sel_name or 'Country'}")
        + (
            _pr("ECI score", f"{own_eci:+.2f}", ec)
            + _pr("Global rank", f"{own_rank} of {total_eci}", COLOR_CYAN)
            + f'<div style="padding:10px 12px;font-size:12px;color:#D7E2EA;'
              f'line-height:1.6;border-bottom:1px solid rgba(255,255,255,0.07);">{_eci_interp}</div>'
            + (_ps("Nearest comparators") + "".join(
                _pr(n, f"#{r} · {s:+.2f}",
                    COLOR_GREEN if r < own_rank else COLOR_ORANGE)
                for n, r, s in _eci_nbrs
            ) if _eci_nbrs else "")
            if own_eci is not None
            else _pr("No ECI data available", "—", "#7C8FA0")
        )
        + _pnote("Source: Harvard Atlas of Economic Complexity (2012).")
    )

    exp_panel = (
        _ph(f"Complexity exposure · {len(_peci_data)} partners with ECI data")
        + (_ps("Highest complexity partners") + "".join(
            _pr(n, f"{s:+.2f}",
                COLOR_GREEN if s > 0.5 else (COLOR_ORANGE if s > -0.2 else COLOR_RED))
            for n, s, _ in _peci_top
        ) if _peci_top else _pr("No partner ECI data", "—", "#7C8FA0"))
        + (_ps("Lowest complexity partners") + "".join(
            _pr(n, f"{s:+.2f}",
                COLOR_GREEN if s > 0.5 else (COLOR_ORANGE if s > -0.2 else COLOR_RED))
            for n, s, _ in _peci_bot
        ) if _peci_bot else "")
        + _pnote("FTA partners ranked by ECI. Higher ECI = greater complexity exposure.")
    )

    # ── Assemble all five cards ────────────────────────────────────────────

    def _card_full(wc, pc_cls, label, value_str, note, colour, panel_body, pw=340):
        return (
            f'<div style="flex:1;position:relative;" class="{wc}">'
            f'<div style="border-left:4px solid {colour};background:var(--panel-bg);'
            f'backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);'
            f'border-radius:0 6px 6px 0;padding:14px 16px;cursor:default;">'
            f'<div style="font-size:17px;color:{COLOR_TEAL};'
            f'letter-spacing:.02em;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:32px;font-weight:700;color:{colour};line-height:1.15;">'
            f'{value_str}</div>'
            f'<div style="font-size:17px;color:#EAF1F7;margin-top:4px;">{note}</div>'
            f'</div>'
            f'<div class="{pc_cls}" style="{_PS}width:{pw}px;">{panel_body}</div>'
            f'</div>'
        )

    _hover_css = "".join(
        f'.{w}:hover .{p}{{display:block!important;}}'
        for w, p in [("cw","cp"),("dw","dp"),("xw","xp")]
    )

    _cent_label = "Group centrality" if _grp_mode else "Network centrality"
    _exp_label  = "Simulated additionality" if (_grp_mode and _sim_exp_peci is not None) else "Complexity additionality"

    cards_html = "".join([
        _card_full("cw", "cp", _cent_label, _disp_cent_val,
                   _disp_cent_note, _cc2, cent_panel),
        _card_full("dw", "dp", "Agreement depth", _disp_depth_val,
                   _disp_depth_note, dc, depth_panel),
        _card_full("xw", "xp", _exp_label, _disp_exp_val,
                   _disp_exp_note, _pc2, exp_panel),
    ])

    st.markdown(
        f'<style>{_hover_css}</style>'
        f'<div style="display:flex;gap:12px;margin-bottom:8px;">{cards_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Partner recommendations ────────────────────────────────────────────
    # _depth_cands / _cent_cands / _eci_cands were computed earlier (alongside
    # the typology calc) so the analysis paragraph could also name each metric's
    # top pick — this section just renders them.
    st.markdown("<br>", unsafe_allow_html=True)

    if sel:
        def _rec_row(name, val_str, colour):
            return (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:7px 12px;border-bottom:1px solid rgba(255,255,255,0.07);">'
                f'<span style="color:#EAF1F7;font-size:17px;">{_html.escape(name)}</span>'
                f'<span style="font-weight:700;color:{colour};white-space:nowrap;'
                f'font-size:12.5px;margin-left:8px;">{val_str}</span></div>'
            )

        def _rec_panel(title, subtitle, rows_html):
            return (
                f'<div style="flex:1;border:1px solid var(--panel-border);border-radius:8px;'
                f'overflow:hidden;background:var(--panel-bg);backdrop-filter:blur(14px);'
                f'-webkit-backdrop-filter:blur(14px);">'
                f'<div style="padding:10px 12px;background:rgba(255,255,255,0.04);'
                f'border-bottom:1px solid var(--panel-border);">'
                f'<div style="font-size:17px;font-weight:700;color:{COLOR_CYAN};'
                f'letter-spacing:.02em;">{title}</div>'
                f'<div style="font-size:17px;color:#EAF1F7;margin-top:2px;">{subtitle}</div>'
                f'</div>{rows_html}</div>'
            )

        _depth_rows = "".join(
            _rec_row(n, f"{v} agreements", COLOR_TEAL)
            for n, v in _depth_cands[:7]
        ) or '<div style="padding:12px;color:#EAF1F7;font-size:17px;">No data.</div>'

        _cent_rows = "".join(
            _rec_row(n, f"{v} / 100", COLOR_TEAL)
            for n, v in _cent_cands[:7]
        ) or '<div style="padding:12px;color:#EAF1F7;font-size:17px;">No data.</div>'

        _eci_rows = "".join(
            _rec_row(n, f"{v:+.2f}", COLOR_TEAL)
            for n, v in _eci_cands[:7]
        ) or '<div style="padding:12px;color:#EAF1F7;font-size:17px;">No data.</div>'

        st.markdown(
            f'<div style="margin-bottom:8px;font-size:17px;font-weight:700;color:{COLOR_TEAL};'
            f'letter-spacing:.02em;">Recommended trade partners</div>'
            f'<div style="display:flex;gap:12px;">'
            f'{_rec_panel(f"{sel_name} could increase the depth of its agreements with the following countries", "Non-partners ranked by FTA track record (agreement count proxy)", _depth_rows)}'
            f'{_rec_panel(f"{sel_name} could increase its network centrality with the following countries", "Non-partners whose centrality would most lift your own", _cent_rows)}'
            f'{_rec_panel(f"{sel_name} could increase its economic complexity exposure with the following countries", "Non-partners with highest ECI — Harvard Atlas 2012", _eci_rows)}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="padding:16px 20px;background:var(--panel-bg);border-radius:8px;'
            f'backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);'
            f'border:1px solid var(--panel-border);font-size:17px;color:#EAF1F7;">'
            f'Select a country above to see recommended trade partners.</div>',
            unsafe_allow_html=True,
        )

    # ── Backdrop image credit ───────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center;margin-top:24px;font-size:10px;color:rgba(255,255,255,0.35);">'
        'Photo by <a href="https://unsplash.com/@visaxslr?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText" '
        'style="color:rgba(255,255,255,0.35);" target="_blank">Visax</a> on '
        '<a href="https://unsplash.com/photos/a-black-background-with-a-wavy-pattern-FpkeKQlgJtI?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText" '
        'style="color:rgba(255,255,255,0.35);" target="_blank">Unsplash</a></div>',
        unsafe_allow_html=True,
    )

def _unused():
    sel = st.session_state["country"]
    sel_name = COUNTRY_LOOKUP[sel]["name"] if sel and sel in COUNTRY_LOOKUP else None

    title_suffix = f" · <span style='color:{COLOR_GREEN};'>{sel_name}</span>" if sel_name else ""
    st.markdown(
        f'<div class="page-title" style="font-size:36px;">Economic Complexity{title_suffix}</div>'
        f'<div class="page-sub">How diversified and sophisticated is this country\'s productive base? '
        f'Source: Harvard Atlas of Economic Complexity (2012).</div>',
        unsafe_allow_html=True,
    )

    if not ECI_LOADED:
        st.warning("ECI data not loaded. Check that data/processed/eci_scores.csv exists.")
        return

    eci_df = pd.read_csv(_eci_path)
    eci_df = eci_df[eci_df["eci_score"].notna()].sort_values("eci_rank")

    # Selected country stats
    if sel and sel in _eci_index:
        score = _eci_index[sel]
        rank  = int(_eci_rank[sel])
        total = len(eci_df)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-label">ECI Score</div>'
                f'<div class="stat-value">{score:+.3f}</div>'
                f'<div class="stat-sub">Higher = more complex economy</div>'
                f'</div>', unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f'<div class="stat-card" style="border-left-color:{COLOR_GREEN};">'
                f'<div class="stat-label">Global Rank</div>'
                f'<div class="stat-value">{rank} / {total}</div>'
                f'<div class="stat-sub">Out of {total} countries</div>'
                f'</div>', unsafe_allow_html=True,
            )
        with col3:
            cent = _centrality_index.get(sel)
            cent_str = f"{cent:.4f}" if cent else "N/A"
            st.markdown(
                f'<div class="stat-card" style="border-left-color:{COLOR_ORANGE};">'
                f'<div class="stat-label">Network Centrality</div>'
                f'<div class="stat-value" style="font-size:22px;">{cent_str}</div>'
                f'<div class="stat-sub">FTA eigenvector centrality (Fan et al.)</div>'
                f'</div>', unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
    elif sel:
        st.info(f"ECI data not available for {sel_name or sel}.")

    # Chart: top 30 + bottom 10 countries
    st.markdown(
        f'<p style="font-size:14px;font-weight:600;color:{COLOR_BLUE};margin-bottom:8px;">'
        f'ECI Rankings — Top 30 and Bottom 10 countries</p>',
        unsafe_allow_html=True,
    )
    top30   = eci_df.head(30)
    bot10   = eci_df.tail(10)
    display = pd.concat([top30, bot10]).drop_duplicates()

    # Merge country names
    name_map = {c["iso3"]: c["name"] for c in COUNTRIES}
    display["name"] = display["iso3"].map(name_map).fillna(display["iso3"])
    display = display.sort_values("eci_score", ascending=True)

    colours = []
    for iso in display["iso3"]:
        if iso == sel:
            colours.append(COLOR_ORANGE)
        elif iso in top30["iso3"].values:
            colours.append(COLOR_BLUE)
        else:
            colours.append("#cccccc")

    fig = go.Figure(go.Bar(
        x=display["eci_score"],
        y=display["name"],
        orientation="h",
        marker_color=colours,
        text=display["eci_score"].map(lambda x: f"{x:+.3f}"),
        textposition="outside",
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(500, len(display) * 18),
        margin=dict(l=10, r=60, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(title="ECI Score", gridcolor="#f0f0f0", zeroline=True,
                   zerolinecolor="#aaa", zerolinewidth=1),
        yaxis=dict(tickfont=dict(size=11)),
        font=dict(family="Arial"),
        showlegend=False,
    )
    fig.add_vline(x=0, line_width=1, line_color="#aaa")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="data-note">Source: Harvard Atlas of Economic Complexity, '
        'CID Harvard GitHub archive — 2012 data. '
        'More recent data (2021–22) is available at '
        '<a href="https://atlas.hks.harvard.edu" target="_blank">atlas.hks.harvard.edu</a> '
        'but requires manual download.</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════════

render_home()
