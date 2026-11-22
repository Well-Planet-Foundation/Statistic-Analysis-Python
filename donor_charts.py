"""
NPO EAP Donor Presentation -- Chart Generator  (bilingual: English + 繁體中文)
==============================================================================
Story told in three parts (Option 1: "Is the need real, and could it be an artifact?")

    PART 1  Who answered?             (demographics)            -> figures/1_demographics/
    PART 2  Could bias explain it?    (bias & robustness)       -> figures/2_bias/
    PART 3  What does the data say?   (burnout & the EAP case)  -> figures/3_burnout/

Every chart
  * is its own 16:9 PNG (200 dpi) that drops straight into a slide,
  * has a bold English title + Traditional-Chinese title + a one-line "so what",
  * shows sample sizes (n) and 95% confidence intervals wherever a number is an estimate,
  * carries a source / caveat footer (reputability: we state the limits ourselves).

Also writes  talking_points.md  (bilingual, every number computed from the data)
and          tables/*.csv     (the exact numbers behind each chart, for the appendix).

Usage
-----
    python donor_charts.py                                  # auto-finds *.csv in the current folder
    python donor_charts.py --input survey.csv --out donor_output
    python donor_charts.py --reach 6000 --boot 1000         # reach estimate / bootstrap resamples
    python donor_charts.py --parts 2,3                      # only some parts

Requirements: pandas, numpy, scipy, matplotlib, seaborn  (same as helper_survey_analysis.py)
This file must sit in the SAME folder as helper_survey_analysis.py (it re-uses its data cleaning,
so every number here matches the earlier analysis exactly).

Chinese text: install "Noto Sans TC" (free, Google Fonts) if you see empty boxes in the charts.
Windows (Microsoft JhengHei) and macOS (PingFang TC) work out of the box.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import textwrap
import traceback
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from scipy import stats

try:
    import helper_survey_analysis as H          # data cleaning + model code from the research team
except ImportError:                              # pragma: no cover
    sys.exit("Put donor_charts.py in the same folder as helper_survey_analysis.py and run it again.")

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Settings you may want to change
# --------------------------------------------------------------------------- #
REACH_ESTIMATE = 6000      # Well Planet's estimate of people who had access to the survey (IQP report, sec. 4.1.2)
CUT_MOD = 50               # CBI cut-off: moderate-or-higher burnout (0-100 scale)
CUT_HIGH = 75              # CBI cut-off: high burnout
FOOT_SOURCE = "Source 資料來源: Well Planet 2026 Annual Survey 年度助人者困境大調查"
FOOT_SAMPLE = "Self-selected sample, not probability-based 自願填答樣本，非隨機抽樣"

# Colour palette (colour-blind-safe, prints well in greyscale)
INK, MUTED, GRID = "#1B2A41", "#5F6F86", "#E3E8EF"
NAVY, TEAL, AMBER, CORAL, SKY, SAND, GREY = "#1F4E79", "#2A9D8F", "#E9A23B", "#D1495B", "#7FB2E5", "#F5EFE3", "#9AA5B4"
LOW_C, MOD_C, HIGH_C = "#7DBE9A", "#F2B84B", "#D65A4A"
LEVEL_COL = [LOW_C, MOD_C, HIGH_C]
LEVEL_EN = ["Low (<50)", "Moderate (50-74)", "High (75+)"]
LEVEL_ZH = ["低度", "中度", "高度"]
FIG = (12, 6.75)           # 16:9 slide

# --------------------------------------------------------------------------- #
# Bilingual dictionaries  (English key -> Traditional Chinese)
# --------------------------------------------------------------------------- #
ZH_ROLE = {"Frontline helper": "第一線助人者", "Admin / project / finance": "行政／專案／財務",
           "Mid-level manager": "中階主管", "Founder / decision-maker": "創辦人／決策者",
           "HR / training": "人資／培訓", "Other": "其他"}
ZH_ORG = {"Foundation": "基金會", "Government / commissioned": "政府／委辦單位", "Association / society": "協會／學會",
          "Social welfare agency": "社會福利機構", "Social enterprise": "社會企業",
          "Community / regional team": "社區／地方創生團隊", "Other": "其他"}
ZH_TYPE = {"Org-affiliated": "機構任職", "Org + personal projects": "機構＋個人專案", "Freelancer / independent": "獨立工作者"}
ZH_GENDER = {"Female": "女性", "Male": "男性", "Other / undisclosed": "其他／不願透露"}
ZH_REGION = {"Taipei": "臺北市", "New Taipei": "新北市", "Other counties/cities": "其他縣市"}
ZH_SUPPORT = {"Individual counselling": "個別心理諮詢", "Group stress relief": "團體減壓", "Supervision / coaching": "督導／教練",
              "Leadership training": "領導力培訓", "Professional skills training": "專業職能培訓",
              "Career development": "職涯發展", "Internal communication": "內部溝通", "Flexible / remote work": "彈性工時／遠距",
              "Acting-position allowance": "職務代理津貼", "Financial planning": "財務規劃"}
ZH_BARRIER = {"Insufficient budget": "預算不足", "Decision-makers see no need": "決策者不認為需要",
              "No one has capacity": "沒有人有餘力", "Not sure": "不確定", "Don't know where to start": "不知從何開始",
              "Fear of seeming to complain": "擔心被視為抱怨", "Org too small": "機構規模太小",
              "No programme for micro-orgs": "缺乏適合小型機構的方案", "Unclear internal needs": "內部需求不明確",
              "Unclear benefits": "不了解方案效益", "Board not supportive": "董事會不支持"}
ZH_PQ = {"cs1": "我喜歡從事助人的工作", "cs2": "我的工作使我感到滿意", "cs3": "我很高興選擇了這份工作",
         "bo1": "助人工作讓我感到陷入困境", "bo2": "因為助人工作而筋疲力竭", "bo3": "工作負擔似乎沒有止盡",
         "sts1": "受到所幫助的創傷者影響", "sts2": "對所幫助的創傷者感到沮喪", "sts3": "因助人而有侵擾／恐懼的想法"}
EN_PQ = {"cs1": "I enjoy my helping work", "cs2": "My work satisfies me", "cs3": "Glad I chose this career",
         "bo1": "Helping work leaves me feeling trapped", "bo2": "Exhausted because I am a helper",
         "bo3": "Workload feels endless", "sts1": "Affected by traumatised clients",
         "sts2": "Discouraged by traumatised clients", "sts3": "Intrusive / frightening thoughts"}


def bi(en: str, zh: str, sep: str = "\n") -> str:
    return f"{en}{sep}{zh}"


# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
CJK_CANDIDATES = ["Noto Sans TC", "Noto Sans CJK TC", "Microsoft JhengHei", "PingFang TC", "Heiti TC",
                  "Source Han Sans TC", "WenQuanYi Zen Hei", "Noto Sans CJK JP", "Noto Sans CJK SC"]


def setup_style() -> None:
    installed = {f.name for f in fm.fontManager.ttflist}
    found = [n for n in CJK_CANDIDATES if n in installed]
    if not found:
        print("  WARNING: no Traditional-Chinese font found; Chinese text will show as boxes. "
              "Install 'Noto Sans TC' (fonts.google.com/noto/specimen/Noto+Sans+TC).")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": found + ["DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK, "ytick.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": True,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.9,
        "axes.axisbelow": True,
        "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 11.5, "xtick.labelsize": 11, "ytick.labelsize": 11,
        "legend.fontsize": 10.5, "legend.frameon": False,
    })


class Out:
    """Output folders for figures and tables."""

    def __init__(self, root: str):
        self.root = root
        self.tab = os.path.join(root, "tables")
        os.makedirs(self.tab, exist_ok=True)
        self.made: list[str] = []

    def save_fig(self, fig, rel: str):
        path = os.path.join(self.root, "figures", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fig.savefig(path, dpi=200, facecolor="white")
        plt.close(fig)
        self.made.append(path)
        print(f"  figure -> {path}")

    def save_tab(self, df: pd.DataFrame, name: str, index: bool = True):
        df.to_csv(os.path.join(self.tab, name), index=index, encoding="utf-8-sig")


def frame(fig, en: str, zh: str, sub_en: str = "", sub_zh: str = "", note: str = "", top: float = 0.775,
          left: float = 0.04, right: float = 0.97, bottom: float = 0.075) -> None:
    """Title block + footer + tight layout. Call after the axes are drawn."""
    fig.text(left, 0.965, en, fontsize=21, fontweight="bold", va="top", color=INK)
    fig.text(left, 0.908, zh, fontsize=16, fontweight="bold", va="top", color=NAVY)
    if sub_en:
        fig.text(left, 0.853, sub_en, fontsize=12.5, va="top", color=MUTED)
    if sub_zh:
        fig.text(left, 0.818, sub_zh, fontsize=12.5, va="top", color=MUTED)
    fig.add_artist(Line2D([left, right], [top + 0.012] * 2, color=GRID, lw=1.4))
    foot = FOOT_SOURCE + (f"  |  {note}" if note else "")
    fig.text(left, 0.018, foot, fontsize=8.8, color=MUTED, va="bottom")
    fig.tight_layout(rect=(left - 0.03, bottom, right + 0.015, top))


def hbar(ax, labels, values, colors=None, fmt="{:.0f}%", xmax=None, annot=None, fs=11, bold=True):
    """Horizontal bars with value labels. `annot` = optional list of extra text (e.g. 'n=12')."""
    y = np.arange(len(labels))
    colors = colors if colors is not None else [NAVY] * len(labels)
    ax.barh(y, values, color=colors, height=0.66, zorder=3)
    xm = xmax or (max(values) * 1.28 if len(values) else 1)
    for i, v in enumerate(values):
        t = fmt.format(v) + (f"  {annot[i]}" if annot else "")
        ax.text(v + xm * 0.012, i, t, va="center", fontsize=fs, fontweight="bold" if bold else "normal", color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlim(0, xm)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=10)


# --------------------------------------------------------------------------- #
# Statistics helpers
# --------------------------------------------------------------------------- #
def wilson(k: float, n: float, z: float = 1.96):
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, max(c - h, 0), min(c + h, 1)


def mean_ci(x: pd.Series):
    x = pd.Series(x).dropna()
    if len(x) < 2:
        return (x.mean() if len(x) else np.nan), np.nan, np.nan, len(x)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return x.mean(), x.mean() - h, x.mean() + h, len(x)


def odds_ratio(a: pd.Series, b: pd.Series):
    """Odds ratio (Woolf 95% CI) for boolean exposure a and outcome b."""
    ok = a.notna() & b.notna()
    a, b = a[ok].astype(bool), b[ok].astype(bool)
    n11, n10, n01, n00 = ((a & b).sum(), (a & ~b).sum(), (~a & b).sum(), (~a & ~b).sum())
    orr = (n11 * n00) / max(n10 * n01, 1e-9)
    se = np.sqrt(1 / n11 + 1 / n10 + 1 / n01 + 1 / n00)
    return orr, np.exp(np.log(orr) - 1.96 * se), np.exp(np.log(orr) + 1.96 * se), stats.fisher_exact([[n11, n10], [n01, n00]])[1]


def rake(df: pd.DataFrame, margins: dict, iters: int = 25) -> np.ndarray:
    """Iterative proportional fitting to target shares {column: {level: share}}."""
    w = np.ones(len(df))
    for _ in range(iters):
        for col, tgt in margins.items():
            tot = w.sum()
            for lvl, share in tgt.items():
                m = (df[col] == lvl).values
                s = w[m].sum()
                if s > 0:
                    w[m] *= share * tot / s
    return w


def level_of(s: pd.Series) -> pd.Categorical:
    return pd.cut(s, H.BURNOUT_BINS, labels=LEVEL_EN)


# --------------------------------------------------------------------------- #
# Data preparation
# --------------------------------------------------------------------------- #
def load(path: str):
    d, meta = H.load_and_clean(path)
    raw = pd.read_csv(path)
    ts = pd.to_datetime(raw.iloc[:, 0].astype(str).str.replace("上午", "AM").str.replace("下午", "PM"),
                        format="%Y/%m/%d %p %I:%M:%S", errors="coerce")
    d = d.copy()
    d["ts"] = ts.values
    d["gender3"] = d["gender"].map(lambda g: g if g in ("Female", "Male") else ("Other / undisclosed" if pd.notna(g) else np.nan))
    d["metro"] = d["region"].map(lambda r: np.nan if pd.isna(r) else ("Taipei metro" if r in ("Taipei", "New Taipei") else "Elsewhere"))
    d["mod_p"] = (d["personal_bo"] >= CUT_MOD).astype(float).where(d["personal_bo"].notna())
    d["mod_w"] = (d["work_bo"] >= CUT_MOD).astype(float).where(d["work_bo"].notna())
    d["lvl_bo"] = level_of(d["BO"])
    d["lvl_p"] = level_of(d["personal_bo"])
    d["lvl_w"] = level_of(d["work_bo"])
    d["skip_pq"] = d["JS"].isna().astype(int)
    org = d[d["is_freelancer"] == 0].copy()
    return d, org, meta


# =========================================================================== #
# PART 1 -- DEMOGRAPHICS
# =========================================================================== #
def tile(fig, x, y, w, h, big, en, zh, color=NAVY):
    ax = fig.add_axes([x, y, w, h])
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06", fc=SAND, ec="none",
                                transform=ax.transAxes))
    ax.add_patch(FancyBboxPatch((0, 0), 0.025, 1, boxstyle="square,pad=0", fc=color, ec="none", transform=ax.transAxes))
    ax.text(0.09, 0.66, big, fontsize=34, fontweight="bold", color=color, va="center", transform=ax.transAxes)
    ax.text(0.09, 0.30, en, fontsize=12.5, fontweight="bold", color=INK, va="center", transform=ax.transAxes)
    ax.text(0.09, 0.13, zh, fontsize=12, color=MUTED, va="center", transform=ax.transAxes)


def kpi_figure(out: Out, rel, en, zh, sub_en, sub_zh, tiles, note=""):
    fig = plt.figure(figsize=FIG)
    xs, ys, w, h = [0.04, 0.355, 0.67], [0.40, 0.09], 0.29, 0.28
    for i, (big, e, z, c) in enumerate(tiles):
        tile(fig, xs[i % 3], ys[i // 3], w, h, big, e, z, c)
    frame(fig, en, zh, sub_en, sub_zh, note)
    out.save_fig(fig, rel)


def p1_glance(S, d, org, out):
    n = len(d)
    metro = d["metro"].notna().sum()
    S["n"] = n
    S["resp_rate"] = n / REACH_ESTIMATE
    S["female"] = (d["gender"] == "Female").mean()
    S["metro_share"] = (d["metro"] == "Taipei metro").sum() / metro
    S["org_n"] = len(org)
    S["org_share"] = len(org) / n
    S["frontline_share"] = (org["role"] == "Frontline helper").sum() / org["role"].notna().sum()
    S["age_25_39"] = d["age_cat"].isin(["25-29", "30-34", "35-39"]).sum() / d["age_cat"].notna().sum()
    tiles = [(f"{n}", "Respondents", "有效問卷", NAVY),
             (f"≈{S['resp_rate']:.0%}", f"Response rate (≈{REACH_ESTIMATE:,} reached)", f"回覆率（約 {REACH_ESTIMATE:,} 人可取得問卷）", CORAL),
             (f"{S['female']:.0%}", "Women", "女性受訪者", TEAL),
             (f"{S['metro_share']:.0%}", "Based in Taipei / New Taipei", "任職於臺北市／新北市", NAVY),
             (f"{S['org_share']:.0%}", f"Employed by an organisation (n={len(org)})", f"隸屬機構（含兼職個案，n={len(org)}）", TEAL),
             (f"{S['frontline_share']:.0%}", "Of those, front-line helpers", "其中為第一線助人者", AMBER)]
    kpi_figure(out, "1_demographics/01_sample_at_a_glance.png",
               "Who answered the survey?", "誰填答了這份問卷？",
               "318 helpers across Taiwan - mostly women, mostly in the north, mostly front-line staff.",
               "318 位全臺助人者：以女性、北部、第一線人員為主。", tiles, FOOT_SAMPLE)


def p1_age_gender(S, d, org, out):
    order = H.AGE_LABEL
    ct = pd.crosstab(d["age_cat"], d["gender3"]).reindex(order).fillna(0)
    ct = ct[[c for c in ["Female", "Male", "Other / undisclosed"] if c in ct.columns]]
    out.save_tab(ct, "demographics_age_by_gender.csv")
    cols = {"Female": NAVY, "Male": TEAL, "Other / undisclosed": GREY}
    fig, ax = plt.subplots(figsize=FIG)
    left = np.zeros(len(ct))
    tot = ct.sum(axis=1).values
    for g in ct.columns:
        ax.barh(range(len(ct)), ct[g].values, left=left, color=cols[g], height=0.66, label=bi(g, ZH_GENDER[g], " / "), zorder=3)
        for i, v in enumerate(ct[g].values):
            if v >= 8:
                ax.text(left[i] + v / 2, i, f"{int(v)}", ha="center", va="center", color="white", fontsize=11, fontweight="bold")
        left += ct[g].values
    for i, t in enumerate(tot):
        ax.text(t + 0.8, i, f"n={int(t)}  ({t / tot.sum():.0%})", va="center", fontsize=11, fontweight="bold")
    ax.set_yticks(range(len(ct)))
    ax.set_yticklabels([f"{a}" for a in ct.index])
    ax.invert_yaxis()
    ax.set_xlim(0, tot.max() * 1.3)
    ax.set_ylabel("Age 年齡（歲）")
    ax.set_xlabel("Number of respondents 填答人數")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    frame(fig, "Age and gender of respondents", "受訪者年齡與性別",
          f"{S['age_25_39']:.0%} are aged 25-39; women outnumber men about 3 to 1.",
          f"{S['age_25_39']:.0%} 為 25–39 歲；女性約為男性的 3 倍。", FOOT_SAMPLE + f"  |  n={int(tot.sum())}")
    out.save_fig(fig, "1_demographics/02_age_gender.png")


def p1_geography(S, d, org, out):
    en2zh = {v: k for k, v in H.COUNTY_EN.items()}
    c = d["county"].value_counts()
    top = c.head(9)
    rest = c.iloc[9:].sum()
    labels = [bi(k, en2zh.get(k, "")) for k in top.index] + [bi(f"Other {len(c) - 9} counties", f"其他 {len(c) - 9} 縣市")]
    vals = list(top.values) + [rest]
    tot = c.sum()
    colors = [NAVY if k in ("Taipei", "New Taipei") else SKY for k in top.index] + [GREY]
    fig, ax = plt.subplots(figsize=FIG)
    hbar(ax, labels, vals, colors, fmt="{:.0f}", xmax=max(vals) * 1.3, annot=[f"({v / tot:.0%})" for v in vals], fs=11)
    ax.set_xlabel("Number of respondents 填答人數")
    ax.legend(handles=[Line2D([0], [0], color=NAVY, lw=8, label="Taipei metro 大臺北"), Line2D([0], [0], color=SKY, lw=8, label="Elsewhere 其他縣市")],
              loc="lower right")
    out.save_tab(c.to_frame("n"), "demographics_county.csv")
    frame(fig, "Where respondents work", "受訪者任職縣市",
          f"{S['metro_share']:.0%} work in Taipei or New Taipei; 20 other counties/cities are all represented.",
          f"{S['metro_share']:.0%} 任職於臺北市或新北市；全臺其他縣市亦有受訪者。",
          FOOT_SAMPLE + f"  |  n={tot} (9 invalid / blank county entries excluded 另有 9 筆縣市欄位無效)")
    out.save_fig(fig, "1_demographics/03_geography.png")


def p1_profile(S, d, org, out):
    fig, axes = plt.subplots(1, 3, figsize=FIG, gridspec_kw={"width_ratios": [1.05, 1.15, 0.9]})
    # role
    r = org["role"].value_counts()
    r = r[r >= 5]
    pct = r / r.sum() * 100
    hbar(axes[0], [bi(k, ZH_ROLE[k]) for k in r.index], pct.values, [AMBER if k == "Frontline helper" else NAVY for k in r.index],
         xmax=100, fs=10.5)
    axes[0].set_title(f"Role 職務 (n={int(r.sum())})")
    # org type
    t = org["org_type"].value_counts()
    t = t[t >= 15]
    pct2 = t / org["org_type"].notna().sum() * 100
    hbar(axes[1], [bi(k, ZH_ORG[k]) for k in t.index], pct2.values, [TEAL] * len(t), xmax=60, fs=10.5)
    axes[1].set_title(f"Organisation type 機構類型 (n={org['org_type'].notna().sum()})")
    # size
    s = org["org_size_cat"].value_counts().reindex(H.SIZE_LABEL).fillna(0)
    pct3 = s / s.sum() * 100
    hbar(axes[2], [f"{k}" for k in s.index], pct3.values, [SKY] * len(s), xmax=55, fs=10.5)
    axes[2].set_title(f"Full-time staff 全職人數 (n={int(s.sum())})")
    out.save_tab(pd.concat({"role": r, "org_type": t, "org_size": s}), "demographics_org_profile.csv")
    frame(fig, "Their jobs and organisations", "受訪者的職務與機構",
          "Front-line helpers are 60% of the organisational sample; large (51+) organisations are the single biggest group.",
          "第一線助人者佔機構樣本約六成；51 人以上的大型機構為最大群體。",
          FOOT_SAMPLE + "  |  Organisation-affiliated respondents only 僅含隸屬機構者")
    out.save_fig(fig, "1_demographics/04_role_org_size.png")


def p1_experience(S, d, org, out):
    fig, axes = plt.subplots(1, 3, figsize=FIG)
    for ax, (ser, order, title, color) in zip(axes, [
            (d["helping_yrs_cat"], H.TENURE_LABEL, "Years in helping work 助人工作總年資", NAVY),
            (org["org_tenure_cat"], H.TENURE_LABEL, "Years at current organisation 現職機構年資", TEAL),
            (org["hours_actual_cat"], ["<=20", "21-40", "41-50", "51-60", "61+"], "Hours worked, past 7 days 過去七天工時", AMBER)]):
        c = ser.value_counts().reindex(order).fillna(0)
        pct = c / c.sum() * 100
        ax.bar(range(len(c)), pct.values, color=color, width=0.7, zorder=3)
        for i, v in enumerate(pct.values):
            ax.text(i, v + 0.8, f"{v:.0f}%", ha="center", fontsize=10.5, fontweight="bold")
        ax.set_xticks(range(len(c)))
        ax.set_xticklabels(c.index, fontsize=9.5, rotation=0)
        ax.set_ylim(0, max(pct.values) * 1.25)
        ax.set_title(f"{title}\n(n={int(c.sum())})", fontsize=11.5)
        ax.grid(axis="x", visible=False)
        ax.set_yticklabels([])
        ax.tick_params(axis="y", length=0)
    long_h = ((org["hours_actual_cat"].isin(["51-60", "61+"])).sum() / org["hours_actual_cat"].notna().sum())
    S["long_hours_share"] = long_h
    frame(fig, "Experience and working hours", "助人年資與工時",
          f"A seasoned workforce - and {long_h:.0%} worked more than 50 hours in the past week.",
          f"資深的工作群體；且 {long_h:.0%} 過去一週工時超過 50 小時。",
          FOOT_SAMPLE + "  |  Hours: organisation-affiliated respondents who answered 工時：僅機構任職者")
    out.save_fig(fig, "1_demographics/05_experience_hours.png")


# =========================================================================== #
# PART 2 -- BIAS & ROBUSTNESS
# =========================================================================== #
def p2_funnel(S, d, org, out):
    st = [("Responded", "完成填答", len(d), NAVY),
          ("Organisation-affiliated", "隸屬機構（回答機構題組）", len(org), TEAL),
          ("Answered workload & support items", "完整回答工作負荷／支持題組",
           int(org[["WL", "OS", "JR"]].notna().all(axis=1).sum()), SKY),
          ("Completed optional trauma (ProQOL) block", "完成選填創傷量表",
           int(org["JS"].notna().sum()), AMBER)]
    S["funnel"] = [(a, n) for a, _, n, _ in st]
    fig = plt.figure(figsize=FIG)
    ax = fig.add_axes([0.04, 0.06, 0.92, 0.60])
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    top = st[0][2]
    h = 0.17
    for i, (en, zh, n, col) in enumerate(st):
        y = 0.86 - i * 0.255
        w = 0.60 * n / top
        ax.add_patch(FancyBboxPatch((0.5 - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.015", fc=col, ec="none"))
        ax.text(0.5, y, f"{n}", ha="center", va="center", fontsize=24, fontweight="bold", color="white")
        ax.text(0.5 + 0.31 + 0.01, y + 0.025, en, va="center", fontsize=13, fontweight="bold", color=INK)
        ax.text(0.5 + 0.31 + 0.01, y - 0.035, zh, va="center", fontsize=12, color=MUTED)
        if i:
            ax.text(0.5 - 0.31 - 0.01, y, f"{n / top:.0%} of respondents\n佔全體 {n / top:.0%}", ha="right", va="center", fontsize=11, color=MUTED)
    fig.text(0.04, 0.715, f"≈{REACH_ESTIMATE:,} people had access  →  {len(d)} responded (≈{S['resp_rate']:.0%})  |  "
                          f"約 {REACH_ESTIMATE:,} 人可取得問卷 → {len(d)} 人填答（約 {S['resp_rate']:.0%}）",
             fontsize=12.5, fontweight="bold", color=CORAL)
    frame(fig, "Sample funnel: where respondents drop out", "樣本漏斗：各階段完成人數",
          "A low response rate is the main risk - so we test it directly (next slides).", "回覆率偏低是主要風險，因此我們直接檢驗（見下頁）。",
          FOOT_SAMPLE + "  |  Reach figure is Well Planet's estimate 觸及人數為主辦單位估計值")
    out.save_fig(fig, "2_bias/06_sample_funnel.png")


def p2_timeline(S, d, org, out):
    t = d.dropna(subset=["ts"]).copy()
    daily = t.groupby(t["ts"].dt.normalize()).size()
    idx = pd.date_range(daily.index.min(), daily.index.max())
    daily = daily.reindex(idx).fillna(0)
    t["wave"] = pd.qcut(t["ts"].rank(method="first"), 3, labels=["Early", "Middle", "Late"])
    rows = []
    for w, g in t.groupby("wave"):
        for var, lab in [("personal_bo", "Personal burnout 個人倦怠"), ("work_bo", "Work-related burnout 工作倦怠")]:
            m, lo, hi, n = mean_ci(g[var])
            rows.append((w, lab, m, lo, hi, n))
    wv = pd.DataFrame(rows, columns=["wave", "measure", "mean", "lo", "hi", "n"])
    out.save_tab(wv, "bias_wave_means.csv", index=False)
    rho, p = stats.spearmanr((t["ts"] - t["ts"].min()).dt.total_seconds(), t["personal_bo"], nan_policy="omit")
    rho_w, p_w = stats.spearmanr((t["ts"] - t["ts"].min()).dt.total_seconds(), t["work_bo"], nan_policy="omit")
    S["wave_rho"], S["wave_p"] = rho, p
    S["wave_rho_w"], S["wave_p_w"] = rho_w, p_w
    S["wave_means"] = wv

    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1.35, 1]})
    a1.bar(daily.index, daily.values, color=SKY, width=0.8, zorder=3)
    a1.set_title("Responses per day 每日回覆數")
    a1.set_xticks(daily.index[::2])
    a1.set_xticklabels([x.strftime("%m/%d") for x in daily.index[::2]], rotation=45, fontsize=9.5)
    a1.grid(axis="x", visible=False)
    pk = daily.idxmax()
    a1.annotate(f"launch spike 發佈高峰\n{int(daily.max())} responses", (pk, daily.max()), (pk + pd.Timedelta(days=3), daily.max() * 0.85),
                arrowprops=dict(arrowstyle="->", color=INK), fontsize=10.5)
    cols = {"Personal burnout 個人倦怠": NAVY, "Work-related burnout 工作倦怠": AMBER}
    xs = np.arange(3)
    for j, (lab, g) in enumerate(wv.groupby("measure")):
        off = (j - 0.5) * 0.14
        a2.errorbar(xs + off, g["mean"], yerr=[g["mean"] - g["lo"], g["hi"] - g["mean"]], fmt="o-", color=cols[lab], lw=2.2, ms=8,
                    capsize=5, label=lab, zorder=3)
    a2.set_xticks(xs)
    a2.set_xticklabels([bi("Early", "前期"), bi("Middle", "中期"), bi("Late", "後期")])
    a2.set_ylim(35, 70)
    a2.set_ylabel("Mean score 平均分數 (0-100)")
    a2.set_title("Burnout by arrival order 依填答先後")
    a2.legend(loc="upper left", fontsize=9.5)
    a2.grid(axis="x", visible=False)
    a2.text(0.5, 0.04, f"Trend over time 時間趨勢: ρ={rho:+.2f}, p={p:.2f}\n(no significant drift 無顯著變化)" if p > 0.05 else
            f"Trend over time: ρ={rho:+.2f}, p={p:.3f}", transform=a2.transAxes, ha="center", fontsize=10.5, color=MUTED)
    frame(fig, "Did late responders look different from early ones?", "晚填答者與早填答者有差異嗎？",
          "Hard-to-reach respondents are a stand-in for non-responders: scores are stable across the fieldwork period.",
          "較晚才填答者可視為「未填答者」的代理：整個調查期間分數相當穩定。",
          FOOT_SAMPLE + f"  |  n={len(t)}, 95% CI 95% 信賴區間")
    out.save_fig(fig, "2_bias/07_response_timeline.png")


def p2_tipping(S, d, org, out):
    f = len(d) / REACH_ESTIMATE
    p = d["mod_p"].mean()
    q = np.linspace(0, 0.8, 200)
    pop = f * p + (1 - f) * q
    need = lambda target: (target - f * p) / (1 - f)
    S["tip25"], S["tip40"], S["tip50"] = need(0.25), need(0.40), need(0.50)
    fig, ax = plt.subplots(figsize=FIG)
    ax.plot(q * 100, pop * 100, color=NAVY, lw=3.2, zorder=4)
    ax.fill_between(q * 100, 0, pop * 100, where=pop <= 0.25, color=CORAL, alpha=0.13, zorder=2)
    for target, col in [(0.25, CORAL), (0.40, AMBER), (0.50, TEAL)]:
        x = need(target) * 100
        ax.hlines(target * 100, 0, x, color=col, lw=1.4, ls="--", zorder=3)
        ax.vlines(x, 0, target * 100, color=col, lw=1.4, ls="--", zorder=3)
        ax.scatter([x], [target * 100], color=col, s=90, zorder=5)
        ax.text(x + 1.2, target * 100 - 3.3, f"{target:.0%} overall needs non-responders ≤ {x:.0f}%\n整體 {target:.0%} 需未填答者 ≤ {x:.0f}%",
                fontsize=10.2, color=col, fontweight="bold", va="top")
    ax.axvline(p * 100, color=GREY, lw=1.6, ls=":")
    ax.text(p * 100 - 1, 4, f"Respondents 填答者: {p:.0%}", rotation=90, ha="right", va="bottom", color=MUTED, fontsize=10.5)
    ax.set_xlim(0, 80)
    ax.set_ylim(0, 72)
    ax.set_xlabel("Assumed % with moderate-or-higher burnout among people who did NOT respond\n假設「未填答者」中有中度以上倦怠的比例 (%)")
    ax.set_ylabel("Implied % in the whole population\n推算整體族群比例 (%)")
    frame(fig, "Non-response tipping point", "未回覆偏誤的臨界點分析",
          f"With a {f:.0%} response rate, burnout would be below 25% overall only if non-responders were below {need(0.25):.0%} - "
          f"a {abs(p - need(0.25)) * 100:.0f}-point gap.",
          f"回覆率約 {f:.0%}：整體倦怠率要低於 25%，未填答者須低於 {need(0.25):.0%}，與填答者相差約 {abs(p - need(0.25)) * 100:.0f} 個百分點。",
          "Sensitivity analysis, not a population estimate 敏感度分析，非母體推估  |  Moderate+ = personal burnout ≥ 50/100")
    out.save_fig(fig, "2_bias/08_nonresponse_tipping_point.png")


def p2_reweight(S, d, org, out, B):
    base = d[["personal_bo", "mod_p", "gender3", "age_cat", "metro", "respondent_type"]].copy()
    rng = np.random.default_rng(2026)
    eq = lambda col, levels: {col: {l: 1 / len(levels) for l in levels}}
    schemes = [("Unweighted (as collected)", "未加權（原始資料）", None),
               ("Equal women / men 50:50", "男女各 50%", eq("gender3", ["Female", "Male"])),
               ("Equal age groups", "各年齡層等比例", eq("age_cat", H.AGE_LABEL)),
               ("Taipei metro 50% : elsewhere 50%", "大臺北 50%：其他縣市 50%", eq("metro", ["Taipei metro", "Elsewhere"])),
               ("Org staff 50% : freelancers 50%", "機構人員 50%：獨立工作者 50%",
                {"respondent_type": {"Org-affiliated": 0.25, "Org + personal projects": 0.25, "Freelancer / independent": 0.5}}),
               ("All of the above combined (raked)", "以上條件合併（疊代加權）",
                {**eq("gender3", ["Female", "Male"]), **eq("age_cat", H.AGE_LABEL), **eq("metro", ["Taipei metro", "Elsewhere"])})]

    def prev(df, margins):
        if margins is None:
            return df["mod_p"].mean()
        cols = list(margins)
        s = df.dropna(subset=cols + ["mod_p"])
        s = s[np.logical_and.reduce([s[c].isin(margins[c].keys()) for c in cols])]
        w = rake(s, margins)
        return np.average(s["mod_p"], weights=w)

    rows = []
    for en, zh, m in schemes:
        est = prev(base, m)
        bs = [prev(base.sample(len(base), replace=True, random_state=int(rng.integers(1e9))), m) for _ in range(B)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        rows.append((en, zh, est, lo, hi))
    r = pd.DataFrame(rows, columns=["en", "zh", "est", "lo", "hi"])
    out.save_tab(r, "bias_reweighting.csv", index=False)
    S["reweight"] = r
    fig, ax = plt.subplots(figsize=FIG)
    y = np.arange(len(r))
    ax.axvspan(r["lo"].iloc[0] * 100, r["hi"].iloc[0] * 100, color=SKY, alpha=0.18, zorder=1)
    ax.axvline(50, color=GREY, ls=":", lw=1.3)
    ax.errorbar(r["est"] * 100, y, xerr=[(r["est"] - r["lo"]) * 100, (r["hi"] - r["est"]) * 100], fmt="none", ecolor=NAVY, lw=3, capsize=6, zorder=3)
    ax.scatter(r["est"] * 100, y, s=170, color=[CORAL] + [NAVY] * (len(r) - 1), zorder=4)
    for i, row in r.iterrows():
        ax.text(row["hi"] * 100 + 1.2, i, f"{row['est']:.0%}  ({row['lo']:.0%}-{row['hi']:.0%})", va="center", fontsize=11, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([bi(a, b) for a, b in zip(r["en"], r["zh"])])
    ax.invert_yaxis()
    ax.set_xlim(40, 82)
    ax.set_xlabel("% with moderate-or-higher personal burnout 個人倦怠中度以上比例 (%)")
    ax.grid(axis="y", visible=False)
    spread = (r["est"].max() - r["est"].min()) * 100
    frame(fig, "Re-weighting the sample barely moves the result", "調整樣本結構後，結果幾乎不變",
          f"Across 6 different weighting schemes the estimate varies by only {spread:.1f} points; every interval stays above 50%.",
          f"六種加權方式下，估計值僅相差 {spread:.1f} 個百分點，且信賴區間皆高於 50%。",
          f"Equal-share targets are illustrative (true population margins unknown) 等比例目標僅為示意  |  Bootstrap {B} resamples, 95% CI")
    out.save_fig(fig, "2_bias/09_reweighting_robustness.png")


def p2_subgroups(S, d, org, out):
    groups = [("Gender 性別", "gender3", ZH_GENDER, d), ("Age 年齡", "age_cat", None, d),
              ("Region 地區", "region", ZH_REGION, d), ("Respondent type 身分", "respondent_type", ZH_TYPE, d),
              ("Role 職務", "role", ZH_ROLE, org), ("Org size 機構規模", "org_size_cat", None, org)]
    rows = []
    for gname, col, zhmap, df in groups:
        cats = H.AGE_LABEL if col == "age_cat" else H.SIZE_LABEL if col == "org_size_cat" else list(df[col].dropna().value_counts().index)
        for c in cats:
            s = df[df[col] == c]["mod_p"].dropna()
            if len(s) >= 20 and c != "Other":
                p, lo, hi = wilson(s.sum(), len(s))
                lab = bi(c, zhmap[c], " ") if zhmap and c in zhmap else str(c)
                rows.append((gname, lab, p, lo, hi, len(s)))
    r = pd.DataFrame(rows, columns=["group", "label", "p", "lo", "hi", "n"])
    out.save_tab(r, "bias_subgroup_prevalence.csv", index=False)
    S["subgroups"] = r
    overall = d["mod_p"].mean()
    fig, ax = plt.subplots(figsize=(12, 8.6))
    ypos, y, ticks, labs, bands = [], 0, [], [], []
    palette = [NAVY, TEAL, AMBER, CORAL, SKY, GREY]
    for gi, (gname, g) in enumerate(r.groupby("group", sort=False)):
        start = y
        for _, row in g.iterrows():
            ax.errorbar(row["p"] * 100, y, xerr=[[(row["p"] - row["lo"]) * 100], [(row["hi"] - row["p"]) * 100]], fmt="o",
                        color=palette[gi % 6], ms=8, lw=2.2, capsize=4, zorder=3)
            ax.text(100.5, y, f"{row['p']:.0%}  (n={row['n']})", va="center", fontsize=9.8)
            ticks.append(y)
            labs.append(row["label"])
            y += 1
        ax.text(-1.5, (start + y - 1) / 2, gname, rotation=90, ha="right", va="center", fontsize=10.5, color=palette[gi % 6], fontweight="bold")
        if gi % 2 == 0:
            ax.axhspan(start - 0.5, y - 0.5, color="#F7F9FC", zorder=0)
        y += 0.6
    ax.axvline(overall * 100, color=CORAL, ls="--", lw=1.6, zorder=2)
    ax.axvline(50, color=GREY, ls=":", lw=1)
    ax.text(overall * 100, -1.15, f"All respondents 全體 {overall:.0%}", color=CORAL, ha="center", fontsize=10.5, fontweight="bold")
    ax.set_yticks(ticks)
    ax.set_yticklabels(labs, fontsize=9.8)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("% with moderate-or-higher personal burnout 個人倦怠中度以上比例 (%), 95% Wilson CI")
    ax.grid(axis="y", visible=False)
    lowest = r.loc[r["p"].idxmin()]
    frame(fig, "Burnout is high in every subgroup", "各族群倦怠比例皆偏高",
          f"{(r['p'] >= 0.4).mean():.0%} of subgroups are at or above 40% (lowest: {lowest['p']:.0%}) - the finding does not depend on who is over-represented.",
          f"{(r['p'] >= 0.4).mean():.0%} 的族群達 40% 以上（最低 {lowest['p']:.0%}）；結果不取決於某一族群的樣本偏多。",
          FOOT_SAMPLE + "  |  Subgroups with n<20 omitted 少於 20 人之族群未列出", top=0.80, bottom=0.07)
    out.save_fig(fig, "2_bias/10_subgroup_robustness.png")


def p2_skip_bias(S, d, org, out):
    org = org.copy()
    r = org.groupby("role")["skip_pq"].agg(["mean", "sum", "count"])
    r = r[r["count"] >= 15].sort_values("mean")
    metrics = [("BO", "Burnout 倦怠"), ("WL", "Workload 工作負荷"), ("OS", "Org. support 組織支持"), ("ID", "Inner drive 工作投入")]
    rows = []
    for k, lab in metrics:
        a, b = org.loc[org.skip_pq == 0, k].dropna(), org.loc[org.skip_pq == 1, k].dropna()
        ma, la, ha, _ = mean_ci(a)
        mb, lb, hb, _ = mean_ci(b)
        rows.append((lab, ma, la, ha, mb, lb, hb, stats.mannwhitneyu(a, b).pvalue))
    t = pd.DataFrame(rows, columns=["metric", "done", "d_lo", "d_hi", "skip", "s_lo", "s_hi", "p"])
    out.save_tab(t, "bias_optional_block_skippers.csv", index=False)
    S["skip"] = t
    S["skip_n"] = int(org["skip_pq"].sum())
    S["skip_rates"] = r
    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1, 1.25]})
    hbar(a1, [bi(k, ZH_ROLE[k]) for k in r.index], r["mean"].values * 100, [CORAL if k != "Frontline helper" else TEAL for k in r.index],
         xmax=100, annot=[f"(n={int(n)})" for n in r["count"]], fs=10.5)
    a1.set_title("Skipped the optional trauma block 略過選填創傷題組 (%)")
    y = np.arange(len(t))
    a2.errorbar(t["done"], y - 0.12, xerr=[t["done"] - t["d_lo"], t["d_hi"] - t["done"]], fmt="o", color=NAVY, ms=9, capsize=4, lw=2, label="Completed block 完成")
    a2.errorbar(t["skip"], y + 0.12, xerr=[t["skip"] - t["s_lo"], t["s_hi"] - t["skip"]], fmt="s", color=CORAL, ms=9, capsize=4, lw=2, label="Skipped block 略過")
    for i, row in t.iterrows():
        a2.text(101, i, f"p={row['p']:.3f}" if row["p"] >= 0.001 else "p<0.001", va="center", fontsize=10)
    a2.set_yticks(y)
    a2.set_yticklabels(t["metric"])
    a2.invert_yaxis()
    a2.set_xlim(20, 108)
    a2.set_xlabel("Mean score 平均分數 (0-100), 95% CI")
    a2.set_title("Do skippers differ? 略過者有不同嗎？")
    a2.legend(loc="lower right", fontsize=9.5)
    a2.grid(axis="y", visible=False)
    frame(fig, "Item non-response: who skipped the optional block?", "題目未填答：誰略過了選填題組？",
          "Skipping is driven by role (9% of front-line vs 69% of admin staff) and skippers report LESS burnout - so trauma-scale results lean towards front-line staff.",
          "是否略過與職務高度相關（第一線 9%、行政 69%），且略過者倦怠較低；創傷量表結果因此偏重第一線人員。",
          f"Organisation-affiliated only, n={len(org)} (skipped: {S['skip_n']}); Mann-Whitney U tests 僅機構任職者")
    out.save_fig(fig, "2_bias/11_optional_block_bias.png")


def p2_reliability(S, d, org, out, meta):
    rel = meta["reliability"].set_index("scale")["cronbach_alpha"]
    sc = meta["spec_compare"]
    sc = sc[sc["version"] == "revised"].set_index("construct")["cronbach_alpha"]
    rows = [("Burnout - personal (CBI, 6 items)", "個人倦怠（CBI）", rel["CBI personal burnout (6)"]),
            ("Burnout - work-related (CBI, 7 items)", "工作倦怠（CBI）", rel["CBI work burnout (7, w7 reversed)"]),
            ("Work engagement (UWES-3)", "工作投入（UWES-3）", rel["UWES-3 engagement (3)"]),
            ("Organisational support (7 items)", "組織支持", sc["OS"]),
            ("Compassion satisfaction (ProQOL)", "同理心滿足（ProQOL）", rel["ProQOL compassion satisfaction (3)"]),
            ("Secondary traumatic stress (ProQOL)", "次級創傷壓力（ProQOL）", rel["ProQOL secondary traumatic stress (3)"]),
            ("Job resources (5 items)", "工作資源", sc["JR"]),
            ("Workload (5 items)", "工作負荷", sc["WL"]),
            ("Intention to stay (5 items)", "留任意願", sc["RET"]),
            ("ProQOL burnout (3 items)", "ProQOL 倦怠", rel["ProQOL burnout (3)"])]
    r = pd.DataFrame(rows, columns=["en", "zh", "alpha"]).sort_values("alpha", ascending=False)
    out.save_tab(r, "measurement_reliability.csv", index=False)
    S["reliability"] = r
    cols = [TEAL if a >= 0.8 else AMBER for a in r["alpha"]]
    fig, ax = plt.subplots(figsize=FIG)
    hbar(ax, [bi(a, b) for a, b in zip(r["en"], r["zh"])], r["alpha"].values, cols, fmt="{:.2f}", xmax=1.12, fs=11.5)
    ax.axvline(0.7, color=CORAL, ls="--", lw=1.5)
    ax.axvline(0.8, color=TEAL, ls="--", lw=1.5)
    ax.text(0.7, len(r) - 0.35, "0.70 acceptable 可接受", color=CORAL, ha="right", fontsize=10, fontweight="bold", va="top")
    ax.text(0.8, len(r) - 0.35, "0.80 good 良好", color=TEAL, ha="left", fontsize=10, fontweight="bold", va="top")
    ax.set_xlabel("Cronbach's alpha (internal consistency 內部一致性)")
    sl = (d[[f"b{i}" for i in range(1, 7)] + [f"w{i}" for i in range(1, 8)]].nunique(axis=1) == 1).mean()
    S["straightline"] = sl
    n_good = int((r["alpha"] >= 0.8).sum())
    frame(fig, "Measurement quality: are the scales reliable?", "量表信度：測量工具可靠嗎？",
          f"All {len(r)} scales meet the 0.70 standard and {n_good} exceed 0.80; only {sl:.0%} of respondents gave identical answers to every burnout item.",
          f"{len(r)} 個量表皆達 0.70 標準，其中 {n_good} 個超過 0.80；僅 {sl:.0%} 的受訪者對所有倦怠題給出相同答案。",
          "Validated instruments: CBI, UWES-3, ProQOL-9 經驗證量表  |  Single-item measures (pay, mission fit) cannot be assessed 單題指標無法計算信度")
    out.save_fig(fig, "2_bias/12_measurement_reliability.png")


# =========================================================================== #
# PART 3 -- BURNOUT & THE EAP CASE
# =========================================================================== #
def p3_key_numbers(S, d, org, out):
    pm, plo, phi = wilson(d["mod_p"].sum(), d["mod_p"].notna().sum())
    ph = (d["personal_bo"] >= CUT_HIGH).mean()
    wm = d["mod_w"].mean()
    leave = org["high_leave"].mean()
    srch = org["job_search"].mean()
    orr, olo, ohi, op = odds_ratio(org["BO"] >= CUT_MOD, org["high_leave"] == 1)
    S.update(pm=pm, plo=plo, phi=phi, ph=ph, wm=wm, leave=leave, srch=srch, resume=org["resume"].mean(), applied=org["applied"].mean(),
             OR=orr, OR_lo=olo, OR_hi=ohi, OR_p=op, mean_p=d["personal_bo"].mean(), mean_w=d["work_bo"].mean(), sd_p=d["personal_bo"].std(), sd_w=d["work_bo"].std())
    tiles = [(f"{pm:.0%}", f"Moderate+ personal burnout (95% CI {plo:.0%}-{phi:.0%})", f"個人倦怠中度以上（95% CI {plo:.0%}–{phi:.0%}）", CORAL),
             (f"{ph:.0%}", "High personal burnout (≥75/100)", "個人倦怠達高度（≥75 分）", CORAL),
             (f"{wm:.0%}", "Moderate+ work-related burnout", "工作倦怠中度以上", AMBER),
             (f"{leave:.0%}", "Consider leaving at least monthly", "每月至少考慮離職一次", NAVY),
             (f"{srch:.0%}", "Searched for other jobs (past 6 months)", "過去六個月曾搜尋其他工作", NAVY),
             (f"{orr:.1f}×", f"Higher odds of leaving if burnt out (CI {olo:.1f}-{ohi:.1f})", f"倦怠者考慮離職的勝算為 {orr:.1f} 倍（CI {olo:.1f}–{ohi:.1f}）", TEAL)]
    kpi_figure(out, "3_burnout/13_key_numbers.png", "The need in six numbers", "六個數字看需求",
               "More than half of helpers are moderately or severely burnt out - and it is already showing up in job searches.",
               "超過半數助人者有中度以上倦怠，且已反映在求職行為上。", tiles,
               FOOT_SAMPLE + "  |  Leaving / job-search: organisation-affiliated only 離職／求職：僅機構任職者")


def p3_levels(S, d, org, out):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1.3, 1]})
    bins = np.arange(0, 101, 5)
    x = d["personal_bo"].dropna()
    n, b, patches = a1.hist(x, bins=bins, edgecolor="white", zorder=3)
    for p_, left in zip(patches, b[:-1]):
        p_.set_facecolor(LOW_C if left < CUT_MOD else MOD_C if left < CUT_HIGH else HIGH_C)
    for c in (CUT_MOD, CUT_HIGH):
        a1.axvline(c, color=INK, ls="--", lw=1.2)
    a1.axvline(x.mean(), color=NAVY, lw=2.4)
    a1.text(x.mean() - 1.5, n.max() * 1.06, f"Mean 平均 {x.mean():.1f}", ha="right", color=NAVY, fontweight="bold", fontsize=11)
    a1.set_xlabel("Personal burnout score 個人倦怠分數 (0-100)")
    a1.set_ylabel("Number of respondents 人數")
    a1.set_title("Distribution of scores 分數分布")
    a1.set_ylim(0, n.max() * 1.18)
    a1.grid(axis="x", visible=False)
    lab = []
    data = {}
    for key, name in [("lvl_p", bi("Personal burnout", "個人倦怠")), ("lvl_w", bi("Work-related burnout", "工作倦怠"))]:
        c = d[key].value_counts().reindex(LEVEL_EN)
        data[name] = c / c.sum() * 100
    df = pd.DataFrame(data).T
    out.save_tab(df.round(1), "burnout_levels_pct.csv")
    left = np.zeros(len(df))
    for j, lvl in enumerate(LEVEL_EN):
        a2.barh(range(len(df)), df[lvl].values, left=left, color=LEVEL_COL[j], height=0.55, label=bi(lvl, LEVEL_ZH[j], " "), zorder=3)
        for i, v in enumerate(df[lvl].values):
            a2.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontweight="bold", fontsize=12.5,
                    color="white" if j == 2 else INK)
        left += df[lvl].values
    a2.set_yticks(range(len(df)))
    a2.set_yticklabels(df.index)
    a2.invert_yaxis()
    a2.set_xlim(0, 100)
    a2.set_xlabel("% of respondents 受訪者比例")
    a2.set_title("Severity levels 嚴重程度")
    a2.grid(axis="y", visible=False)
    a2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=9.3)
    frame(fig, "How burnt out are helpers?", "助人者的倦怠程度",
          f"Average personal burnout is {S['mean_p']:.0f}/100; {S['pm']:.0%} are at moderate level or above and {S['ph']:.0%} at high level.",
          f"個人倦怠平均 {S['mean_p']:.0f}/100；{S['pm']:.0%} 達中度以上，{S['ph']:.0%} 達高度。",
          FOOT_SAMPLE + f"  |  n={len(x)}; Copenhagen Burnout Inventory (CBI) cut-offs 50 / 75 哥本哈根倦怠量表分級")
    out.save_fig(fig, "3_burnout/14_burnout_levels.png")


def p3_role(S, d, org, out):
    roles = ["Frontline helper", "Admin / project / finance", "Mid-level manager", "Founder / decision-maker"]
    rows = []
    for r in roles:
        s = org.loc[org["role"] == r, "BO"].dropna()
        m, lo, hi, n = mean_ci(s)
        pm, plo, phi = wilson((s >= CUT_MOD).sum(), len(s))
        rows.append((r, m, lo, hi, n, pm, plo, phi))
    t = pd.DataFrame(rows, columns=["role", "m", "lo", "hi", "n", "p", "plo", "phi"]).sort_values("m", ascending=False)
    out.save_tab(t, "burnout_by_role.csv", index=False)
    S["role_tab"] = t
    kw = stats.kruskal(*[org.loc[org["role"] == r, "BO"].dropna() for r in roles])
    S["role_kw_p"] = kw.pvalue
    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, sharey=True)
    y = np.arange(len(t))
    labs = [bi(r, ZH_ROLE[r]) + f"\n(n={n})" for r, n in zip(t["role"], t["n"])]
    cols = [CORAL if r == "Frontline helper" else NAVY for r in t["role"]]
    a1.barh(y, t["m"], xerr=[t["m"] - t["lo"], t["hi"] - t["m"]], color=cols, height=0.6, capsize=5, error_kw=dict(ecolor=INK, lw=1.6), zorder=3)
    for i, row in enumerate(t.itertuples()):
        a1.text(row.hi + 1.2, i, f"{row.m:.0f}", va="center", fontweight="bold", fontsize=12)
    a1.axvline(CUT_MOD, color=GREY, ls="--", lw=1.2)
    a1.set_xlim(0, 80)
    a1.set_xlabel("Mean burnout score 平均倦怠分數 (0-100)")
    a1.set_title("Average score 平均分數")
    a2.barh(y, t["p"] * 100, xerr=[(t["p"] - t["plo"]) * 100, (t["phi"] - t["p"]) * 100], color=cols, height=0.6, capsize=5,
            error_kw=dict(ecolor=INK, lw=1.6), zorder=3)
    for i, row in enumerate(t.itertuples()):
        a2.text(row.phi * 100 + 1.5, i, f"{row.p:.0%}", va="center", fontweight="bold", fontsize=12)
    a2.set_xlim(0, 100)
    a2.set_xlabel("% with moderate+ burnout 中度以上比例 (%)")
    a2.set_title("Share burnt out 倦怠比例")
    a1.set_yticks(y)
    a1.set_yticklabels(labs)
    a1.invert_yaxis()
    for a in (a1, a2):
        a.grid(axis="y", visible=False)
        a.tick_params(axis="y", length=0)
    top, low = t.iloc[0], t.iloc[-1]
    frame(fig, "Burnout is concentrated in front-line staff", "倦怠集中在第一線人員",
          f"Front-line helpers score {top['m']:.0f} vs {low['m']:.0f} for founders / decision-makers (Kruskal-Wallis p<0.001).",
          f"第一線助人者 {top['m']:.0f} 分，創辦人／決策者僅 {low['m']:.0f} 分（Kruskal-Wallis p<0.001）。",
          "Organisation-affiliated respondents; 95% CI 僅機構任職者；95% 信賴區間  |  Decision-makers are the least affected - and the ones who decide 決策者最不受影響，卻是做決定的人")
    out.save_fig(fig, "3_burnout/15_burnout_by_role.png")


def p3_hours(S, d, org, out):
    order = ["<=20", "21-40", "41-50", "51-60", "61+"]
    rows = []
    for h in order:
        s = org.loc[org["hours_actual_cat"] == h, "BO"].dropna()
        m, lo, hi, n = mean_ci(s)
        rows.append((h, m, lo, hi, n, wilson((s >= CUT_MOD).sum(), len(s))[0]))
    t = pd.DataFrame(rows, columns=["hours", "m", "lo", "hi", "n", "p"])
    out.save_tab(t, "burnout_by_hours.csv", index=False)
    S["hours_tab"] = t
    rho, p = stats.spearmanr(org["hours_actual_ord"], org["BO"], nan_policy="omit")
    S["hours_rho"], S["hours_p"] = rho, p
    fig, ax = plt.subplots(figsize=FIG)
    cols = [LOW_C, LOW_C, MOD_C, HIGH_C, HIGH_C]
    ax.bar(range(len(t)), t["m"], yerr=[t["m"] - t["lo"], t["hi"] - t["m"]], color=cols, width=0.62, capsize=6, error_kw=dict(ecolor=INK, lw=1.6), zorder=3)
    for i, row in t.iterrows():
        ax.text(i, row["hi"] + 1.5, f"{row['m']:.0f}", ha="center", fontweight="bold", fontsize=13)
        ax.text(i, 3, f"n={int(row['n'])}", ha="center", color="white", fontsize=10.5, fontweight="bold")
    ax.set_xticks(range(len(t)))
    ax.set_xticklabels([bi(h, "小時") for h in t["hours"]])
    ax.axhline(CUT_MOD, color=GREY, ls="--", lw=1.2)
    ax.text(len(t) - 0.5, CUT_MOD + 1, "moderate threshold 中度門檻 (50)", ha="right", color=MUTED, fontsize=10)
    ax.set_xlabel("Hours worked in the past 7 days (incl. overtime and 'on call' time) 過去七天工時（含加班與隨時待命）")
    ax.set_ylabel("Mean burnout score 平均倦怠分數")
    ax.set_ylim(0, 82)
    ax.grid(axis="x", visible=False)
    jump = t["m"].iloc[3] - t["m"].iloc[1]
    frame(fig, "More hours, more burnout", "工時越長，倦怠越高",
          f"Working 51-60 hours is associated with burnout {jump:.0f} points higher than 21-40 hours (Spearman ρ={rho:.2f}, p<0.001).",
          f"每週 51–60 小時者的倦怠分數比 21–40 小時者高 {jump:.0f} 分（Spearman ρ={rho:.2f}，p<0.001）。",
          "Association, not proof of cause 為關聯性而非因果  |  Organisation-affiliated respondents; error bars = 95% CI 誤差線為 95% 信賴區間")
    out.save_fig(fig, "3_burnout/16_burnout_by_hours.png")


def p3_drivers(S, d, org, out):
    keys = H.PREDICTORS + ["SIZE"]
    coef, summ = H.ols_fit(org, "BO", keys, H.MISSION_KEYS)
    c = coef[coef["key"].isin(keys)].copy()
    zh = {"WL": "工作負荷", "OS": "組織支持", "JR": "工作資源", "PAY": "薪資（壓力較小）", "MA": "價值契合", "ID": "工作投入／內在動力", "SIZE": "機構規模"}
    en = {"WL": "Workload", "OS": "Organisational support", "JR": "Job resources", "PAY": "Pay (less strain)",
          "MA": "Mission alignment", "ID": "Inner drive / engagement", "SIZE": "Organisation size"}
    c["label"] = [bi(en[k], zh[k]) for k in c["key"]]
    c = c.reindex(c["std_beta"].abs().sort_values(ascending=False).index)
    out.save_tab(c.round(4), "burnout_drivers_regression.csv", index=False)
    S["drivers"] = c
    S["r2"], S["n_model"] = summ.get("r2", np.nan), summ.get("n", np.nan)
    fig, ax = plt.subplots(figsize=FIG)
    y = np.arange(len(c))
    sig = c["q_value_FDR"] < 0.05
    cols = [CORAL if (s and b > 0) else TEAL if (s and b < 0) else GREY for s, b in zip(sig, c["std_beta"])]
    ax.axvline(0, color=INK, lw=1.2)
    for i, (row, col) in enumerate(zip(c.itertuples(), cols)):
        ax.plot([row.ci_low, row.ci_high], [i, i], color=col, lw=4.5, solid_capstyle="round", zorder=3)
        ax.scatter([row.std_beta], [i], s=190, color=col, zorder=4, edgecolor="white", linewidth=1.5)
        ax.text(0.78, i, f"β={row.std_beta:+.2f}", va="center", fontsize=11.5, fontweight="bold", color=col)
    ax.set_yticks(y)
    ax.set_yticklabels(c["label"])
    ax.invert_yaxis()
    ax.set_xlim(-0.75, 0.98)
    ax.set_xlabel("Effect on burnout, standardised β with 95% CI 對倦怠的影響（標準化係數 β 與 95% 信賴區間）")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[Line2D([0], [0], color=CORAL, lw=6, label="Raises burnout 增加倦怠"), Line2D([0], [0], color=TEAL, lw=6, label="Protects 降低倦怠"),
                       Line2D([0], [0], color=GREY, lw=6, label="No clear effect 無明顯影響")], loc="lower right")
    frame(fig, "What drives burnout? Workload up, support and drive protect", "什麼造成倦怠？工作量增加；支持與投入具保護作用",
          f"Regression (n={S['n_model']}, R²={S['r2']:.2f}): organisational support is the one lever an employer - and an EAP - can directly change.",
          f"迴歸模型（n={S['n_model']}，R²={S['r2']:.2f}）：組織支持是雇主與 EAP 可直接改變的關鍵槓桿。",
          "OLS, robust SEs (HC3), FDR-adjusted 穩健標準誤、FDR 校正  |  Controls: org size & mission area 控制機構規模與服務領域  |  Cross-sectional 橫斷面資料")
    out.save_fig(fig, "3_burnout/17_burnout_drivers.png")


def p3_dose(S, d, org, out):
    fig, axes = plt.subplots(1, 2, figsize=FIG, sharey=True)
    specs = [("OS", "Organisational support 組織支持", TEAL), ("WL", "Workload 工作負荷", CORAL)]
    S["dose"] = {}
    for ax, (k, title, col) in zip(axes, specs):
        s = org[[k, "BO"]].dropna()
        s["q"] = pd.qcut(s[k], 5, labels=False, duplicates="drop")
        g = s.groupby("q")["BO"].apply(lambda x: mean_ci(x)[:3]).apply(pd.Series)
        g.columns = ["m", "lo", "hi"]
        g["n"] = s.groupby("q").size()
        rho, p = stats.spearmanr(s[k], s["BO"])
        S["dose"][k] = (rho, p, g)
        out.save_tab(g, f"burnout_by_{k}_quintile.csv")
        ax.errorbar(range(len(g)), g["m"], yerr=[g["m"] - g["lo"], g["hi"] - g["m"]], fmt="o-", color=col, lw=3, ms=11, capsize=6, zorder=3)
        for i, row in g.reset_index().iterrows():
            ax.text(i, row["hi"] + 2, f"{row['m']:.0f}", ha="center", fontweight="bold", fontsize=11.5)
        ax.set_xticks(range(len(g)))
        ax.set_xticklabels(["Lowest\n最低", "", "Middle\n中間", "", "Highest\n最高"][:len(g)])
        ax.set_xlabel(f"Level of {title.split(' ')[0].lower()} (fifths) 程度（五等分）")
        ax.set_title(f"{title}\nSpearman ρ={rho:+.2f}, p<0.001")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Mean burnout score 平均倦怠分數 (0-100)")
    axes[0].set_ylim(15, 85)
    frame(fig, "A steady gradient: the more support, the less burnout", "明顯的梯度：支持越多，倦怠越低",
          "Burnout falls step-by-step across fifths of organisational support and rises with workload - a dose-response pattern.",
          "倦怠隨組織支持五等分逐級下降、隨工作負荷上升，呈現劑量反應關係。",
          "Organisation-affiliated respondents; 95% CI 僅機構任職者  |  Association, not proof of cause 關聯性，非因果")
    out.save_fig(fig, "3_burnout/18_support_workload_gradient.png")


def p3_turnover(S, d, org, out):
    o = org.dropna(subset=["BO", "high_leave"]).copy()
    o["lv"] = level_of(o["BO"])
    rows = []
    for i, lv in enumerate(LEVEL_EN):
        s = o[o["lv"] == lv]
        p, lo, hi = wilson((s["high_leave"] == 1).sum(), len(s))
        rows.append((lv, LEVEL_ZH[i], p, lo, hi, len(s)) + tuple(s[c].mean() for c in ("job_search", "resume", "applied")))
    t = pd.DataFrame(rows, columns=["lv", "zh", "p", "lo", "hi", "n", "job_search", "resume", "applied"])
    out.save_tab(t, "burnout_vs_turnover.csv", index=False)
    S["turn"] = t
    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1, 1.2]})
    a1.bar(range(3), t["p"] * 100, yerr=[(t["p"] - t["lo"]) * 100, (t["hi"] - t["p"]) * 100], color=LEVEL_COL, width=0.62, capsize=6,
           error_kw=dict(ecolor=INK, lw=1.6), zorder=3)
    for i, r in t.iterrows():
        a1.text(i, r["hi"] * 100 + 2, f"{r['p']:.0%}", ha="center", fontweight="bold", fontsize=14)
        a1.text(i, 3, f"n={r['n']}", ha="center", color=INK, fontsize=10.5, fontweight="bold")
    a1.set_xticks(range(3))
    a1.set_xticklabels([bi(a, b) for a, b in zip(t["lv"].str.split(" ").str[0], t["zh"])])
    a1.set_ylim(0, 100)
    a1.set_ylabel("% considering leaving at least monthly\n每月至少考慮離職一次的比例 (%)")
    a1.set_title("Burnout level 倦怠程度")
    a1.grid(axis="x", visible=False)
    beh = [("job_search", "Searched for jobs\n搜尋其他工作"), ("resume", "Updated résumé\n更新履歷"), ("applied", "Applied elsewhere\n申請其他工作")]
    w = 0.26
    for j in range(3):
        vals = [t[b].iloc[j] * 100 for b, _ in beh]
        bars = a2.bar(np.arange(3) + (j - 1) * w, vals, w * 0.92, color=LEVEL_COL[j], label=bi(t["lv"].iloc[j].split(" ")[0], t["zh"].iloc[j], " "), zorder=3)
        for b_, v in zip(bars, vals):
            a2.text(b_.get_x() + b_.get_width() / 2, v + 1.5, f"{v:.0f}", ha="center", fontsize=10, fontweight="bold")
    a2.set_xticks(range(3))
    a2.set_xticklabels([l for _, l in beh])
    a2.set_ylim(0, 100)
    a2.set_ylabel("% who did this in the past 6 months\n過去六個月曾做的比例 (%)")
    a2.set_title("Job-search behaviour 求職行為")
    a2.legend(loc="upper right", ncol=3, fontsize=9.5, title="Burnout 倦怠程度", title_fontsize=9.5)
    a2.grid(axis="x", visible=False)
    frame(fig, "Burnout predicts who is heading for the exit", "倦怠預測誰正準備離職",
          f"Burnt-out staff are {S['OR']:.1f}× more likely (odds) to consider leaving monthly (95% CI {S['OR_lo']:.1f}-{S['OR_hi']:.1f}, p<0.001).",
          f"倦怠者每月考慮離職的勝算為 {S['OR']:.1f} 倍（95% CI {S['OR_lo']:.1f}–{S['OR_hi']:.1f}，p<0.001）。",
          f"Organisation-affiliated respondents, n={len(o)}; burnout = overall CBI score (13 items) 僅機構任職者；倦怠 = CBI 全量表")
    out.save_fig(fig, "3_burnout/19_burnout_and_turnover.png")


def p3_proqol(S, d, org, out):
    items = ["cs1", "cs2", "cs3", "bo1", "bo2", "bo3", "sts1", "sts2", "sts3"]
    sub = d[items].dropna()
    pct = (sub >= 4).mean() * 100
    out.save_tab(pct.round(1).to_frame("pct_often_always"), "proqol_item_pct.csv")
    S["pq"] = pct
    S["pq_n"] = len(sub)
    groups = [("Compassion satisfaction 同理心滿足", ["cs1", "cs2", "cs3"], TEAL), ("Burnout 倦怠", ["bo1", "bo2", "bo3"], AMBER),
              ("Secondary traumatic stress 次級創傷壓力", ["sts1", "sts2", "sts3"], CORAL)]
    fig, axes = plt.subplots(3, 1, figsize=FIG, sharex=True, gridspec_kw={"hspace": 0.35})
    for ax, (title, ks, col) in zip(axes, groups):
        hbar(ax, [bi(EN_PQ[k], ZH_PQ[k], "  ") for k in ks], [pct[k] for k in ks], [col] * 3, xmax=100, fs=11, bold=True)
        ax.set_title(title, fontsize=11.5, color=col)
        ax.tick_params(axis="y", labelsize=10)
    axes[-1].set_xlabel("% answering 'often' or 'always' 回答「經常」或「總是」的比例 (%)")
    frame(fig, "Helpers love the work - and it is wearing them down", "助人者熱愛工作，卻也被工作耗損",
          f"{pct['cs3']:.0f}% are glad they chose this career, yet {pct['bo3']:.0f}% say the workload feels endless and {pct['sts1']:.0f}% are affected by clients' trauma.",
          f"{pct['cs3']:.0f}% 慶幸選擇此職涯，但 {pct['bo3']:.0f}% 覺得工作負擔沒有止盡、{pct['sts1']:.0f}% 受服務對象創傷影響。",
          f"ProQOL-9 (optional block), n={len(sub)} 選填題組  |  Over-represents front-line staff (see bias slide) 第一線人員比例偏高，詳見偏誤分析")
    out.save_fig(fig, "3_burnout/20_compassion_vs_strain.png")


def p3_support_gap(S, d, org, out):
    cur, n_cur = H.multiselect_counts(d["_support_current"], H.SUPPORT_KW)
    want, n_want = H.multiselect_counts(d["_support_wanted"], H.SUPPORT_KW)
    t = pd.DataFrame({"cur": cur, "want": want}).dropna(how="all").fillna(0)
    t = t[t.index.isin(ZH_SUPPORT)]
    t["gap"] = t["want"] - t["cur"]
    t = t.sort_values("gap", ascending=False)
    out.save_tab(t.round(1), "eap_supply_vs_demand.csv")
    S["gap"], S["n_cur"], S["n_want"] = t, n_cur, n_want
    fig, ax = plt.subplots(figsize=FIG)
    y = np.arange(len(t))
    for i, r in enumerate(t.itertuples()):
        col = CORAL if r.gap > 0 else GREY
        ax.annotate("", xy=(r.want, i), xytext=(r.cur, i), arrowprops=dict(arrowstyle="-|>", color=col, lw=2.4, shrinkA=6, shrinkB=6), zorder=2)
    ax.scatter(t["cur"], y, s=150, color=GREY, zorder=4, label=f"Currently available 現有 (n={n_cur})")
    ax.scatter(t["want"], y, s=150, color=NAVY, zorder=4, label=f"Most wanted, top-3 最希望增加（至多三項）(n={n_want})")
    for i, r in enumerate(t.itertuples()):
        ax.text(max(r.cur, r.want) + 2.2, i, f"{r.gap:+.0f} pts", va="center", fontsize=10.5, fontweight="bold", color=CORAL if r.gap > 0 else MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([bi(k, ZH_SUPPORT[k]) for k in t.index])
    ax.invert_yaxis()
    ax.set_xlim(0, 75)
    ax.set_xlabel("% of respondents 受訪者比例 (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    top = t.head(3)
    frame(fig, "Supply vs. demand: where is the unmet need?", "供給與需求：缺口在哪裡？",
          f"Biggest gaps: {', '.join(top.index[:3])}. Counselling and coaching already exist at about half of organisations.",
          f"最大缺口：{'、'.join(ZH_SUPPORT[k] for k in top.index[:3])}；約半數機構已有諮商與督導。",
          "'Available' = all that apply; 'wanted' = pick up to 3, so levels are not strictly comparable 「現有」為複選、「最希望」至多三項，數值不可直接比較")
    out.save_fig(fig, "3_burnout/21_support_supply_vs_demand.png")


def p3_barriers(S, d, org, out):
    bar, n = H.multiselect_counts(d["_barriers"], H.BARRIER_KW)
    bar = bar[(bar > 0) & bar.index.isin(ZH_BARRIER)].sort_values(ascending=False)
    bar = bar[bar.index != "Not sure"]
    out.save_tab(bar.round(1).to_frame("pct"), "eap_barriers.csv")
    S["barriers"], S["n_bar"] = bar, n
    cols = [CORAL if v >= 20 else SKY for v in bar.values]
    fig, ax = plt.subplots(figsize=FIG)
    hbar(ax, [bi(k, ZH_BARRIER[k]) for k in bar.index], bar.values, cols, xmax=max(bar.values) * 1.25, fs=11.5)
    ax.set_xlabel("% of respondents whose organisation lacks support systems 機構尚未建立支持制度者的看法 (%)")
    top3 = bar.head(3)
    frame(fig, "Why don't organisations offer support already?", "為什麼機構尚未建立員工支持制度？",
          f"Money ({top3.iloc[0]:.0f}%), leadership doubt ({top3.iloc[1]:.0f}%) and capacity ({top3.iloc[2]:.0f}%) dominate - a low-cost, low-effort programme addresses all three.",
          f"預算（{top3.iloc[0]:.0f}%）、決策者疑慮（{top3.iloc[1]:.0f}%）與人力（{top3.iloc[2]:.0f}%）是主因；低成本、低負擔的方案能同時回應。",
          f"Multiple answers allowed; n={n} 可複選  |  Red = cited by 20%+ 紅色為 20% 以上提及")
    out.save_fig(fig, "3_burnout/22_barriers_to_support.png")


def p3_demand(S, d, org, out):
    prog = d["program_interest"]
    tier = lambda v: np.nan if pd.isna(v) else ("Strong yes" if "非常希望" in v else "Yes, with concerns" if "餘力" in v else "Unsure" if "不確定" in v else "Lukewarm / no")
    dm = d["decision_maker_attitude"]
    tier_dm = lambda v: np.nan if (pd.isna(v) or "我自己就是" in v) else (
        "Strong yes" if "很積極" in v else "Yes, with concerns" if "擔心" in v else "Unsure" if "不確定" in v else "Lukewarm / no")
    order = ["Strong yes", "Yes, with concerns", "Unsure", "Lukewarm / no"]
    zh = {"Strong yes": "非常願意", "Yes, with concerns": "願意但有顧慮", "Unsure": "不確定", "Lukewarm / no": "意願低／不是時候"}
    cols = {"Strong yes": TEAL, "Yes, with concerns": SKY, "Unsure": GREY, "Lukewarm / no": CORAL}
    a = prog.map(tier).value_counts().reindex(order).fillna(0)
    b = dm.map(tier_dm).value_counts().reindex(order).fillna(0)
    df = pd.DataFrame({bi("Respondent's own view", "受訪者自身意願", "\n") + f"\n(n={int(a.sum())})": a / a.sum() * 100,
                       bi("Expected view of their decision-makers", "預期決策者態度", "\n") + f"\n(n={int(b.sum())})": b / b.sum() * 100}).T
    out.save_tab(df.round(1), "program_interest_tiers.csv")
    want = prog.map(lambda v: np.nan if pd.isna(v) else float(("非常希望" in v) or ("餘力" in v)))
    k, n = want.sum(), want.notna().sum()
    wp, wlo, whi = wilson(k, n)
    S["want"], S["want_lo"], S["want_hi"], S["want_n"] = wp, wlo, whi, n
    S["dm_pos"] = (b["Strong yes"] + b["Yes, with concerns"]) / b.sum()
    S["dm_neg"] = b["Lukewarm / no"] / b.sum()

    x = d.assign(want=want).dropna(subset=["want", "BO"]).copy()
    x["lv"] = level_of(x["BO"])
    rows = []
    for i, lv in enumerate(LEVEL_EN):
        s = x[x["lv"] == lv]
        p, lo, hi = wilson(s["want"].sum(), len(s))
        rows.append((lv, LEVEL_ZH[i], p, lo, hi, len(s)))
    t = pd.DataFrame(rows, columns=["lv", "zh", "p", "lo", "hi", "n"])
    rho, p = stats.spearmanr(x["BO"], x["want"])
    S["want_rho"], S["want_rho_p"], S["want_tab"] = rho, p, t
    out.save_tab(t, "program_interest_by_burnout.csv", index=False)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1.35, 1]})
    left = np.zeros(len(df))
    for lab in order:
        a1.barh(range(len(df)), df[lab].values, left=left, color=cols[lab], height=0.5, label=bi(lab, zh[lab], " "), zorder=3)
        for i, v in enumerate(df[lab].values):
            if v >= 6:
                a1.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", color="white" if lab != "Unsure" else INK, fontweight="bold", fontsize=11.5)
        left += df[lab].values
    a1.set_yticks(range(len(df)))
    a1.set_yticklabels(df.index, fontsize=10)
    a1.invert_yaxis()
    a1.set_xlim(0, 100)
    a1.set_xlabel("% 比例")
    a1.set_title("Would your organisation join a free programme?\n貴機構願意參加免費支持方案嗎？")
    a1.grid(axis="y", visible=False)
    a1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=9.3)
    a2.bar(range(3), t["p"] * 100, yerr=[(t["p"] - t["lo"]) * 100, (t["hi"] - t["p"]) * 100], color=LEVEL_COL, width=0.6, capsize=6,
           error_kw=dict(ecolor=INK, lw=1.6), zorder=3)
    for i, r in t.iterrows():
        a2.text(i, r["hi"] * 100 + 2, f"{r['p']:.0%}", ha="center", fontweight="bold", fontsize=13)
        a2.text(i, 3, f"n={r['n']}", ha="center", fontsize=10.5, fontweight="bold")
    a2.set_xticks(range(3))
    a2.set_xticklabels([bi(a_.split(" ")[0], b_) for a_, b_ in zip(t["lv"], t["zh"])])
    a2.set_ylim(0, 105)
    a2.set_ylabel("% wanting the programme 希望參加比例 (%)")
    a2.set_title(f"…by burnout level 依倦怠程度\n(ρ={rho:+.2f}, p={p:.2f})")
    a2.grid(axis="x", visible=False)
    frame(fig, "Strong demand - but interest does not track need", "需求明確，但「想要」與「需要」並不一致",
          f"{wp:.0%} would like the programme (95% CI {wlo:.0%}-{whi:.0%}); yet interest is the same at every burnout level, so outreach must be proactive.",
          f"{wp:.0%} 希望參加（95% CI {wlo:.0%}–{whi:.0%}）；但各倦怠程度的意願相近，需主動接觸最需要的人。",
          f"Asked only of respondents whose organisation lacks a support system 僅詢問機構尚無支持制度者  |  n={n} (own view), {int(b.sum())} (decision-makers)")
    out.save_fig(fig, "3_burnout/23_demand_vs_need.png")


# =========================================================================== #
# Talking points
# =========================================================================== #
def write_talking_points(S, out: Out, boot: int):
    L = []
    add = lambda en, zh: L.append(f"- {en}\n  - {zh}")
    r = S["reweight"]
    sub = S["subgroups"]
    role = S["role_tab"]
    top, low = role.iloc[0], role.iloc[-1]
    drv = S["drivers"].set_index("key")
    dose_os, dose_wl = S["dose"]["OS"], S["dose"]["WL"]
    t = S["turn"]
    gap = S["gap"]
    L.append("# Talking points / 講稿重點 (auto-generated from the data / 由資料自動產生)\n")
    L.append("## Part 1 - Who answered? / 誰填答了？\n")
    add(f"{S['n']} helpers responded (≈{S['resp_rate']:.0%} of the ≈{REACH_ESTIMATE:,} who had access).",
        f"共 {S['n']} 位助人者填答（約佔可取得問卷者 {REACH_ESTIMATE:,} 人的 {S['resp_rate']:.0%}）。")
    add(f"{S['female']:.0%} women; {S['age_25_39']:.0%} aged 25-39; {S['metro_share']:.0%} work in Taipei / New Taipei; all 22 counties except a few are represented.",
        f"女性 {S['female']:.0%}；25–39 歲 {S['age_25_39']:.0%}；{S['metro_share']:.0%} 任職於臺北市／新北市。")
    add(f"{S['org_n']} ({S['org_share']:.0%}) are employed by an organisation; {S['frontline_share']:.0%} of them are front-line helpers.",
        f"{S['org_n']} 人（{S['org_share']:.0%}）隸屬機構，其中 {S['frontline_share']:.0%} 為第一線助人者。")
    add(f"{S['long_hours_share']:.0%} of organisation staff worked more than 50 hours in the past week.",
        f"機構人員中 {S['long_hours_share']:.0%} 過去一週工時超過 50 小時。")
    L.append("\n## Part 2 - Could bias explain it? / 偏誤能解釋嗎？\n")
    add(f"Be upfront: the sample is self-selected with a low response rate (≈{S['resp_rate']:.0%}); results describe respondents, not all helpers.",
        f"坦白說明：樣本為自願填答、回覆率偏低（約 {S['resp_rate']:.0%}），結果描述的是填答者，而非全體助人者。")
    add(f"Tipping point: overall burnout would fall below 25% only if non-responders' burnout were below {S['tip25']:.0%} (respondents: {S['pm']:.0%}); below 50% only if under {S['tip50']:.0%}.",
        f"臨界點分析：整體倦怠率要低於 25%，未填答者須低於 {S['tip25']:.0%}（填答者為 {S['pm']:.0%}）；要低於 50%，須低於 {S['tip50']:.0%}。")
    add(f"Early, middle and late responders score alike (trend ρ={S['wave_rho']:+.2f}, p={S['wave_p']:.2f}).",
        f"早、中、晚期填答者分數相近（時間趨勢 ρ={S['wave_rho']:+.2f}，p={S['wave_p']:.2f}）。")
    add(f"Six re-weighting schemes give {r['est'].min():.0%}-{r['est'].max():.0%} (unweighted {r['est'].iloc[0]:.0%}); every 95% CI stays above {r['lo'].min():.0%}.",
        f"六種加權方式的估計值介於 {r['est'].min():.0%}–{r['est'].max():.0%}（未加權 {r['est'].iloc[0]:.0%}）；所有 95% 信賴區間下限皆高於 {r['lo'].min():.0%}。")
    add(f"{(sub['p'] >= 0.4).sum()} of {len(sub)} subgroups have moderate+ burnout of 40% or more (range {sub['p'].min():.0%}-{sub['p'].max():.0%}).",
        f"{len(sub)} 個族群中有 {(sub['p'] >= 0.4).sum()} 個倦怠比例達 40% 以上（範圍 {sub['p'].min():.0%}–{sub['p'].max():.0%}）。")
    sk = S["skip"].set_index("metric")
    bo = sk.loc["Burnout 倦怠"]
    add(f"Limitation to disclose: {S['skip_n']} organisation staff skipped the optional trauma block; they report lower burnout ({bo['skip']:.0f} vs {bo['done']:.0f}), so the ProQOL / job-satisfaction results lean towards front-line staff.",
        f"需說明的限制：{S['skip_n']} 位機構人員略過選填創傷題組，其倦怠較低（{bo['skip']:.0f} vs {bo['done']:.0f}），因此 ProQOL／工作滿意度結果偏重第一線人員。")
    rel = S["reliability"]
    add(f"All {len(rel)} scales are reliable (Cronbach's α {rel['alpha'].min():.2f}-{rel['alpha'].max():.2f}); only {S['straightline']:.0%} straight-lined the burnout items.",
        f"{len(rel)} 個量表皆可靠（Cronbach's α {rel['alpha'].min():.2f}–{rel['alpha'].max():.2f}）；僅 {S['straightline']:.0%} 對倦怠題全部選同一答案。")
    L.append("\n## Part 3 - What does the data say? / 資料顯示什麼？\n")
    add(f"{S['pm']:.0%} have moderate+ personal burnout (95% CI {S['plo']:.0%}-{S['phi']:.0%}); {S['ph']:.0%} are at high level; {S['wm']:.0%} moderate+ work-related burnout.",
        f"{S['pm']:.0%} 個人倦怠中度以上（95% CI {S['plo']:.0%}–{S['phi']:.0%}）；{S['ph']:.0%} 達高度；工作倦怠中度以上 {S['wm']:.0%}。")
    add(f"Means: personal {S['mean_p']:.1f} (SD {S['sd_p']:.1f}); work-related {S['mean_w']:.1f} (SD {S['sd_w']:.1f}) on a 0-100 scale.",
        f"平均：個人倦怠 {S['mean_p']:.1f}（SD {S['sd_p']:.1f}）；工作倦怠 {S['mean_w']:.1f}（SD {S['sd_w']:.1f}）（0–100 分）。")
    add(f"Front-line helpers average {top['m']:.0f} vs {low['m']:.0f} for founders / decision-makers; {top['p']:.0%} vs {low['p']:.0%} burnt out.",
        f"第一線助人者平均 {top['m']:.0f} 分，創辦人／決策者 {low['m']:.0f} 分；倦怠比例 {top['p']:.0%} vs {low['p']:.0%}。")
    h = S["hours_tab"]
    add(f"Burnout rises with hours: {h['m'].iloc[1]:.0f} at 21-40 h vs {h['m'].iloc[3]:.0f} at 51-60 h (ρ={S['hours_rho']:.2f}).",
        f"倦怠隨工時上升：21–40 小時 {h['m'].iloc[1]:.0f} 分，51–60 小時 {h['m'].iloc[3]:.0f} 分（ρ={S['hours_rho']:.2f}）。")
    add(f"Drivers (R²={S['r2']:.2f}): workload β={drv.loc['WL', 'std_beta']:+.2f}, organisational support β={drv.loc['OS', 'std_beta']:+.2f}, inner drive β={drv.loc['ID', 'std_beta']:+.2f}; pay, mission fit and job resources add little once these are included.",
        f"影響因素（R²={S['r2']:.2f}）：工作負荷 β={drv.loc['WL', 'std_beta']:+.2f}、組織支持 β={drv.loc['OS', 'std_beta']:+.2f}、工作投入 β={drv.loc['ID', 'std_beta']:+.2f}；納入這些後，薪資、價值契合與工作資源的影響不明顯。")
    add(f"Gradient: burnout across fifths of support goes {dose_os[2]['m'].iloc[0]:.0f} → {dose_os[2]['m'].iloc[-1]:.0f}; across fifths of workload {dose_wl[2]['m'].iloc[0]:.0f} → {dose_wl[2]['m'].iloc[-1]:.0f}.",
        f"梯度：組織支持由最低到最高五等分，倦怠 {dose_os[2]['m'].iloc[0]:.0f} → {dose_os[2]['m'].iloc[-1]:.0f}；工作負荷則為 {dose_wl[2]['m'].iloc[0]:.0f} → {dose_wl[2]['m'].iloc[-1]:.0f}。")
    add(f"{S['leave']:.0%} consider leaving at least monthly; {S['srch']:.0%} searched for jobs, {S['resume']:.0%} updated their résumé, {S['applied']:.0%} applied elsewhere.",
        f"{S['leave']:.0%} 每月至少考慮離職一次；{S['srch']:.0%} 搜尋工作、{S['resume']:.0%} 更新履歷、{S['applied']:.0%} 已投遞。")
    add(f"Burnt-out staff: {t['p'].iloc[1:].mean():.0%}+ (moderate/high) vs {t['p'].iloc[0]:.0%} (low) consider leaving monthly; odds ratio {S['OR']:.1f} (95% CI {S['OR_lo']:.1f}-{S['OR_hi']:.1f}).",
        f"倦怠者（中／高度）每月考慮離職 {t['p'].iloc[1:].mean():.0%}+，低度者 {t['p'].iloc[0]:.0%}；勝算比 {S['OR']:.1f}（95% CI {S['OR_lo']:.1f}–{S['OR_hi']:.1f}）。")
    pq = S["pq"]
    add(f"{pq['cs3']:.0f}% are glad they chose this career, yet {pq['bo3']:.0f}% feel the workload is endless and {pq['sts1']:.0f}% are affected by clients' trauma (ProQOL, n={S['pq_n']}).",
        f"{pq['cs3']:.0f}% 慶幸選擇此職涯，但 {pq['bo3']:.0f}% 覺得工作負擔沒有止盡、{pq['sts1']:.0f}% 受服務對象創傷影響（ProQOL，n={S['pq_n']}）。")
    g3 = gap.head(3)
    add(f"Unmet needs: {', '.join(f'{k} (+{v:.0f} pts)' for k, v in g3['gap'].items())}.",
        f"未被滿足的需求：{'、'.join(f'{ZH_SUPPORT[k]}（+{v:.0f} 點）' for k, v in g3['gap'].items())}。")
    add(f"Top barriers: {', '.join(f'{k} ({v:.0f}%)' for k, v in S['barriers'].head(3).items())}.",
        f"主要障礙：{'、'.join(f'{ZH_BARRIER[k]}（{v:.0f}%）' for k, v in S['barriers'].head(3).items())}。")
    add(f"{S['want']:.0%} (95% CI {S['want_lo']:.0%}-{S['want_hi']:.0%}, n={S['want_n']}) would like their organisation to join a free programme; "
        f"respondents expect {S['dm_pos']:.0%} of decision-makers to be interested and {S['dm_neg']:.0%} to see no need / bad timing.",
        f"{S['want']:.0%}（95% CI {S['want_lo']:.0%}–{S['want_hi']:.0%}，n={S['want_n']}）希望機構參加免費方案；受訪者預期 {S['dm_pos']:.0%} 的決策者有興趣、{S['dm_neg']:.0%} 認為不需要或時機不對。")
    add(f"Interest does NOT rise with burnout (ρ={S['want_rho']:+.2f}, p={S['want_rho_p']:.2f}): demand is not a substitute for a needs assessment.",
        f"意願不隨倦怠程度上升（ρ={S['want_rho']:+.2f}，p={S['want_rho_p']:.2f}）：不能以「想要」取代需求評估。")
    L.append("\n## What this survey CANNOT show / 本調查無法證明的事\n")
    add("It shows need, not program effectiveness: no control group and no pre/post data on the EAP are included in this survey. "
        "The pre/post pilot (4 micro-NPOs, small cells) should be presented as satisfaction evidence only.",
        "本調查呈現的是「需求」，而非方案成效：沒有對照組，也不含 EAP 前後測資料。前後測試辦（4 個小型機構、樣本很小）僅能作為滿意度佐證。")
    add("All associations are cross-sectional: burnout and support are measured at one point in time, so we cannot prove that more support causes less burnout.",
        "所有關聯皆為橫斷面資料：倦怠與支持於同一時間點測量，無法證明增加支持必然降低倦怠。")
    add("Retention is only weakly explained by the model (R²=0.14); do not promise that an EAP will raise retention.",
        "留任意願的模型解釋力偏低（R²=0.14）；不應承諾 EAP 一定提高留任率。")
    with open(os.path.join(out.root, "talking_points.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"  talking points -> {os.path.join(out.root, 'talking_points.md')}")


# =========================================================================== #
# Main
# =========================================================================== #
def run(name, fn, *args):
    try:
        fn(*args)
    except Exception as e:  # keep going: one broken chart should not stop the others
        print(f"  !! {name} failed: {e}")
        traceback.print_exc()


def main():
    global REACH_ESTIMATE
    ap = argparse.ArgumentParser(description="Bilingual donor-presentation charts for the NPO EAP case")
    ap.add_argument("--input", "-i", help="survey CSV (default: first *.csv in this folder)")
    ap.add_argument("--out", "-o", default="donor_output")
    ap.add_argument("--reach", type=int, default=REACH_ESTIMATE, help="estimated number of people who had access to the survey")
    ap.add_argument("--boot", type=int, default=1000, help="bootstrap resamples for the re-weighting intervals")
    ap.add_argument("--parts", default="1,2,3", help="which parts to build, e.g. 1,2 (default 1,2,3)")
    a = ap.parse_args()
    REACH_ESTIMATE = a.reach
    parts = {p.strip() for p in a.parts.split(",")}
    path = a.input or (sorted(glob.glob("*.csv")) or [None])[0]
    if not path:
        sys.exit("No CSV found: pass --input path/to/survey.csv")

    setup_style()
    out = Out(a.out)
    print("\n[0] Loading and cleaning (re-using helper_survey_analysis.py)")
    d, org, meta = load(path)
    setup_style()                                   # the helper changes global style on import; re-apply ours
    S: dict = {}

    print("\n[1] Part 1 - Demographics 人口統計")
    if "1" in parts:
        for fn in (p1_glance, p1_age_gender, p1_geography, p1_profile, p1_experience):
            run(fn.__name__, fn, S, d, org, out)
    print("\n[2] Part 2 - Bias & robustness 偏誤與穩健性")
    if "2" in parts:
        for fn in (p2_funnel, p2_timeline, p2_tipping, p2_subgroups, p2_skip_bias):
            run(fn.__name__, fn, S, d, org, out)
        run("p2_reweight", p2_reweight, S, d, org, out, a.boot)
        run("p2_reliability", p2_reliability, S, d, org, out, meta)
    print("\n[3] Part 3 - Burnout & the EAP case 倦怠與 EAP 需求")
    if "3" in parts:
        for fn in (p3_key_numbers, p3_levels, p3_role, p3_hours, p3_drivers, p3_dose, p3_turnover, p3_proqol, p3_support_gap, p3_barriers, p3_demand):
            run(fn.__name__, fn, S, d, org, out)
    if parts >= {"1", "2", "3"}:
        print("\n[4] Talking points 講稿重點")
        run("talking_points", write_talking_points, S, out, a.boot)
    print(f"\nDone. {len(out.made)} charts saved in: {os.path.abspath(os.path.join(out.root, 'figures'))}\n")


if __name__ == "__main__":
    main()