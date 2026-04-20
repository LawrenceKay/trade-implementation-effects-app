import pandas as pd
import numpy as np


def normalise(series: pd.Series, invert: bool = False) -> pd.Series:
    """Normalise a series to 0–100. Set invert=True for measures where lower raw = better."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    scaled = (series - mn) / (mx - mn) * 100
    return (100 - scaled) if invert else scaled


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Commitment Score, Implementation Score, and Gap Score.

    Commitment measures (higher raw = more committed, except tariff which is inverted):
      - tariff_mean:     mean applied tariff rate — lower = more open, so inverted
      - trade_pct_gdp:   trade as % of GDP — higher = more integrated
      - dta_depth:       World Bank DTA 2.0 depth score — higher = deeper agreements
      - desta_design:    DESTA institutional design score — higher = better designed
      - rta_count:       number of RTAs in force — higher = broader engagement

    Implementation measures (higher raw = better implementation):
      - rule_of_law:         WGI Rule of Law estimate
      - regulatory_quality:  WGI Regulatory Quality estimate
      - govt_effectiveness:  WGI Government Effectiveness estimate
      - control_corruption:  WGI Control of Corruption estimate
      - wto_dispute_rate:    WTO DSB cases as respondent per year — lower = better, so inverted
      - isds_rate:           ISDS cases per year — lower = better, so inverted
      - gta_distortion_ratio: distorting interventions / total GTA interventions — lower = better, inverted
      - ntm_coverage:        NTM coverage ratio — lower = less friction, inverted
      - stc_count:           STCs filed against the country per year — lower = better, inverted
    """
    COMMITMENT_MEASURES = {
        "tariff_mean":    {"invert": True},
        "trade_pct_gdp":  {"invert": False},
        "dta_depth":      {"invert": False},
        "desta_design":   {"invert": False},
        "rta_count":      {"invert": False},
    }

    IMPLEMENTATION_MEASURES = {
        "rule_of_law":          {"invert": False},
        "regulatory_quality":   {"invert": False},
        "govt_effectiveness":   {"invert": False},
        "control_corruption":   {"invert": False},
        "wto_dispute_rate":     {"invert": True},
        "isds_rate":            {"invert": True},
        "gta_distortion_ratio": {"invert": True},
        "ntm_coverage":         {"invert": True},
        "stc_count":            {"invert": True},
    }

    result = df.copy()

    for col, opts in {**COMMITMENT_MEASURES, **IMPLEMENTATION_MEASURES}.items():
        norm_col = f"{col}_norm"
        if col in result.columns:
            result[norm_col] = normalise(result[col].fillna(result[col].median()), invert=opts["invert"])
        else:
            result[norm_col] = np.nan

    commitment_cols = [f"{c}_norm" for c in COMMITMENT_MEASURES if f"{c}_norm" in result.columns and result[f"{c}_norm"].notna().any()]
    implementation_cols = [f"{c}_norm" for c in IMPLEMENTATION_MEASURES if f"{c}_norm" in result.columns and result[f"{c}_norm"].notna().any()]

    result["commitment_score"] = result[commitment_cols].mean(axis=1).round(1)
    result["implementation_score"] = result[implementation_cols].mean(axis=1).round(1)
    result["gap_score"] = (result["commitment_score"] - result["implementation_score"]).round(1)

    result["data_completeness"] = (
        result[[c.replace("_norm", "") for c in commitment_cols + implementation_cols]]
        .notna().sum(axis=1)
    )
    result["limited_data"] = result["data_completeness"] < 6

    result["quadrant"] = result.apply(_assign_quadrant, axis=1)

    return result


def _assign_quadrant(row: pd.Series) -> str:
    c = row.get("commitment_score", np.nan)
    i = row.get("implementation_score", np.nan)
    if pd.isna(c) or pd.isna(i):
        return "Insufficient data"
    high_c, high_i = c >= 50, i >= 50
    if high_c and high_i:
        return "Strong performer"
    if high_c and not high_i:
        return "Over-committed"
    if not high_c and high_i:
        return "Quiet complier"
    return "Disengaged"


def tooltip_text(row: pd.Series) -> str:
    q = row.get("quadrant", "—")
    interpretations = {
        "Strong performer":    "Deep agreements, strong implementation — low investment risk",
        "Over-committed":      "Ambitious agreements, poor follow-through — elevated investment risk",
        "Quiet complier":      "Limited agreements but reliable within them — moderate risk",
        "Disengaged":          "Shallow integration and weak compliance — high investment risk",
        "Insufficient data":   "Insufficient data to score",
    }
    return interpretations.get(q, "—")
