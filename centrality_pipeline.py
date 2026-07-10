"""
centrality_pipeline.py
======================
Computes FTA-network eigenvector centrality following Fan et al. (2025):
"Does centrality within trade agreements network matter to economic complexity?"
International Review of Economics & Finance, 98.

Method (Fan et al. eq. 1):
    Centrality_i = λ⁻¹ · Σⱼ Depth_ij · eⱼ

where Depth_ij = count of legally enforceable provisions between countries i and j
(Hofmann et al. 2017 coding, 0–52 scale across 14 WTO+ and 38 WTO-X areas),
λ = largest eigenvalue, e = eigenvector.

Three centrality variants are computed:
  • overall_centrality  — all FTA partners
  • nn_centrality       — inter-regional (non-natural) partners only
  • n_centrality        — intra-regional (natural) partners only

Fan et al. find nn_centrality has a significantly larger effect on ECI (β=0.298***)
while n_centrality is not significant once controls are added.

─────────────────────────────────────────────────────────────────────────────────
DATA REQUIRED (download once, place in data/raw/)
─────────────────────────────────────────────────────────────────────────────────
1. DESTA dyadic dataset
   • URL: https://www.designoftradeagreements.org/downloads/
   • File to download: "List of dyads" → desta_list_of_dyads_02_01.csv
   • Save to: data/raw/desta_dyads.csv
   • Contains: one row per country-pair-agreement combination, with year and
     depth/provision indicators

2. World Bank DTA 1.0 horizontal depth  [optional but improves accuracy]
   • URL: https://datatopics.worldbank.org/dta/  → Download → DTA 1.0
   • Save to: data/raw/DTA 1.0 - Horizontal Content (v2).xlsx
   • Contains: legally enforceable provision scores (0/1/2) for 52 policy areas
     across 390 agreements, plus bilateral country-pair data
   • Depth_ij = count of provisions with legal enforceability score >= 1
     (Hofmann et al. 2017 total depth measure, max 52)

If only DESTA is present the pipeline falls back to DESTA's depth_index proxy.
─────────────────────────────────────────────────────────────────────────────────

Output
------
  data/processed/centrality_scores.csv
    iso3, name, region, overall_centrality, nn_centrality, n_centrality,
    overall_rank, nn_rank, n_rank, n_agreements, n_partners

Usage
-----
  conda activate trade-app
  python centrality_pipeline.py

  # Optional: specify a year (defaults to most recent available)
  python centrality_pipeline.py --year 2015

  # Run and immediately open results table
  python centrality_pipeline.py --show
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import pycountry

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
DATA_RAW     = PROJECT_ROOT / "data" / "raw"
DATA_PROC    = PROJECT_ROOT / "data" / "processed"
DATA_PROC.mkdir(parents=True, exist_ok=True)

DESTA_PATH    = DATA_RAW / "desta_dyads.csv"
DTA_EXCEL_PATH = DATA_RAW / "DTA 1.0 - Horizontal Content (v2).xlsx"
OUTPUT_PATH   = DATA_PROC / "centrality_scores.csv"
EDGES_PATH    = DATA_PROC / "fta_network_edges.csv"

# ── World Bank regional classification ────────────────────────────────────────
# Used to split natural (intra-regional) vs non-natural (inter-regional) networks.
# Source: World Bank country classification (same as network_example.py)

WB_REGION = {
    # East Asia & Pacific
    "AUS":"EAP","BRN":"EAP","CHN":"EAP","FJI":"EAP","IDN":"EAP","JPN":"EAP",
    "KHM":"EAP","KOR":"EAP","LAO":"EAP","MHL":"EAP","MMR":"EAP","MNG":"EAP",
    "MYS":"EAP","NRU":"EAP","NZL":"EAP","PHL":"EAP","PLW":"EAP","PNG":"EAP",
    "PRK":"EAP","SGP":"EAP","SLB":"EAP","THA":"EAP","TLS":"EAP","TON":"EAP",
    "TUV":"EAP","VNM":"EAP","VUT":"EAP","WSM":"EAP","FSM":"EAP","KIR":"EAP",
    # Europe & Central Asia
    "ALB":"ECA","ARM":"ECA","AUT":"ECA","AZE":"ECA","BEL":"ECA","BGR":"ECA",
    "BIH":"ECA","BLR":"ECA","CHE":"ECA","CYP":"ECA","CZE":"ECA","DEU":"ECA",
    "DNK":"ECA","ESP":"ECA","EST":"ECA","FIN":"ECA","FRA":"ECA","GBR":"ECA",
    "GEO":"ECA","GRC":"ECA","HRV":"ECA","HUN":"ECA","IRL":"ECA","ISL":"ECA",
    "ITA":"ECA","KAZ":"ECA","KGZ":"ECA","LIE":"ECA","LTU":"ECA","LUX":"ECA",
    "LVA":"ECA","MDA":"ECA","MKD":"ECA","MLT":"ECA","MNE":"ECA","NLD":"ECA",
    "NOR":"ECA","POL":"ECA","PRT":"ECA","ROU":"ECA","RUS":"ECA","SRB":"ECA",
    "SVK":"ECA","SVN":"ECA","SWE":"ECA","TJK":"ECA","TKM":"ECA","TUR":"ECA",
    "UKR":"ECA","UZB":"ECA","XKX":"ECA",
    # Latin America & Caribbean
    "ARG":"LAC","ATG":"LAC","BHS":"LAC","BLZ":"LAC","BOL":"LAC","BRA":"LAC",
    "BRB":"LAC","CHL":"LAC","COL":"LAC","CRI":"LAC","CUB":"LAC","DMA":"LAC",
    "DOM":"LAC","ECU":"LAC","GRD":"LAC","GTM":"LAC","GUY":"LAC","HND":"LAC",
    "HTI":"LAC","JAM":"LAC","KNA":"LAC","LCA":"LAC","MEX":"LAC","NIC":"LAC",
    "PAN":"LAC","PER":"LAC","PRY":"LAC","SLV":"LAC","SUR":"LAC","TTO":"LAC",
    "URY":"LAC","VCT":"LAC","VEN":"LAC",
    # Middle East & North Africa
    "ARE":"MENA","BHR":"MENA","DJI":"MENA","DZA":"MENA","EGY":"MENA",
    "IRN":"MENA","IRQ":"MENA","ISR":"MENA","JOR":"MENA","KWT":"MENA",
    "LBN":"MENA","LBY":"MENA","MAR":"MENA","MLT":"MENA","OMN":"MENA",
    "PSE":"MENA","QAT":"MENA","SAU":"MENA","SYR":"MENA","TUN":"MENA",
    "YEM":"MENA",
    # North America
    "CAN":"NAM","MEX":"LAC","USA":"NAM",
    # South Asia
    "AFG":"SAS","BGD":"SAS","BTN":"SAS","IND":"SAS","LKA":"SAS","MDV":"SAS",
    "NPL":"SAS","PAK":"SAS",
    # Sub-Saharan Africa
    "AGO":"SSA","BDI":"SSA","BEN":"SSA","BFA":"SSA","BWA":"SSA","CAF":"SSA",
    "CIV":"SSA","CMR":"SSA","COD":"SSA","COG":"SSA","COM":"SSA","CPV":"SSA",
    "ERI":"SSA","ETH":"SSA","GAB":"SSA","GHA":"SSA","GIN":"SSA","GMB":"SSA",
    "GNB":"SSA","GNQ":"SSA","KEN":"SSA","LBR":"SSA","LSO":"SSA","MDG":"SSA",
    "MLI":"SSA","MOZ":"SSA","MRT":"SSA","MUS":"SSA","MWI":"SSA","NAM":"SSA",
    "NER":"SSA","NGA":"SSA","RWA":"SSA","SDN":"SSA","SEN":"SSA","SLE":"SSA",
    "SOM":"SSA","SSD":"SSA","STP":"SSA","SWZ":"SSA","SYC":"SSA","TCD":"SSA",
    "TGO":"SSA","TZA":"SSA","UGA":"SSA","ZAF":"SSA","ZMB":"SSA","ZWE":"SSA",
}

# Country name lookup (iso3 → readable name)
COUNTRY_NAMES = {
    "USA":"United States","CAN":"Canada","MEX":"Mexico","DEU":"Germany",
    "FRA":"France","GBR":"United Kingdom","ITA":"Italy","ESP":"Spain",
    "NLD":"Netherlands","CHE":"Switzerland","BEL":"Belgium","AUT":"Austria",
    "SWE":"Sweden","NOR":"Norway","DNK":"Denmark","FIN":"Finland","PRT":"Portugal",
    "GRC":"Greece","POL":"Poland","CZE":"Czech Republic","HUN":"Hungary",
    "ROU":"Romania","BGR":"Bulgaria","HRV":"Croatia","SVK":"Slovakia",
    "SVN":"Slovenia","LTU":"Lithuania","LVA":"Latvia","EST":"Estonia",
    "IRL":"Ireland","LUX":"Luxembourg","TUR":"Turkey","UKR":"Ukraine",
    "RUS":"Russia","CHN":"China","JPN":"Japan","KOR":"South Korea",
    "AUS":"Australia","NZL":"New Zealand","SGP":"Singapore","MYS":"Malaysia",
    "THA":"Thailand","VNM":"Vietnam","IDN":"Indonesia","PHL":"Philippines",
    "IND":"India","PAK":"Pakistan","BGD":"Bangladesh","LKA":"Sri Lanka",
    "BRA":"Brazil","ARG":"Argentina","CHL":"Chile","COL":"Colombia",
    "PER":"Peru","ECU":"Ecuador","VEN":"Venezuela","BOL":"Bolivia",
    "ZAF":"South Africa","NGA":"Nigeria","KEN":"Kenya","EGY":"Egypt",
    "MAR":"Morocco","TUN":"Tunisia","DZA":"Algeria","GHA":"Ghana",
    "ETH":"Ethiopia","TZA":"Tanzania","MOZ":"Mozambique","ZMB":"Zambia",
    "SAU":"Saudi Arabia","ARE":"UAE","ISR":"Israel","JOR":"Jordan",
    "IRN":"Iran","IRQ":"Iraq","KWT":"Kuwait","QAT":"Qatar","OMN":"Oman",
    "BHR":"Bahrain","KAZ":"Kazakhstan","UZB":"Uzbekistan","GEO":"Georgia",
    "ARM":"Armenia","AZE":"Azerbaijan","BLR":"Belarus",
}

# ── Argument parsing ───────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Compute FTA network centrality (Fan et al. 2025)")
    p.add_argument("--year", type=int, default=None,
                   help="Use agreements in force as of this year (default: latest)")
    p.add_argument("--show", action="store_true",
                   help="Print top-20 countries by centrality after computing")
    return p.parse_args()

# ── Data loading ───────────────────────────────────────────────────────────────

def numeric_to_alpha3(numeric_code):
    """Convert ISO numeric country code (int or str) to ISO 3166-1 alpha-3."""
    try:
        country = pycountry.countries.get(numeric=str(int(numeric_code)).zfill(3))
        return country.alpha_3 if country else None
    except (ValueError, TypeError):
        return None


def check_data_files():
    """Check required files are present; exit with instructions if not."""
    if not DESTA_PATH.exists():
        print("""
ERROR: DESTA dyadic dataset not found.

Download it here:
  https://www.designoftradeagreements.org/downloads/

Steps:
  1. Go to the URL above
  2. Under "Dyadic data", download "List of dyads (version 02_01)"
  3. Save the CSV file as:
     data/raw/desta_dyads.csv

Then re-run:  python centrality_pipeline.py
""")
        sys.exit(1)


def load_desta(year_filter=None):
    """
    Load DESTA dyadic dataset.

    DESTA dyadic columns used:
      iso1, iso2       — ISO3 country codes
      base_treaty      — agreement identifier
      year             — year agreement entered into force
      depth_index      — overall depth index (0–1 range, Fan et al. proxy)
      pta              — 1 if preferential trade agreement
      fta_goods        — 1 if FTA covering goods

    Fan et al. use the Hofmann et al. (2017) depth measure from DTA 2.0.
    DESTA's depth_index is used here as a good available proxy when DTA 2.0
    depth scores are not available.
    """
    df = pd.read_csv(DESTA_PATH, low_memory=False, encoding="latin-1")
    print(f"  Loaded DESTA: {len(df):,} dyadic rows, columns: {list(df.columns[:10])}...")

    # Normalise column names to lower case
    df.columns = df.columns.str.lower().str.strip()

    # Convert numeric ISO codes to alpha-3
    if "iso1" in df.columns and df["iso1"].dtype in [int, float, "int64", "float64"]:
        print("  Converting numeric ISO codes to alpha-3...")
        df["iso1"] = df["iso1"].apply(numeric_to_alpha3)
        df["iso2"] = df["iso2"].apply(numeric_to_alpha3)

    # Drop rows where conversion failed
    before = len(df)
    df = df.dropna(subset=["iso1", "iso2"])
    if len(df) < before:
        print(f"  Dropped {before - len(df):,} rows with unresolved country codes")

    # Keep only active PTAs
    if year_filter and "entryforceyear" in df.columns:
        df = df[df["entryforceyear"] <= year_filter]
    elif year_filter and "year" in df.columns:
        df = df[df["year"] <= year_filter]

    # Fan et al. restrict to PTAs (excluding WTO/MFN-only)
    if "pta" in df.columns:
        df = df[df["pta"] == 1]
    elif "fta_goods" in df.columns:
        df = df[df["fta_goods"] == 1]

    return df


def load_dta_bilateral_depth():
    """
    Load WB DTA 1.0 horizontal depth scores (Hofmann et al. 2017).

    Reads the WTO+ LE and WTO-X LE sheets, counts legally enforceable provisions
    (value >= 1) per agreement across all 52 policy areas, then joins to the
    Bilateral Information sheet to produce a per-country-pair depth lookup.

    Returns dict {(iso1, iso2): depth_score} with keys sorted alphabetically,
    or None if the Excel file is not present.
    """
    if not DTA_EXCEL_PATH.exists():
        return None

    print(f"  Loading DTA 1.0 from {DTA_EXCEL_PATH.name}...")
    wto_plus_le = pd.read_excel(DTA_EXCEL_PATH, sheet_name="WTO+ LE")
    wto_x_le   = pd.read_excel(DTA_EXCEL_PATH, sheet_name="WTO-X LE")
    bilateral  = pd.read_excel(DTA_EXCEL_PATH, sheet_name="Bilateral Information")

    # Count legally enforceable provisions (value >= 1) per agreement
    meta_cols = {"RTAID", "WBID", "Agreement"}
    prov_plus = [c for c in wto_plus_le.columns if c not in meta_cols]
    prov_x    = [c for c in wto_x_le.columns   if c not in meta_cols]

    depth_scores = pd.DataFrame({
        "WBID":  wto_plus_le["WBID"],
        "depth": (wto_plus_le[prov_plus] >= 1).sum(axis=1)
                 + (wto_x_le[prov_x] >= 1).sum(axis=1),
    })
    print(f"  Depth scores: {len(depth_scores)} agreements, "
          f"max={depth_scores['depth'].max()}, mean={depth_scores['depth'].mean():.1f}")

    # Join depth to bilateral country-pair data
    bilateral = bilateral.merge(depth_scores, on="WBID", how="left")
    bilateral = bilateral.dropna(subset=["depth"])

    # Build lookup keyed on sorted (iso1, iso2) tuple; take max depth per pair
    lookup = {}
    for _, row in bilateral.iterrows():
        key = tuple(sorted([str(row["iso1"]).strip().upper(),
                            str(row["iso2"]).strip().upper()]))
        depth = float(row["depth"])
        if depth > lookup.get(key, 0):
            lookup[key] = depth

    print(f"  Bilateral depth lookup: {len(lookup):,} country pairs")
    return lookup


# ── Network construction ───────────────────────────────────────────────────────

def detect_depth_column(df):
    """
    Identify the best available depth column in the DESTA dataframe.
    Priority: depth_index > depth_ra_goods_sd > wto_coverage > 1 (binary)
    """
    for col in ["depth_index", "depth_ra_goods_sd", "depth_ra_goods", "depth_goods", "wto_coverage"]:
        if col in df.columns:
            print(f"  Using depth column: '{col}'")
            return col
    print("  No depth column found — using binary (agreement present = 1)")
    return None


def build_network(df, depth_col, bilateral_depth_lookup=None):
    """
    Build a weighted undirected graph.

    Edge weight = Depth_ij from Hofmann et al. (2017) when the DTA 1.0 bilateral
    lookup is available; falls back to DESTA's depth_index proxy otherwise.
    If multiple agreements exist between a pair, the maximum depth is kept,
    following Fan et al.'s approach.
    """
    G = nx.Graph()

    for _, row in df.iterrows():
        iso1 = str(row.get("iso1", "")).strip().upper()
        iso2 = str(row.get("iso2", "")).strip().upper()

        if not iso1 or not iso2 or iso1 == iso2:
            continue

        # Prefer DTA 1.0 bilateral depth (Hofmann et al. 2017)
        weight = None
        if bilateral_depth_lookup is not None:
            key = tuple(sorted([iso1, iso2]))
            weight = bilateral_depth_lookup.get(key, None)

        # Fall back to DESTA depth proxy
        if weight is None and depth_col:
            raw = row.get(depth_col, np.nan)
            weight = float(raw) if pd.notna(raw) and raw != "" else 1.0
        elif weight is None:
            weight = 1.0

        weight = max(float(weight), 0.01)  # guard against zero weights

        if G.has_edge(iso1, iso2):
            G[iso1][iso2]["weight"] = max(G[iso1][iso2]["weight"], weight)
        else:
            G.add_edge(iso1, iso2, weight=weight)

    print(f"  Network: {G.number_of_nodes()} countries, {G.number_of_edges()} agreement pairs")
    return G


def build_region_lookup_from_desta(df):
    """
    Build a per-country region dict from DESTA's regioncon column.
    DESTA regioncon encodes the region of country1 for each dyad row.
    We take the most frequent regioncon value for each iso1 code.
    """
    if "regioncon" not in df.columns:
        return {}
    lookup = {}
    for iso_col, region_col in [("iso1", "regioncon"), ("iso2", "regioncon")]:
        if iso_col == "iso2":
            # regioncon in DESTA records the region of country1 only, so
            # use WB_REGION as fallback for iso2
            break
        grp = df.groupby(iso_col)["regioncon"].agg(lambda x: x.mode().iloc[0])
        lookup.update(grp.to_dict())
    return lookup


def split_natural_nonnatural(G, desta_region_lookup=None):
    """
    Split edges into natural (intra-regional) and non-natural (inter-regional).
    Fan et al. (2025) classify intra-regional as 'natural' following Baldwin (2006).
    Uses WB_REGION dict; falls back to DESTA regioncon if WB_REGION has no entry.
    """
    G_natural     = nx.Graph()
    G_nonnatural  = nx.Graph()

    for u, v, data in G.edges(data=True):
        region_u = WB_REGION.get(u) or (desta_region_lookup or {}).get(u)
        region_v = WB_REGION.get(v) or (desta_region_lookup or {}).get(v)
        if region_u and region_v and region_u == region_v:
            G_natural.add_edge(u, v, **data)
        else:
            G_nonnatural.add_edge(u, v, **data)

    print(f"  Natural (intra-regional) edges:     {G_natural.number_of_edges()}")
    print(f"  Non-natural (inter-regional) edges: {G_nonnatural.number_of_edges()}")
    return G_natural, G_nonnatural


# ── Centrality computation ─────────────────────────────────────────────────────

def safe_eigenvector_centrality(G, label=""):
    """
    Compute weighted eigenvector centrality, falling back to power iteration
    if numpy solver fails (e.g. disconnected graph).
    Returns a dict {node: centrality_score}.
    """
    if G.number_of_nodes() == 0:
        return {}
    try:
        cent = nx.eigenvector_centrality_numpy(G, weight="weight")
    except nx.PowerIterationFailedConvergence:
        cent = nx.eigenvector_centrality(G, weight="weight", max_iter=1000, tol=1e-6)
    except Exception as exc:
        print(f"  WARNING: eigenvector centrality failed for {label}: {exc}")
        cent = {n: 0.0 for n in G.nodes()}

    # Ensure all values are positive (eigenvector direction can be negative)
    vals = list(cent.values())
    if vals and min(vals) < 0:
        cent = {k: abs(v) for k, v in cent.items()}

    return cent


def compute_all_centralities(G, G_natural, G_nonnatural):
    """Return three centrality dicts: overall, natural, non-natural."""
    print("  Computing overall centrality...")
    overall = safe_eigenvector_centrality(G, "overall")

    print("  Computing non-natural (inter-regional) centrality...")
    nn = safe_eigenvector_centrality(G_nonnatural, "non-natural")

    print("  Computing natural (intra-regional) centrality...")
    n = safe_eigenvector_centrality(G_natural, "natural")

    return overall, nn, n


# ── Degree statistics ─────────────────────────────────────────────────────────

def compute_degree_stats(G, df):
    """Compute n_agreements and n_partners per country."""
    n_partners = dict(G.degree())

    if "base_treaty" in df.columns and "iso1" in df.columns:
        agreements = (
            pd.concat([
                df[["iso1", "base_treaty"]].rename(columns={"iso1": "iso"}),
                df[["iso2", "base_treaty"]].rename(columns={"iso2": "iso"}),
            ])
            .drop_duplicates()
            .groupby("iso")["base_treaty"]
            .nunique()
            .to_dict()
        )
    else:
        agreements = {n: 1 for n in G.nodes()}

    return n_partners, agreements


# ── Results assembly ──────────────────────────────────────────────────────────

def assemble_results(overall, nn, n, n_partners, n_agreements):
    """Build results DataFrame from centrality dicts."""
    all_countries = set(overall) | set(nn) | set(n) | set(n_partners)

    rows = []
    for iso in all_countries:
        rows.append({
            "iso3":               iso,
            "name":               COUNTRY_NAMES.get(iso, iso),
            "region":             WB_REGION.get(iso, "Unknown"),
            "overall_centrality": overall.get(iso, 0.0),
            "nn_centrality":      nn.get(iso, 0.0),
            "n_centrality":       n.get(iso, 0.0),
            "n_partners":         n_partners.get(iso, 0),
            "n_agreements":       n_agreements.get(iso, 0),
        })

    results = pd.DataFrame(rows)

    # Add ranks (1 = highest centrality)
    for col in ["overall_centrality", "nn_centrality", "n_centrality"]:
        rank_col = col.replace("centrality", "rank")
        results[rank_col] = results[col].rank(ascending=False, method="min").astype(int)

    results = results.sort_values("overall_rank")
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print("\n── FTA Network Centrality Pipeline ──────────────────────────────")
    print(f"Method: Fan et al. (2025) weighted eigenvector centrality")
    if args.year:
        print(f"Sample: agreements in force ≤ {args.year}")
    else:
        print(f"Sample: all agreements in the DESTA dataset")
    print()

    # 1. Check files
    check_data_files()

    # 2. Load data
    print("Loading data...")
    df              = load_desta(year_filter=args.year)
    bilateral_depth = load_dta_bilateral_depth()  # None if Excel absent

    # 3. Build network
    print("\nBuilding network...")
    depth_col = detect_depth_column(df)
    if bilateral_depth:
        print("  Depth source: DTA 1.0 Hofmann et al. (2017) — legally enforceable provisions")
    else:
        print("  Depth source: DESTA depth_index proxy (DTA 1.0 Excel not found)")
    G = build_network(df, depth_col, bilateral_depth)

    # 4. Split natural / non-natural
    desta_regions = build_region_lookup_from_desta(df)
    G_natural, G_nonnatural = split_natural_nonnatural(G, desta_regions)

    # 5. Compute centrality
    print("\nComputing centrality scores...")
    overall, nn, n = compute_all_centralities(G, G_natural, G_nonnatural)

    # 6. Degree statistics
    n_partners, n_agreements = compute_degree_stats(G, df)

    # 7. Assemble and save
    print("\nAssembling results...")
    results = assemble_results(overall, nn, n, n_partners, n_agreements)
    results.to_csv(OUTPUT_PATH, index=False)
    print(f"  Saved: {OUTPUT_PATH}  ({len(results)} countries)")

    # 8. Save edge list for what-if simulation in the app
    edges_df = pd.DataFrame(
        [(u, v, d["weight"]) for u, v, d in G.edges(data=True)],
        columns=["iso1", "iso2", "weight"],
    )
    edges_df.to_csv(EDGES_PATH, index=False)
    print(f"  Saved: {EDGES_PATH}  ({len(edges_df)} edges, "
          f"mean weight={edges_df['weight'].mean():.2f})")

    # 8. Optional display
    if args.show:
        print("\n── Top 30 Countries by Overall Centrality ───────────────────────")
        display = results.head(30)[["overall_rank","iso3","name","region",
                                    "overall_centrality","nn_centrality","n_centrality",
                                    "n_agreements","n_partners"]]
        display = display.rename(columns={
            "overall_rank":        "Rank",
            "iso3":                "ISO3",
            "name":                "Country",
            "region":              "Region",
            "overall_centrality":  "Overall",
            "nn_centrality":       "Non-natural",
            "n_centrality":        "Natural",
            "n_agreements":        "# Agreements",
            "n_partners":          "# Partners",
        })
        # Round floats
        for col in ["Overall","Non-natural","Natural"]:
            display[col] = display[col].map(lambda x: f"{x:.4f}")
        print(display.to_string(index=False))
        print()
        print("Fan et al. key finding:")
        print("  Non-natural centrality (inter-regional) → ECI: β=0.298***")
        print("  Natural centrality (intra-regional)     → ECI: not significant")
        print("  Centrality to developed partners        → ECI: β=3.514***")

    print("\nDone. Wire results into network_example.py with:")
    print("  import pandas as pd")
    print("  cent = pd.read_csv('data/processed/centrality_scores.csv').set_index('iso3')")
    print("  # Then use cent.loc[iso3,'overall_centrality'] as node size")


if __name__ == "__main__":
    main()
