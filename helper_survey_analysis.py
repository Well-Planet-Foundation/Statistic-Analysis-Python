#!/usr/bin/env python3
"""
2026 Taiwan Helpers' Needs Survey (Well Planet) -- analysis pipeline
====================================================================

Reads the raw Google-Forms CSV export and produces
  * a cleaned, anonymised, numerically-coded dataset
  * descriptive charts (demographics, Likert items, burnout, turnover, EAP needs)
  * correlation heatmaps (composite indices, item-level clustermap, segment heatmap)
  * statistical tests (Spearman + FDR, Kruskal-Wallis, Mann-Whitney, Cronbach's alpha)
  * regression (standardised OLS) and a random-forest classifier for intent to leave
  * a Markdown summary of the key findings

Usage
-----
    python helper_survey_analysis.py                       # auto-finds *.csv in cwd
    python helper_survey_analysis.py --input survey.csv --out results
    python helper_survey_analysis.py --no-ml               # skip random forest

Requirements: pandas, numpy, scipy, matplotlib, seaborn  (scikit-learn optional)

Privacy: e-mail addresses, free-text answers, timestamps and any non-county text
typed in the county field (some respondents typed their names) are dropped and
never written to any output file.

Chart labels are in English so no CJK font is required.
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MIN_PAIR_N = 20          # minimum pairwise-complete N for a correlation
MIN_GROUP_N = 10         # minimum group size shown in the segment heatmap
MIN_TEST_GROUP_N = 5     # minimum group size included in Kruskal-Wallis tests
ALPHA = 0.05
# Commonly used CBI cut-offs on the 0-100 scale (adjust if your protocol differs)
BURNOUT_BINS = [-0.1, 49.99, 74.99, 100.0]
BURNOUT_LABELS = ["Low (<50)", "Moderate (50-74)", "High (75+)"]

sns.set_theme(style="whitegrid", context="notebook", font_scale=0.95)
PALETTE = sns.color_palette("deep")

# --------------------------------------------------------------------------- #
# Answer-label -> numeric maps (keys are whitespace-stripped, dash-normalised)
# --------------------------------------------------------------------------- #
DISTRESS = {"完全沒有": 0, "輕微": 1, "中等": 2, "嚴重": 3, "非常嚴重": 4}
AGREE = {"非常不同意": 1, "不同意": 2, "普通": 3, "同意": 4, "非常同意": 5}
LEAVE = {"從未": 0, "一次或兩次": 1, "一個月一次": 2, "一週一次": 3, "每天": 4}
STAY = {"確定不會": 1, "應該不會": 2, "不確定": 3,
        "應該會，但不確定更久以後": 4, "會，而且我打算長期待下去": 5}
YESNO = {"有": 1, "無": 0}
UWES = {"從未": 1, "幾乎從不": 2, "很少": 3, "有時": 4, "經常": 5, "非常經常": 6, "總是": 7}
OVERWORK = {"從未或幾乎從未": 1, "不常": 2, "有時候": 3, "常常": 4, "總是": 5}
PROQOL = {"從未有過": 1, "很少": 2, "有些時候": 3, "經常如此": 4, "總是如此": 5}

SIZE_ORDER = ["1-4人", "5-10人", "11-15人", "16-30人", "31-50人", "51人以上"]
SIZE_LABEL = ["1-4", "5-10", "11-15", "16-30", "31-50", "51+"]
TENURE_ORDER = ["1年以內", "1年以上，未滿3年", "3年以上，未滿5年",
                "5年以上，未滿8年", "8年以上，未滿15年", "15年以上"]
TENURE_LABEL = ["<1 yr", "1-3 yrs", "3-5 yrs", "5-8 yrs", "8-15 yrs", "15+ yrs"]
AGE_ORDER = ["18-24歲", "25-29歲", "30-34歲", "35-39歲", "40-49歲", "50歲以上"]
AGE_LABEL = ["18-24", "25-29", "30-34", "35-39", "40-49", "50+"]
HOURS_AGREED = {"20小時以下": "<=20", "21-40小時": "21-40", "41小時以上": "41+",
                "沒有明確約定": "No agreement"}
HOURS_ACTUAL_MID = {"20小時以下": 15, "21-40小時": 30, "41-50小時": 45,
                    "51-60小時": 55, "61小時以上": 65}
HOURS_ACTUAL_LABEL = {"20小時以下": "<=20", "21-40小時": "21-40", "41-50小時": "41-50",
                      "51-60小時": "51-60", "61小時以上": "61+"}

# ordered (substring -> label) rules; first match wins
RULES_TYPE = [("獨立工作者", "Freelancer / independent"),
              ("同時有機構工作", "Org + personal projects"),
              ("隸屬於一個機構", "Org-affiliated")]
RULES_ORG = [("財團法人基金會", "Foundation"), ("政府部門", "Government / commissioned"),
             ("社團法人", "Association / society"), ("社會福利機構", "Social welfare agency"),
             ("社會企業", "Social enterprise"), ("地方創生", "Community / regional team")]
RULES_ROLE = [("創辦人", "Founder / decision-maker"), ("中階", "Mid-level manager"),
              ("第一線", "Frontline helper"), ("行政", "Admin / project / finance"),
              ("人資", "HR / training")]
RULES_GENDER = [("非二元", "Non-binary / other"), ("女性", "Female"), ("男性", "Male"),
                ("不願透露", "Prefer not to say")]
COUNTY_EN = {"臺北市": "Taipei", "新北市": "New Taipei", "基隆市": "Keelung", "桃園市": "Taoyuan",
             "新竹市": "Hsinchu City", "新竹縣": "Hsinchu County", "苗栗縣": "Miaoli",
             "臺中市": "Taichung", "彰化縣": "Changhua", "南投縣": "Nantou", "雲林縣": "Yunlin",
             "嘉義市": "Chiayi City", "嘉義縣": "Chiayi County", "臺南市": "Tainan",
             "高雄市": "Kaohsiung", "屏東縣": "Pingtung", "宜蘭縣": "Yilan", "花蓮縣": "Hualien",
             "臺東縣": "Taitung", "澎湖縣": "Penghu", "金門縣": "Kinmen", "連江縣": "Lienchiang"}

# multi-select option keywords -> English label
SUPPORT_KW = [("個別心理諮詢", "Individual counselling"), ("團體減壓", "Group stress relief"),
              ("督導或教練", "Supervision / coaching"), ("領導力", "Leadership training"),
              ("專業職能培訓", "Professional skills training"), ("專業技能培訓", "Professional skills training"),
              ("職涯發展", "Career development"), ("內部溝通", "Internal communication"),
              ("彈性工時", "Flexible / remote work"), ("遠距", "Flexible / remote work"),
              ("職務代理津貼", "Acting-position allowance"), ("財務規劃", "Financial planning")]
BARRIER_KW = [("預算不足", "Insufficient budget"), ("決策者不認為", "Decision-makers see no need"),
              ("沒有人有餘力", "No one has capacity"), ("沒有專人", "No one has capacity"),
              ("不知道從哪裡開始", "Don't know where to start"),
              ("被視為抱怨", "Fear of seeming to complain"), ("規模太小", "Org too small"),
              ("市場上沒有適合", "No programme for micro-orgs"), ("內部需求不明確", "Unclear internal needs"),
              ("不了解這類方案", "Unclear benefits"), ("董事會", "Board not supportive"),
              ("我不確定", "Not sure")]

# --------------------------------------------------------------------------- #
# Variable definitions: (key, English label, header fragment)
# Org block and freelancer block share the same fragments; the first match is
# the organisational column, the second (".1") the freelancer one, and they are
# coalesced into one variable.
# --------------------------------------------------------------------------- #
D_ITEMS = [("d_workload", "Excess workload / uneven division", "[工作量過大"),
           ("d_role", "Unclear role definition", "[角色定位不清"),
           ("d_skill", "Job demands exceed training", "[工作要求的能力超出"),
           ("d_coworker", "Difficulty w/ colleagues", "[與同事溝通困難]"),
           ("d_supervisor", "Difficulty w/ supervisor", "[與主管溝通困難]"),
           ("d_client", "Client boundaries / emotional load", "[與服務對象之間的界線"),
           ("d_career", "Limited career path", "[職涯發展受限"),
           ("d_pay", "Pay / conditions unsustainable", "[薪資與勞動條件"),
           ("d_values", "Values misaligned w/ org", "[個人價值觀與機構方向不契合]")]
R_ITEMS = [("r_clear", "Clear expectations", "[我清楚知道工作上對我的期待"),
           ("r_autonomy", "Control over how I work", "[我能掌控自己執行工作的方式]"),
           ("r_coworker", "Colleague support", "[工作遇到困難時，同事會幫助我]"),
           ("r_supervisor", "Supervisor support", "[工作遇到困難時，主管會支持我]"),
           ("r_recognition", "Recognition", "[我的貢獻在工作中有獲得足夠的肯定"),
           ("r_wlb", "Org supports work-life balance", "[我的組織支持工作與個人生活"),
           ("r_voice", "Free to voice concerns", "[我可以自由地向組織的管理層表達"),
           ("r_skilldev", "Skill development opportunity", "[我在工作中有機會進一步發展"),
           ("r_careertalk", "Career talks w/ leadership", "[我的主管或組織負責人，會與我討論職涯")]
UWES_ITEMS = [("u_energy", "Full of energy", "[在工作時，我感到充滿能量。]"),
              ("u_passion", "Passionate about work", "[我對我的工作充滿熱忱。]"),
              ("u_absorbed", "Absorbed in work", "[我沉浸在我的工作中。]")]
# first 6 = personal burnout; last 7 = work-related burnout; the final one is reverse-scored
CBI_ITEMS = [("b1", "Often tired", "[你常覺得疲勞嗎"),
             ("b2", "Physically drained", "[你常覺得身體上體力透支嗎"),
             ("b3", "Emotionally drained", "[你常覺得情緒上心力交瘁嗎"),
             ("b4", "'Can't take it anymore'", "我快要撐不下去了"),
             ("b5", "Completely exhausted", "[你常覺得精疲力竭嗎"),
             ("b6", "Weak / about to get sick", "[你常常覺得虛弱"),
             ("w1", "Work emotionally draining", "[你的工作會令人情緒上心力交瘁嗎"),
             ("w2", "Work: about to collapse", "[你的工作會讓你覺得快要累垮了嗎"),
             ("w3", "Work is frustrating", "[你的工作會讓你覺得挫折嗎"),
             ("w4", "Drained after work day", "[工作一整天之後"),
             ("w5", "Dread another work day", "[上班之前只要想到"),
             ("w6", "Every work hour is an ordeal", "[上班時你會覺得每一刻都很難熬嗎"),
             ("w7", "Energy for friends/family (rev.)", "[不工作的時候")]
PQ_ITEMS = [("sts1", "Affected by traumatised clients", "[我想我已經被這些我所幫助"),
            ("bo1", "Feel stuck in helping work", "[從事助人的工作讓我感到陷入困境"),
            ("cs1", "I enjoy helping work", "[我喜歡從事助人的工作"),
            ("sts2", "Discouraged by traumatised clients", "[我所幫助的嚴重創傷經驗者讓我感到沮喪"),
            ("cs2", "Work gives me satisfaction", "[我的工作使我感到滿意"),
            ("bo2", "Exhausted because I'm a helper", "[我覺得筋疲力竭，因為"),
            ("bo3", "Overwhelmed by endless workload", "[我覺得很受不了"),
            ("sts3", "Intrusive / frightening thoughts", "[由於我助人的結果"),
            ("cs3", "Glad I chose this career", "[我很高興我選擇了做這份工作")]

LABELS: dict[str, str] = {k: l for k, l, _ in D_ITEMS + R_ITEMS + UWES_ITEMS + CBI_ITEMS + PQ_ITEMS}
LABELS.update({
    "demands_idx": "Job-demand index (0-4)", "resources_idx": "Job-resource index (1-5)",
    "personal_bo": "Personal burnout (0-100)", "work_bo": "Work-related burnout (0-100)",
    "engagement": "Work engagement UWES-3 (1-7)", "proqol_cs": "ProQOL compassion satisfaction",
    "proqol_bo": "ProQOL burnout", "proqol_sts": "ProQOL secondary traumatic stress",
    "consider_leaving": "Frequency considering leaving (0-4)", "expect_stay": "Expect to stay 1 yr (1-5)",
    "job_search_n": "Job-search behaviours (0-3)", "hours_actual": "Actual weekly hours (midpoint)",
    "helping_yrs": "Years in helping work (ordinal)", "org_tenure": "Tenure at org (ordinal)",
    "org_size": "Org size (ordinal)", "age_ord": "Age (ordinal)",
    "job_search": "Searched for jobs", "resume": "Updated resume", "applied": "Applied elsewhere",
})


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def norm(v):
    """Strip whitespace and normalise dashes so label matching is robust."""
    if pd.isna(v):
        return np.nan
    return re.sub(r"\s+", "", str(v)).replace("–", "-").replace("—", "-").replace("－", "-")


def find_cols(df: pd.DataFrame, frag: str) -> list[str]:
    return [c for c in df.columns if frag in c]


def coalesce(df: pd.DataFrame, frag: str, mapper=None, exact: bool = False) -> pd.Series:
    """Combine all columns that contain `frag` (org + freelancer blocks) into one Series."""
    cols = [c for c in df.columns if (c.strip() == frag if exact else frag in c)]
    if not cols:
        print(f"  [warn] column not found for fragment: {frag!r}")
        return pd.Series(np.nan, index=df.index)
    out = pd.Series(np.nan, index=df.index, dtype="object")
    for c in cols:
        s = df[c].map(norm) if mapper is not None else df[c]
        if mapper is not None:
            s = s.map(lambda v: mapper.get(v, np.nan) if not pd.isna(v) else np.nan)
        out = out.combine_first(s.astype("object"))
    return pd.to_numeric(out, errors="coerce") if mapper is not None else out


def label_rules(series: pd.Series, rules, default="Other") -> pd.Series:
    def f(v):
        if pd.isna(v):
            return np.nan
        for kw, lab in rules:
            if kw in str(v):
                return lab
        return default
    return series.map(f)


def ordinal(series: pd.Series, order: list[str], labels: list[str]):
    """Return (ordinal code Series, ordered labelled Categorical)."""
    n = series.map(norm)
    code = n.map({k: i for i, k in enumerate(order)}).astype(float)
    cat = pd.Categorical(n.map(dict(zip(order, labels))), categories=labels, ordered=True)
    return code, pd.Series(cat, index=series.index)


def row_mean(frame: pd.DataFrame, min_frac: float = 0.5) -> pd.Series:
    ok = frame.notna().sum(axis=1) >= math.ceil(frame.shape[1] * min_frac)
    return frame.mean(axis=1).where(ok)


def cronbach_alpha(items: pd.DataFrame) -> tuple[float, int]:
    x = items.dropna()
    k = x.shape[1]
    if len(x) < 10 or k < 2:
        return np.nan, len(x)
    var_sum = x.var(axis=0, ddof=1).sum()
    tot = x.sum(axis=1).var(ddof=1)
    return (k / (k - 1)) * (1 - var_sum / tot), len(x)


def bh_fdr(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (NaN-safe)."""
    p = np.asarray(p, dtype=float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adj = np.empty_like(pv)
    adj[order] = np.minimum(ranked, 1)
    q[ok] = adj
    return q


def stars(q: float) -> str:
    return "***" if q < 0.001 else "**" if q < 0.01 else "*" if q < 0.05 else ""


def multiselect_counts(series: pd.Series, kw_map) -> pd.Series:
    """% of answering respondents selecting each canonical option (keyword match)."""
    ans = series.dropna()
    ans = ans[ans.astype(str).str.strip() != ""]
    labels = list(dict.fromkeys(l for _, l in kw_map))
    counts = {lab: 0 for lab in labels}
    for cell in ans:
        hit = {lab for kw, lab in kw_map if kw in str(cell)}
        for lab in hit:
            counts[lab] += 1
    return pd.Series(counts) / max(len(ans), 1) * 100, len(ans)


def joined(df: pd.DataFrame, frag: str) -> pd.Series:
    cols = find_cols(df, frag)
    if not cols:
        return pd.Series(np.nan, index=df.index, dtype="object")
    return df[cols].apply(lambda r: " | ".join(str(x) for x in r.dropna()) or np.nan, axis=1)


class Out:
    """Output directory manager."""

    def __init__(self, root: str):
        self.root = root
        self.fig = os.path.join(root, "figures")
        self.tab = os.path.join(root, "tables")
        os.makedirs(self.fig, exist_ok=True)
        os.makedirs(self.tab, exist_ok=True)

    def save_fig(self, fig, name: str):
        path = os.path.join(self.fig, name)
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  figure -> {path}")

    def save_tab(self, df: pd.DataFrame, name: str, index: bool = True):
        path = os.path.join(self.tab, name)
        df.to_csv(path, index=index, encoding="utf-8-sig")
        print(f"  table  -> {path}")


# --------------------------------------------------------------------------- #
# 1. Load + clean
# --------------------------------------------------------------------------- #
def load_and_clean(path: str) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(path)
    print(f"Loaded {raw.shape[0]} responses x {raw.shape[1]} columns from {path}")
    d = pd.DataFrame(index=raw.index)
    meta: dict = {}

    # --- profile -----------------------------------------------------------
    d["respondent_type"] = label_rules(coalesce(raw, "你目前的助人／公益工作型態"), RULES_TYPE)
    d["is_freelancer"] = (d["respondent_type"] == "Freelancer / independent").astype(int)
    d["org_type"] = label_rules(coalesce(raw, "你任職機構的性質"), RULES_ORG)
    d["org_size_code"], d["org_size_cat"] = ordinal(coalesce(raw, "你的機構目前全職人數"), SIZE_ORDER, SIZE_LABEL)
    d["helping_yrs"], d["helping_yrs_cat"] = ordinal(coalesce(raw, "你的助人工作總年資"), TENURE_ORDER, TENURE_LABEL)
    d["org_tenure"], d["org_tenure_cat"] = ordinal(coalesce(raw, "你在目前所屬機構的總年資"), TENURE_ORDER, TENURE_LABEL)
    d["org_size"] = d["org_size_code"]
    d["age_ord"], d["age_cat"] = ordinal(coalesce(raw, "年齡", exact=True), AGE_ORDER, AGE_LABEL)
    d["role"] = label_rules(coalesce(raw, "你在機構中的角色"), RULES_ROLE)
    d["gender"] = label_rules(coalesce(raw, "性別", exact=True), RULES_GENDER)
    # county: map only known counties -> anything else (names/e-mails typed in error) is dropped
    d["county"] = coalesce(raw, "主要工作縣市", exact=True).map(lambda v: COUNTY_EN.get(str(v).strip(), np.nan))
    d["region"] = d["county"].map(lambda v: np.nan if pd.isna(v) else v if v in ("Taipei", "New Taipei") else "Other counties/cities")

    agreed = coalesce(raw, "「約定」的每週工時").map(norm)
    d["hours_agreed"] = agreed.map(HOURS_AGREED)
    actual = coalesce(raw, "「過去七天」").map(norm)
    d["hours_actual"] = actual.map(HOURS_ACTUAL_MID).astype(float)
    d["hours_actual_cat"] = pd.Categorical(actual.map(HOURS_ACTUAL_LABEL),
                                           categories=list(HOURS_ACTUAL_LABEL.values()), ordered=True)

    # --- item-level scales -------------------------------------------------
    for key, _, frag in D_ITEMS:
        d[key] = coalesce(raw, frag, DISTRESS)
    for key, _, frag in R_ITEMS:
        d[key] = coalesce(raw, frag, AGREE)
    for key, _, frag in UWES_ITEMS:
        d[key] = coalesce(raw, frag, UWES)
    for key, _, frag in CBI_ITEMS:
        d[key] = coalesce(raw, frag, OVERWORK)
    for key, _, frag in PQ_ITEMS:
        d[key] = coalesce(raw, frag, PROQOL)

    d["consider_leaving"] = coalesce(raw, "多常認真考慮離開", LEAVE)
    d["expect_stay"] = coalesce(raw, "你預期一年後", STAY)
    d["job_search"] = coalesce(raw, "[主動搜尋其他工作機會]", YESNO)
    d["resume"] = coalesce(raw, "[更新你的履歷]", YESNO)
    d["applied"] = coalesce(raw, "[申請其他工作機會]", YESNO)
    sb = d[["job_search", "resume", "applied"]]
    d["job_search_n"] = sb.sum(axis=1).where(sb.notna().all(axis=1))

    # --- composite indices -------------------------------------------------
    dk = [k for k, _, _ in D_ITEMS]
    rk = [k for k, _, _ in R_ITEMS]
    d["demands_idx"] = row_mean(d[dk])
    d["resources_idx"] = row_mean(d[rk])
    d["engagement"] = row_mean(d[[k for k, _, _ in UWES_ITEMS]], 1.0)

    cbi = d[[k for k, _, _ in CBI_ITEMS]].copy()
    cbi["w7"] = 6 - cbi["w7"]                       # reverse-score the 'energy left' item
    cbi01 = (cbi - 1) / 4 * 100                      # 0-100 scale
    d["personal_bo"] = row_mean(cbi01[[f"b{i}" for i in range(1, 7)]])
    d["work_bo"] = row_mean(cbi01[[f"w{i}" for i in range(1, 8)]])
    d["total_bo"] = row_mean(cbi01)
    d["work_bo_level"] = pd.cut(d["work_bo"], BURNOUT_BINS, labels=BURNOUT_LABELS)
    d["personal_bo_level"] = pd.cut(d["personal_bo"], BURNOUT_BINS, labels=BURNOUT_LABELS)
    d["proqol_cs"] = row_mean(d[["cs1", "cs2", "cs3"]], 1.0)
    d["proqol_bo"] = row_mean(d[["bo1", "bo2", "bo3"]], 1.0)
    d["proqol_sts"] = row_mean(d[["sts1", "sts2", "sts3"]], 1.0)
    d["high_leave"] = (d["consider_leaving"] >= 2).astype(float).where(d["consider_leaving"].notna())

    # --- multi-select / text-based fields (kept raw for charts only) -------
    d["_support_current"] = joined(raw, "你的機構目前有以下哪些支持制度")
    d["_support_wanted"] = joined(raw, "你最希望")
    d["_barriers"] = joined(raw, "還沒有建立這些制度").combine_first(joined(raw, "影響你的機構導入"))
    d["_free_support"] = coalesce(raw, "什麼樣的支持，會對現在的你最有幫助")
    d["_free_challenge1"] = coalesce(raw, "[第一大挑戰]")
    d["program_interest"] = coalesce(raw, "免費的支持方案")
    d["decision_maker_attitude"] = coalesce(raw, "決策者，對這件事")

    # reliability of the scales (Cronbach alpha)
    rel = []
    for name, cols, scale in [
        ("Job demands (9)", dk, d), ("Job resources (9)", rk, d),
        ("UWES-3 engagement (3)", [k for k, _, _ in UWES_ITEMS], d),
        ("CBI personal burnout (6)", [f"b{i}" for i in range(1, 7)], cbi),
        ("CBI work burnout (7, w7 reversed)", [f"w{i}" for i in range(1, 8)], cbi),
        ("ProQOL compassion satisfaction (3)", ["cs1", "cs2", "cs3"], d),
        ("ProQOL burnout (3)", ["bo1", "bo2", "bo3"], d),
        ("ProQOL secondary traumatic stress (3)", ["sts1", "sts2", "sts3"], d)]:
        a, n = cronbach_alpha(scale[cols])
        rel.append({"scale": name, "cronbach_alpha": round(a, 3), "n_complete": n})
    meta["reliability"] = pd.DataFrame(rel)
    meta["raw_n"] = len(raw)
    return d, meta


# --------------------------------------------------------------------------- #
# 2. Statistics
# --------------------------------------------------------------------------- #
def spearman_matrix(df: pd.DataFrame, cols: list[str]):
    n = len(cols)
    rho = pd.DataFrame(np.nan, index=cols, columns=cols)
    pv = rho.copy()
    nn = rho.copy()
    for i, a in enumerate(cols):
        for j in range(i, n):
            b = cols[j]
            sub = df[[a, b]].dropna()
            if i == j:
                r, p = 1.0, 0.0
            elif len(sub) >= MIN_PAIR_N and sub[a].nunique() > 1 and sub[b].nunique() > 1:
                r, p = stats.spearmanr(sub[a], sub[b])
            else:
                r, p = np.nan, np.nan
            rho.loc[a, b] = rho.loc[b, a] = r
            pv.loc[a, b] = pv.loc[b, a] = p
            nn.loc[a, b] = nn.loc[b, a] = len(sub)
    iu = np.triu_indices(n, 1)
    q = np.full((n, n), np.nan)
    qv = bh_fdr(pv.values[iu])
    q[iu] = qv
    q = np.where(np.isnan(q), q.T, q)
    np.fill_diagonal(q, 0.0)
    return rho, pv, pd.DataFrame(q, index=cols, columns=cols), nn


def long_corr(rho, pv, qv, nn) -> pd.DataFrame:
    rows = []
    cols = list(rho.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            rows.append({"var_1": LABELS.get(a, a), "var_2": LABELS.get(b, b),
                         "spearman_rho": rho.loc[a, b], "p_value": pv.loc[a, b],
                         "q_value_FDR": qv.loc[a, b], "n": int(nn.loc[a, b])})
    out = pd.DataFrame(rows).dropna(subset=["spearman_rho"])
    out["abs_rho"] = out["spearman_rho"].abs()
    return out.sort_values("abs_rho", ascending=False).drop(columns="abs_rho")


def group_tests(d: pd.DataFrame) -> pd.DataFrame:
    segmenters = {"Respondent type": "respondent_type", "Org type": "org_type",
                  "Org size": "org_size_cat", "Role": "role", "Gender": "gender",
                  "Age": "age_cat", "Region": "region", "Years in helping work": "helping_yrs_cat",
                  "Tenure at org": "org_tenure_cat", "Actual weekly hours": "hours_actual_cat",
                  "Agreed weekly hours": "hours_agreed"}
    outcomes = ["work_bo", "personal_bo", "engagement", "proqol_cs", "proqol_bo", "proqol_sts",
                "demands_idx", "resources_idx", "consider_leaving"]
    rows = []
    for sname, scol in segmenters.items():
        for o in outcomes:
            sub = d[[scol, o]].dropna()
            sub[scol] = sub[scol].astype(str)
            vc = sub[scol].value_counts()
            sub = sub[sub[scol].isin(vc[vc >= MIN_TEST_GROUP_N].index)]
            groups = [g[o].values for _, g in sub.groupby(scol)]
            if len(groups) < 2:
                continue
            if len(groups) == 2:
                u, p = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
                stat, test = u, "Mann-Whitney U"
                eff = abs(1 - 2 * u / (len(groups[0]) * len(groups[1])))   # rank-biserial
            else:
                stat, p = stats.kruskal(*groups)
                test = "Kruskal-Wallis H"
                eff = stat / (len(sub) - 1)                                  # epsilon-squared
            means = sub.groupby(scol)[o].mean().round(2).to_dict()
            rows.append({"segment": sname, "outcome": LABELS.get(o, o), "test": test,
                         "statistic": round(float(stat), 3), "p_value": p,
                         "effect_size": round(float(eff), 3), "n": len(sub),
                         "group_means": "; ".join(f"{k}={v}" for k, v in means.items())})
    out = pd.DataFrame(rows)
    out["q_value_FDR"] = bh_fdr(out["p_value"].values)
    return out.sort_values("p_value")


def ols_standardised(df: pd.DataFrame, y: str, xs: list[str]):
    """Standardised OLS (betas) with 95% CI via numpy -- no statsmodels needed."""
    sub = df[[y] + xs].dropna()
    z = (sub - sub.mean()) / sub.std(ddof=0)
    X = np.column_stack([np.ones(len(z)), z[xs].values])
    Y = z[y].values
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    dof = n - k
    sigma2 = resid @ resid / dof
    cov = sigma2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), dof)
    tcrit = stats.t.ppf(0.975, dof)
    r2 = 1 - (resid @ resid) / (Y @ Y - n * Y.mean() ** 2)
    adj = 1 - (1 - r2) * (n - 1) / dof
    fstat = (r2 / (k - 1)) / ((1 - r2) / dof)
    fp = stats.f.sf(fstat, k - 1, dof)
    # variance inflation factors
    vifs = []
    for j, name in enumerate(xs):
        others = [c for c in xs if c != name]
        Xo = np.column_stack([np.ones(n), z[others].values])
        bj, *_ = np.linalg.lstsq(Xo, z[name].values, rcond=None)
        rj = 1 - ((z[name].values - Xo @ bj) ** 2).sum() / ((z[name].values ** 2).sum())
        vifs.append(1 / (1 - rj) if rj < 1 else np.inf)
    coef = pd.DataFrame({"predictor": [LABELS.get(c, c) for c in xs], "key": xs,
                         "std_beta": beta[1:], "ci_low": beta[1:] - tcrit * se[1:],
                         "ci_high": beta[1:] + tcrit * se[1:], "p_value": p[1:], "VIF": vifs})
    coef["q_value_FDR"] = bh_fdr(coef["p_value"].values)
    summary = {"n": n, "r2": r2, "adj_r2": adj, "F": fstat, "F_p": fp}
    return coef.sort_values("std_beta", key=np.abs, ascending=False), summary


def random_forest_leave(d: pd.DataFrame, features: list[str], target: str = "high_leave"):
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.inspection import permutation_importance
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedKFold
        from sklearn.pipeline import make_pipeline
    except ImportError:
        print("  [skip] scikit-learn not installed -> random forest skipped")
        return None, None
    sub = d.dropna(subset=[target]).copy()
    X, y = sub[features], sub[target].astype(int)
    skf = StratifiedKFold(5, shuffle=True, random_state=42)
    aucs, imps = [], []
    for tr, te in skf.split(X, y):
        pipe = make_pipeline(SimpleImputer(strategy="median"),
                             RandomForestClassifier(n_estimators=400, min_samples_leaf=3,
                                                    class_weight="balanced", random_state=42, n_jobs=-1))
        pipe.fit(X.iloc[tr], y.iloc[tr])
        aucs.append(roc_auc_score(y.iloc[te], pipe.predict_proba(X.iloc[te])[:, 1]))
        pi = permutation_importance(pipe, X.iloc[te], y.iloc[te], n_repeats=20,
                                    scoring="roc_auc", random_state=42)
        imps.append(pi.importances_mean)
    imp = pd.DataFrame({"feature": [LABELS.get(f, f) for f in features], "key": features,
                        "perm_importance_auc_drop": np.mean(imps, axis=0)}
                       ).sort_values("perm_importance_auc_drop", ascending=False)
    info = {"n": len(sub), "positive_rate": float(y.mean()),
            "auc_mean": float(np.mean(aucs)), "auc_sd": float(np.std(aucs))}
    return imp, info


# --------------------------------------------------------------------------- #
# 3. Plots
# --------------------------------------------------------------------------- #
def barh_counts(ax, series: pd.Series, title: str, order=None, color=None, top: int | None = None):
    s = series.dropna()
    vc = s.value_counts()
    if order is not None:
        vc = vc.reindex([o for o in order if o in vc.index]).dropna()
    elif top:
        vc = vc.head(top)
    vc = vc[::-1]
    ax.barh(vc.index.astype(str), vc.values, color=color or PALETTE[0])
    for i, v in enumerate(vc.values):
        ax.text(v + vc.max() * 0.01, i, f"{v} ({v / len(s) * 100:.0f}%)", va="center", fontsize=8)
    ax.set_xlim(0, vc.max() * 1.28)
    ax.set_title(f"{title} (n={len(s)})", fontsize=10, loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)


def fig_profile(d, out: Out):
    fig, axes = plt.subplots(3, 3, figsize=(16, 12))
    barh_counts(axes[0, 0], d["respondent_type"], "Respondent type")
    barh_counts(axes[0, 1], d["org_type"], "Organisation type", color=PALETTE[1])
    barh_counts(axes[0, 2], d["org_size_cat"].astype(object), "Organisation size (full-time staff)",
                order=SIZE_LABEL[::-1][::-1], color=PALETTE[2])
    barh_counts(axes[1, 0], d["role"], "Role in organisation", color=PALETTE[3])
    barh_counts(axes[1, 1], d["gender"], "Gender", color=PALETTE[4])
    barh_counts(axes[1, 2], d["age_cat"].astype(object), "Age", order=AGE_LABEL, color=PALETTE[5])
    barh_counts(axes[2, 0], d["county"], "Main county / city (top 10)", top=10, color=PALETTE[6])
    barh_counts(axes[2, 1], d["helping_yrs_cat"].astype(object), "Years in helping work",
                order=TENURE_LABEL, color=PALETTE[7])
    barh_counts(axes[2, 2], d["hours_actual_cat"].astype(object), "Actual hours worked, past 7 days",
                order=list(HOURS_ACTUAL_LABEL.values()), color=PALETTE[8])
    fig.suptitle("Respondent profile", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out.save_fig(fig, "01_respondent_profile.png")

    # custom charts for gender, age, org size (for presentation)

    fig2, axes2 = plt.subplots(1, 1, figsize=(16, 12))
    barh_counts(axes2, d["gender"], "Gender", color=PALETTE[4])
    out.save_fig(fig2, "01_respondent_profile_gender.png")

    fig3, axes3 = plt.subplots(1, 1, figsize=(16, 12))
    barh_counts(axes3, d["age_cat"].astype(object), "Age", order=AGE_LABEL, color=PALETTE[5])
    out.save_fig(fig3, "01_respondent_profile_age.png")

    fig4, axes4 = plt.subplots(1, 1, figsize=(16, 12))
    barh_counts(axes4, d['org_size_cat'].astype(object), "Organization size (full-time staff)",
                order=SIZE_LABEL[::-1][::-1], color=PALETTE[2])
    out.save_fig(fig4, "01_respondent_profile_org_size.png")




def likert_stack(ax, data: pd.DataFrame, levels, level_labels, cmap, title):
    pct = pd.DataFrame({lv: (data == lv).sum() / data.notna().sum() * 100 for lv in levels})
    pct = pct.loc[data.mean().sort_values().index]
    names = [LABELS.get(k, k) for k in pct.index]
    left = np.zeros(len(pct))
    for lv, lab, col in zip(levels, level_labels, sns.color_palette(cmap, len(levels))):
        ax.barh(names, pct[lv], left=left, color=col, label=lab, edgecolor="white", linewidth=0.5)
        for i, (l, w) in enumerate(zip(left, pct[lv])):
            if w >= 7:
                ax.text(l + w / 2, i, f"{w:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if lv in (levels[0], levels[-1]) else "black")
        left += pct[lv].values
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of respondents")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.legend(ncol=len(levels), loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False, fontsize=8)
    ax.grid(axis="y", visible=False)


def fig_likert(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    likert_stack(ax, org[[k for k, _, _ in D_ITEMS]], [0, 1, 2, 3, 4],
                 ["None", "Mild", "Moderate", "Severe", "Very severe"], "YlOrRd",
                 f"Distress caused by job demands, past 6 months (org respondents, n={len(org.dropna(subset=['d_workload']))})")
    out.save_fig(fig, "02_job_demands_distress.png")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    likert_stack(ax, org[[k for k, _, _ in R_ITEMS]], [1, 2, 3, 4, 5],
                 ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"], "RdYlBu",
                 "Agreement with job-resource statements (org respondents)")
    out.save_fig(fig, "03_job_resources_agreement.png")


def fig_burnout(d, out: Out):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax = axes[0, 0]
    for col, name, c in [("personal_bo", "Personal burnout", PALETTE[0]), ("work_bo", "Work-related burnout", PALETTE[3])]:
        sns.kdeplot(d[col].dropna(), ax=ax, fill=True, alpha=0.35, color=c, label=f"{name} (mean {d[col].mean():.1f})")
    for x in (50, 75):
        ax.axvline(x, ls="--", c="grey", lw=0.8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("C-CBI-style score (0-100)")
    ax.set_title("Burnout score distributions", loc="left", fontweight="bold")
    ax.legend(frameon=False)

    ax = axes[0, 1]
    lv = pd.DataFrame({"Personal": d["personal_bo_level"].value_counts(normalize=True),
                       "Work-related": d["work_bo_level"].value_counts(normalize=True)}).reindex(BURNOUT_LABELS) * 100
    lv.T.plot(kind="barh", stacked=True, ax=ax, color=["#8fd19e", "#f6c85f", "#e4572e"], edgecolor="white")
    for i, row in enumerate(lv.T.values):
        left = 0
        for v in row:
            if v >= 6:
                ax.text(left + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9)
            left += v
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of respondents")
    ax.set_title("Burnout level (cut-offs 50 / 75)", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    ax.grid(axis="y", visible=False)

    ax = axes[1, 0]
    melt = d.melt(id_vars="respondent_type", value_vars=["personal_bo", "work_bo"]).dropna()
    melt["variable"] = melt["variable"].map({"personal_bo": "Personal", "work_bo": "Work-related"})
    sns.boxplot(data=melt, x="variable", y="value", hue="respondent_type", ax=ax, palette="Set2", fliersize=2)
    ax.set_xlabel("")
    ax.set_ylabel("Burnout score (0-100)")
    ax.set_title("Burnout by respondent type", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, title="")

    ax = axes[1, 1]
    order = [o for o in ["Frontline helper", "Mid-level manager", "Admin / project / finance",
                         "Founder / decision-maker"] if o in d["role"].values]
    sns.boxplot(data=d[d["role"].isin(order)], x="work_bo", y="role", order=order, ax=ax, palette="Set3", fliersize=2)
    ax.set_xlabel("Work-related burnout (0-100)")
    ax.set_ylabel("")
    ax.set_title("Work-related burnout by role", loc="left", fontweight="bold")
    fig.suptitle("Burnout (Copenhagen-style overwork scale)", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out.save_fig(fig, "04_burnout_overview.png")


def fig_wellbeing(d, out: Out):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    long = d.melt(value_vars=["proqol_cs", "proqol_bo", "proqol_sts"]).dropna()
    long["variable"] = long["variable"].map({"proqol_cs": "Compassion\nsatisfaction", "proqol_bo": "Burnout",
                                              "proqol_sts": "Secondary\ntraumatic stress"})
    sns.violinplot(data=long, x="variable", y="value", ax=axes[0], palette=["#6bbf8a", "#e4572e", "#7a6fb0"],
                   inner="quartile", cut=0)
    axes[0].set_ylabel("Mean item score (1-5)")
    axes[0].set_xlabel("")
    axes[0].set_title("ProQOL-9 subscales", loc="left", fontweight="bold")

    sns.histplot(d["engagement"].dropna(), bins=np.arange(0.75, 7.5, 0.5), ax=axes[1], color=PALETTE[2])
    axes[1].set_xlabel("UWES-3 engagement (1 = never ... 7 = always)")
    axes[1].set_title(f"Work engagement (mean {d['engagement'].mean():.2f})", loc="left", fontweight="bold")

    vals = d[[f"b{i}" for i in range(1, 7)] + [f"w{i}" for i in range(1, 8)]].copy()
    vals["w7"] = 6 - vals["w7"]
    m = vals.mean().sort_values()
    colors = [PALETTE[0] if k.startswith("b") else PALETTE[3] for k in m.index]
    axes[2].barh([LABELS[k] for k in m.index], m.values, color=colors)
    axes[2].set_xlim(1, 5)
    axes[2].set_xlabel("Mean (1-5, higher = more burnout)")
    axes[2].set_title("Burnout items (blue personal / red work)", loc="left", fontweight="bold")
    axes[2].tick_params(axis="y", labelsize=8)
    axes[2].grid(axis="y", visible=False)
    fig.tight_layout()
    out.save_fig(fig, "05_wellbeing_scales.png")


def fig_turnover(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    lab = {0: "Never", 1: "Once/twice", 2: "Monthly", 3: "Weekly", 4: "Daily"}
    vc = org["consider_leaving"].map(lab).value_counts().reindex(list(lab.values()))
    axes[0].bar(vc.index, vc.values, color=sns.color_palette("YlOrRd", 5))
    axes[0].set_title("Considered leaving, past 6 months", loc="left", fontweight="bold")
    axes[0].tick_params(axis="x", rotation=25)
    lab2 = {1: "Definitely\nnot", 2: "Probably\nnot", 3: "Unsure", 4: "Probably\nyes", 5: "Yes, long-term"}
    vc = org["expect_stay"].map(lab2).value_counts().reindex(list(lab2.values()))
    axes[1].bar(vc.index, vc.values, color=sns.color_palette("RdYlGn", 5))
    axes[1].set_title("Expect to be here in 1 year?", loc="left", fontweight="bold")
    axes[1].tick_params(axis="x", labelsize=8)
    pct = org[["job_search", "resume", "applied"]].mean() * 100
    axes[2].bar(["Searched for\njobs", "Updated\nresume", "Applied\nelsewhere"], pct.values, color=PALETTE[:3])
    for i, v in enumerate(pct.values):
        axes[2].text(i, v + 1, f"{v:.0f}%", ha="center")
    axes[2].set_ylim(0, 100)
    axes[2].set_ylabel("% of org respondents")
    axes[2].set_title("Job-search behaviour, past 6 months", loc="left", fontweight="bold")
    fig.tight_layout()
    out.save_fig(fig, "06_turnover_intent.png")


def fig_hours(d, out: Out):
    sub = d.dropna(subset=["hours_agreed", "hours_actual_cat"])
    ct = pd.crosstab(sub["hours_agreed"], sub["hours_actual_cat"]).reindex(
        index=[v for v in ["<=20", "21-40", "41+", "No agreement"] if v in sub["hours_agreed"].values],
        columns=list(HOURS_ACTUAL_LABEL.values()), fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1, 1]})
    sns.heatmap(ct, annot=True, fmt="d", cmap="Blues", ax=axes[0], cbar_kws={"label": "respondents"})
    axes[0].set_xlabel("Actual hours worked (past 7 days)")
    axes[0].set_ylabel("Agreed weekly hours")
    axes[0].set_title("Agreed vs actual working hours", loc="left", fontweight="bold")
    sub2 = d.dropna(subset=["hours_actual_cat", "work_bo"])
    sns.boxplot(data=sub2, x="hours_actual_cat", y="work_bo", ax=axes[1], palette="YlOrRd", fliersize=2)
    axes[1].set_xlabel("Actual hours worked (past 7 days)")
    axes[1].set_ylabel("Work-related burnout (0-100)")
    axes[1].set_title("Burnout by actual hours", loc="left", fontweight="bold")
    fig.tight_layout()
    out.save_fig(fig, "07_working_hours.png")


def fig_eap(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    cur, n_cur = multiselect_counts(d["_support_current"], SUPPORT_KW)
    want, n_want = multiselect_counts(d["_support_wanted"], SUPPORT_KW)
    cmp_ = pd.DataFrame({"Currently available": cur, "Most wanted (pick up to 3)": want}).dropna(how="all")
    cmp_ = cmp_.sort_values("Most wanted (pick up to 3)")
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(cmp_))
    ax.barh(y + 0.2, cmp_["Currently available"], 0.4, label=f"Currently available (n={n_cur})", color=PALETTE[0])
    ax.barh(y - 0.2, cmp_["Most wanted (pick up to 3)"], 0.4, label=f"Most wanted (n={n_want})", color=PALETTE[3])
    ax.set_yticks(y)
    ax.set_yticklabels(cmp_.index)
    ax.set_xlabel("% of respondents")
    ax.set_title("Employee-support (EAP) measures: availability vs need", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "08_eap_supply_vs_demand.png")
    out.save_tab(cmp_.round(1), "eap_supply_vs_demand_pct.csv")

    bar, n_b = multiselect_counts(d["_barriers"], BARRIER_KW)
    bar = bar[bar > 0].sort_values()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(bar.index, bar.values, color=PALETTE[4])
    for i, v in enumerate(bar.values):
        ax.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=9)
    ax.set_xlabel("% of respondents")
    ax.set_title(f"Why the organisation has no/limited support systems (n={n_b})", loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "09_eap_barriers.png")
    out.save_tab(bar.round(1).to_frame("pct"), "eap_barriers_pct.csv")

    # programme interest + decision-maker attitude
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    barh_counts(axes[0], d["program_interest"].map(
        lambda v: np.nan if pd.isna(v) else
        "Very much, we need it" if "非常希望" in v else "Yes, unsure of capacity" if "餘力" in v else
        "Fine / optional" if "可有可無" in v else "Not interested (other priorities)" if "不太希望" in v else "Not sure"),
        "Would your org join a free support programme?", color=PALETTE[2])
    barh_counts(axes[1], d["decision_maker_attitude"].map(
        lambda v: np.nan if pd.isna(v) else
        "Interested but cost/workload worry" if "擔心成本" in v else "Might think unnecessary" if "不需要" in v else
        "Not the right time" if "不是時候" in v else "Very enthusiastic" if "很積極" in v else
        "I am the decision-maker" if "決策者" in v and "自己" in v else "Not sure"),
        "Expected attitude of decision-makers", color=PALETTE[5])
    fig.tight_layout()
    out.save_fig(fig, "10_programme_interest.png")


def fig_corr_composite(d, out: Out):
    keys = ["demands_idx", "resources_idx", "personal_bo", "work_bo", "engagement", "proqol_cs", "proqol_bo",
            "proqol_sts", "consider_leaving", "expect_stay", "job_search_n", "hours_actual", "helping_yrs",
            "org_tenure", "org_size", "age_ord"]
    rho, pv, qv, nn = spearman_matrix(d, keys)
    out.save_tab(rho.rename(index=LABELS, columns=LABELS).round(3), "corr_composite_spearman_rho.csv")
    out.save_tab(qv.rename(index=LABELS, columns=LABELS).round(4), "corr_composite_fdr_q.csv")
    annot = rho.copy().astype(object)
    for a in keys:
        for b in keys:
            r = rho.loc[a, b]
            annot.loc[a, b] = "" if pd.isna(r) else f"{r:.2f}{stars(qv.loc[a, b]) if a != b else ''}"
    mask = np.triu(np.ones_like(rho, dtype=bool), k=1)
    fig, ax = plt.subplots(figsize=(13, 10.5))
    sns.heatmap(rho.astype(float), mask=mask, annot=annot.values, fmt="", cmap="RdBu_r", vmin=-1, vmax=1,
                center=0, linewidths=0.5, square=True, ax=ax, annot_kws={"size": 7.5},
                cbar_kws={"label": "Spearman rho", "shrink": 0.7},
                xticklabels=[LABELS[k] for k in keys], yticklabels=[LABELS[k] for k in keys])
    ax.set_title("Correlation heatmap: composite indices (Spearman; * q<.05, ** q<.01, *** q<.001, BH-FDR)",
                 loc="left", fontweight="bold", fontsize=11)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    out.save_fig(fig, "11_corr_heatmap_composites.png")
    return rho, pv, qv, nn


def fig_corr_items(d, out: Out):
    keys = ([k for k, _, _ in D_ITEMS] + [k for k, _, _ in R_ITEMS] + [k for k, _, _ in UWES_ITEMS]
            + [k for k, _, _ in CBI_ITEMS] + [k for k, _, _ in PQ_ITEMS] + ["consider_leaving", "expect_stay"])
    rho, pv, qv, nn = spearman_matrix(d, keys)
    rho_full = rho.fillna(0).astype(float)
    labels = [LABELS[k] for k in keys]
    g = sns.clustermap(rho_full.set_axis(labels, axis=0).set_axis(labels, axis=1), cmap="RdBu_r", vmin=-1, vmax=1,
                       center=0, figsize=(17, 16), linewidths=0.2, cbar_kws={"label": "Spearman rho"},
                       dendrogram_ratio=0.08, method="average")
    g.fig.suptitle("Item-level correlation clustermap (hierarchically clustered)", y=1.0, fontweight="bold", fontsize=14)
    plt.setp(g.ax_heatmap.get_xticklabels(), rotation=90, fontsize=7.5)
    plt.setp(g.ax_heatmap.get_yticklabels(), fontsize=7.5)
    out.save_fig(g.fig, "12_corr_clustermap_items.png")
    out.save_tab(long_corr(rho, pv, qv, nn).round(4), "corr_item_level_all_pairs.csv", index=False)
    return rho, pv, qv, nn


def fig_demand_vs_resource(d, out: Out):
    """Cross-block heatmap: job demands (rows) vs resources (cols) and vs outcomes."""
    dk = [k for k, _, _ in D_ITEMS]
    rk = [k for k, _, _ in R_ITEMS]
    outcomes = ["work_bo", "personal_bo", "engagement", "proqol_cs", "proqol_bo", "proqol_sts",
                "consider_leaving", "expect_stay"]
    rho, pv, qv, nn = spearman_matrix(d, dk + rk + outcomes)
    block = rho.loc[dk + rk, outcomes].astype(float)
    qb = qv.loc[dk + rk, outcomes]
    annot = block.copy().astype(object)
    for r in block.index:
        for c in block.columns:
            annot.loc[r, c] = f"{block.loc[r, c]:.2f}{stars(qb.loc[r, c])}"
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(block, annot=annot.values, fmt="", cmap="RdBu_r", vmin=-0.7, vmax=0.7, center=0,
                linewidths=0.5, ax=ax, cbar_kws={"label": "Spearman rho"},
                xticklabels=[LABELS[c] for c in outcomes], yticklabels=[LABELS[k] for k in dk + rk])
    ax.axhline(len(dk), color="black", lw=2)
    ax.set_title("Which job demands / resources relate to well-being & retention?\n"
                 "(top block: demands, bottom block: resources; * q<.05 FDR)", loc="left", fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    out.save_fig(fig, "13_demands_resources_vs_outcomes_heatmap.png")
    out.save_tab(block.rename(index=LABELS, columns=LABELS).round(3), "corr_items_vs_outcomes_rho.csv")


def fig_segment_heatmap(d, out: Out):
    metrics = {"Work burnout": ("work_bo", 0, 100), "Personal burnout": ("personal_bo", 0, 100),
               "Engagement": ("engagement", 1, 7), "Compassion satisf.": ("proqol_cs", 1, 5),
               "ProQOL burnout": ("proqol_bo", 1, 5), "Sec. traumatic stress": ("proqol_sts", 1, 5),
               "Job demands": ("demands_idx", 0, 4), "Job resources": ("resources_idx", 1, 5),
               "Considers leaving": ("consider_leaving", 0, 4)}
    segs = [("Role", "role"), ("Org size", "org_size_cat"), ("Org type", "org_type"), ("Gender", "gender"),
            ("Age", "age_cat"), ("Region", "region"), ("Helping yrs", "helping_yrs_cat"),
            ("Org tenure", "org_tenure_cat"), ("Actual hrs", "hours_actual_cat"), ("Type", "respondent_type")]
    rows, idx = [], []
    for sname, col in segs:
        for g, sub in d.groupby(col, observed=True):
            if len(sub) < MIN_GROUP_N:
                continue
            rows.append({m: (sub[c].mean() - lo) / (hi - lo) * 100 for m, (c, lo, hi) in metrics.items()})
            idx.append(f"{sname}: {g} (n={len(sub)})")
    seg = pd.DataFrame(rows, index=idx)
    out.save_tab(seg.round(1), "segment_means_scaled_0_100.csv")
    z = (seg - seg.mean()) / seg.std(ddof=0)       # column-wise colour so metrics are comparable
    fig, ax = plt.subplots(figsize=(12, max(8, 0.3 * len(seg))))
    sns.heatmap(z, annot=seg.round(0), fmt=".0f", cmap="RdYlBu_r", center=0, linewidths=0.4,
                ax=ax, cbar_kws={"label": "column z-score (colour)  |  numbers = mean rescaled 0-100"}, annot_kws={"size": 8})
    ax.set_title("Segment heatmap: mean well-being indicators by subgroup (groups with n>=%d)" % MIN_GROUP_N,
                 loc="left", fontweight="bold")
    ax.xaxis.tick_top()
    plt.setp(ax.get_xticklabels(), rotation=35, ha="left")
    out.save_fig(fig, "14_segment_heatmap.png")


def fig_correlates_of_burnout(d, target: str, fname: str, out: Out, title: str):
    cands = ([k for k, _, _ in D_ITEMS] + [k for k, _, _ in R_ITEMS] + ["demands_idx", "resources_idx",
             "hours_actual", "helping_yrs", "org_tenure", "org_size", "age_ord", "engagement", "proqol_cs"])
    rows = []
    for c in cands:
        sub = d[[target, c]].dropna()
        if len(sub) >= MIN_PAIR_N and sub[c].nunique() > 1:
            r, p = stats.spearmanr(sub[target], sub[c])
            rows.append({"key": c, "variable": LABELS[c], "rho": r, "p": p, "n": len(sub)})
    t = pd.DataFrame(rows)
    t["q"] = bh_fdr(t["p"].values)
    t = t.sort_values("rho")
    fig, ax = plt.subplots(figsize=(9.5, 0.28 * len(t) + 1.5))
    ax.barh(t["variable"], t["rho"], color=np.where(t["rho"] > 0, "#e4572e", "#2e86ab"))
    for i, (r, q) in enumerate(zip(t["rho"], t["q"])):
        ax.text(r + (0.01 if r >= 0 else -0.01), i, stars(q), va="center", ha="left" if r >= 0 else "right", fontsize=9)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Spearman rho (* q<.05, ** q<.01, *** q<.001)")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, fname)
    return t.sort_values("rho", key=np.abs, ascending=False)


def fig_scatter(d, out: Out):
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for ax, (x, y, c) in zip(axes.flat[:3], [("demands_idx", "work_bo", PALETTE[3]),
                                             ("resources_idx", "work_bo", PALETTE[0]),
                                             ("work_bo", "engagement", PALETTE[2])]):
        sub = d[[x, y]].dropna()
        sns.regplot(data=sub, x=x, y=y, ax=ax, color=c, scatter_kws={"alpha": 0.45, "s": 25},
                    line_kws={"lw": 2}, lowess=False)
        r, p = stats.spearmanr(sub[x], sub[y])
        ax.set_xlabel(LABELS[x])
        ax.set_ylabel(LABELS[y])
        ax.set_title(f"rho = {r:.2f}, p = {p:.1g}, n = {len(sub)}", loc="left", fontsize=10, fontweight="bold")
    ax = axes[1, 1]
    lab = {0: "Never", 1: "1-2x", 2: "Monthly", 3: "Weekly", 4: "Daily"}
    sub = d.dropna(subset=["consider_leaving", "work_bo"]).copy()
    sub["lv"] = pd.Categorical(sub["consider_leaving"].map(lab), categories=list(lab.values()), ordered=True)
    sns.boxplot(data=sub, x="lv", y="work_bo", ax=ax, palette="YlOrRd", fliersize=2)
    ax.set_xlabel("Frequency of considering leaving (past 6 months)")
    ax.set_ylabel(LABELS["work_bo"])
    r, p = stats.spearmanr(sub["consider_leaving"], sub["work_bo"])
    ax.set_title(f"rho = {r:.2f}, p = {p:.1g}, n = {len(sub)}", loc="left", fontsize=10, fontweight="bold")
    fig.suptitle("Key relationships", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out.save_fig(fig, "16_key_relationships_scatter.png")


def fig_regression(coef: pd.DataFrame, summ: dict, out: Out, name: str, title: str):
    c = coef.sort_values("std_beta")
    fig, ax = plt.subplots(figsize=(9.5, 0.3 * len(c) + 1.8))
    colors = np.where(c["p_value"] < ALPHA, np.where(c["std_beta"] > 0, "#e4572e", "#2e86ab"), "#b0b0b0")
    ax.barh(c["predictor"], c["std_beta"], color=colors)
    ax.errorbar(c["std_beta"], np.arange(len(c)), xerr=[c["std_beta"] - c["ci_low"], c["ci_high"] - c["std_beta"]],
                fmt="none", ecolor="black", lw=0.8, capsize=2)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Standardised beta (95% CI) -- coloured = p<.05, grey = n.s.")
    ax.set_title(f"{title}\nn={summ['n']}, R²={summ['r2']:.2f}, adj. R²={summ['adj_r2']:.2f}",
                 loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, name)


def fig_rf(imp: pd.DataFrame, info: dict, out: Out):
    t = imp.head(15).sort_values("perm_importance_auc_drop")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(t["feature"], t["perm_importance_auc_drop"], color=PALETTE[4])
    ax.set_xlabel("Permutation importance (drop in held-out AUC)")
    ax.set_title(f"Random forest: considers leaving at least monthly\n5-fold CV AUC = {info['auc_mean']:.2f} ± {info['auc_sd']:.2f}"
                 f"  (n={info['n']}, {info['positive_rate'] * 100:.0f}% positive)", loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "18_random_forest_intent_to_leave.png")


# --------------------------------------------------------------------------- #
# 4. Report
# --------------------------------------------------------------------------- #
def write_report(d, meta, out: Out, comp_corr, burn_tab, gt, regs, rf_imp, rf_info):
    rho, pv, qv, nn = comp_corr
    L: list[str] = []
    org = d[d["is_freelancer"] == 0]
    L.append("# 2026 Taiwan Helpers' Needs Survey -- automated analysis summary\n")
    L.append(f"- Responses analysed: **{meta['raw_n']}** "
             f"({int((d['is_freelancer'] == 0).sum())} organisation-affiliated incl. hybrid, "
             f"{int(d['is_freelancer'].sum())} freelancers/independents)")
    L.append(f"- Women: {(d['gender'] == 'Female').mean() * 100:.0f}%; "
             f"Taipei + New Taipei: {d['region'].isin(['Taipei', 'New Taipei']).sum() / d['region'].notna().sum() * 100:.0f}% "
             "of those reporting a county.")
    L.append("- Sample is self-selected (not probability-based): treat percentages as descriptive of respondents, not of all Taiwanese helpers.\n")

    L.append("## Scale reliability (Cronbach's alpha)\n")
    L.append(meta["reliability"].to_markdown(index=False) + "\n")

    L.append("## Burnout headline numbers\n")
    for col, nm in [("personal_bo", "Personal burnout"), ("work_bo", "Work-related burnout")]:
        s = d[col].dropna()
        hi = (s >= 75).mean() * 100
        mod = ((s >= 50) & (s < 75)).mean() * 100
        L.append(f"- {nm}: mean {s.mean():.1f} (SD {s.std():.1f}, n={len(s)}); "
                 f"{mod:.0f}% moderate (50-74), {hi:.0f}% high (>=75)")
    L.append(f"- ≥ monthly thoughts of leaving (org respondents): {org['high_leave'].mean() * 100:.0f}%; "
             f"actively searched for jobs: {org['job_search'].mean() * 100:.0f}%.\n")

    L.append("## Strongest correlations among composite indices (FDR q<.05)\n")
    keys = list(rho.columns)
    rows = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if qv.loc[a, b] < ALPHA:
                rows.append((LABELS[a], LABELS[b], rho.loc[a, b], qv.loc[a, b], int(nn.loc[a, b])))
    rows.sort(key=lambda r: -abs(r[2]))
    L.append("| Variable 1 | Variable 2 | rho | q | n |\n|---|---|---|---|---|")
    for a, b, r, q, n in rows[:15]:
        L.append(f"| {a} | {b} | {r:.2f} | {q:.3g} | {n} |")
    L.append("")

    L.append("## Items most associated with work-related burnout (Spearman)\n")
    L.append("| Variable | rho | q | n |\n|---|---|---|---|")
    for _, r in burn_tab.head(10).iterrows():
        L.append(f"| {r['variable']} | {r['rho']:.2f} | {r['q']:.3g} | {int(r['n'])} |")
    L.append("")

    L.append("## Significant group differences (FDR q<.05)\n")
    sig = gt[gt["q_value_FDR"] < ALPHA]
    if sig.empty:
        L.append("No subgroup difference survived FDR correction.\n")
    else:
        L.append("| Segment | Outcome | Test | p | q | effect | n | Group means |\n|---|---|---|---|---|---|---|---|")
        for _, r in sig.head(15).iterrows():
            L.append(f"| {r['segment']} | {r['outcome']} | {r['test']} | {r['p_value']:.3g} | "
                     f"{r['q_value_FDR']:.3g} | {r['effect_size']} | {r['n']} | {r['group_means']} |")
        L.append("")

    for name, (coef, s) in regs.items():
        L.append(f"## Regression: {name}\n")
        L.append(f"Standardised OLS, n={s['n']}, R²={s['r2']:.3f}, adj. R²={s['adj_r2']:.3f}, "
                 f"F p={s['F_p']:.2g}. Significant predictors (p<.05):\n")
        sg = coef[coef["p_value"] < ALPHA]
        if sg.empty:
            L.append("_none_\n")
        else:
            L.append("| Predictor | std. beta | 95% CI | p | VIF |\n|---|---|---|---|---|")
            for _, r in sg.iterrows():
                L.append(f"| {r['predictor']} | {r['std_beta']:.2f} | [{r['ci_low']:.2f}, {r['ci_high']:.2f}] | "
                         f"{r['p_value']:.3g} | {r['VIF']:.1f} |")
            L.append("")
    if rf_info:
        L.append("## Random forest: considers leaving at least monthly\n")
        L.append(f"5-fold CV AUC {rf_info['auc_mean']:.2f} ± {rf_info['auc_sd']:.2f} (n={rf_info['n']}). Top drivers:\n")
        for _, r in rf_imp.head(6).iterrows():
            L.append(f"- {r['feature']} (importance {r['perm_importance_auc_drop']:.3f})")
        L.append("")
    L.append("## Method notes\n")
    L.append("- Likert answers are coded ordinally; correlations are Spearman (rank-based); p-values corrected with Benjamini-Hochberg FDR.\n"
             "- Burnout: 13 overwork items rescaled 0-100 (item 'energy for friends/family' reverse-scored); personal = items 1-6, work = items 7-13. Cut-offs 50/75 are conventional, editable at the top of the script.\n"
             "- ProQOL-9: subscale means of three items each. UWES-3: mean of three items (1-7).\n"
             "- Freelancer and organisational answer blocks are merged for shared scales; job-demand/resource, turnover and EAP items exist only for the organisational block.\n"
             "- Correlation and regression show association, not causation; the sample is self-selected.\n")
    path = os.path.join(out.root, "analysis_summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  report -> {path}")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Analyse the 2026 Taiwan Helpers' Needs Survey CSV")
    ap.add_argument("--input", "-i", help="survey CSV (default: first *.csv in cwd)")
    ap.add_argument("--out", "-o", default="analysis_output", help="output directory")
    ap.add_argument("--no-ml", action="store_true", help="skip the random-forest model")
    args = ap.parse_args()

    path = args.input
    if not path:
        found = sorted(glob.glob("*.csv"))
        if not found:
            sys.exit("No CSV found: pass --input path/to/survey.csv")
        path = found[0]
    out = Out(args.out)

    print("\n[1/6] Cleaning & coding data")
    d, meta = load_and_clean(path)
    public = d[[c for c in d.columns if not c.startswith("_")]].copy()
    for c in public.select_dtypes("category").columns:
        public[c] = public[c].astype(object)
    out.save_tab(public, "cleaned_coded_data_anonymised.csv")
    out.save_tab(meta["reliability"], "scale_reliability.csv", index=False)

    print("\n[2/6] Descriptive statistics")
    num = [k for k in LABELS if k in d.columns]
    desc = d[num].describe().T.rename(index=LABELS)
    desc["missing"] = d[num].isna().sum().values
    out.save_tab(desc.round(3), "descriptive_statistics.csv")

    print("\n[3/6] Descriptive charts")
    fig_profile(d, out)
    fig_likert(d, out)
    fig_burnout(d, out)
    fig_wellbeing(d, out)
    fig_turnover(d, out)
    fig_hours(d, out)
    fig_eap(d, out)

    print("\n[4/6] Correlations & heatmaps")
    comp = fig_corr_composite(d, out)
    out.save_tab(long_corr(*comp).round(4), "corr_composite_all_pairs.csv", index=False)
    fig_corr_items(d, out)
    fig_demand_vs_resource(d, out)
    fig_segment_heatmap(d, out)
    burn_tab = fig_correlates_of_burnout(d, "work_bo", "15_correlates_of_work_burnout.png", out,
                                         "Correlates of work-related burnout (Spearman rho)")
    out.save_tab(burn_tab.round(4), "correlates_of_work_burnout.csv", index=False)
    fig_correlates_of_burnout(d, "consider_leaving", "17_correlates_of_intent_to_leave.png", out,
                              "Correlates of considering leaving (Spearman rho)")
    fig_scatter(d, out)

    print("\n[5/6] Group comparisons & models")
    gt = group_tests(d)
    out.save_tab(gt.round(5), "group_comparison_tests.csv", index=False)
    predictors = [k for k, _, _ in D_ITEMS] + [k for k, _, _ in R_ITEMS]
    regs = {}
    for target, nm in [("work_bo", "Work-related burnout"), ("engagement", "Work engagement")]:
        coef, summ = ols_standardised(d, target, predictors)
        regs[nm] = (coef, summ)
        out.save_tab(coef.round(4), f"regression_{target}.csv", index=False)
        fig_regression(coef, summ, out, f"19_regression_{target}.png",
                       f"Standardised OLS: {nm} ~ job demands + job resources")
    rf_imp = rf_info = None
    if not args.no_ml:
        feats = predictors + ["hours_actual", "org_tenure", "helping_yrs", "org_size", "age_ord"]
        rf_imp, rf_info = random_forest_leave(d, feats)
        if rf_imp is not None:
            out.save_tab(rf_imp.round(4), "random_forest_importance.csv", index=False)
            fig_rf(rf_imp, rf_info, out)

    print("\n[6/6] Writing summary report")
    write_report(d, meta, out, comp, burn_tab, gt, regs, rf_imp, rf_info)
    print(f"\nDone. Everything is in: {os.path.abspath(out.root)}")


if __name__ == "__main__":
    main()