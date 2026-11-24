"""
Compute percentage breakdowns for Mission Alignment, Job Satisfaction,
and Personal Drivers (UWES-3) from the 2026 Taiwan Helpers' Needs Survey CSV.
"""

import argparse
import json
import numpy as np
import pandas as pd

DISTRESS_MAP = {
    "完全沒有": 0,
    "輕微": 1,
    "中等": 2,
    "嚴重": 3,
    "非常嚴重": 4,
}

PROQOL_MAP = {
    "從未有過": 1,
    "很少": 2,
    "有些時候": 3,
    "經常如此": 4,
    "總是如此": 5,
}

UWES_MAP = {
    "從未": 1,
    "幾乎從不": 2,
    "很少": 3,
    "有時": 4,
    "經常": 5,
    "非常經常": 6,
    "總是": 7,
}


def coalesce_pair(df: pd.DataFrame, col_idx_1: int, col_idx_2: int, mapping: dict) -> pd.Series:
    s1 = df.iloc[:, col_idx_1].map(lambda x: mapping.get(str(x).strip(), np.nan) if pd.notna(x) else np.nan)
    s2 = df.iloc[:, col_idx_2].map(lambda x: mapping.get(str(x).strip(), np.nan) if pd.notna(x) else np.nan)
    return pd.to_numeric(s1.combine_first(s2), errors="coerce")


def pct_row(label: str, count: int, total: int) -> dict:
    return {
        "category": label,
        "n": int(count),
        "total_n": int(total),
        "pct": round(float(count / total * 100.0), 1) if total > 0 else 0.0,
    }


def compute_breakdowns(csv_path: str) -> dict:
    raw = pd.read_csv(csv_path)

    # 1. Mission Alignment via Column 17 (mismatch distress: 0 = no distress / aligned .. 4 = very severe mismatch)
    c17_series = raw.iloc[:, 17].dropna().astype(str).str.strip()
    c17_num = c17_series[c17_series.isin(DISTRESS_MAP.keys())].map(DISTRESS_MAP).astype(int)
    n_ma = int(len(c17_num))

    ma_tiers = [
        pct_row("Closely aligned / no mismatch distress (0: 完全沒有)", int((c17_num == 0).sum()), n_ma),
        pct_row("Mild mismatch distress (1: 輕微)", int((c17_num == 1).sum()), n_ma),
        pct_row("Moderate mismatch distress (2: 中等)", int((c17_num == 2).sum()), n_ma),
        pct_row("High/severe mismatch distress (3-4: 嚴重/非常嚴重)", int((c17_num >= 3).sum()), n_ma),
        pct_row("Combined low/no mismatch (0-1: 完全沒有/輕微)", int((c17_num <= 1).sum()), n_ma),
        pct_row("Combined moderate+ mismatch (2-4: 中等/嚴重/非常嚴重)", int((c17_num >= 2).sum()), n_ma),
    ]

    # 2. Job Satisfaction (ProQOL Compassion Satisfaction mean 1-5)
    cs1 = coalesce_pair(raw, 51, 93, PROQOL_MAP)
    cs2 = coalesce_pair(raw, 53, 95, PROQOL_MAP)
    cs3 = coalesce_pair(raw, 57, 99, PROQOL_MAP)
    js_mean = pd.concat([cs1, cs2, cs3], axis=1).mean(axis=1).dropna()
    n_js = int(len(js_mean))

    js_tiers = [
        pct_row("High satisfaction (mean >= 4.0)", int((js_mean >= 4.0).sum()), n_js),
        pct_row("Moderate satisfaction (3.0 <= mean < 4.0)", int(((js_mean >= 3.0) & (js_mean < 4.0)).sum()), n_js),
        pct_row("Low satisfaction (mean < 3.0)", int((js_mean < 3.0).sum()), n_js),
    ]

    # 3. Personal Drivers / Inner Drive (UWES-3 mean 1-7)
    u1 = coalesce_pair(raw, 32, 73, UWES_MAP)
    u2 = coalesce_pair(raw, 33, 74, UWES_MAP)
    u3 = coalesce_pair(raw, 34, 75, UWES_MAP)
    id_mean = pd.concat([u1, u2, u3], axis=1).mean(axis=1).dropna()
    n_id = int(len(id_mean))

    id_tiers = [
        pct_row("High / frequent engagement (mean >= 5.0)", int((id_mean >= 5.0).sum()), n_id),
        pct_row("Moderate engagement (3.5 <= mean < 5.0)", int(((id_mean >= 3.5) & (id_mean < 5.0)).sum()), n_id),
        pct_row("Lower / infrequent engagement (mean < 3.5)", int((id_mean < 3.5).sum()), n_id),
    ]

    return {
        "mission_alignment_breakdown": ma_tiers,
        "job_satisfaction_breakdown": js_tiers,
        "personal_drivers_uwes_breakdown": id_tiers,
    }


def main():
    parser = argparse.ArgumentParser(description="Percentage breakdowns for MA, JS, and Personal Drivers.")
    parser.add_argument("--input", required=True, help="Path to survey CSV")
    parser.add_argument("--out-json", default="percentage_breakdowns.json", help="Output JSON path")
    args = parser.parse_args()

    res = compute_breakdowns(args.input)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    for key, rows in res.items():
        print(f"\n--- {key} ---")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()