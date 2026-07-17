"""
centrality_pipeline.py
======================
Computes the eigenvector centrality of a country within the network of trade agreements 
it has signed, using the method of Fan et al (2025) "Does centrality within trade agreements 
network matter to economic complexity?". Basically, the centrality of a country is found through
the manipulation of squares of numbers -- matrices -- that represent the agreements that it is a
party to. Each country starts with its own square, which is then combined with all other countries,
the depth of the agreement of those other countries, and the centrality in their networks brought by
those countries. This leads to a centrality score for all countries. 

The Fan et al (2025) equation is centrality_i = λ⁻¹ · Σⱼ Depth_ij · eⱼ, where 
Depth_ij is a binary count of whether the countries i and j have a provision 
according to the list of available ones as per WB DTA 2.0 "Vertical Content" for
which there are data 1,007 scoreable provisions across approximately 20 policy areas. 
λ = largest eigenvalue, e = eigenvector.

Depth is drawn from DTA 2.0, which is more granular than the Hofmann et al (2017)
coding used by Fan etal (2025). Absolute depth values are therefore not the same as in
Fan etal (2025), but the relative ordering persists. This does not affect the 
centrality ranking. 

Five types of centrality are computed to reflect the Fan et al (2025) H2/H3 hypotheses.
In short, countries are thought to have 'natural' trade partners which are their geographic
neighbours, and for these to have similar production profiles. They are also divided into
'developed' and 'developing' groups. Fan et al (2025) find that partnering with non-natural
countries tends to raise complexity access (H2), as does developing countries doing so with
developed ones (H3).

The centrality variants are as follows: 
  • overall_centrality  — all FTA partners
  • nn_centrality       — via "non-natural" partners (CEPII bilateral
                          distance above the country's own average — H2)
  • n_centrality        — via "natural" partners (distance below the
                          country's own average — H2)
  • ed_centrality       — via connections to "Developed" (WB high-income,
                          minus 5 oil-rich exclusions) partners (H3)
  • ing_centrality      — via connections to "Developing" partners (H3)

─────────────────────────────────────────────────────────────────────────────────
DATA REQUIRED (download once, place in data/raw/)
─────────────────────────────────────────────────────────────────────────────────
1. World Bank DTA 2.0 vertical content  [network topology, depth, and
   agreement stats; see CLAUDE.md Section 5, "Base network source mismatch",
   for why the pipeline was migrated off DESTA]
   • URL: https://datatopics.worldbank.org/dta/  → Download → DTA 2.0
   • Save to: data/raw/DTA 2.0 - Vertical Content (v2).xlsx
   • Contains: binary provision codings (0/1) for ~1,071 provisions across
     ~20 policy areas and 400 agreements ("STATA" sheet), a bilateral
     country-pair-year panel keyed by WBID ("Bilateral Information" sheet),
     and per-agreement Status/entry-date metadata ("Agreements" sheet)
   • Depth_ij = count of the 1,007 binary provisions coded 1 for the deepest
     agreement between i and j (64 categorical/multiple-choice provisions in
     the same sheet are excluded — they don't code presence/absence)
   • Network edges = country pairs with a currently-in-force agreement
     (Status == "In Force" or "In force for at least one Party"), or —
     with --year — agreements whose goods entry-into-force date is on or
     before that year, regardless of current Status (see get_valid_wbids)

2. World Bank Country and Lending Groups classification  [region (display
   only) + income group per country; income group feeds the ED/ING
   developed/developing split — see CLAUDE.md Section 5, "'Developed'/
   'developing' sub-network split (H3)"]
   • URL: https://datahelpdesk.worldbank.org/knowledgebase/articles/906519
   • Save to: data/raw/CLASS_2026_07_01.xlsx (filename has a date — update
     INCOME_CLASS_PATH if downloading a newer version)
   • "Developed" = WB "High income" minus 5 oil-abundant economies Fan et
     al. (2025, footnote 4, p.7) explicitly exclude: SAU, KWT, QAT, OMN, BHR

3. CEPII GeoDist bilateral distance database  [real geographic distance,
   used for the natural/non-natural split — see CLAUDE.md Section 5,
   "'Non-natural' split is a coarser proxy"]
   • URL: https://www.cepii.fr/distance/dist_cepii.dta (Etalab 2.0 licence)
   • Save to: data/raw/dist_cepii.dta
   • Uses `distw` (bilateral weighted geographic distance) — the exact CEPII
     variable Fan et al. cite in their data appendix. Each country's own
     natural/non-natural threshold is its own average distw to its own trade
     partners (a per-country average, not one global cutoff — see
     compute_natural_thresholds). CEPII uses an older ISO3 vintage for a
     few countries (CEPII_ISO_ALIASES maps the unambiguous ones); 6 others
     (Montenegro, Serbia, Liechtenstein, Palestine, Kosovo, South Sudan) are
     genuinely absent from this CEPII vintage.
─────────────────────────────────────────────────────────────────────────────────

Output
------
  data/processed/centrality_scores.csv
    iso3, name, region, income_group, overall_centrality, nn_centrality,
    n_centrality, ed_centrality, ing_centrality, overall_rank, nn_rank,
    n_rank, ed_rank, ing_rank, n_agreements, n_partners, avg_enforceable,
    max_enforceable
  data/processed/fta_network_edges.csv
    iso1, iso2, weight
  data/processed/agreements.csv
    iso1, iso2, WBID, agreement, entry_year — feeds network_example.py's
    PARTNER_MAP/AGREEMENTS_MAP/PAIR_AGREEMENTS

Usage
-----
  conda activate trade-app
  python centrality_pipeline.py

  # Historical snapshot: agreements with goods entry-into-force <= 2015
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

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
DATA_RAW     = PROJECT_ROOT / "data" / "raw"
DATA_PROC    = PROJECT_ROOT / "data" / "processed"
DATA_PROC.mkdir(parents=True, exist_ok=True)

DTA_EXCEL_PATH = DATA_RAW / "DTA 2.0 - Vertical Content (v2).xlsx"
INCOME_CLASS_PATH = DATA_RAW / "CLASS_2026_07_01.xlsx"
CEPII_DIST_PATH = DATA_RAW / "dist_cepii.dta"
OUTPUT_PATH   = DATA_PROC / "centrality_scores.csv"
EDGES_PATH    = DATA_PROC / "fta_network_edges.csv"
AGREEMENTS_PATH = DATA_PROC / "agreements.csv"

# CEPII GeoDist uses an older ISO3 vintage for a few countries — maps our
# network's current code to CEPII's code where the equivalence is
# unambiguous (Romania's pre-ISO-update code; Zaire, DR Congo's former
# name/code). Other missing countries (Montenegro, Serbia, Liechtenstein,
# Palestine, Kosovo, South Sudan) are genuinely absent from this CEPII
# vintage — mostly newer/partially-recognised states — and are left as a
# real "no distance data" gap rather than guessed at.
CEPII_ISO_ALIASES = {"ROU": "ROM", "COD": "ZAR"}

# Oil-abundant high-income economies excluded from "developed" per Fan et al.
# (2025), footnote 4, page 7 — see CLAUDE.md Section 5, "'Developed'/
# 'developing' sub-network split (H3)"
OIL_RICH_EXCLUDED = {"SAU", "KWT", "QAT", "OMN", "BHR"}

# Historical ISO codes for states that no longer exist, present in WB DTA
# 2.0's Bilateral Information panel as a legacy artefact of an old
# agreement's row history but not a country the app should ever surface.
# Currently just Yugoslavia (YUG), which appears solely under the Protocol
# on Trade Negotiations (WBID 317, entered into force 1973) — excluded from
# `bilateral` before any other processing so it can't appear as a node,
# accrue agreement stats, or contribute to another country's depth-proxy pool.
HISTORICAL_ISO_EXCLUDE = {"YUG"}

# A WBID's Status can be "In Force" for an agreement as a whole (e.g. "EU -
# Syria") while one member's own participation has since lapsed (e.g. every
# EU FTA stopped covering the UK on 31-Dec-2020, at Brexit). WB DTA 2.0
# doesn't record that via Status — it records it by simply not emitting
# further per-(iso1, iso2, WBID) rows in Bilateral Information once that
# country's coverage ends (verified: UK-Syria and UK-Armenia rows stop at
# 2020, while France-Syria and Germany-Armenia rows for the same WBIDs
# continue to the sheet's latest year). RECENCY_BUFFER_YEARS tolerates this
# many years of ordinary reporting lag in the newest data before treating an
# otherwise-active pair as lapsed — see get_valid_pairs.
RECENCY_BUFFER_YEARS = 1

# WB DTA 2.0 hasn't finished provision-level depth coding for these UK
# post-Brexit continuity agreements — every agree_<WBID> cell is blank in the
# STATA sheet, so their raw computed depth is 0, which without an explicit
# override would silently drop them from the network graph entirely (see
# Extensionslimitations.md, "Zero-depth continuity agreements", for the full
# rationale, verification, and caveats around this proxy). Since a UK
# continuity agreement was negotiated to replicate the EU agreement it
# succeeded, that EU agreement's own (fully-coded) depth is used as an
# explicit, labelled stand-in. Matched by exact partner name against the
# equivalent "EU - <partner>" WBID; verified against WB DTA 2.0 on
# 2026-07-17. {UK WBID: EU-precursor WBID to borrow depth from}.
UK_CONTINUITY_DEPTH_PROXY_WBID = {
    354: 229,  # United Kingdom - Colombia, Ecuador and Peru   <- EU - Colombia, Ecuador and Peru
    355: 154,  # United Kingdom - CARIFORUM States              <- EU - CARIFORUM States
    356: 230,  # United Kingdom - Central America               <- EU - Central America
    357: 87,   # United Kingdom - Chile                         <- EU - Chile
    358: 157,  # United Kingdom - Côte d'Ivoire                 <- EU - Côte d'Ivoire
    359: 207,  # United Kingdom - Eastern and Southern Africa States <- EU - same
    360: 34,   # United Kingdom - Faroe Islands                 <- EU - Faroe Islands
    361: 251,  # United Kingdom - Georgia                       <- EU - Georgia
    364: 76,   # United Kingdom - Jordan                        <- EU - Jordan
    366: 79,   # United Kingdom - Lebanon                       <- EU - Lebanon
    367: 55,   # United Kingdom - Morocco                       <- EU - Morocco
    368: 202,  # United Kingdom - Pacific States                <- EU - Pacific States
    369: 36,   # United Kingdom - Palestine                     <- EU - Palestine
    371: 289,  # United Kingdom - SACU and Mozambique           <- EU - SADC (covers SACU members + Mozambique)
    373: 40,   # United Kingdom - Tunisia                       <- EU - Tunisia
    374: 250,  # United Kingdom - Ukraine                       <- EU - Ukraine
    375: 121,  # United Kingdom - Albania                       <- EU - Albania
    376: 173,  # United Kingdom - Cameroon                      <- EU - Cameroon
    377: 96,   # United Kingdom - Egypt                         <- EU - Egypt
    378: 290,  # United Kingdom - Ghana                         <- EU - Ghana
    380: 248,  # United Kingdom - Moldova, Republic of          <- EU - Moldova, Republic of
    381: 70,   # United Kingdom - North Macedonia               <- EU - North Macedonia
    382: 184,  # United Kingdom - Serbia                        <- EU - Serbia
    383: 287,  # United Kingdom - Singapore                     <- EU - Singapore
    385: 288,  # United Kingdom - Viet Nam                      <- EU - Viet Nam
    388: 352,  # United Kingdom - Pacific States - Accession of Samoa <- EU - same
    389: 353,  # United Kingdom - Pacific States - Accession of Solomon Islands <- EU - same
}

# United Kingdom - Iceland, Liechtenstein and Norway (WBID 392) bundles three
# EFTA states under one WBID, so unlike the table above it has no single EU
# precursor — Iceland and Norway each have their own EU deal, and
# Liechtenstein's is shared with Switzerland. Depth is assigned per partner
# country rather than uniformly across the WBID.
UK_EFTA_BUNDLE_WBID = 392
UK_EFTA_BUNDLE_DEPTH_PROXY_ISO = {
    "ISL": 67,  # <- EU - Iceland (WBID 7)
    "NOR": 68,  # <- EU - Norway (WBID 8)
    "LIE": 69,  # <- EU - Switzerland - Liechtenstein (WBID 6)
}

# United Kingdom - Kenya (387) and United Kingdom - Kosovo (365): no EU
# precursor exists anywhere in WB DTA 2.0 for either partner (no "EU -
# Kenya"/"EU - EAC" or "EU - Kosovo" WBID is coded in this dataset at all).
# Last-resort proxy: the UK's own average depth across its other valid
# agreements — computed in load_wb_dta, after the overrides above are
# applied, excluding these two WBIDs themselves.
UK_NO_PRECURSOR_WBIDS = {365, 387}

# Zero-depth agreements with no Brexit connection at all (2026-07-17) — see
# Extensionslimitations.md, "Zero-depth agreements unrelated to Brexit", for
# the full rationale and caveats. None of these is a rollover of an
# already-coded agreement, so there's no single precursor WBID to borrow
# from; instead, each pair is assigned the lowest depth score found across
# either of its two countries' OTHER real bilateral relationships — a
# deliberately conservative proxy (see get_lowest_of_two_depth_proxies).
PTN_WBID = 317                    # Protocol on Trade Negotiations (1971)
PACER_PLUS_WBID = 329             # Pacific Agreement on Closer Economic Relations Plus
MOROCCO_UAE_WBID = 328
INDONESIA_PAKISTAN_WBID = 344
LOWEST_OF_TWO_PROXY_WBIDS = {PTN_WBID, PACER_PLUS_WBID, MOROCCO_UAE_WBID, INDONESIA_PAKISTAN_WBID}

# Mexico - Cuba (310) and Mexico - Paraguay (334): assigned Mexico's own
# average depth across its other Latin American Integration Association
# (LAIA/ALADI) partners — Argentina, Bolivia, Brazil, Chile, Colombia,
# Ecuador, Panama, Peru, Uruguay, Venezuela (LAIA's membership minus Mexico,
# Cuba, and Paraguay themselves).
MEXICO_LAIA_PROXY_WBIDS = {310, 334}
LAIA_MEMBERS_EXCL_MEXICO_CUBA_PARAGUAY = {
    "ARG", "BOL", "BRA", "CHL", "COL", "ECU", "PAN", "PER", "URY", "VEN"
}

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
    # Small territories not in the standard WB region tables — classified by
    # geographic proximity, not by governing/sovereign state (see CLAUDE.md
    # Section 5, "Base network source mismatch", task 4). Most are
    # unambiguous (Caribbean -> LAC, Pacific -> EAP, Hong Kong/Macao/Taiwan
    # -> EAP, Andorra/San Marino -> ECA). Four North Atlantic territories are
    # politically European/British but geographically at or near North
    # America — classified by physical location: Greenland and Saint Pierre
    # & Miquelon -> NAM (on/off the North American continent); Bermuda ->
    # NAM (~1,050km to North Carolina vs ~5,000km to the UK); Faroe Islands
    # -> ECA (North Atlantic, near Norway/Scotland, not close to NAM).
    "ABW":"LAC","AIA":"LAC","CYM":"LAC","MSR":"LAC","TCA":"LAC",     # Caribbean
    "COK":"EAP","NCL":"EAP","NIU":"EAP","PCN":"EAP","PYF":"EAP",
    "WLF":"EAP","HKG":"EAP","MAC":"EAP","TWN":"EAP",                # Pacific / East Asia
    "AND":"ECA","SMR":"ECA","FRO":"ECA",                            # Europe
    "BMU":"NAM","GRL":"NAM","SPM":"NAM",                            # North Atlantic (geographic proximity)
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
                   help="Historical mode: agreements whose goods entry-into-force date is "
                        "<= this year, ignoring current Status (default: live network — "
                        "agreements currently in force)")
    p.add_argument("--show", action="store_true",
                   help="Print top-20 countries by centrality after computing")
    return p.parse_args()

# ── Data loading ───────────────────────────────────────────────────────────────

def check_data_files():
    """Check required files are present; exit with instructions if not."""
    if not DTA_EXCEL_PATH.exists():
        print(f"""
ERROR: WB DTA 2.0 dataset not found — this is the sole data source for
this pipeline (see CLAUDE.md Section 5, "Base network source mismatch"),
so it cannot run without it.

Download it here:
  https://datatopics.worldbank.org/dta/

Steps:
  1. Go to the URL above and download DTA 2.0 ("Vertical Content")
  2. Save the file as:
     data/raw/{DTA_EXCEL_PATH.name}

Then re-run:  python centrality_pipeline.py
""")
        sys.exit(1)
    if not INCOME_CLASS_PATH.exists():
        print(f"""
ERROR: WB income classification file not found — needed for the ED/ING
(developed/developing) centrality split (see CLAUDE.md Section 5,
"'Developed'/'developing' sub-network split (H3)").

Download it here:
  https://datahelpdesk.worldbank.org/knowledgebase/articles/906519

Steps:
  1. Go to the URL above and download the current "CLASS.xlsx" file
  2. Save it as:
     data/raw/{INCOME_CLASS_PATH.name}
     (note: this filename has a date in it — if you've downloaded a newer
     version, update INCOME_CLASS_PATH in centrality_pipeline.py to match)

Then re-run:  python centrality_pipeline.py
""")
        sys.exit(1)
    if not CEPII_DIST_PATH.exists():
        print(f"""
ERROR: CEPII GeoDist distance dataset not found — needed for the natural/
non-natural centrality split (see CLAUDE.md Section 5, "'Non-natural' split
is a coarser proxy").

Download it here:
  https://www.cepii.fr/distance/dist_cepii.dta

Steps:
  1. Go to the URL above (Etalab 2.0 open licence, no auth needed)
  2. Save the file as:
     data/raw/{CEPII_DIST_PATH.name}

Then re-run:  python centrality_pipeline.py
""")
        sys.exit(1)


def get_valid_wbids(agreements, year_filter=None):
    """
    Determine which WBIDs count as a live network edge — see CLAUDE.md
    Section 5 ("Base network source mismatch") for the full reasoning.

    Default (year_filter=None) — live/current-state snapshot:
      Status in {"In Force", "In force for at least one Party"}. Excludes
      the 16 "Inactive" agreements (e.g. NAFTA, superseded by USMCA in 2020)
      and "Early Announcement" agreements never actually ratified (e.g.
      EU-MERCOSUR). PACER Plus / SADC ("In force for at least one Party")
      are included at the WBID level and trusted pair-by-pair via whichever
      rows actually appear in Bilateral Information, rather than excluded
      for partial ratification elsewhere.

    --year mode — historical snapshot:
      Agreements whose goods entry-into-force date (Date of Entry into
      Force (G) — not (S)/services, a deliberate goods-focused scope choice)
      is on or before year_filter, regardless of current Status. An
      agreement inactive today (e.g. NAFTA) still counts for a year when it
      really was in force.
    """
    if year_filter is None:
        mask = agreements["Status"].isin(["In Force", "In force for at least one Party"])
    else:
        entry_g = pd.to_datetime(agreements["Date of Entry into Force (G)"], errors="coerce")
        mask = entry_g.dt.year <= year_filter
    return set(agreements.loc[mask, "WBID"])


def get_valid_pairs(bilateral, year_filter=None):
    """
    Determine which (iso1, iso2, WBID) triples are actually covered as of the
    reference year, using Bilateral Information's own year panel rather than
    Agreements' Status field — see RECENCY_BUFFER_YEARS for why Status alone
    is not enough (e.g. "EU - Syria" stays "In Force" after Brexit even
    though the UK's own coverage lapsed 31-Dec-2020).

    A triple is valid if the reference year falls within [pair_min_year,
    pair_max_year + RECENCY_BUFFER_YEARS], where pair_min_year/pair_max_year
    are that exact triple's earliest/latest recorded year in Bilateral
    Information (accession and lapse are both visible this way — confirmed
    against known cases: UK-Syria/UK-Armenia rows stop at 2020, Samoa's
    EU-Pacific-States rows only start at 2018, its accession year).

    Default (year_filter=None) — live/current-state snapshot: reference year
    is the dataset's own latest year (bilateral["year"].max()).

    --year mode — historical snapshot: reference year is year_filter itself,
    so a pair only counts for a given historical year if it was actually
    covered then (e.g. UK-Syria is valid at year_filter=2015, not at 2022).

    Returns a DataFrame with columns iso1, iso2, WBID — one row per valid
    triple, suitable for an inner-join filter on the bilateral panel.
    """
    reference_year = year_filter if year_filter is not None else bilateral["year"].max()
    pair_span = bilateral.groupby(["iso1", "iso2", "WBID"])["year"].agg(["min", "max"])
    pair_span.columns = ["pair_min_year", "pair_max_year"]
    pair_span = pair_span.reset_index()
    covers_reference = (
        (pair_span["pair_min_year"] <= reference_year)
        & (pair_span["pair_max_year"] >= reference_year - RECENCY_BUFFER_YEARS)
    )
    return pair_span.loc[covers_reference, ["iso1", "iso2", "WBID"]]


def build_depth_lookup(bilateral):
    """
    Resolve bilateral (with a populated "depth" column) into dict
    {(iso1, iso2) sorted: depth}, taking the max depth where more than one
    valid agreement connects the same pair. Factored out of load_wb_dta so it
    can be run twice: once to get each country's real (already-resolved)
    depth with its other partners before the lowest-of-two/average proxies
    below are computed, and once more, finally, after they're written in.
    """
    lookup = {}
    for _, row in bilateral.iterrows():
        key = tuple(sorted([str(row["iso1"]).strip().upper(),
                            str(row["iso2"]).strip().upper()]))
        depth = float(row["depth"])
        if depth > lookup.get(key, 0):
            lookup[key] = depth
    return lookup


def get_lowest_of_two_depth_proxy(lookup, iso_a, iso_b):
    """
    The lowest depth score found across either iso_a's or iso_b's other real
    bilateral relationships in `lookup` — the proxy used for PTN, PACER Plus,
    Morocco-UAE, and Indonesia-Pakistan (see LOWEST_OF_TWO_PROXY_WBIDS).
    `lookup` should be a first-pass depth_lookup that does not yet include
    the pair being proxied, so its own (still-zero) depth can't contaminate
    the pool. Returns None if neither country has any other real relationship
    in `lookup` (not expected in practice, but handled rather than crashing).
    """
    pool = [depth for (a, b), depth in lookup.items() if iso_a in (a, b) or iso_b in (a, b)]
    return min(pool) if pool else None


def load_wb_dta(year_filter=None):
    """
    Load WB DTA 2.0 as the sole source of network topology, edge depth, and
    per-country agreement stats — see CLAUDE.md Section 5 ("Base network
    source mismatch") for why DESTA was retired from this role. Topology and
    depth now come from the exact same Status/year-filtered dataset, so
    (unlike the old DESTA+DTA-2.0 split) every edge has a real depth by
    construction — with one documented exception: a handful of recent UK
    continuity agreements have no provision-level coding in WB DTA 2.0 yet
    (raw depth 0), so their edge would otherwise silently vanish from the
    network graph. These get an explicit depth proxy applied here — see
    UK_CONTINUITY_DEPTH_PROXY_WBID, UK_EFTA_BUNDLE_DEPTH_PROXY_ISO,
    UK_NO_PRECURSOR_WBIDS, and Extensionslimitations.md, "Zero-depth
    continuity agreements". A handful of zero-depth agreements unconnected to
    Brexit get a proxy too — see LOWEST_OF_TWO_PROXY_WBIDS,
    MEXICO_LAIA_PROXY_WBIDS, and Extensionslimitations.md, "Zero-depth
    agreements unrelated to Brexit".

    Reads the STATA sheet, a provision (row) x agreement (column, `agree_N`)
    matrix where `agree_N` corresponds to WBID=N (verified 1:1, both run 1-400).
    Each provision row is classified as binary (values only in {0, 1, blank})
    or categorical (free-text / multiple-choice, e.g. "A/B/C" classification
    questions). Depth_agreement = count of binary provisions coded 1;
    categorical rows are excluded since they don't code presence/absence.

    Joins the resulting per-agreement depth to the Bilateral Information sheet
    (iso1, iso2, WBID panel), after filtering to valid WBIDs (see
    get_valid_wbids) and then to valid pairs within those WBIDs (see
    get_valid_pairs — drops pairs whose own bloc-membership coverage has
    lapsed even though the agreement itself is still "In Force"), to produce
    a per-country-pair depth lookup — this lookup IS the network's edge set,
    not just a weight overlay — and separately a per-country lookup of
    avg/max provision depth across all of that country's own (valid)
    agreements.

    Returns (depth_lookup, country_depth_stats, entry_year_lookup,
    pair_agreements) where depth_lookup is dict {(iso1, iso2): depth_score}
    with keys sorted alphabetically, country_depth_stats is a DataFrame with
    columns iso, n_agreements, avg_enforceable, max_enforceable,
    entry_year_lookup is dict {WBID: year} from the goods entry-into-force
    date, and pair_agreements is a DataFrame with columns iso1, iso2, WBID,
    agreement, entry_year (one row per valid country-pair-agreement,
    deduplicated across the bilateral panel's years) — feeds
    network_example.py's agreement-listing UI. Returns
    (None, None, None, None) if the Excel file is not present.
    """
    if not DTA_EXCEL_PATH.exists():
        return None, None, None, None

    print(f"  Loading DTA 2.0 from {DTA_EXCEL_PATH.name}...")
    agreements = pd.read_excel(DTA_EXCEL_PATH, sheet_name="Agreements").rename(columns={"WB ID": "WBID"})
    stata      = pd.read_excel(DTA_EXCEL_PATH, sheet_name="STATA")
    bilateral  = pd.read_excel(DTA_EXCEL_PATH, sheet_name="Bilateral Information")

    # Drop historical/defunct-state codes (see HISTORICAL_ISO_EXCLUDE) before
    # anything else touches bilateral, so they can't become a node, accrue
    # agreement stats, or feed into another country's depth-proxy pool.
    n_before_historical = len(bilateral)
    bilateral = bilateral[
        ~bilateral["iso1"].isin(HISTORICAL_ISO_EXCLUDE) & ~bilateral["iso2"].isin(HISTORICAL_ISO_EXCLUDE)
    ].copy()
    print(f"  Historical/defunct-state rows dropped: {n_before_historical - len(bilateral):,} "
          f"({', '.join(sorted(HISTORICAL_ISO_EXCLUDE))})")

    valid_wbids = get_valid_wbids(agreements, year_filter)
    if year_filter:
        print(f"  Historical mode: agreements with goods entry-into-force <= {year_filter}: {len(valid_wbids)}")
    else:
        print(f"  Live mode: agreements currently in force: {len(valid_wbids)}")
    bilateral = bilateral[bilateral["WBID"].isin(valid_wbids)].copy()

    # Drop stale bloc-membership pairs (see get_valid_pairs / RECENCY_BUFFER_YEARS)
    # — a WBID passing the Status filter above doesn't mean every pair under it
    # is still covered (e.g. UK-Syria, UK-Armenia lapsed at Brexit while
    # "EU - Syria"/"EU - Armenia" remain "In Force" for the EU and the partner).
    n_before = len(bilateral)
    valid_pairs = get_valid_pairs(bilateral, year_filter)
    bilateral = bilateral.merge(valid_pairs, on=["iso1", "iso2", "WBID"], how="inner")
    print(f"  Stale bloc-membership pairs dropped: {n_before - len(bilateral):,} rows")

    entry_g = pd.to_datetime(agreements["Date of Entry into Force (G)"], errors="coerce")
    entry_year_lookup = {
        int(wbid): int(yr) for wbid, yr in zip(agreements["WBID"], entry_g.dt.year) if pd.notna(yr)
    }

    agree_cols = [c for c in stata.columns if str(c).startswith("agree_")]

    # A provision row is "binary" if every value across all agreements is
    # in {0, 1, blank}; anything else (free text, letter codes) is categorical.
    def is_binary_row(row):
        return row[agree_cols].apply(
            lambda v: pd.isna(v) or v in (0, 1, "0", "1", "")
        ).all()

    binary_mask = stata.apply(is_binary_row, axis=1)
    print(f"  Provisions: {binary_mask.sum()} binary (scored), "
          f"{(~binary_mask).sum()} categorical (excluded)")

    binary_provisions = stata.loc[binary_mask, agree_cols]
    depth_per_wbid = (binary_provisions == 1).sum(axis=0)  # sum down rows, per agreement column
    depth_per_wbid.index = depth_per_wbid.index.str.replace("agree_", "", regex=False).astype(int)

    # Zero-depth UK continuity agreements: borrow depth from the EU precursor
    # they replicate — see UK_CONTINUITY_DEPTH_PROXY_WBID and
    # Extensionslimitations.md, "Zero-depth continuity agreements".
    for wbid, proxy_wbid in UK_CONTINUITY_DEPTH_PROXY_WBID.items():
        depth_per_wbid[wbid] = depth_per_wbid[proxy_wbid]

    depth_scores = depth_per_wbid.rename("depth").rename_axis("WBID").reset_index()
    print(f"  Depth scores: {len(depth_scores)} agreements, "
          f"max={depth_scores['depth'].max()}, mean={depth_scores['depth'].mean():.1f}")

    # Join depth to bilateral country-pair data
    bilateral = bilateral.merge(depth_scores, on="WBID", how="left")
    bilateral = bilateral.dropna(subset=["depth"])
    # float, not int: the Kenya/Kosovo proxy below is a fractional average
    bilateral["depth"] = bilateral["depth"].astype(float)

    # UK - Iceland, Liechtenstein and Norway (WBID 392): per-partner proxy,
    # not a single WBID-level value — see UK_EFTA_BUNDLE_DEPTH_PROXY_ISO.
    bundle_mask = bilateral["WBID"] == UK_EFTA_BUNDLE_WBID
    if bundle_mask.any():
        partner = bilateral.loc[bundle_mask, ["iso1", "iso2"]].apply(
            lambda r: r["iso2"] if r["iso1"] == "GBR" else r["iso1"], axis=1
        )
        bilateral.loc[bundle_mask, "depth"] = partner.map(UK_EFTA_BUNDLE_DEPTH_PROXY_ISO).values

    # United Kingdom - Kenya / United Kingdom - Kosovo: no EU precursor exists
    # for either, so use the UK's own average depth across its other valid
    # agreements (one row per distinct WBID, computed after the overrides
    # above so the EFTA-bundle proxies count too) — see UK_NO_PRECURSOR_WBIDS.
    uk_wbids = bilateral.loc[
        ((bilateral["iso1"] == "GBR") | (bilateral["iso2"] == "GBR"))
        & (~bilateral["WBID"].isin(UK_NO_PRECURSOR_WBIDS)),
        ["WBID", "depth"],
    ].drop_duplicates(subset=["WBID"])
    uk_avg_depth = uk_wbids["depth"].mean()
    bilateral.loc[bilateral["WBID"].isin(UK_NO_PRECURSOR_WBIDS), "depth"] = uk_avg_depth
    print(f"  UK average depth across {len(uk_wbids)} other valid agreements: "
          f"{uk_avg_depth:.1f} — assigned to Kenya/Kosovo (no EU precursor exists)")

    # First-pass lookup: every WBID handled above is now real (proxied or
    # genuinely coded), but the six zero-depth agreements below are still 0,
    # so they're naturally absent here — exactly the "other real bilateral
    # relationships" pool the proxies below need, with no circularity.
    first_pass_lookup = build_depth_lookup(bilateral)

    # Zero-depth agreements with no Brexit connection — see
    # LOWEST_OF_TWO_PROXY_WBIDS, get_lowest_of_two_depth_proxy, and
    # Extensionslimitations.md, "Zero-depth agreements unrelated to Brexit".
    for wbid in LOWEST_OF_TWO_PROXY_WBIDS:
        wbid_mask = bilateral["WBID"] == wbid
        pairs = bilateral.loc[wbid_mask, ["iso1", "iso2"]].apply(
            lambda r: tuple(sorted([str(r["iso1"]).upper(), str(r["iso2"]).upper()])), axis=1
        ).unique()
        n_proxied = 0
        for iso_a, iso_b in pairs:
            proxy = get_lowest_of_two_depth_proxy(first_pass_lookup, iso_a, iso_b)
            if proxy is None:
                print(f"  WARNING: no other real relationship found for {iso_a}/{iso_b} "
                      f"(WBID {wbid}) — left at depth 0")
                continue
            pair_mask = wbid_mask & (
                ((bilateral["iso1"] == iso_a) & (bilateral["iso2"] == iso_b))
                | ((bilateral["iso1"] == iso_b) & (bilateral["iso2"] == iso_a))
            )
            bilateral.loc[pair_mask, "depth"] = proxy
            n_proxied += 1
        print(f"  WBID {wbid}: lowest-of-two-countries proxy assigned to {n_proxied}/{len(pairs)} pairs")

    # Mexico - Cuba / Mexico - Paraguay: Mexico's own average depth across its
    # other LAIA partners — see MEXICO_LAIA_PROXY_WBIDS.
    laia_depths = [
        depth for (a, b), depth in first_pass_lookup.items()
        if "MEX" in (a, b)
        and (b if a == "MEX" else a) in LAIA_MEMBERS_EXCL_MEXICO_CUBA_PARAGUAY
    ]
    mex_laia_avg = sum(laia_depths) / len(laia_depths) if laia_depths else None
    if mex_laia_avg is not None:
        bilateral.loc[bilateral["WBID"].isin(MEXICO_LAIA_PROXY_WBIDS), "depth"] = mex_laia_avg
    print(f"  Mexico's average depth across {len(laia_depths)} other LAIA partners: "
          f"{mex_laia_avg:.1f} — assigned to Mexico-Cuba/Mexico-Paraguay")

    # Final lookup, built after every proxy above has been written into
    # bilateral's "depth" column — takes the max depth per pair across all
    # valid agreements, exactly as before.
    lookup = build_depth_lookup(bilateral)

    print(f"  Network edges (unique country pairs, valid agreements only): {len(lookup):,}")

    # Per-country agreement stats: for each country, n_agreements (count of
    # its own valid WBIDs) and avg/max depth across those agreements
    # (regardless of partner) — one row per (country, WBID), deduplicated
    # across the bilateral panel's years.
    country_agreements = pd.concat([
        bilateral[["iso1", "WBID", "depth"]].rename(columns={"iso1": "iso"}),
        bilateral[["iso2", "WBID", "depth"]].rename(columns={"iso2": "iso"}),
    ]).drop_duplicates(subset=["iso", "WBID"])
    country_depth_stats = (
        country_agreements.groupby("iso")
        .agg(n_agreements=("WBID", "nunique"),
             avg_enforceable=("depth", "mean"),
             max_enforceable=("depth", "max"))
        .reset_index()
    )
    print(f"  Country agreement/depth stats: {len(country_depth_stats)} countries")

    # Per-pair-per-agreement listing (name + entry year), one row per
    # (iso1, iso2, WBID), deduplicated across the bilateral panel's years —
    # feeds network_example.py's PARTNER_MAP/AGREEMENTS_MAP/PAIR_AGREEMENTS
    # (see CLAUDE.md Section 5, task 7 of the DESTA migration).
    pair_agreements = (
        bilateral[["iso1", "iso2", "WBID"]]
        .drop_duplicates()
        .merge(agreements[["WBID", "Agreement"]], on="WBID", how="left")
        .rename(columns={"Agreement": "agreement"})
    )
    pair_agreements["entry_year"] = pair_agreements["WBID"].map(entry_year_lookup)
    print(f"  Pair/agreement listing: {len(pair_agreements):,} rows")

    return lookup, country_depth_stats, entry_year_lookup, pair_agreements


def load_cepii_distance():
    """
    Load CEPII GeoDist bilateral weighted distance (distw) — see CLAUDE.md
    Section 5, "'Non-natural' split is a coarser proxy", for why this
    replaces the WB-region proxy. Fan et al. (2025) cite this exact CEPII
    variable ("bilateral weighted geographic distance", appendix table; same
    term used in their IV robustness equation) as their distance measure.

    Applies CEPII_ISO_ALIASES for the two countries with an unambiguous
    older-code equivalent in this CEPII vintage; other missing countries
    are a genuine data gap, not remapped.

    Returns dict {(iso1, iso2): distw_km} with keys sorted alphabetically
    (distance is symmetric — confirmed empirically to match to ~1m of
    rounding noise in both directions).
    """
    alias_to_current = {v: k for k, v in CEPII_ISO_ALIASES.items()}
    df = pd.read_stata(CEPII_DIST_PATH)
    df = df[df["iso_o"] != df["iso_d"]]
    df["iso_o"] = df["iso_o"].map(lambda x: alias_to_current.get(x, x))
    df["iso_d"] = df["iso_d"].map(lambda x: alias_to_current.get(x, x))

    lookup = {}
    for _, row in df.iterrows():
        key = tuple(sorted([row["iso_o"], row["iso_d"]]))
        lookup[key] = row["distw"]
    print(f"  CEPII distance lookup: {len(lookup):,} country pairs")
    return lookup


# ── Network construction ───────────────────────────────────────────────────────

def build_network(depth_lookup):
    """
    Build a weighted undirected graph directly from the WB DTA 2.0 depth
    lookup (see load_wb_dta) — topology and edge weight both come from the
    exact same Status/year-filtered dataset, so every edge has a real depth
    by construction. If multiple valid agreements connect the same pair, the
    maximum depth is kept, following Fan et al.'s approach.
    """
    G = nx.Graph()

    for (iso1, iso2), weight in depth_lookup.items():
        weight = max(float(weight), 0.01)  # guard against zero weights
        G.add_edge(iso1, iso2, weight=weight)

    print(f"  Network: {G.number_of_nodes()} countries, {G.number_of_edges()} agreement pairs")
    return G


def compute_natural_thresholds(G, distance_lookup):
    """
    Each country's own natural/non-natural distance threshold: the average
    CEPII bilateral weighted distance (distw) across all of *its own* trade
    partners with known distance data — see CLAUDE.md Section 5, "'Non-
    natural' split is a coarser proxy", for why this is a per-country average
    rather than one global cutoff (per the paper's own self-referential
    phrasing: "the country"... "its trade partners"... "the average level").

    Returns dict {iso3: threshold_km}. Countries with no partners having
    known distance data are omitted (threshold undefined for them).
    """
    thresholds = {}
    for node in G.nodes():
        partner_dists = [
            distance_lookup[tuple(sorted([node, nbr]))]
            for nbr in G.neighbors(node)
            if tuple(sorted([node, nbr])) in distance_lookup
        ]
        if partner_dists:
            thresholds[node] = sum(partner_dists) / len(partner_dists)
    print(f"  Natural/non-natural thresholds computed for {len(thresholds)} "
          f"of {G.number_of_nodes()} countries")
    return thresholds


def split_natural_nonnatural(G, distance_lookup, thresholds):
    """
    Split edges into natural and non-natural subgraphs using real CEPII
    bilateral distance data and each country's own per-country threshold
    (see compute_natural_thresholds) — replacing the earlier WB-region proxy
    with Fan et al. (2025)'s actual distance-based methodology.

    Like the ED/ING split, this is asymmetric and the two subgraphs
    *overlap* rather than partition cleanly: an edge (i,j) can be "natural"
    from i's perspective (dist < i's own threshold) while simultaneously
    "non-natural" from j's perspective (dist > j's own threshold), since i
    and j generally have different thresholds. G_natural includes an edge if
    *either* endpoint's own threshold classifies it natural; G_nonnatural if
    either classifies it non-natural. Edges with no distance data, or where
    neither endpoint has a computable threshold, are excluded from both.
    """
    G_natural     = nx.Graph()
    G_nonnatural  = nx.Graph()
    n_no_data = 0

    for u, v, data in G.edges(data=True):
        dist_uv = distance_lookup.get(tuple(sorted([u, v])))
        if dist_uv is None:
            n_no_data += 1
            continue

        is_natural = False
        is_nonnatural = False
        if u in thresholds:
            if dist_uv < thresholds[u]:
                is_natural = True
            else:
                is_nonnatural = True
        if v in thresholds:
            if dist_uv < thresholds[v]:
                is_natural = True
            else:
                is_nonnatural = True

        if is_natural:
            G_natural.add_edge(u, v, **data)
        if is_nonnatural:
            G_nonnatural.add_edge(u, v, **data)

    print(f"  Natural edges:     {G_natural.number_of_edges()}")
    print(f"  Non-natural edges: {G_nonnatural.number_of_edges()}")
    print(f"  Edges excluded from both (no distance data): {n_no_data}")
    return G_natural, G_nonnatural


def load_income_classification():
    """
    Load WB income classification (data/raw/CLASS_2026_07_01.xlsx, "List of
    economies" sheet), applying Fan et al.'s oil-rich exclusion.

    A country is "Developed" if WB classifies it "High income" AND it is not
    one of the 5 oil-abundant economies Fan et al. (2025, footnote 4, p.7)
    explicitly exclude from that bucket (OIL_RICH_EXCLUDED). Every other
    country with a known income group (Low/Lower middle/Upper middle income,
    or High income but oil-rich) is "Developing" — see CLAUDE.md Section 5,
    "'Developed'/'developing' sub-network split (H3)" for the full reasoning.

    Returns dict {iso3: "Developed" | "Developing"}.
    """
    df = pd.read_excel(INCOME_CLASS_PATH, sheet_name="List of economies")
    classification = {}
    for _, row in df.iterrows():
        iso = row["Code"]
        income_group = row["Income group"]
        if pd.isna(iso) or pd.isna(income_group):
            continue
        if income_group == "High income" and iso not in OIL_RICH_EXCLUDED:
            classification[iso] = "Developed"
        else:
            classification[iso] = "Developing"
    n_developed = sum(1 for v in classification.values() if v == "Developed")
    print(f"  Income classification: {n_developed} Developed, "
          f"{len(classification) - n_developed} Developing")
    return classification


def split_developed_developing(G, income_classification):
    """
    Build G_ED (edges touching at least one Developed country) and G_ING
    (edges touching at least one Developing country) — see CLAUDE.md Section
    5, "'Developed'/'developing' sub-network split (H3)" for why this is an
    asymmetric, *overlapping* pair of subgraphs rather than a clean partition
    like natural/non-natural: Fan et al. define a partner as belonging to a
    country's "developed network" based on the *partner's* own classification,
    not a symmetric same-group requirement, so a Developed-Developing edge
    genuinely belongs to both a developing country's ED network and a
    developed country's ING network simultaneously.

    Edges where neither endpoint has a known classification (e.g. a
    territory not covered by the WB income file) are excluded from both.
    """
    G_ed  = nx.Graph()
    G_ing = nx.Graph()

    for u, v, data in G.edges(data=True):
        class_u = income_classification.get(u)
        class_v = income_classification.get(v)
        if class_u == "Developed" or class_v == "Developed":
            G_ed.add_edge(u, v, **data)
        if class_u == "Developing" or class_v == "Developing":
            G_ing.add_edge(u, v, **data)

    print(f"  ED (developed-partner) edges:  {G_ed.number_of_edges()}")
    print(f"  ING (developing-partner) edges: {G_ing.number_of_edges()}")
    return G_ed, G_ing


# ── Centrality computation ─────────────────────────────────────────────────────

def eigenvector_centrality_per_component(G, label=""):
    """
    Compute eigenvector centrality separately within each connected component,
    then rescale each component's (unit-normalised) score vector by that
    component's own dominant eigenvalue.

    A single global power iteration on a disconnected graph converges to the
    dominant eigenvector of whichever component has the largest eigenvalue —
    every other component's scores underflow towards 0 (e.g. Canada/Vietnam/
    Peru's natural centrality reading as ~1e-223 when Europe dominates).
    Solving per component and rescaling by each component's own eigenvalue
    keeps that same "richer/denser region scores higher" property, while
    still giving every region a meaningful, non-degenerate internal ranking.
    Isolated (single-node) components get a score of 0.
    """
    cent = {}
    for nodes in nx.connected_components(G):
        sub = G.subgraph(nodes)
        if sub.number_of_nodes() == 1:
            cent[next(iter(nodes))] = 0.0
            continue
        try:
            # scipy's sparse ARPACK solver (used internally here) requires
            # k < N-1 eigenvalues, which fails for small components (a handful
            # of nodes) — fall back to power iteration for those.
            sub_cent = nx.eigenvector_centrality_numpy(sub, weight="weight")
        except (nx.PowerIterationFailedConvergence, TypeError):
            sub_cent = nx.eigenvector_centrality(sub, weight="weight", max_iter=1000, tol=1e-6)
        eigval = max(nx.adjacency_spectrum(sub, weight="weight").real)
        cent.update({node: value * eigval for node, value in sub_cent.items()})

    # Renormalise to unit length, matching eigenvector_centrality_numpy's own
    # convention for connected graphs, so this column stays on a comparable
    # scale to overall_centrality / nn_centrality (the per-component eigenvalue
    # rescaling above sets each component's *relative* weight; this step just
    # brings the combined vector back to a standard, comparable magnitude).
    norm = np.sqrt(sum(v ** 2 for v in cent.values()))
    if norm > 0:
        cent = {k: v / norm for k, v in cent.items()}

    print(f"  {label}: {nx.number_connected_components(G)} disconnected components, "
          f"computed centrality per component")
    return cent


def safe_eigenvector_centrality(G, label=""):
    """
    Compute weighted eigenvector centrality, falling back to per-component
    computation if the numpy solver fails (e.g. disconnected graph).
    Returns a dict {node: centrality_score}.
    """
    if G.number_of_nodes() == 0:
        return {}
    try:
        cent = nx.eigenvector_centrality_numpy(G, weight="weight")
    except nx.AmbiguousSolution:
        # Raised on disconnected graphs (e.g. the natural/intra-regional
        # subgraph, which splits into one component per WB region).
        cent = eigenvector_centrality_per_component(G, label)
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


def compute_all_centralities(G, G_natural, G_nonnatural, G_ed, G_ing):
    """Return five centrality dicts: overall, natural, non-natural, ED, ING."""
    print("  Computing overall centrality...")
    overall = safe_eigenvector_centrality(G, "overall")

    print("  Computing non-natural (inter-regional) centrality...")
    nn = safe_eigenvector_centrality(G_nonnatural, "non-natural")

    print("  Computing natural (intra-regional) centrality...")
    n = safe_eigenvector_centrality(G_natural, "natural")

    print("  Computing ED (developed-partner) centrality...")
    ed = safe_eigenvector_centrality(G_ed, "ED")

    print("  Computing ING (developing-partner) centrality...")
    ing = safe_eigenvector_centrality(G_ing, "ING")

    return overall, nn, n, ed, ing


# ── Results assembly ─────────────────────────────────────────────────────────

def assemble_results(overall, nn, n, ed, ing, n_partners, income_classification=None, country_depth_stats=None):
    """
    Build results DataFrame from centrality dicts.

    n_agreements/avg_enforceable/max_enforceable all come from
    country_depth_stats (WB DTA 2.0 — see load_wb_dta); n_partners comes
    from the network's own degree (G.degree()), so both are now sourced
    from the same WB-DTA-2.0-built graph.
    """
    all_countries = set(overall) | set(nn) | set(n) | set(ed) | set(ing) | set(n_partners)
    income_classification = income_classification or {}

    rows = []
    for iso in all_countries:
        rows.append({
            "iso3":               iso,
            "name":               COUNTRY_NAMES.get(iso, iso),
            "region":             WB_REGION.get(iso, "Unknown"),
            "income_group":       income_classification.get(iso, "Unknown"),
            "overall_centrality": overall.get(iso, 0.0),
            "nn_centrality":      nn.get(iso, 0.0),
            "n_centrality":       n.get(iso, 0.0),
            "ed_centrality":      ed.get(iso, 0.0),
            "ing_centrality":     ing.get(iso, 0.0),
            "n_partners":         n_partners.get(iso, 0),
        })

    results = pd.DataFrame(rows)

    # Merge in per-country agreement/provision-depth stats from WB DTA 2.0
    # (n_agreements, avg/max enforceable provisions). Countries with no WB
    # DTA 2.0 coverage get 0 for all three — a real "no data" value,
    # consistent with n_partners defaulting to 0 above.
    if country_depth_stats is not None:
        results = results.merge(
            country_depth_stats.rename(columns={"iso": "iso3"}),
            on="iso3", how="left",
        )
        stat_cols = ["n_agreements", "avg_enforceable", "max_enforceable"]
        results[stat_cols] = results[stat_cols].fillna(0.0)
        results["n_agreements"] = results["n_agreements"].astype(int)
    else:
        results["n_agreements"] = 0
        results["avg_enforceable"] = 0.0
        results["max_enforceable"] = 0.0

    # Add ranks (1 = highest centrality)
    for col in ["overall_centrality", "nn_centrality", "n_centrality", "ed_centrality", "ing_centrality"]:
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
        print(f"Sample: historical — agreements with goods entry-into-force ≤ {args.year}")
    else:
        print(f"Sample: live — agreements currently in force")
    print()

    # 1. Check files
    check_data_files()

    # 2. Load data — WB DTA 2.0 is the sole source of topology, depth,
    # n_agreements, and region classification (see CLAUDE.md Section 5,
    # "Base network source mismatch"). DESTA has been fully retired from
    # this file and from network_example.py.
    print("Loading data...")
    depth_lookup, country_depth_stats, entry_year_lookup, pair_agreements = load_wb_dta(year_filter=args.year)
    income_classification = load_income_classification()
    cepii_distance = load_cepii_distance()

    # 3. Build network
    print("\nBuilding network...")
    G = build_network(depth_lookup)

    # 4. Split natural / non-natural (real CEPII distance, per-country
    # threshold — see CLAUDE.md Section 5), and developed / developing (H3)
    natural_thresholds = compute_natural_thresholds(G, cepii_distance)
    G_natural, G_nonnatural = split_natural_nonnatural(G, cepii_distance, natural_thresholds)
    G_ed, G_ing = split_developed_developing(G, income_classification)

    # 5. Compute centrality
    print("\nComputing centrality scores...")
    overall, nn, n, ed, ing = compute_all_centralities(G, G_natural, G_nonnatural, G_ed, G_ing)

    # 6. Degree statistics — n_partners comes directly from the WB-DTA-2.0-built
    # graph's own degree; n_agreements comes from country_depth_stats (also
    # WB DTA 2.0), merged in by assemble_results()
    n_partners = dict(G.degree())

    # 7. Assemble and save
    print("\nAssembling results...")
    results = assemble_results(overall, nn, n, ed, ing, n_partners, income_classification, country_depth_stats)
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

    # 8b. Save per-pair-agreement listing for the app's agreement-hover UI
    pair_agreements.to_csv(AGREEMENTS_PATH, index=False)
    print(f"  Saved: {AGREEMENTS_PATH}  ({len(pair_agreements)} rows)")

    # 8. Optional display
    if args.show:
        print("\n── Top 30 Countries by Overall Centrality ───────────────────────")
        display = results.head(30)[["overall_rank","iso3","name","region","income_group",
                                    "overall_centrality","nn_centrality","n_centrality",
                                    "ed_centrality","ing_centrality",
                                    "n_agreements","n_partners"]]
        display = display.rename(columns={
            "overall_rank":        "Rank",
            "iso3":                "ISO3",
            "name":                "Country",
            "region":              "Region",
            "income_group":        "Income",
            "overall_centrality":  "Overall",
            "nn_centrality":       "Non-natural",
            "n_centrality":        "Natural",
            "ed_centrality":       "ED",
            "ing_centrality":      "ING",
            "n_agreements":        "# Agreements",
            "n_partners":          "# Partners",
        })
        # Round floats
        for col in ["Overall","Non-natural","Natural","ED","ING"]:
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
