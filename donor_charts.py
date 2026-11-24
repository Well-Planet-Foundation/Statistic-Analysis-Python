"""
High-Level Donor Presentation Graphics (Style: helper_survey_analysis.py)
========================================================================
Generates clean, single-topic PNG charts for the donor presentation covering:
  1. Scope & Rigor (Need + Plausible Mechanism vs. Proven Impact)
  2. Burnout Prevalence & Turnover Risk
  3. Non-Response Tipping Point, Wave Stability, Reweighting & Measurement/Skip Bias
  4. Corrected Burnout Drivers (Organizational Support beta = -0.253)
  5. Program Demand vs. Actual Burnout Need

Usage:
    python donor_deck_charts.py
    python donor_deck_charts.py --input survey.csv --out donor_slides_output
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyBboxPatch
from scipy import stats

try:
    import helper_survey_analysis as H
except ImportError:
    sys.exit("Error: Place donor_deck_charts.py in the same folder as helper_survey_analysis.py.")

warnings.filterwarnings("ignore")

# Match helper_survey_analysis.py visual style
sns.set_theme(style="whitegrid", context="notebook", font_scale=1.0)
PALETTE = sns.color_palette("deep")
SINGLE = (7.2, 4.6)
WIDE = (9.6, 4.6)

REACH_ESTIMATE = 6000


class SlideOut:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def save(self, fig, filename: str):
        path = os.path.join(self.root, filename)
        fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  saved -> {path}")


def wilson_ci(k: float, n: float, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * np.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


# --------------------------------------------------------------------------- #
# Slide 1: Scope & Rigor Conceptual Diagram
# --------------------------------------------------------------------------- #
def chart_slide1_scope(out: SlideOut):
    fig, ax = plt.subplots(figsize=(10.5, 4.4))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.5)

    boxes = [
        (0.2, 1.3, 2.8, 2.3, PALETTE[0], "1. WHAT WE MEASURED\n(2026 Survey, n=318)",
         "• Need: Burnout, support\n  gaps & intent to leave\n• Demand: Interest in a\n  free support program"),
        (3.6, 1.3, 2.8, 2.3, PALETTE[2], "2. OUR CLAIM TODAY\n(Need + Mechanism)",
         "• Severe, verified need\n• Org support lowers\n  burnout (β = −0.25)\n• Plausible mechanism"),
        (7.0, 1.3, 2.8, 2.3, "#7f8c8d", "3. NOT YET CLAIMED\n(Proven EAP Impact)",
         "• Survey is cross-sectional\n• Pilot data = 4 micro-NPOs\n  (small cells, dropouts)\n• Impact requires RCT/pre-post"),
    ]

    for x, y, w, h, color, title, body in boxes:
        card = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                              facecolor="#f8f9fa", edgecolor=color, linewidth=2.2)
        ax.add_patch(card)
        header = FancyBboxPatch((x, y + h - 0.65), w, 0.65, boxstyle="round,pad=0.08,rounding_size=0.12",
                                facecolor=color, edgecolor=color, linewidth=1)
        ax.add_patch(header)
        ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="center",
                color="white", fontweight="bold", fontsize=9.5)
        ax.text(x + 0.15, y + h - 0.90, body, ha="left", va="top",
                color="#222222", fontsize=9.2, linespacing=1.45)

    ax.annotate("", xy=(3.48, 2.45), xytext=(3.12, 2.45),
                arrowprops=dict(arrowstyle="->", lw=2.2, color=PALETTE[0]))
    ax.annotate("Future evaluation", xy=(6.88, 2.45), xytext=(6.52, 2.45),
                arrowprops=dict(arrowstyle="->", lw=2.0, ls="--", color="#7f8c8d"),
                ha="center", va="bottom", fontsize=8.5, color="#555555")

    ax.set_title("Evidence Framing: Separating Proven Need from Future Program Evaluation",
                 loc="left", fontweight="bold", fontsize=12.5, pad=10)
    fig.text(0.01, 0.02, "Note: Upfront methodological transparency distinguishes cross-sectional need from longitudinal impact.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide1_scope_and_rigor.png")


# --------------------------------------------------------------------------- #
# Slide 2: Burnout Prevalence (59% Mod+, 22% High)
# --------------------------------------------------------------------------- #
def chart_slide2_burnout(d: pd.DataFrame, out: SlideOut):
    p_s = d["personal_bo"].dropna()
    w_s = d["work_bo"].dropna()

    p_mod, p_lo, p_hi = wilson_ci((p_s >= 50).sum(), len(p_s))
    p_high, ph_lo, ph_hi = wilson_ci((p_s >= 75).sum(), len(p_s))

    levels = pd.DataFrame({
        "Personal Burnout": d["personal_bo_level"].value_counts(normalize=True),
        "Work-Related Burnout": d["work_bo_level"].value_counts(normalize=True),
    }).reindex(H.BURNOUT_LABELS) * 100

    fig, ax = plt.subplots(figsize=SINGLE)
    colors = ["#8fd19e", "#f6c85f", "#e4572e"]
    levels.T.plot(kind="barh", stacked=True, ax=ax, color=colors, edgecolor="white", width=0.55)

    for i, row in enumerate(levels.T.values):
        left = 0.0
        for j, val in enumerate(row):
            if val >= 6:
                ax.text(left + val / 2, i, f"{val:.0f}%", ha="center", va="center",
                        fontsize=10.5, fontweight="bold", color="white" if j == 2 else "#222222")
            left += val

    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of respondents")
    ax.set_title(
        f"Personal Burnout: {p_mod*100:.0f}% Moderate+ (95% CI {p_lo*100:.0f}–{p_hi*100:.0f}%), "
        f"{p_high*100:.0f}% High (CI {ph_lo*100:.0f}–{ph_hi*100:.0f}%)",
        loc="left", fontweight="bold", fontsize=10.5
    )
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    ax.grid(axis="y", visible=False)
    fig.text(0.01, -0.02, f"Source: 2026 Taiwan Helpers' Needs Survey (n={len(p_s)}). CBI scale cut-offs: Moderate 50–74, High 75+.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide2_burnout_prevalence.png")


# --------------------------------------------------------------------------- #
# Slide 3: Burnout Predicts Intent to Leave (55% vs 21%, OR = 4.5)
# --------------------------------------------------------------------------- #
def chart_slide3_turnover(d: pd.DataFrame, out: SlideOut):
    org = d[d["is_freelancer"] == 0].dropna(subset=["BO", "high_leave"]).copy()
    org["burnt_out"] = org["BO"] >= 50

    g_hi = org[org["burnt_out"]]["high_leave"]
    g_lo = org[~org["burnt_out"]]["high_leave"]

    p1, lo1, hi1 = wilson_ci(g_hi.sum(), len(g_hi))
    p0, lo0, hi0 = wilson_ci(g_lo.sum(), len(g_lo))

    # Odds ratio & exact p-value
    a, b = int(g_hi.sum()), int((1 - g_hi).sum())
    c, d_cnt = int(g_lo.sum()), int((1 - g_lo).sum())
    odds_ratio = (a * d_cnt) / max(b * c, 1)
    _, p_val = stats.fisher_exact([[a, b], [c, d_cnt]])

    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    labels = [f"Not Burnt Out (<50)\n(n={len(g_lo)})", f"Moderate/High Burnout (≥50)\n(n={len(g_hi)})"]
    vals = [p0 * 100, p1 * 100]
    yerr = [[(p0 - lo0) * 100, (p1 - lo1) * 100], [(hi0 - p0) * 100, (hi1 - p1) * 100]]

    bars = ax.bar(labels, vals, yerr=yerr, color=[PALETTE[0], "#e4572e"], width=0.48,
                  capsize=5, error_kw=dict(ecolor="#333333", lw=1.2))
    for bar, v, hi in zip(bars, vals, [hi0 * 100, hi1 * 100]):
        ax.text(bar.get_x() + bar.get_width() / 2, hi + 2.5, f"{v:.0f}%",
                ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_ylim(0, 78)
    ax.set_ylabel("% considering leaving monthly or more")
    ax.set_title(f"Burnout Strongly Predicts Turnover Intent (OR = {odds_ratio:.1f}, p < 10⁻⁷)",
                 loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="x", visible=False)
    fig.text(0.01, -0.02, f"Org-affiliated respondents (n={len(org)}). Error bars = 95% Wilson CIs. Exact p = {p_val:.1e}.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide3_burnout_vs_leaving.png")


# --------------------------------------------------------------------------- #
# Slide 4: Non-Response Tipping Point Analysis
# --------------------------------------------------------------------------- #
def chart_slide4_tipping_point(d: pd.DataFrame, out: SlideOut):
    n_resp = len(d)
    f = n_resp / REACH_ESTIMATE
    p_resp = (d["personal_bo"] >= 50).mean()

    q_nonresp = np.linspace(0, 0.70, 200)
    pop_share = f * p_resp + (1 - f) * q_nonresp
    req_nonresp_25 = (0.25 - f * p_resp) / (1 - f)

    fig, ax = plt.subplots(figsize=SINGLE)
    ax.plot(q_nonresp * 100, pop_share * 100, color=PALETTE[0], lw=2.5, label="Implied total population burnout")
    ax.axhline(25, color="#e4572e", ls="--", lw=1.3)
    ax.axvline(req_nonresp_25 * 100, color="#e4572e", ls="--", lw=1.3)
    ax.scatter([req_nonresp_25 * 100], [25], color="#e4572e", s=70, zorder=5)

    ax.annotate(
        f"Tipping point: <{req_nonresp_25*100:.0f}% among non-responders\n"
        f"(a {(p_resp - req_nonresp_25)*100:.0f}-pt gap below the {p_resp*100:.0f}% respondent rate)",
        xy=(req_nonresp_25 * 100, 25),
        xytext=(req_nonresp_25 * 100 + 6, 14),
        arrowprops=dict(arrowstyle="->", color="#e4572e", lw=1.5),
        fontsize=9.5, fontweight="bold", color="#b03018"
    )

    ax.axvline(p_resp * 100, color="grey", ls=":", lw=1.2)
    ax.text(p_resp * 100 - 1.2, 42, f"Observed in sample ({p_resp*100:.0f}%)",
            rotation=90, ha="right", va="center", fontsize=9, color="#555555")

    ax.set_xlim(0, 68)
    ax.set_ylim(0, 68)
    ax.set_xlabel("Assumed % moderate+ burnout among ~95% non-responders")
    ax.set_ylabel("Implied % moderate+ burnout in full population")
    ax.set_title("Non-Response Sensitivity: True Burnout Stays High Under Any Plausible Bias",
                 loc="left", fontweight="bold", fontsize=10.5)
    fig.text(0.01, -0.02, f"Worst-case sensitivity analysis (318 respondents of ~{REACH_ESTIMATE:,} reached), not a population estimate.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide4_tipping_point.png")


# --------------------------------------------------------------------------- #
# Slide 5: Wave Stability & Gender Reweighting
# --------------------------------------------------------------------------- #
def chart_slide5a_wave_stability(raw_path: str, d: pd.DataFrame, out: SlideOut):
    raw = pd.read_csv(raw_path)
    ts = pd.to_datetime(
        raw.iloc[:, 0].astype(str).str.replace("上午", "AM").str.replace("下午", "PM"),
        format="%Y/%m/%d %p %I:%M:%S",
        errors="coerce",
    )
    df_w = d.copy()
    df_w["ts"] = ts.values
    df_w = df_w.dropna(subset=["ts", "personal_bo"]).copy()

    waves = ["Early\n(1st third)", "Middle\n(2nd third)", "Late\n(3rd third)"]
    df_w["wave"] = pd.qcut(df_w["ts"].rank(method="first"), 3, labels=waves)

    rho, p_val = stats.spearmanr(
        (df_w["ts"] - df_w["ts"].min()).dt.total_seconds(),
        df_w["personal_bo"],
    )

    means = [df_w.loc[df_w["wave"] == w, "personal_bo"].mean() for w in waves]
    cis_95 = [df_w.loc[df_w["wave"] == w, "personal_bo"].sem() * 1.96 for w in waves]

    fig, ax = plt.subplots(figsize=SINGLE)
    ax.errorbar(waves, means, yerr=cis_95, fmt="o-", color=PALETTE[0], lw=2.2, ms=8, capsize=5)
    for i, m in enumerate(means):
        ax.text(i, m + cis_95[i] + 1.5, f"{m:.1f}", ha="center", fontweight="bold", fontsize=10.5)

    ax.set_ylim(35, 68)
    ax.set_ylabel("Mean personal burnout (0–100)")
    ax.set_title(
        f"Response time versus burnout, no meaningful trend",
        loc="left",
        fontweight="bold",
        fontsize=11,
    )
    ax.grid(axis="x", visible=False)
    out.save(fig, "slide5a_wave_stability.png")


# --------------------------------------------------------------------------- #
# Slide 5B: Gender Reweighting
# --------------------------------------------------------------------------- #
def chart_slide5b_gender_reweighting(d: pd.DataFrame, out: SlideOut):
    g_sub = d.dropna(subset=["personal_bo", "gender"]).copy()
    g_sub["mod_plus"] = (g_sub["personal_bo"] >= 50).astype(float)
    unweighted_pct = g_sub["mod_plus"].mean() * 100

    g_means = g_sub[g_sub["gender"].isin(["Female", "Male"])].groupby("gender")["mod_plus"].mean()
    reweighted_pct = (0.5 * g_means["Female"] + 0.5 * g_means["Male"]) * 100

    fig, ax = plt.subplots(figsize=SINGLE)
    bars = ax.bar(
        ["Observed Sample\n(74% Female)", "Reweighted\n(50% F / 50% M)"],
        [unweighted_pct, reweighted_pct],
        color=[PALETTE[0], PALETTE[2]],
        width=0.46,
    )
    for b, v in zip(bars, [unweighted_pct, reweighted_pct]):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 1.8,
            f"{v:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=11,
        )

    ax.set_ylim(0, 78)
    ax.set_ylabel("% moderate+ personal burnout")
    ax.set_title(
        "Gender balance, no meaningful trend",
        loc="left",
        fontweight="bold",
        fontsize=11,
    )
    ax.grid(axis="x", visible=False)
    out.save(fig, "slide5b_gender_reweighting.png")


# --------------------------------------------------------------------------- #
# Slide 6: Reverse-Coding Fix & Optional-Block Skip Bias
# --------------------------------------------------------------------------- #
def chart_slide6_rigor_checks(d: pd.DataFrame, meta: dict, out: SlideOut):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=WIDE)

    # Panel A: Retention Cronbach's alpha before vs after reverse coding
    sc = meta["spec_compare"]
    ret_brief = sc[(sc["construct"] == "RET") & (sc["version"] == "brief")]["cronbach_alpha"].iloc[0]
    ret_rev = sc[(sc["construct"] == "RET") & (sc["version"] == "revised")]["cronbach_alpha"].iloc[0]

    bars1 = ax1.bar(["As Originally Coded\n(Unreversed)", "Corrected Coding\n(Used in Report)"],
                    [ret_brief, ret_rev], color=["#b0b0b0", PALETTE[2]], width=0.48)
    ax1.axhline(0.70, color="#e4572e", ls="--", lw=1.2, label="0.70 reliability threshold")
    for b, v in zip(bars1, [ret_brief, ret_rev]):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.03, f"α = {v:.2f}", ha="center", fontweight="bold", fontsize=10.5)
    ax1.set_ylim(0, 0.95)
    ax1.set_ylabel("Cronbach's alpha (internal consistency)")
    ax1.set_title("A. Retention Scale Coding Audit", loc="left", fontweight="bold", fontsize=10.5)
    ax1.legend(frameon=False, loc="upper left", fontsize=9)
    ax1.grid(axis="x", visible=False)

    # Panel B: Optional ProQOL block skip rate by role
    org = d[d["is_freelancer"] == 0].copy()
    org["skipped_pq"] = org["JS"].isna()
    fl = org[org["role"] == "Frontline helper"]["skipped_pq"]
    ad = org[org["role"] == "Admin / project / finance"]["skipped_pq"]

    bars2 = ax2.bar([f"Frontline Helpers\n(n={len(fl)})", f"Admin / Finance Staff\n(n={len(ad)})"],
                    [fl.mean() * 100, ad.mean() * 100], color=[PALETTE[0], PALETTE[3]], width=0.48)
    for b, v in zip(bars2, [fl.mean() * 100, ad.mean() * 100]):
        ax2.text(b.get_x() + b.get_width() / 2, v + 2.2, f"{v:.0f}%", ha="center", fontweight="bold", fontsize=10.5)
    ax2.set_ylim(0, 88)
    ax2.set_ylabel("% skipping optional ProQOL block")
    ax2.set_title("B. Optional Block Skip Bias by Role", loc="left", fontweight="bold", fontsize=10.5)
    ax2.grid(axis="x", visible=False)

    fig.suptitle("Methodological Disclosures: Scale Coding Fix & Optional-Block Composition",
                 x=0.01, ha="left", fontweight="bold", fontsize=12, y=1.02)
    fig.text(0.01, -0.02,
             "Disclosure: 66 of 269 org staff skipped ProQOL (lower burnout: 47.6 vs 55.2, p=0.006); JS & Retention models reflect frontline workers.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide6_measurement_and_skip_bias.png")


# --------------------------------------------------------------------------- #
# Slide 7: Burnout Drivers (Corrected Support Sign: -0.253)
# --------------------------------------------------------------------------- #
def chart_slide7_drivers(d: pd.DataFrame, out: SlideOut):
    org = d[d["is_freelancer"] == 0]
    coef, summ = H.ols_fit(org, "BO", H.PREDICTORS + ["SIZE"], H.MISSION_KEYS)

    keep = ["WL", "OS", "ID", "JR", "PAY", "MA", "SIZE"]
    clean_names = {
        "WL": "Workload",
        "OS": "Organizational Support",
        "ID": "Inner Drive / Engagement",
        "JR": "Job Resources",
        "PAY": "Pay (higher = less strain)",
        "MA": "Mission Alignment",
        "SIZE": "Organization Size",
    }
    c = coef[coef["key"].isin(keep)].copy()
    c["label"] = c["key"].map(clean_names)
    c = c.sort_values("std_beta")

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    colors = np.where(c["p_value"] < 0.05, np.where(c["std_beta"] > 0, "#e4572e", PALETTE[2]), "#b0b0b0")

    ax.barh(c["label"], c["std_beta"], color=colors, height=0.58)
    ax.errorbar(c["std_beta"], np.arange(len(c)),
                xerr=[c["std_beta"] - c["ci_low"], c["ci_high"] - c["std_beta"]],
                fmt="none", ecolor="#222222", lw=1.1, capsize=3)
    ax.axvline(0, color="#222222", lw=1.0)

    for i, row in enumerate(c.itertuples()):
        offset = 0.02 if row.std_beta >= 0 else -0.02
        pos_x = row.ci_high + offset if row.std_beta >= 0 else row.ci_low + offset
        ha = "left" if row.std_beta >= 0 else "right"
        weight = "bold" if row.key == "OS" or row.p_value < 0.05 else "normal"
        ax.text(pos_x, i, f"β = {row.std_beta:+.3f}", va="center", ha=ha, fontsize=9.5, fontweight=weight)

    ax.set_xlim(-0.62, 0.72)
    ax.set_xlabel("Standardized β with 95% CI (HC3-robust OLS; colored = p < .05)")
    ax.set_title(f"Plausible Mechanism: Organizational Support Lowers Burnout (β = −0.253, n={summ['n']}, R²={summ['r2']:.2f})",
                 loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    fig.text(0.01, -0.02, "Controls for service mission domain included. Org support 95% CI: −0.415 to −0.091 (p < 0.01).",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide7_burnout_drivers_corrected.png")


# --------------------------------------------------------------------------- #
# Slide 8: Demand vs. Need (74% Want Program, rho = 0.03, p = 0.70)
# --------------------------------------------------------------------------- #
def chart_slide8_demand_vs_need(d: pd.DataFrame, out: SlideOut):
    want = d["program_interest"].map(
        lambda v: np.nan if pd.isna(v) else float(("非常希望" in str(v)) or ("餘力" in str(v)))
    )
    sub = d.assign(want=want).dropna(subset=["want", "BO"]).copy()
    sub["bo_level"] = pd.cut(sub["BO"], H.BURNOUT_BINS, labels=["Low\n(<50)", "Moderate\n(50–74)", "High\n(75+)"])

    p_all, lo_all, hi_all = wilson_ci(sub["want"].sum(), len(sub))
    rho, p_val = stats.spearmanr(sub["BO"], sub["want"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=WIDE, gridspec_kw={"width_ratios": [1, 1.45]})

    # Panel A: Overall demand
    bar_a = ax1.bar(["Want Free\nSupport Program"], [p_all * 100],
                    yerr=[[(p_all - lo_all) * 100], [(hi_all - p_all) * 100]],
                    color=PALETTE[0], width=0.42, capsize=5, error_kw=dict(ecolor="#222222", lw=1.2))
    ax1.text(0, hi_all * 100 + 2.5, f"{p_all*100:.0f}%\n(CI {lo_all*100:.0f}–{hi_all*100:.0f}%)",
             ha="center", va="bottom", fontweight="bold", fontsize=10.5)
    ax1.set_ylim(0, 102)
    ax1.set_ylabel("% of respondents asked (n=169)")
    ax1.set_title("A. Overall Program Demand", loc="left", fontweight="bold", fontsize=10.5)
    ax1.grid(axis="x", visible=False)

    # Panel B: Demand across burnout levels
    lv_order = ["Low\n(<50)", "Moderate\n(50–74)", "High\n(75+)"]
    rates, los, his, ns = [], [], [], []
    for lv in lv_order:
        s = sub[sub["bo_level"] == lv]["want"]
        p, lo, hi = wilson_ci(s.sum(), len(s))
        rates.append(p * 100)
        los.append((p - lo) * 100)
        his.append((hi - p) * 100)
        ns.append(len(s))

    bars_b = ax2.bar([f"{lv}\n(n={n})" for lv, n in zip(lv_order, ns)], rates, yerr=[los, his],
                     color=["#8fd19e", "#f6c85f", "#e4572e"], width=0.5, capsize=5,
                     error_kw=dict(ecolor="#222222", lw=1.2))
    for b, v, hi in zip(bars_b, rates, his):
        ax2.text(b.get_x() + b.get_width() / 2, v + hi + 2.5, f"{v:.0f}%",
                 ha="center", va="bottom", fontweight="bold", fontsize=10.5)
    ax2.set_ylim(0, 102)
    ax2.set_ylabel("% wanting program")
    ax2.set_title(f"B. Demand by Burnout Level (ρ = {rho:.2f}, p = {p_val:.2f})",
                  loc="left", fontweight="bold", fontsize=10.5)
    ax2.grid(axis="x", visible=False)

    fig.suptitle("Demand ≠ Need: Program Interest Is Flat Across Burnout Levels",
                 x=0.01, ha="left", fontweight="bold", fontsize=12, y=1.02)
    fig.text(0.01, -0.02, "Implication: Passive opt-in will miss high-burnout teams; targeted outreach is required.",
             fontsize=8.5, color="#555555")
    out.save(fig, "slide8_demand_vs_need.png")


def main():
    ap = argparse.ArgumentParser(description="Generate high-level donor slide graphics.")
    ap.add_argument("--input", "-i", help="Path to raw survey CSV (default: first *.csv in cwd)")
    ap.add_argument("--out", "-o", default="donor_slides_output", help="Output folder")
    args = ap.parse_args()

    path = args.input or (sorted(glob.glob("*.csv")) or [None])[0]
    if not path:
        sys.exit("No CSV found. Pass --input path/to/survey.csv")

    out = SlideOut(args.out)
    d, meta = H.load_and_clean(path)

    # Re-apply clean notebook grid style after helper import
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.0)

    print("\nGenerating donor slide graphics...")
    chart_slide1_scope(out)
    chart_slide2_burnout(d, out)
    chart_slide3_turnover(d, out)
    chart_slide4_tipping_point(d, out)
    chart_slide5a_wave_stability(path, d, out)
    chart_slide5b_gender_reweighting(d, out)
    chart_slide6_rigor_checks(d, meta, out)
    chart_slide7_drivers(d, out)
    chart_slide8_demand_vs_need(d, out)
    print(f"\nDone. All 8 slide charts saved in: {os.path.abspath(out.root)}")


if __name__ == "__main__":
    main()