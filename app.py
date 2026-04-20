"""
Trade Implementation Effects App
Assesses the institutional quality of countries in implementing trade deals.
"""

import copy
import os
import re
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import folium
import branca.colormap as cm
import streamlit as st
from streamlit_folium import st_folium
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Colours and constants ───────────────────────────────────────────────────

COLOR_GREEN  = "#00A651"
COLOR_BLUE   = "#004B87"
COLOR_ORANGE = "#F7941D"
COLOR_RED    = "#C0392B"

QUADRANT_COLOURS = {
    "Strong performer":  COLOR_GREEN,
    "Over-committed":    COLOR_ORANGE,
    "Quiet complier":    COLOR_BLUE,
    "Disengaged":        COLOR_RED,
    "Insufficient data": "#AAAAAA",
}

REGIONS = {
    "All regions": None,
    "East Asia & Pacific":      ["AUS","CHN","HKG","IDN","JPN","KOR","MYS","NZL","PHL","SGP","THA","VNM"],
    "Europe & Central Asia":    ["AUT","BEL","BGR","CHE","CYP","CZE","DEU","DNK","ESP","EST","FIN","FRA","GBR","HRV","HUN","IRL","ISR","ITA","KAZ","LTU","LUX","LVA","NLD","NOR","POL","PRT","ROU","RUS","SVK","SWE","TUR","UKR"],
    "Latin America & Caribbean":["ARG","BRA","CHL","COL","MEX","PER"],
    "Middle East & North Africa":["ARE","EGY","SAU"],
    "North America":             ["CAN","MEX","USA"],
    "South Asia":                ["BGD","IND","PAK"],
    "Sub-Saharan Africa":        ["NGA","ZAF"],
}

COMMITMENT_MEASURES = [
    "tariff_mean_norm", "trade_pct_gdp_norm",
    "dta_depth_norm", "desta_design_norm", "rta_count_norm",
]
IMPLEMENTATION_MEASURES = [
    "rule_of_law_norm", "regulatory_quality_norm",
    "govt_effectiveness_norm", "control_corruption_norm",
    "wto_dispute_rate_norm", "isds_rate_norm",
    "gta_distortion_ratio_norm", "ntm_coverage_norm", "stc_count_norm",
]
MEASURE_LABELS = {
    "tariff_mean_norm":          "Tariff openness",
    "trade_pct_gdp_norm":        "Trade integration",
    "dta_depth_norm":            "DTA depth",
    "desta_design_norm":         "Agreement design",
    "rta_count_norm":            "No. of agreements",
    "rule_of_law_norm":          "Rule of law",
    "regulatory_quality_norm":   "Regulatory quality",
    "govt_effectiveness_norm":   "Govt effectiveness",
    "control_corruption_norm":   "Control of corruption",
    "wto_dispute_rate_norm":     "WTO dispute record",
    "isds_rate_norm":            "ISDS record",
    "gta_distortion_ratio_norm": "Trade policy stability",
    "ntm_coverage_norm":         "NTM friction",
    "stc_count_norm":            "STC record",
}

# ── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Trade Implementation Effects",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main .block-container { padding-top: 1.2rem; }
    .stMetric label { font-size: 0.78rem; color: #555; }
    .badge {
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-size: 0.78rem; font-weight: 600; color: white; margin-bottom: 0.5rem;
    }
    h3 { margin-bottom: 0.2rem; }
</style>
""", unsafe_allow_html=True)

# ── Data ─────────────────────────────────────────────────────────────────────

@st.cache_data
def load_scores() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed", "scores.csv")
    return pd.read_csv(path, index_col="iso3")

df_base = load_scores()

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Trade Implementation Effects")
    st.caption("Institutional quality for long-term FDI")
    st.divider()

    region = st.selectbox("Region", list(REGIONS.keys()))

    st.divider()
    st.markdown("**Score weights**")
    st.caption("Shift the balance between the two dimensions")
    w_c = st.slider("Commitment weight", 0.1, 1.0, 0.5, 0.05, key="w_c")
    w_i = st.slider("Implementation weight", 0.1, 1.0, 0.5, 0.05, key="w_i")

    st.divider()
    st.markdown("**Country comparison**")
    country_options = sorted(df_base["country"].dropna().tolist())
    compare = st.multiselect(
        "Select up to 3 countries",
        options=country_options,
        max_selections=3,
        placeholder="Choose countries…",
    )

    st.divider()
    st.caption("Data: WGI 2022 · WDI 2022\nDTA/DESTA/GTA pending manual download.")

# ── Score recomputation ───────────────────────────────────────────────────────

def recompute(df: pd.DataFrame, w_c: float, w_i: float) -> pd.DataFrame:
    df = df.copy()
    c_cols = [c for c in COMMITMENT_MEASURES if c in df.columns and df[c].notna().any()]
    i_cols = [c for c in IMPLEMENTATION_MEASURES if c in df.columns and df[c].notna().any()]
    if c_cols:
        df["commitment_score"] = df[c_cols].mean(axis=1).round(1)
    if i_cols:
        df["implementation_score"] = df[i_cols].mean(axis=1).round(1)
    total = w_c + w_i
    df["gap_score"] = (
        (df["commitment_score"] * w_c - df["implementation_score"] * w_i) / total
    ).round(1)
    return df

df = recompute(df_base, w_c, w_i)

region_filter = REGIONS[region]
df_map = df[df.index.isin(region_filter)] if region_filter else df

# ── GeoJSON ───────────────────────────────────────────────────────────────────

@st.cache_data
def load_geojson() -> dict:
    url = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

# ── Map ───────────────────────────────────────────────────────────────────────

st.markdown("### Institutional quality — Gap Score by country")
st.caption(
    "**Gap Score** = Commitment minus Implementation (weighted). "
    "Positive = under-delivering on trade commitments → investment risk. "
    "Negative = strong follow-through → stable climate. "
    "Click a country for a detailed breakdown."
)

def build_map(df_map: pd.DataFrame, geojson_raw: dict) -> folium.Map:
    score_dict       = df_map["gap_score"].dropna().to_dict()
    commitment_dict  = df_map["commitment_score"].dropna().to_dict()
    impl_dict        = df_map["implementation_score"].dropna().to_dict()
    quadrant_dict    = df_map["quadrant"].to_dict()
    country_dict     = df_map["country"].to_dict()

    valid_scores = [v for v in score_dict.values() if pd.notna(v)]
    gap_min = min(valid_scores) if valid_scores else -50
    gap_max = max(valid_scores) if valid_scores else  50
    abs_max = max(abs(gap_min), abs(gap_max))

    colormap = cm.LinearColormap(
        colors=[COLOR_GREEN, "#CCECDB", "#F5F5F5", "#FADBD8", COLOR_RED],
        vmin=-abs_max,
        vmax= abs_max,
        index=[-abs_max, -abs_max * 0.25, 0, abs_max * 0.25, abs_max],
        caption="Gap Score  (negative = strong implementation; positive = investment risk)",
    )

    m = folium.Map(
        location=[20, 10],
        zoom_start=2,
        tiles="cartodbpositron",
        min_zoom=1,
        max_zoom=7,
        prefer_canvas=True,
    )

    geojson = copy.deepcopy(geojson_raw)

    for feature in geojson["features"]:
        iso3 = feature["properties"].get("ISO_A3", "")
        gap  = score_dict.get(iso3)
        feature["properties"]["_iso3"]          = iso3
        feature["properties"]["_country"]       = country_dict.get(iso3, feature["properties"].get("ADMIN", iso3))
        feature["properties"]["_gap"]           = f"{gap:.1f}" if pd.notna(gap) else "No data"
        feature["properties"]["_commitment"]    = f"{commitment_dict[iso3]:.1f}"  if iso3 in commitment_dict  else "No data"
        feature["properties"]["_impl"]          = f"{impl_dict[iso3]:.1f}"        if iso3 in impl_dict        else "No data"
        feature["properties"]["_quadrant"]      = quadrant_dict.get(iso3, "No data")

    def style_fn(feature):
        iso3 = feature["properties"].get("ISO_A3", "")
        gap  = score_dict.get(iso3)
        fill = colormap(gap) if pd.notna(gap) else "#DDDDDD"
        return {"fillColor": fill, "fillOpacity": 0.75, "color": "#888888", "weight": 0.4}

    def highlight_fn(_):
        return {"fillOpacity": 0.95, "weight": 1.8, "color": "#333333"}

    folium.GeoJson(
        geojson,
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["_country", "_gap", "_commitment", "_impl", "_quadrant"],
            aliases=["Country", "Gap Score", "Commitment", "Implementation", "Quadrant"],
            sticky=True,
            style="font-size:13px; font-family:sans-serif;",
        ),
        popup=folium.GeoJsonPopup(
            fields=["_iso3"],
            aliases=[""],
            labels=False,
            max_width=1,
        ),
        name="Gap Score",
    ).add_to(m)

    colormap.add_to(m)
    return m

with st.spinner("Loading map…"):
    geojson_raw = load_geojson()
    folium_map  = build_map(df_map, geojson_raw)

map_out = st_folium(
    folium_map,
    use_container_width=True,
    height=500,
    returned_objects=["last_object_clicked_popup"],
    key="folium_map",
)

# ── Determine selected country ────────────────────────────────────────────────

clicked_iso3 = None
popup_raw = map_out.get("last_object_clicked_popup") if map_out else None
if popup_raw:
    match = re.search(r"\b([A-Z]{3})\b", popup_raw)
    if match:
        clicked_iso3 = match.group(1)

name_to_iso3 = {v: k for k, v in df["country"].items()}

# ── Detail panel ──────────────────────────────────────────────────────────────

def detail_panel(iso3: str, df: pd.DataFrame):
    if iso3 not in df.index:
        st.warning(f"No data for {iso3}.")
        return

    row        = df.loc[iso3]
    name       = row["country"]
    gap        = row.get("gap_score", np.nan)
    commitment = row.get("commitment_score", np.nan)
    impl       = row.get("implementation_score", np.nan)
    quadrant   = row.get("quadrant", "Insufficient data")
    colour     = QUADRANT_COLOURS.get(quadrant, "#AAAAAA")

    st.markdown("---")
    st.markdown(f"### {name}")
    st.markdown(f'<span class="badge" style="background:{colour}">{quadrant}</span>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Gap Score",      f"{gap:.1f}"        if pd.notna(gap)        else "—")
    c2.metric("Commitment",     f"{commitment:.1f}" if pd.notna(commitment) else "—")
    c3.metric("Implementation", f"{impl:.1f}"       if pd.notna(impl)       else "—")

    available = {
        k: MEASURE_LABELS[k] for k in MEASURE_LABELS
        if k in df.columns and pd.notna(row.get(k))
    }

    col_radar, col_bar = st.columns([1, 1])

    # Radar
    with col_radar:
        if len(available) >= 3:
            cols   = list(available.keys())
            labels = list(available.values()) + [list(available.values())[0]]
            values = [float(row[c]) for c in cols] + [float(row[cols[0]])]
            fig_r  = go.Figure(go.Scatterpolar(
                r=values, theta=labels,
                fill="toself",
                fillcolor="rgba(0,166,81,0.12)",
                line=dict(color=COLOR_GREEN, width=2),
            ))
            fig_r.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0,100], tickfont=dict(size=8)),
                    angularaxis=dict(tickfont=dict(size=9)),
                ),
                showlegend=False,
                margin=dict(l=30, r=30, t=20, b=20),
                height=300,
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.info("Not enough measures to render radar chart.")

    # Bar — peer comparison
    with col_bar:
        if len(available) >= 1:
            peers    = df[df["quadrant"] == quadrant].drop(index=iso3, errors="ignore")
            peer_avg = peers[[c for c in available if c in peers.columns]].mean()
            measures = list(available.values())
            country_vals = [float(row[c]) for c in available]
            peer_vals    = [float(peer_avg.get(c, np.nan)) for c in available]

            fig_b = go.Figure()
            fig_b.add_trace(go.Bar(name=name,         x=measures, y=country_vals, marker_color=COLOR_GREEN))
            fig_b.add_trace(go.Bar(name="Peer avg",   x=measures, y=peer_vals,    marker_color=COLOR_BLUE))
            fig_b.update_layout(
                barmode="group",
                xaxis=dict(tickangle=-35, tickfont=dict(size=8)),
                yaxis=dict(range=[0, 105], title="Score (0–100)", tickfont=dict(size=9)),
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=9)),
                margin=dict(l=0, r=0, t=20, b=90),
                height=300,
                paper_bgcolor="white",
                plot_bgcolor="#FAFAFA",
            )
            st.plotly_chart(fig_b, use_container_width=True)

    # Claude narrative
    st.markdown("**AI analysis**")
    st.caption("Claude-generated — not verified analysis. Verify all claims before use.")
    if st.button(f"Generate analysis for {name}", key=f"btn_{iso3}"):
        _generate_narrative(iso3, row, quadrant, gap, commitment, impl)


def _generate_narrative(iso3, row, quadrant, gap, commitment, impl):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("Set ANTHROPIC_API_KEY in your .env file.")
        return

    measure_lines = "\n".join(
        f"  - {MEASURE_LABELS[k]}: {row[k]:.1f}/100"
        for k in MEASURE_LABELS if k in row.index and pd.notna(row.get(k))
    )

    prompt = f"""You are a trade economist analysing institutional quality for long-term trade-linked FDI.

Country: {row['country']} ({iso3})
Quadrant: {quadrant}
Commitment Score: {commitment:.1f}/100  |  Implementation Score: {impl:.1f}/100
Gap Score: {gap:.1f}  (positive = under-delivering on commitments; negative = over-delivering)

Individual measure scores (0–100, higher is better):
{measure_lines}

Write a concise 3-paragraph analysis (200–250 words) covering:
1. What the scores reveal about this country's institutional quality for trade-linked investment
2. The key drivers of the gap between commitment and implementation
3. Specific investment implications — what an investor should watch for

Be specific and cautious. Do not fabricate data not provided above."""

    client = anthropic.Anthropic(api_key=api_key)
    box = st.empty()
    text = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=450,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk
            box.markdown(text + "▌")
    box.markdown(text)


# ── Render ────────────────────────────────────────────────────────────────────

if clicked_iso3:
    detail_panel(clicked_iso3, df)
elif compare:
    for cname in compare:
        iso3 = name_to_iso3.get(cname)
        if iso3:
            detail_panel(iso3, df)
else:
    st.markdown("---")
    st.caption("Click a country on the map, or use **Country comparison** in the sidebar.")

# ── Full table ────────────────────────────────────────────────────────────────

with st.expander("Full Gap Score table", expanded=False):
    display = df_map[["country","commitment_score","implementation_score","gap_score","quadrant"]].copy()
    display = display.sort_values("gap_score", ascending=False)
    display.columns = ["Country","Commitment","Implementation","Gap Score","Quadrant"]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV",
        display.to_csv(index=True),
        file_name="trade_implementation_scores.csv",
        mime="text/csv",
    )
