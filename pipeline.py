"""
Data pipeline for the Trade Implementation Effects App.

Run this script to fetch data, compute scores, and save to data/processed/scores.csv.

    conda activate trade-app
    python pipeline.py

Data sources:
  Automatic (fetched via wbdata):
    - WGI governance indicators  → implementation proxy
    - Applied tariff mean        → commitment proxy
    - Trade as % of GDP          → commitment proxy

  Manual downloads required (place CSVs in data/raw/ then re-run):
    - data/raw/dta.csv           ← World Bank DTA 2.0: datatopics.worldbank.org/dta
    - data/raw/desta.csv         ← DESTA: designoftradeagreements.org/downloads
    - data/raw/wto_disputes.csv  ← WTO DSB: wto.org/english/tratop_e/dispu_e
    - data/raw/isds.csv          ← UNCTAD ISDS Navigator: investmentpolicy.unctad.org/isds
    - data/raw/gta.csv           ← Global Trade Alert: globaltradealert.org
    - data/raw/ntm.csv           ← UNCTAD NTM: unctad.org
    - data/raw/stc.csv           ← WTO STCs via ePing: epingalert.org
"""

import os
import warnings
import pandas as pd
import numpy as np
import wbdata
from datetime import datetime
from score import compute_scores

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Top 60 FDI destinations (ISO3 codes, UNCTAD World Investment Report 2023)
COUNTRIES = {
    "USA": "United States",       "CHN": "China",               "GBR": "United Kingdom",
    "SGP": "Singapore",           "HKG": "Hong Kong SAR",        "BRA": "Brazil",
    "IND": "India",               "NLD": "Netherlands",          "AUS": "Australia",
    "CAN": "Canada",              "FRA": "France",               "DEU": "Germany",
    "IRL": "Ireland",             "MEX": "Mexico",               "ESP": "Spain",
    "ITA": "Italy",               "RUS": "Russia",               "IDN": "Indonesia",
    "THA": "Thailand",            "POL": "Poland",               "TUR": "Turkey",
    "SAU": "Saudi Arabia",        "ARE": "United Arab Emirates", "MYS": "Malaysia",
    "ZAF": "South Africa",        "KOR": "South Korea",          "JPN": "Japan",
    "ARG": "Argentina",           "CHL": "Chile",                "COL": "Colombia",
    "VNM": "Vietnam",             "PHL": "Philippines",          "PAK": "Pakistan",
    "EGY": "Egypt",               "NGA": "Nigeria",              "KAZ": "Kazakhstan",
    "UKR": "Ukraine",             "CZE": "Czech Republic",       "ROU": "Romania",
    "HUN": "Hungary",             "PRT": "Portugal",             "SWE": "Sweden",
    "CHE": "Switzerland",         "BEL": "Belgium",              "AUT": "Austria",
    "FIN": "Finland",             "DNK": "Denmark",              "NOR": "Norway",
    "NZL": "New Zealand",         "ISR": "Israel",               "PER": "Peru",
    "BGD": "Bangladesh",          "BGR": "Bulgaria",             "HRV": "Croatia",
    "SVK": "Slovakia",            "LTU": "Lithuania",            "LVA": "Latvia",
    "EST": "Estonia",             "CYP": "Cyprus",               "LUX": "Luxembourg",
}

# World Bank indicator codes
WB_INDICATORS = {
    "TM.TAX.MRCH.SM.AR.ZS": "tariff_mean",       # Applied mean tariff, all products
    "NE.TRD.GNFS.ZS":        "trade_pct_gdp",     # Trade (imports + exports) as % of GDP
    "GOV_WGI_RL.SC":         "rule_of_law",        # WGI Rule of Law score (0–100)
    "GOV_WGI_RQ.SC":         "regulatory_quality", # WGI Regulatory Quality score (0–100)
    "GOV_WGI_GE.SC":         "govt_effectiveness", # WGI Government Effectiveness score (0–100)
    "GOV_WGI_CC.SC":         "control_corruption", # WGI Control of Corruption score (0–100)
}

DATA_DATE = datetime(2022, 1, 1)  # Most recent year with near-complete WGI coverage
CACHE_PATH = os.path.join(RAW_DIR, "wb_cache.csv")


def fetch_world_bank(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and os.path.exists(CACHE_PATH):
        print("  Loading World Bank data from cache...")
        return pd.read_csv(CACHE_PATH, index_col="iso3")

    print("  Fetching World Bank data (this may take 30–60 seconds)...")
    iso3_codes = list(COUNTRIES.keys())
    raw = wbdata.get_dataframe(WB_INDICATORS, country=iso3_codes, date="2022", skip_cache=True)

    if isinstance(raw.index, pd.MultiIndex):
        raw = raw.droplevel(1)

    # wbdata returns country names as the index; map back to ISO3
    name_to_iso3 = {v: k for k, v in COUNTRIES.items()}
    raw.index = raw.index.map(lambda name: name_to_iso3.get(name, name))
    raw.index.name = "iso3"

    raw.to_csv(CACHE_PATH, index=True)
    print(f"  Saved to {CACHE_PATH}")
    return raw


def load_csv(filename: str, iso3_col: str, value_cols: list) -> pd.DataFrame | None:
    path = os.path.join(RAW_DIR, filename)
    if not os.path.exists(path):
        print(f"  [{filename}] not found — skipping. Download instructions in pipeline.py header.")
        return None
    df = pd.read_csv(path)
    missing = [c for c in [iso3_col] + value_cols if c not in df.columns]
    if missing:
        print(f"  [{filename}] missing columns: {missing} — skipping.")
        return None
    return df[[iso3_col] + value_cols].rename(columns={iso3_col: "iso3"}).set_index("iso3")


def load_manual_sources() -> pd.DataFrame:
    """Load manually downloaded CSVs and merge into a single DataFrame."""
    frames = []

    dta = load_csv("dta.csv", iso3_col="iso3", value_cols=["dta_depth", "rta_count"])
    if dta is not None:
        frames.append(dta)

    desta = load_csv("desta.csv", iso3_col="iso3", value_cols=["desta_design"])
    if desta is not None:
        frames.append(desta)

    disputes = load_csv("wto_disputes.csv", iso3_col="iso3", value_cols=["wto_dispute_rate"])
    if disputes is not None:
        frames.append(disputes)

    isds = load_csv("isds.csv", iso3_col="iso3", value_cols=["isds_rate"])
    if isds is not None:
        frames.append(isds)

    gta = load_csv("gta.csv", iso3_col="iso3", value_cols=["gta_distortion_ratio"])
    if gta is not None:
        frames.append(gta)

    ntm = load_csv("ntm.csv", iso3_col="iso3", value_cols=["ntm_coverage"])
    if ntm is not None:
        frames.append(ntm)

    stc = load_csv("stc.csv", iso3_col="iso3", value_cols=["stc_count"])
    if stc is not None:
        frames.append(stc)

    if not frames:
        return pd.DataFrame(index=pd.Index(list(COUNTRIES.keys()), name="iso3"))

    base = pd.DataFrame(index=pd.Index(list(COUNTRIES.keys()), name="iso3"))
    for f in frames:
        base = base.join(f, how="left")
    return base


def run(force_refresh: bool = False) -> pd.DataFrame:
    print("\n=== Trade Implementation Effects — Data Pipeline ===\n")

    print("Step 1: World Bank data")
    wb = fetch_world_bank(force_refresh=force_refresh)

    print("\nStep 2: Manual data sources")
    manual = load_manual_sources()

    print("\nStep 3: Merging and scoring")
    base = pd.DataFrame({"country": COUNTRIES})
    base.index.name = "iso3"

    df = base.join(wb, how="left").join(manual, how="left")

    df = compute_scores(df)

    out_path = os.path.join(PROCESSED_DIR, "scores.csv")
    df.to_csv(out_path)
    print(f"\nScores saved to {out_path}")

    print("\n--- Coverage summary ---")
    scored = df["gap_score"].notna().sum()
    limited = df["limited_data"].sum()
    print(f"  Countries scored:       {scored} / {len(df)}")
    print(f"  Limited data (<6 measures): {limited}")
    print(f"  Quadrant counts:\n{df['quadrant'].value_counts().to_string()}")

    return df


if __name__ == "__main__":
    import sys
    force = "--refresh" in sys.argv
    run(force_refresh=force)
