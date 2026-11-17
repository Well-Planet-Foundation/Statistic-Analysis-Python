"""
2026 Taiwan Helpers' Needs Survey (Well Planet) -- analysis pipeline  (v2)
========================================================================

Reads the raw Google-Forms CSV export and produces
  * a cleaned, anonymised, numerically-coded dataset
  * the model constructs for Equations 1-3 (Burnout, Job satisfaction, Retention) with reliability diagnostics
  * descriptive charts, correlation heatmaps (incl. partial correlations), group tests
  * Eq.1-3 as robust standardised OLS + a bootstrap mediation analysis
  * a Markdown summary of the key findings
EVERY chart is written as its own PNG (figures/<section>/<name>.png) so it can be dropped straight into a document.

Usage
-----
    python helper_survey_analysis.py                       # auto-finds *.csv in cwd
    python helper_survey_analysis.py --input survey.csv --out results
    python helper_survey_analysis.py --no-ml --boot 500    # faster run

Requirements: pandas, numpy, scipy, matplotlib, seaborn  (scikit-learn optional)

Privacy: e-mail addresses, free-text answers, timestamps and any non-county text typed in the county
field (some respondents typed their names) are dropped and never written to any output file.
Note the cleaned CSV still holds role/age/gender/county/org-size together: share it only with the research team.

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
# MODEL SPECIFICATION  (Equations 1-3)
# All column numbers below are 0-BASED (pandas .iloc positions), exactly as in
# the research team's brief.  Items are located by header text, and the script
# verifies at start-up that the header text really sits at the stated position.
#
#   Eq.1  Burnout (BO)          = b0 + b1 WL + b2 OS + b3 JR + b4 PAY + b5 MA + b6 ID + g1 SIZE + g2 MISSION + e1
#   Eq.2  Job satisfaction (JS) = a0 + a1 WL + a2 OS + a3 JR + a4 PAY + a5 MA + a6 ID + g3 SIZE + g4 MISSION + e2
#   Eq.3  Retention (RET)       = d0 + d1 JS + d2 BO + g5 SIZE + g6 MISSION + e3
# --------------------------------------------------------------------------- #
EXTRA_FRAG = {"hours_agreed_ord": "「約定」的每週工時", "hours_actual_ord": "「過去七天」",
              "consider_leaving": "多常認真考慮離開", "expect_stay": "你預期一年後",
              "job_search": "[主動搜尋其他工作機會]", "resume": "[更新你的履歷]",
              "applied": "[申請其他工作機會]", "SIZE": "你的機構目前全職人數",
              "MISSION": "你的機構主要服務領域"}
ITEM_FRAG = {k: f for k, _, f in D_ITEMS + R_ITEMS + UWES_ITEMS + CBI_ITEMS + PQ_ITEMS}
ITEM_FRAG.update(EXTRA_FRAG)

# theoretical (min, max) of each coded item -> used for 0-100 "percent of maximum possible" (POMP) scaling,
# so that items answered on different scales (0-4, 1-5, 1-7, yes/no, hour bands) can be averaged fairly
ITEM_RANGE = {}
ITEM_RANGE.update({k: (0, 4) for k, _, _ in D_ITEMS})
ITEM_RANGE.update({k: (1, 5) for k, _, _ in R_ITEMS + CBI_ITEMS + PQ_ITEMS})
ITEM_RANGE.update({k: (1, 7) for k, _, _ in UWES_ITEMS})
ITEM_RANGE.update({"hours_agreed_ord": (1, 3), "hours_actual_ord": (1, 5), "consider_leaving": (0, 4),
                   "expect_stay": (1, 5), "job_search": (0, 1), "resume": (0, 1), "applied": (0, 1)})
HOURS_AGREED_ORD = {"20小時以下": 1, "21-40小時": 2, "41小時以上": 3}          # "no agreement" -> missing
HOURS_ACTUAL_ORD = {"20小時以下": 1, "21-40小時": 2, "41-50小時": 3, "51-60小時": 4, "61小時以上": 5}

_BO = [(f"b{i}", 0) for i in range(1, 7)] + [(f"w{i}", 0) for i in range(1, 7)] + [("w7", 1)]
# (item key, reverse-scored?)  ---- 1) the specification EXACTLY as supplied by the team
SPEC_USER = {
    "WL": [("d_workload", 0), ("d_role", 0), ("d_client", 0), ("hours_agreed_ord", 0), ("hours_actual_ord", 0)],
    "OS": [("d_coworker", 0), ("d_supervisor", 1), ("r_coworker", 0), ("r_supervisor", 0),
           ("r_recognition", 0), ("r_wlb", 0), ("r_voice", 0)],
    "JR": [("d_career", 1), ("r_clear", 0), ("r_autonomy", 0), ("r_skilldev", 0), ("r_careertalk", 0)],
    "PAY": [("d_pay", 1)], "MA": [("d_values", 1)],
    "ID": [("u_energy", 0), ("u_passion", 0), ("u_absorbed", 0)],
    "BO": _BO,
    "JS": [("cs1", 0), ("cs2", 0), ("cs3", 0)],
    "RET": [("consider_leaving", 1), ("expect_stay", 0), ("job_search", 0), ("resume", 0), ("applied", 0)],
}
USER_COLS = {"WL": [7, 8, 9, 10, 14], "OS": [12, 13, 20, 21, 22, 23, 24], "JR": [15, 18, 19, 25, 26],
             "PAY": [16], "MA": [17], "ID": [32, 33, 34], "BO": list(range(35, 48)), "JS": [51, 53, 57],
             "RET": [27, 28, 29, 30, 31]}
# ---- 2) the REVISED specification used for every result in this script (reasons in CONSTRUCT_NOTES)
SPEC = {k: list(v) for k, v in SPEC_USER.items()}
SPEC["WL"] = [("d_workload", 0), ("d_role", 0), ("d_skill", 0), ("d_client", 0), ("hours_actual_ord", 0)]
SPEC["OS"] = [("d_coworker", 1), ("d_supervisor", 1), ("r_coworker", 0), ("r_supervisor", 0),
              ("r_recognition", 0), ("r_wlb", 0), ("r_voice", 0)]
SPEC["RET"] = [("consider_leaving", 1), ("expect_stay", 0), ("job_search", 1), ("resume", 1), ("applied", 1)]
MIN_FRAC = {"PAY": 1.0, "MA": 1.0, "ID": 1.0, "JS": 1.0}       # all other composites: >= 50% of items answered

CONSTRUCT_NOTES = {
    "WL": "Added col 11 (skills exceed training; r=.44-.59 with the other workload items, unassigned in the brief). "
          "Dropped col 7 (agreed hours): a contract term rather than load, item-rest r~.1, and 'no agreement' (n=32) is missing.",
    "OS": "Col 12 (difficulty with colleagues) must be reversed like col 13: both are 'difficulty' items on a distress scale, "
          "and col 12 correlates NEGATIVELY (-.29 to -.41) with the other support items.",
    "RET": "Cols 29-31 (searched / updated CV / applied) are coded 1 = yes = leaving, so they must be reversed like col 27. "
           "As briefed, alpha = 0.03 (no internal consistency); reversed, alpha = 0.73.",
    "ID": "Cols 32-34 are the UWES-3 work-engagement items (energy, passion, absorption), not 'personal values'. "
          "Renamed Inner Drive (ID); the notation key's 'PV = Personal Values' should be renamed.",
    "MA": "Col 17 literally asks about personal-values vs organisation-direction mismatch, so it is the best Mission/Value-alignment item. Single item.",
    "PAY": "Single item (col 16, reversed so high = less pay strain). No reliability can be computed.",
    "JR": "Unchanged. Note JR and OS correlate strongly (see construct heatmap) -> watch VIF.",
    "JS": "Cols 51/53/57 are ProQOL compassion-satisfaction items (enjoy helping / work satisfies me / glad I chose this job). "
          "The block was optional, so n drops to ~203.",
    "BO": "Unchanged: 13 CBI items, col 47 reversed (correct).",
}
MISSION_KW = [("兒童與青少年", "mis_child", "Children & youth"), ("身心障礙", "mis_disab", "Disability"),
              ("高齡與長照", "mis_elder", "Elder & long-term care"), ("教育與學習", "mis_edu", "Education"),
              ("經濟弱勢家庭", "mis_lowinc", "Low-income families"), ("心理健康", "mis_mh", "Mental health"),
              ("社會創新", "mis_policy", "Social innovation / advocacy"), ("婦女與性別", "mis_women", "Women & gender")]
MISSION_KEYS = [k for _, k, _ in MISSION_KW]
CONSTRUCTS = ["WL", "OS", "JR", "PAY", "MA", "ID", "BO", "JS", "RET"]
PREDICTORS = ["WL", "OS", "JR", "PAY", "MA", "ID"]
LABELS.update({"WL": "Workload (0-100)", "OS": "Organizational support (0-100)", "JR": "Job resources (0-100)",
               "PAY": "Pay (0-100, high = less strain)", "MA": "Mission alignment (0-100)",
               "ID": "Inner drive / engagement (0-100)", "BO": "Burnout (0-100)",
               "JS": "Job satisfaction (0-100)", "RET": "Retention (0-100)", "SIZE": "Org size (ordinal 0-5)",
               "d_skill": "Job demands exceed training", "hours_actual_ord": "Actual weekly hours (band 1-5)",
               "hours_agreed_ord": "Agreed weekly hours (band 1-3)", "total_bo": "Burnout, all 13 items (0-100)"})
LABELS.update({k: lab for _, k, lab in MISSION_KW})
LABELS.update({"cs1": "Enjoy helping work", "cs2": "Work gives me satisfaction", "cs3": "Glad I chose this career"})


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
        os.makedirs(os.path.dirname(path), exist_ok=True)
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
    d["hours_agreed_ord"] = agreed.map(HOURS_AGREED_ORD).astype(float)
    d["hours_actual_ord"] = actual.map(HOURS_ACTUAL_ORD).astype(float)
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
    add_model_variables(raw, d, meta)
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
    outcomes = ["BO", "JS", "RET", "WL", "OS", "JR", "PAY", "MA", "ID", "work_bo", "personal_bo",
                "proqol_sts", "consider_leaving"]
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


# --------------------------------------------------------------------------- #
# 2b. Model variables, diagnostics and model-based statistics
# --------------------------------------------------------------------------- #
def pomp(s: pd.Series, lo: float, hi: float, reverse: bool = False) -> pd.Series:
    """Percent Of Maximum Possible: rescale to 0-100 (reverse -> 100 - x) so mixed-scale items can be averaged."""
    x = (s - lo) / (hi - lo) * 100
    return 100 - x if reverse else x


def scale_frame(d: pd.DataFrame, items) -> pd.DataFrame:
    """Direction-aligned (higher = more of the construct), 0-100 item frame."""
    return pd.DataFrame({k: pomp(d[k], *ITEM_RANGE[k], reverse=bool(r)) for k, r in items})


def first_pos(raw: pd.DataFrame, frag: str) -> int:
    for i, c in enumerate(raw.columns):
        if frag in c:
            return i
    return -1


def verify_user_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Check that the 0-based column numbers in the brief land on the intended questions."""
    pos = {k: first_pos(raw, f) for k, f in ITEM_FRAG.items()}
    rows, ok = [], True
    for cons, items in SPEC_USER.items():
        found, listed = sorted(pos[k] for k, _ in items), sorted(USER_COLS[cons])
        ok &= found == listed
        rows.append({"construct": cons, "brief_columns": listed, "columns_found_by_header": found, "match": found == listed})
    print("  column map (0-based) %s the brief" % ("MATCHES" if ok else "DOES NOT MATCH"))
    return pd.DataFrame(rows)


def add_model_variables(raw: pd.DataFrame, d: pd.DataFrame, meta: dict) -> None:
    meta["col_check"] = verify_user_columns(raw)
    pos = {k: first_pos(raw, f) for k, f in ITEM_FRAG.items()}
    meta["pos"] = pos
    # ordinal hour bands (needed because 'hours' items are categorical in the questionnaire)
    # (hours_*_ord are created in load_and_clean)
    for cons in CONSTRUCTS:
        d[cons] = scale_frame(d, SPEC[cons]).pipe(row_mean, MIN_FRAC.get(cons, 0.5))
    d["SIZE"] = d["org_size_code"]
    # Mission = multi-select service domains -> one 0/1 dummy per domain (>=10% prevalence); rarer ones are the reference
    dom = coalesce(raw, "你的機構主要服務領域")
    for kw, key, _ in MISSION_KW:
        d[key] = dom.map(lambda v, kw=kw: np.nan if pd.isna(v) else float(kw in str(v)))
    d["mission_n"] = dom.map(lambda v: np.nan if pd.isna(v) else len([x for x in str(v).split(",") if x.strip()]))
    # the brief's own specification, kept ONLY to quantify what the revision changed
    user = pd.DataFrame({c: scale_frame(d, SPEC_USER[c]).pipe(row_mean, MIN_FRAC.get(c, 0.5)) for c in CONSTRUCTS})
    meta["user_constructs"] = user
    # reliability + item diagnostics, user vs revised
    comp, diag = [], []
    for cons in CONSTRUCTS:
        for tag, spec in (("brief", SPEC_USER[cons]), ("revised", SPEC[cons])):
            fr = scale_frame(d, spec)
            a, n = cronbach_alpha(fr) if fr.shape[1] > 1 else (np.nan, int(fr.iloc[:, 0].notna().sum()))
            comp.append({"construct": cons, "version": tag, "n_items": fr.shape[1],
                         "items": ", ".join(f"{k}{'(rev)' if r else ''}" for k, r in spec),
                         "cronbach_alpha": round(a, 3) if pd.notna(a) else np.nan, "n_complete": n})
        fr = scale_frame(d, SPEC[cons])
        for k, r in SPEC[cons]:
            rest = fr.drop(columns=k)
            sub = pd.concat([fr[k], rest.mean(axis=1) if rest.shape[1] else fr[k] * np.nan], axis=1).dropna()
            irc = stats.spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])[0] if len(sub) >= MIN_PAIR_N and sub.iloc[:, 0].nunique() > 1 else np.nan
            ad = cronbach_alpha(rest)[0] if rest.shape[1] > 1 else np.nan
            diag.append({"construct": cons, "item": k, "question": LABELS.get(k, k), "column_0based": pos[k],
                         "reverse_scored": bool(r), "item_rest_rho": round(irc, 3) if pd.notna(irc) else np.nan,
                         "alpha_if_item_deleted": round(ad, 3) if pd.notna(ad) else np.nan})
    meta["spec_compare"] = pd.DataFrame(comp)
    meta["item_diag"] = pd.DataFrame(diag)
    cmp = []
    for k, notes in CONSTRUCT_NOTES.items():
        cmp.append({"construct": k, "brief_items(0-based cols)": ", ".join(f"{pos[i]}{'r' if r else ''}" for i, r in SPEC_USER[k]),
                    "revised_items(0-based cols)": ", ".join(f"{pos[i]}{'r' if r else ''}" for i, r in SPEC[k]),
                    "why": notes})
    meta["changes"] = pd.DataFrame(cmp)


def fdr_sym(pv: pd.DataFrame) -> pd.DataFrame:
    """BH-FDR over the upper triangle of a symmetric p-value matrix."""
    n = pv.shape[0]
    iu = np.triu_indices(n, 1)
    q = np.full((n, n), np.nan)
    q[iu] = bh_fdr(pv.values[iu])
    q = np.where(np.isnan(q), q.T, q)
    np.fill_diagonal(q, 0.0)
    return pd.DataFrame(q, index=pv.index, columns=pv.columns)


def partial_spearman_matrix(df: pd.DataFrame, cols: list[str], controls: list[str]):
    """Spearman partial correlations: rank-transform, residualise on controls, correlate residuals."""
    rho = pd.DataFrame(np.nan, index=cols, columns=cols)
    pv, nn = rho.copy(), rho.copy()
    for i, a in enumerate(cols):
        for b in cols[i:]:
            if a == b:
                rho.loc[a, b], pv.loc[a, b], nn.loc[a, b] = 1.0, 0.0, df[a].notna().sum()
                continue
            sub = df[[a, b] + controls].dropna()
            if len(sub) < MIN_PAIR_N + len(controls) or sub[a].nunique() < 2 or sub[b].nunique() < 2:
                continue
            R = sub.rank()
            C = np.column_stack([np.ones(len(R)), R[controls].values])
            ra = R[a].values - C @ np.linalg.lstsq(C, R[a].values, rcond=None)[0]
            rb = R[b].values - C @ np.linalg.lstsq(C, R[b].values, rcond=None)[0]
            r = np.corrcoef(ra, rb)[0, 1]
            dof = len(sub) - 2 - len(controls)
            t = r * np.sqrt(dof / max(1e-12, 1 - r ** 2))
            rho.loc[a, b] = rho.loc[b, a] = r
            pv.loc[a, b] = pv.loc[b, a] = 2 * stats.t.sf(abs(t), dof)
            nn.loc[a, b] = nn.loc[b, a] = len(sub)
    return rho, pv, fdr_sym(pv), nn


def ols_fit(df: pd.DataFrame, y: str, cont: list[str], dummies: list[str] | None = None):
    """OLS with HC3 heteroskedasticity-robust SEs.  y and `cont` predictors are z-scored (standardised betas);
    0/1 dummies are left as 0/1 (their beta = shift in SD of y).  Also returns VIFs and a joint (Wald) test
    for the dummy block, so a multi-category control such as Mission gets ONE test (the equation's single gamma)."""
    dummies = dummies or []
    xs = list(cont) + list(dummies)
    sub = df[[y] + xs].dropna()
    Z = sub.copy().astype(float)
    for c in [y] + list(cont):
        Z[c] = (sub[c] - sub[c].mean()) / sub[c].std(ddof=0)
    X = np.column_stack([np.ones(len(Z)), Z[xs].values])
    Y = Z[y].values
    n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X)
    beta = XtXi @ X.T @ Y
    res = Y - X @ beta
    dof = n - k
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    meat = (X.T * (res ** 2 / (1 - h) ** 2)) @ X
    cov = XtXi @ meat @ XtXi                                   # HC3
    se = np.sqrt(np.diag(cov))
    p = 2 * stats.t.sf(np.abs(beta / se), dof)
    tcrit = stats.t.ppf(0.975, dof)
    r2 = 1 - (res @ res) / (Y @ Y)
    adj = 1 - (1 - r2) * (n - 1) / dof
    fstat = (r2 / (k - 1)) / ((1 - r2) / dof)
    vif = []
    for j, name in enumerate(xs):
        Xo = np.column_stack([np.ones(n)] + [Z[c].values for c in xs if c != name])
        bj = np.linalg.lstsq(Xo, Z[name].values, rcond=None)[0]
        ss = ((Z[name].values - Z[name].mean()) ** 2).sum()
        rj = 1 - ((Z[name].values - Xo @ bj) ** 2).sum() / ss if ss > 0 else 0
        vif.append(1 / (1 - rj) if rj < 1 else np.inf)
    coef = pd.DataFrame({"predictor": [LABELS.get(c, c) for c in xs], "key": xs, "std_beta": beta[1:], "robust_se": se[1:],
                         "ci_low": beta[1:] - tcrit * se[1:], "ci_high": beta[1:] + tcrit * se[1:],
                         "p_value": p[1:], "VIF": vif})
    coef["q_value_FDR"] = bh_fdr(coef["p_value"].values)
    summ = {"n": n, "r2": r2, "adj_r2": adj, "F": fstat, "F_p": stats.f.sf(fstat, k - 1, dof)}
    if dummies:
        idx = [1 + xs.index(c) for c in dummies]
        b = beta[idx]
        W = b @ np.linalg.pinv(cov[np.ix_(idx, idx)]) @ b
        summ["mission_F"] = W / len(idx)
        summ["mission_p"] = stats.f.sf(W / len(idx), len(idx), dof)
    return coef, summ


def mediation_bootstrap(df: pd.DataFrame, xs: list[str], controls: list[str], B: int = 2000, seed: int = 42):
    """Parallel mediation X -> {BO, JS} -> RET (controls in every equation).  All continuous variables z-scored on the
    complete-case sample; percentile bootstrap CIs for the indirect effects a*b."""
    cols = list(dict.fromkeys(xs + controls + ["BO", "JS", "RET"]))
    sub = df[cols].dropna().astype(float)
    Z = (sub - sub.mean()) / sub.std(ddof=0)
    Z[[c for c in controls if c in MISSION_KEYS]] = sub[[c for c in controls if c in MISSION_KEYS]]   # keep dummies 0/1
    n = len(Z)
    rng = np.random.default_rng(seed)

    def fit(X, Y):
        return np.linalg.lstsq(X, Y, rcond=None)[0]

    def paths(Zb):
        base = np.column_stack([np.ones(len(Zb)), Zb[xs + controls].values])
        a_bo = fit(base, Zb["BO"].values)[1:1 + len(xs)]
        a_js = fit(base, Zb["JS"].values)[1:1 + len(xs)]
        full = np.column_stack([np.ones(len(Zb)), Zb[["BO", "JS"]].values, Zb[xs + controls].values])
        bb = fit(full, Zb["RET"].values)
        b_bo, b_js, direct = bb[1], bb[2], bb[3:3 + len(xs)]
        tot = fit(base, Zb["RET"].values)[1:1 + len(xs)]
        return a_bo * b_bo, a_js * b_js, direct, tot

    ibo, ijs, direct, total = paths(Z)
    draws = []
    for _ in range(B):
        zb = Z.iloc[rng.integers(0, n, n)]
        a, b, _, _ = paths(zb)
        draws.append(np.concatenate([a, b]))
    draws = np.array(draws)
    k = len(xs)
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    tot_ind = draws[:, :k] + draws[:, k:]
    tlo, thi = np.percentile(tot_ind, [2.5, 97.5], axis=0)
    out = pd.DataFrame({"predictor": [LABELS[c] for c in xs], "key": xs,
                        "indirect_via_burnout": ibo, "via_BO_ci_low": lo[:k], "via_BO_ci_high": hi[:k],
                        "indirect_via_job_sat": ijs, "via_JS_ci_low": lo[k:], "via_JS_ci_high": hi[k:],
                        "total_indirect": ibo + ijs, "total_ind_ci_low": tlo, "total_ind_ci_high": thi,
                        "direct_effect": direct, "total_effect": total})
    out["indirect_significant"] = (out["total_ind_ci_low"] > 0) | (out["total_ind_ci_high"] < 0)
    return out, n


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3g}") -> str:
    """Tiny markdown-table writer (avoids the optional `tabulate` dependency)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, (float, np.floating)) and pd.notna(v) else
                                       ("" if pd.isna(v) else str(v)) for v in r.values) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 3. Plots  -- EVERY chart is its own file (no multi-panel figures) so each can be dropped straight into a document
# --------------------------------------------------------------------------- #
SINGLE = (6.8, 4.4)        # default single-chart size (inches)
WIDE = (8.6, 5.2)


def barh_counts(ax, series: pd.Series, title: str, order=None, color=None, titlesize=12, fontsize=8, top: int | None = None):
    s = series.dropna()
    vc = s.value_counts()
    if order is not None:
        vc = vc.reindex([o for o in order if o in vc.index]).dropna()
    elif top:
        vc = vc.head(top)
    vc = vc[::-1]
    ax.barh(vc.index.astype(str), vc.values, color=color or PALETTE[0])
    for i, v in enumerate(vc.values):
        ax.text(v + vc.max() * 0.01, i, f"{int(v)} ({v / len(s) * 100:.0f}%)", va="center", fontsize=fontsize)
    ax.set_xlim(0, vc.max() * 1.28)
    ax.set_title(f"{title} (n={len(s)})", fontsize=titlesize, loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)


def one_bar(d, col, title, fname, out: Out, order=None, color=None, top=None, size=SINGLE):
    fig, ax = plt.subplots(figsize=size)
    barh_counts(ax, d[col].astype(object), title, order=order, color=color, top=top)
    out.save_fig(fig, fname)


def figs_profile(d, out: Out):
    s = "01_profile/"
    one_bar(d, "respondent_type", "Respondent type", s + "respondent_type.png", out, color=PALETTE[0])
    one_bar(d, "org_type", "Organisation type", s + "org_type.png", out, color=PALETTE[1])
    one_bar(d, "org_size_cat", "Organisation size (full-time staff)", s + "org_size.png", out, order=SIZE_LABEL, color=PALETTE[2])
    one_bar(d, "role", "Role in organisation", s + "role.png", out, color=PALETTE[3])
    one_bar(d, "gender", "Gender", s + "gender.png", out, color=PALETTE[4], size=(5.5, 3.6))
    one_bar(d, "age_cat", "Age", s + "age.png", out, order=AGE_LABEL, color=PALETTE[5], size=(5.5, 4))
    one_bar(d, "county", "Main county / city (top 10)", s + "county_top10.png", out, top=10, color=PALETTE[6])
    one_bar(d, "helping_yrs_cat", "Years in helping work", s + "helping_years.png", out, order=TENURE_LABEL, color=PALETTE[7])
    one_bar(d, "hours_actual_cat", "Actual hours worked, past 7 days", s + "hours_actual.png", out,
            order=list(HOURS_ACTUAL_LABEL.values()), color=PALETTE[8])


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
    ax.set_title(title, loc="left", fontweight="bold", fontsize=11)
    ax.legend(ncol=len(levels), loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False, fontsize=8)
    ax.grid(axis="y", visible=False)


def figs_likert(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    likert_stack(ax, org[[k for k, _, _ in D_ITEMS]], [0, 1, 2, 3, 4], ["None", "Mild", "Moderate", "Severe", "Very severe"],
                 "YlOrRd", f"Distress caused by job demands, past 6 months (org respondents, n={len(org.dropna(subset=['d_workload']))})")
    out.save_fig(fig, "02_job_demands_resources/job_demands_distress.png")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    likert_stack(ax, org[[k for k, _, _ in R_ITEMS]], [1, 2, 3, 4, 5],
                 ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"], "RdYlBu",
                 "Agreement with job-resource statements (org respondents)")
    out.save_fig(fig, "02_job_demands_resources/job_resources_agreement.png")


def figs_burnout(d, out: Out):
    s = "03_burnout/"
    fig, ax = plt.subplots(figsize=SINGLE)
    for col, name, c in [("personal_bo", "Personal burnout", PALETTE[0]), ("work_bo", "Work-related burnout", PALETTE[3])]:
        sns.kdeplot(d[col].dropna(), ax=ax, fill=True, alpha=0.35, color=c, label=f"{name} (mean {d[col].mean():.1f})")
    for x in (50, 75):
        ax.axvline(x, ls="--", c="grey", lw=0.8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("C-CBI-style score (0-100)")
    ax.set_title("Burnout score distributions", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    out.save_fig(fig, s + "burnout_distributions.png")

    fig, ax = plt.subplots(figsize=SINGLE)
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
    out.save_fig(fig, s + "burnout_levels.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    melt = d.melt(id_vars="respondent_type", value_vars=["personal_bo", "work_bo"]).dropna()
    melt["variable"] = melt["variable"].map({"personal_bo": "Personal", "work_bo": "Work-related"})
    sns.boxplot(data=melt, x="variable", y="value", hue="respondent_type", ax=ax, palette="Set2", fliersize=2)
    ax.set_xlabel("")
    ax.set_ylabel("Burnout score (0-100)")
    ax.set_title("Burnout by respondent type", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, title="")
    out.save_fig(fig, s + "burnout_by_respondent_type.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    order = [o for o in ["Frontline helper", "Mid-level manager", "Admin / project / finance", "Founder / decision-maker"]
             if o in d["role"].values]
    sns.boxplot(data=d[d["role"].isin(order)], x="work_bo", y="role", order=order, ax=ax, palette="Set3", fliersize=2)
    ax.set_xlabel("Work-related burnout (0-100)")
    ax.set_ylabel("")
    ax.set_title("Work-related burnout by role", loc="left", fontweight="bold")
    out.save_fig(fig, s + "work_burnout_by_role.png")


def figs_wellbeing(d, out: Out):
    s = "04_wellbeing/"
    fig, ax = plt.subplots(figsize=SINGLE)
    long = d.melt(value_vars=["proqol_cs", "proqol_bo", "proqol_sts"]).dropna()
    long["variable"] = long["variable"].map({"proqol_cs": "Compassion\nsatisfaction", "proqol_bo": "Burnout",
                                              "proqol_sts": "Secondary\ntraumatic stress"})
    sns.violinplot(data=long, x="variable", y="value", ax=ax, palette=["#6bbf8a", "#e4572e", "#7a6fb0"], inner="quartile", cut=0)
    ax.set_ylabel("Mean item score (1-5)")
    ax.set_xlabel("")
    ax.set_title("ProQOL-9 subscales", loc="left", fontweight="bold")
    out.save_fig(fig, s + "proqol_subscales.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    sns.histplot(d["engagement"].dropna(), bins=np.arange(0.75, 7.5, 0.5), ax=ax, color=PALETTE[2])
    ax.set_xlabel("UWES-3 engagement (1 = never ... 7 = always)")
    ax.set_title(f"Work engagement / inner drive (mean {d['engagement'].mean():.2f})", loc="left", fontweight="bold")
    out.save_fig(fig, s + "engagement_distribution.png")

    fig, ax = plt.subplots(figsize=(8.4, 5))
    vals = d[[f"b{i}" for i in range(1, 7)] + [f"w{i}" for i in range(1, 8)]].copy()
    vals["w7"] = 6 - vals["w7"]
    m = vals.mean().sort_values()
    ax.barh([LABELS[k] for k in m.index], m.values, color=[PALETTE[0] if k.startswith("b") else PALETTE[3] for k in m.index])
    ax.set_xlim(1, 5)
    ax.set_xlabel("Mean (1-5, higher = more burnout)")
    ax.set_title("Burnout items (blue = personal, red = work-related)", loc="left", fontweight="bold")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, s + "burnout_item_means.png")


def figs_turnover(d, out: Out):
    s = "05_turnover/"
    org = d[d["is_freelancer"] == 0]
    fig, ax = plt.subplots(figsize=SINGLE)
    lab = {0: "Never", 1: "Once/twice", 2: "Monthly", 3: "Weekly", 4: "Daily"}
    vc = org["consider_leaving"].map(lab).value_counts().reindex(list(lab.values()))
    ax.bar(vc.index, vc.values, color=sns.color_palette("YlOrRd", 5))
    ax.set_title("Considered leaving, past 6 months", loc="left", fontweight="bold")
    ax.tick_params(axis="x", rotation=25)
    out.save_fig(fig, s + "considered_leaving.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    lab2 = {1: "Definitely\nnot", 2: "Probably\nnot", 3: "Unsure", 4: "Probably\nyes", 5: "Yes, long-term"}
    vc = org["expect_stay"].map(lab2).value_counts().reindex(list(lab2.values()))
    ax.bar(vc.index, vc.values, color=sns.color_palette("RdYlGn", 5))
    ax.set_title("Expect to be here in 1 year?", loc="left", fontweight="bold")
    ax.tick_params(axis="x", labelsize=8)
    out.save_fig(fig, s + "expect_to_stay.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    pct = org[["job_search", "resume", "applied"]].mean() * 100
    ax.bar(["Searched for\njobs", "Updated\nresume", "Applied\nelsewhere"], pct.values, color=PALETTE[:3])
    for i, v in enumerate(pct.values):
        ax.text(i, v + 1, f"{v:.0f}%", ha="center")
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of org respondents")
    ax.set_title("Job-search behaviour, past 6 months", loc="left", fontweight="bold")
    out.save_fig(fig, s + "job_search_behaviour.png")


def figs_hours(d, out: Out):
    s = "06_working_hours/"
    sub = d.dropna(subset=["hours_agreed", "hours_actual_cat"])
    ct = pd.crosstab(sub["hours_agreed"], sub["hours_actual_cat"]).reindex(
        index=[v for v in ["<=20", "21-40", "41+", "No agreement"] if v in sub["hours_agreed"].values],
        columns=list(HOURS_ACTUAL_LABEL.values()), fill_value=0)
    fig, ax = plt.subplots(figsize=SINGLE)
    sns.heatmap(ct, annot=True, fmt="d", cmap="Blues", ax=ax, cbar_kws={"label": "respondents"})
    ax.set_xlabel("Actual hours worked (past 7 days)")
    ax.set_ylabel("Agreed weekly hours")
    ax.set_title("Agreed vs actual working hours", loc="left", fontweight="bold")
    out.save_fig(fig, s + "agreed_vs_actual_hours.png")

    fig, ax = plt.subplots(figsize=SINGLE)
    sub2 = d.dropna(subset=["hours_actual_cat", "work_bo"])
    sns.boxplot(data=sub2, x="hours_actual_cat", y="work_bo", ax=ax, palette="YlOrRd", fliersize=2)
    ax.set_xlabel("Actual hours worked (past 7 days)")
    ax.set_ylabel("Work-related burnout (0-100)")
    ax.set_title("Burnout by actual hours", loc="left", fontweight="bold")
    out.save_fig(fig, s + "burnout_by_actual_hours.png")


def figs_eap(d, out: Out):
    s = "07_support_programmes/"
    cur, n_cur = multiselect_counts(d["_support_current"], SUPPORT_KW)
    want, n_want = multiselect_counts(d["_support_wanted"], SUPPORT_KW)
    cmp_ = pd.DataFrame({"Currently available": cur, "Most wanted (pick up to 3)": want}).dropna(how="all")
    cmp_ = cmp_.sort_values("Most wanted (pick up to 3)")
    fig, ax = plt.subplots(figsize=(9, 5.8))
    y = np.arange(len(cmp_))
    ax.barh(y + 0.2, cmp_["Currently available"], 0.4, label=f"Currently available (n={n_cur})", color=PALETTE[0])
    ax.barh(y - 0.2, cmp_["Most wanted (pick up to 3)"], 0.4, label=f"Most wanted (n={n_want})", color=PALETTE[3])
    ax.set_yticks(y)
    ax.set_yticklabels(cmp_.index)
    ax.set_xlabel("% of respondents")
    ax.set_title("Employee-support (EAP) measures: availability vs need", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, s + "eap_supply_vs_demand.png")
    out.save_tab(cmp_.round(1), "eap_supply_vs_demand_pct.csv")

    bar, n_b = multiselect_counts(d["_barriers"], BARRIER_KW)
    bar = bar[bar > 0].sort_values()
    fig, ax = plt.subplots(figsize=(8.6, 5))
    ax.barh(bar.index, bar.values, color=PALETTE[4])
    for i, v in enumerate(bar.values):
        ax.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=9)
    ax.set_xlabel("% of respondents")
    ax.set_title(f"Why the organisation has no/limited support systems (n={n_b})", loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, s + "eap_barriers.png")
    out.save_tab(bar.round(1).to_frame("pct"), "eap_barriers_pct.csv")

    prog = d["program_interest"].map(lambda v: np.nan if pd.isna(v) else
        "Very much, we need it" if "非常希望" in v else "Yes, unsure of capacity" if "餘力" in v else
        "Fine / optional" if "可有可無" in v else "Not interested (other priorities)" if "不太希望" in v else "Not sure")
    fig, ax = plt.subplots(figsize=SINGLE)
    barh_counts(ax, prog, "Would your org join a free support programme?", color=PALETTE[2], titlesize=11)
    out.save_fig(fig, s + "programme_interest.png")
    dm = d["decision_maker_attitude"].map(lambda v: np.nan if pd.isna(v) else
        "Interested but cost/workload worry" if "擔心成本" in v else "Might think unnecessary" if "不需要" in v else
        "Not the right time" if "不是時候" in v else "Very enthusiastic" if "很積極" in v else
        "I am the decision-maker" if "決策者" in v and "自己" in v else "Not sure")
    fig, ax = plt.subplots(figsize=SINGLE)
    barh_counts(ax, dm, "Expected attitude of decision-makers", color=PALETTE[5], titlesize=11)
    out.save_fig(fig, s + "decision_maker_attitude.png")


def annotate_corr(rho, qv, keys_r, keys_c, diag_blank=True):
    a = pd.DataFrame("", index=keys_r, columns=keys_c, dtype=object)
    for r in keys_r:
        for c in keys_c:
            v = rho.loc[r, c]
            if pd.isna(v):
                continue
            a.loc[r, c] = f"{v:.2f}" + ("" if (r == c) else stars(qv.loc[r, c]))
    return a


def fig_corr_composite(d, out: Out):
    """Heat-map of every construct in the three equations + the other composite measures."""
    keys = CONSTRUCTS + ["SIZE", "personal_bo", "work_bo", "proqol_bo", "proqol_sts", "consider_leaving", "expect_stay",
                         "job_search_n", "hours_actual", "helping_yrs", "org_tenure", "age_ord"]
    rho, pv, qv, nn = spearman_matrix(d, keys)
    out.save_tab(rho.rename(index=LABELS, columns=LABELS).round(3), "corr_composite_spearman_rho.csv")
    out.save_tab(qv.rename(index=LABELS, columns=LABELS).round(4), "corr_composite_fdr_q.csv")
    annot = annotate_corr(rho, qv, keys, keys)
    mask = np.triu(np.ones_like(rho, dtype=bool), k=1)
    fig, ax = plt.subplots(figsize=(14, 11.5))
    sns.heatmap(rho.astype(float), mask=mask, annot=annot.values, fmt="", cmap="RdBu_r", vmin=-1, vmax=1, center=0,
                linewidths=0.5, square=True, ax=ax, annot_kws={"size": 7.5}, cbar_kws={"label": "Spearman rho", "shrink": 0.7},
                xticklabels=[LABELS[k] for k in keys], yticklabels=[LABELS[k] for k in keys])
    ax.set_title("Correlation heatmap: model constructs and composite measures\n(Spearman; * q<.05, ** q<.01, *** q<.001, BH-FDR)",
                 loc="left", fontweight="bold", fontsize=11)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    out.save_fig(fig, "08_correlations/corr_heatmap_composites.png")
    return rho, pv, qv, nn


def fig_corr_items(d, out: Out):
    keys = ([k for k, _, _ in D_ITEMS] + [k for k, _, _ in R_ITEMS] + [k for k, _, _ in UWES_ITEMS]
            + [k for k, _, _ in CBI_ITEMS] + [k for k, _, _ in PQ_ITEMS] + ["consider_leaving", "expect_stay"])
    rho, pv, qv, nn = spearman_matrix(d, keys)
    labels = [LABELS[k] for k in keys]
    g = sns.clustermap(rho.fillna(0).astype(float).set_axis(labels, axis=0).set_axis(labels, axis=1), cmap="RdBu_r", vmin=-1,
                       vmax=1, center=0, figsize=(17, 16), linewidths=0.2, cbar_kws={"label": "Spearman rho"},
                       dendrogram_ratio=0.08, method="average")
    g.fig.suptitle("Item-level correlation clustermap (hierarchically clustered)", y=1.0, fontweight="bold", fontsize=14)
    plt.setp(g.ax_heatmap.get_xticklabels(), rotation=90, fontsize=7.5)
    plt.setp(g.ax_heatmap.get_yticklabels(), fontsize=7.5)
    out.save_fig(g.fig, "08_correlations/corr_clustermap_items.png")
    out.save_tab(long_corr(rho, pv, qv, nn).round(4), "corr_item_level_all_pairs.csv", index=False)
    return rho, pv, qv, nn


def heat_block(rho, qv, rows, cols, fname, out: Out, title, figsize, vmax=0.7, mask_self=False):
    block = rho.loc[rows, cols].astype(float)
    annot = annotate_corr(rho, qv, rows, cols)
    mask = pd.DataFrame(False, index=rows, columns=cols)
    for r in rows:
        for c in cols:
            if r == c:
                mask.loc[r, c] = True
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(block, annot=annot.values, fmt="", cmap="RdBu_r", vmin=-vmax, vmax=vmax, center=0, linewidths=0.5, ax=ax,
                mask=mask.values, cbar_kws={"label": "Spearman rho"},
                xticklabels=[LABELS[c] for c in cols], yticklabels=[LABELS[r] for r in rows])
    ax.set_title(title, loc="left", fontweight="bold", fontsize=11)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    out.save_fig(fig, fname)
    return block


def fig_demand_vs_resource(d, out: Out):
    """Item-level demands (top) and resources (bottom) against the outcomes."""
    dk = [k for k, _, _ in D_ITEMS]
    rk = [k for k, _, _ in R_ITEMS]
    outcomes = ["BO", "personal_bo", "work_bo", "JS", "ID", "consider_leaving", "expect_stay", "RET"]
    rho, pv, qv, nn = spearman_matrix(d, dk + rk + outcomes)
    block = heat_block(rho, qv, dk + rk, outcomes, "08_correlations/items_vs_outcomes_heatmap.png", out,
                       "Which job demands / resources relate to well-being & retention?\n(top block: demands, bottom: resources; * q<.05 FDR)",
                       (11, 9))
    out.save_tab(block.rename(index=LABELS, columns=LABELS).round(3), "corr_items_vs_outcomes_rho.csv")


def fig_segment_heatmap(d, out: Out):
    metrics = {"Burnout": ("BO", 0, 100), "Job satisfaction": ("JS", 0, 100), "Retention": ("RET", 0, 100),
               "Workload": ("WL", 0, 100), "Org support": ("OS", 0, 100), "Job resources": ("JR", 0, 100),
               "Pay (high=less strain)": ("PAY", 0, 100), "Mission alignment": ("MA", 0, 100),
               "Inner drive": ("ID", 0, 100), "Work burnout": ("work_bo", 0, 100), "Sec. traumatic stress": ("proqol_sts", 1, 5)}
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
    z = (seg - seg.mean()) / seg.std(ddof=0)
    fig, ax = plt.subplots(figsize=(13, max(8, 0.3 * len(seg))))
    sns.heatmap(z, annot=seg.round(0), fmt=".0f", cmap="RdYlBu_r", center=0, linewidths=0.4, ax=ax,
                cbar_kws={"label": "column z-score (colour)  |  numbers = mean rescaled 0-100"}, annot_kws={"size": 8})
    ax.set_title("Segment heatmap: mean indicators by subgroup (groups with n>=%d)" % MIN_GROUP_N, loc="left", fontweight="bold")
    ax.xaxis.tick_top()
    plt.setp(ax.get_xticklabels(), rotation=35, ha="left")
    out.save_fig(fig, "08_correlations/segment_heatmap.png")


def fig_correlates(d, target: str, fname: str, out: Out, title: str, exclude: list[str]):
    cands = ([k for k, _, _ in D_ITEMS] + [k for k, _, _ in R_ITEMS] + CONSTRUCTS +
             ["hours_actual", "helping_yrs", "org_tenure", "SIZE", "age_ord", "proqol_cs"])
    cands = [c for c in cands if c not in exclude and c != target]
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


def scatter_pair(d, x, y, fname, out: Out, color):
    sub = d[[x, y]].dropna()
    fig, ax = plt.subplots(figsize=(6, 4.8))
    rng = np.random.default_rng(1)
    ax.scatter(sub[x] + rng.normal(0, 0.8, len(sub)), sub[y] + rng.normal(0, 0.8, len(sub)), s=22, alpha=0.45, color=color)
    m, b = np.polyfit(sub[x], sub[y], 1)
    xs = np.linspace(sub[x].min(), sub[x].max(), 50)
    ax.plot(xs, m * xs + b, color="black", lw=1.8)
    r, p = stats.spearmanr(sub[x], sub[y])
    ax.set_xlabel(LABELS[x])
    ax.set_ylabel(LABELS[y])
    ax.set_title(f"rho = {r:.2f}, p = {p:.1g}, n = {len(sub)}", loc="left", fontsize=10, fontweight="bold")
    out.save_fig(fig, fname)


def figs_scatter(d, out: Out):
    s = "08_correlations/scatter_"
    for x, y, c in [("WL", "BO", PALETTE[3]), ("OS", "BO", PALETTE[0]), ("JR", "BO", PALETTE[9]), ("ID", "BO", PALETTE[2]),
                    ("BO", "JS", PALETTE[4]), ("BO", "RET", PALETTE[1]), ("JS", "RET", PALETTE[2]), ("OS", "RET", PALETTE[5])]:
        scatter_pair(d, x, y, f"{s}{x}_vs_{y}.png", out, c)
    fig, ax = plt.subplots(figsize=SINGLE)
    lab = {0: "Never", 1: "1-2x", 2: "Monthly", 3: "Weekly", 4: "Daily"}
    sub = d.dropna(subset=["consider_leaving", "BO"]).copy()
    sub["lv"] = pd.Categorical(sub["consider_leaving"].map(lab), categories=list(lab.values()), ordered=True)
    sns.boxplot(data=sub, x="lv", y="BO", ax=ax, palette="YlOrRd", fliersize=2)
    ax.set_xlabel("Frequency of considering leaving (past 6 months)")
    ax.set_ylabel(LABELS["BO"])
    r, p = stats.spearmanr(sub["consider_leaving"], sub["BO"])
    ax.set_title(f"rho = {r:.2f}, p = {p:.1g}, n = {len(sub)}", loc="left", fontsize=10, fontweight="bold")
    out.save_fig(fig, s + "BO_by_consider_leaving.png")


# ---- model-specific charts -------------------------------------------------
def fig_construct_means(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    m = org[CONSTRUCTS].agg(["mean", "std", "count"]).T.sort_values("mean")
    fig, ax = plt.subplots(figsize=WIDE)
    ax.barh([LABELS[k] for k in m.index], m["mean"], xerr=m["std"], color=PALETTE[0], alpha=0.85, capsize=3)
    for i, (mu, n) in enumerate(zip(m["mean"], m["count"])):
        ax.text(2, i, f"{mu:.0f}  (n={int(n)})", va="center", color="white", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 105)
    ax.set_xlabel("Mean score, 0-100 (error bar = SD)")
    ax.set_title("Model constructs: mean level among organisation respondents", loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "09_model/construct_means.png")


def fig_alpha_compare(meta, out: Out):
    t = meta["spec_compare"]
    t = t[t["n_items"] > 1]
    piv = t.pivot(index="construct", columns="version", values="cronbach_alpha").reindex(
        [c for c in CONSTRUCTS if c in t["construct"].values])
    fig, ax = plt.subplots(figsize=SINGLE)
    y = np.arange(len(piv))
    ax.barh(y + 0.2, piv["brief"], 0.4, label="As briefed", color="#b0b0b0")
    ax.barh(y - 0.2, piv["revised"], 0.4, label="Revised", color=PALETTE[2])
    for i, (a, b) in enumerate(zip(piv["brief"], piv["revised"])):
        ax.text(max(a, 0) + 0.01, i + 0.2, f"{a:.2f}", va="center", fontsize=8)
        ax.text(max(b, 0) + 0.01, i - 0.2, f"{b:.2f}", va="center", fontsize=8)
    ax.axvline(0.7, ls="--", c="grey", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(piv.index)
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("Cronbach's alpha (dashed line = .70)")
    ax.set_title("Scale reliability: briefed vs revised item groupings", loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower right")
    out.save_fig(fig, "09_model/reliability_brief_vs_revised.png")


def fig_model_correlations(d, out: Out):
    org = d[d["is_freelancer"] == 0]
    cons = CONSTRUCTS + ["SIZE"]
    # 1) all construct pairs
    rho, pv, qv, nn = spearman_matrix(org, cons)
    annot = annotate_corr(rho, qv, cons, cons)
    fig, ax = plt.subplots(figsize=(9.5, 8))
    sns.heatmap(rho.astype(float), mask=np.triu(np.ones_like(rho, dtype=bool), k=1), annot=annot.values, fmt="", cmap="RdBu_r",
                vmin=-1, vmax=1, center=0, linewidths=0.5, square=True, ax=ax, annot_kws={"size": 8},
                cbar_kws={"label": "Spearman rho", "shrink": 0.75},
                xticklabels=[LABELS[k] for k in cons], yticklabels=[LABELS[k] for k in cons])
    ax.set_title("Equation constructs: Spearman correlations (org respondents)\n* q<.05, ** q<.01, *** q<.001 (BH-FDR)",
                 loc="left", fontweight="bold", fontsize=11)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    out.save_fig(fig, "09_model/construct_correlations.png")
    out.save_tab(long_corr(rho, pv, qv, nn).round(4), "model_construct_correlations.csv", index=False)

    # 2) partial correlations controlling Size + Mission (the equations' control set)
    ctrl = ["SIZE"] + MISSION_KEYS
    prho, ppv, pqv, pnn = partial_spearman_matrix(org, CONSTRUCTS, ctrl)
    annot = annotate_corr(prho, pqv, CONSTRUCTS, CONSTRUCTS)
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sns.heatmap(prho.astype(float), mask=np.triu(np.ones_like(prho, dtype=bool), k=1), annot=annot.values, fmt="", cmap="RdBu_r",
                vmin=-1, vmax=1, center=0, linewidths=0.5, square=True, ax=ax, annot_kws={"size": 8},
                cbar_kws={"label": "partial Spearman rho", "shrink": 0.75},
                xticklabels=[LABELS[k] for k in CONSTRUCTS], yticklabels=[LABELS[k] for k in CONSTRUCTS])
    ax.set_title("Partial correlations controlling for org size + mission area\n* q<.05, ** q<.01, *** q<.001 (BH-FDR)",
                 loc="left", fontweight="bold", fontsize=11)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    out.save_fig(fig, "09_model/construct_partial_correlations.png")
    out.save_tab(long_corr(prho, ppv, pqv, pnn).round(4), "model_construct_partial_correlations.csv", index=False)

    # 3) the equation paths: each predictor (+ mediators) vs each dependent variable
    rows = PREDICTORS + ["SIZE", "BO", "JS"]
    heat_block(rho, qv, rows, ["BO", "JS", "RET"], "09_model/equation_paths_correlations.png", out,
               "Equation paths: predictors vs Burnout / Job satisfaction / Retention\n(Spearman; * q<.05 BH-FDR over all construct pairs)",
               (6.8, 6.2), vmax=0.8)

    # 4) facet level: predictors vs burnout sub-types, satisfaction items and retention behaviours
    facets = ["personal_bo", "work_bo", "cs1", "cs2", "cs3", "consider_leaving", "expect_stay", "job_search_n", "hours_actual"]
    keys = PREDICTORS + ["SIZE"] + facets
    r2, p2, q2, n2 = spearman_matrix(org, keys)
    heat_block(r2, q2, PREDICTORS + ["SIZE"], facets, "09_model/predictors_vs_facets_correlations.png", out,
               "Predictors vs facets of the outcomes\n(Spearman; * q<.05 BH-FDR)", (10.5, 6.4), vmax=0.7)
    out.save_tab(r2.loc[PREDICTORS + ["SIZE"], facets].rename(index=LABELS, columns=LABELS).round(3),
                 "model_predictors_vs_facets_rho.csv")
    return rho, pv, qv, nn, prho, ppv, pqv, pnn


def fig_regression(coef: pd.DataFrame, summ: dict, out: Out, name: str, title: str):
    c = coef.sort_values("std_beta")
    fig, ax = plt.subplots(figsize=(9, 0.3 * len(c) + 2))
    colors = np.where(c["p_value"] < ALPHA, np.where(c["std_beta"] > 0, "#e4572e", "#2e86ab"), "#b0b0b0")
    ax.barh(c["predictor"], c["std_beta"], color=colors)
    ax.errorbar(c["std_beta"], np.arange(len(c)), xerr=[c["std_beta"] - c["ci_low"], c["ci_high"] - c["std_beta"]],
                fmt="none", ecolor="black", lw=0.8, capsize=2)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Standardised beta, 95% CI (HC3-robust) -- coloured = p<.05, grey = n.s.")
    extra = f", Mission block p={summ['mission_p']:.2g}" if "mission_p" in summ else ""
    ax.set_title(f"{title}\nn={summ['n']}, R²={summ['r2']:.2f}, adj. R²={summ['adj_r2']:.2f}{extra}",
                 loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, name)


def fig_mediation(med: pd.DataFrame, n: int, out: Out):
    t = med.sort_values("total_indirect")
    fig, ax = plt.subplots(figsize=(8.8, 5))
    y = np.arange(len(t))
    cols = np.where(t["indirect_significant"], "#e4572e", "#b0b0b0")
    ax.scatter(t["total_indirect"], y, color=cols, zorder=3, s=45)
    ax.hlines(y, t["total_ind_ci_low"], t["total_ind_ci_high"], color=cols, lw=2)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(t["predictor"])
    ax.set_xlabel("Standardised indirect effect on Retention via Burnout + Job satisfaction (95% bootstrap CI)")
    ax.set_title(f"Mediation: do Burnout and Job satisfaction carry each predictor's effect on Retention? (n={n})\n"
                 "red = CI excludes 0", loc="left", fontweight="bold", fontsize=10.5)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "09_model/mediation_indirect_effects.png")


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
                             RandomForestClassifier(n_estimators=400, min_samples_leaf=3, class_weight="balanced",
                                                    random_state=42, n_jobs=-1))
        pipe.fit(X.iloc[tr], y.iloc[tr])
        aucs.append(roc_auc_score(y.iloc[te], pipe.predict_proba(X.iloc[te])[:, 1]))
        pi = permutation_importance(pipe, X.iloc[te], y.iloc[te], n_repeats=20, scoring="roc_auc", random_state=42)
        imps.append(pi.importances_mean)
    imp = pd.DataFrame({"feature": [LABELS.get(f, f) for f in features], "key": features,
                        "perm_importance_auc_drop": np.mean(imps, axis=0)}).sort_values("perm_importance_auc_drop", ascending=False)
    return imp, {"n": len(sub), "positive_rate": float(y.mean()), "auc_mean": float(np.mean(aucs)), "auc_sd": float(np.std(aucs))}


def fig_rf(imp: pd.DataFrame, info: dict, out: Out):
    t = imp.head(15).sort_values("perm_importance_auc_drop")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(t["feature"], t["perm_importance_auc_drop"], color=PALETTE[4])
    ax.set_xlabel("Permutation importance (drop in held-out AUC)")
    ax.set_title(f"Random forest: considers leaving at least monthly\n5-fold CV AUC = {info['auc_mean']:.2f} ± {info['auc_sd']:.2f}"
                 f"  (n={info['n']}, {info['positive_rate'] * 100:.0f}% positive)", loc="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    out.save_fig(fig, "10_random_forest/random_forest_intent_to_leave.png")


# --------------------------------------------------------------------------- #
# 4. Report
# --------------------------------------------------------------------------- #
def sig_pairs(rho, qv, nn, keys):
    rows = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if pd.notna(qv.loc[a, b]) and qv.loc[a, b] < ALPHA:
                rows.append((LABELS[a], LABELS[b], rho.loc[a, b], qv.loc[a, b], int(nn.loc[a, b])))
    return sorted(rows, key=lambda r: -abs(r[2]))


def write_report(d, meta, out: Out, corr, burn_tab, gt, eqs, med, rf_imp, rf_info):
    comp, partial = corr["composite"], corr["partial"]
    L: list[str] = []
    org = d[d["is_freelancer"] == 0]
    L.append("# 2026 Taiwan Helpers' Needs Survey -- automated analysis summary\n")
    L.append(f"- Responses analysed: **{meta['raw_n']}** ({len(org)} organisation-affiliated incl. hybrid, "
             f"{int(d['is_freelancer'].sum())} freelancers/independents). **Equations 1-3 use organisation respondents only** "
             "(freelancers were not asked the workload / support / resource / retention items).")
    L.append("- Sample is self-selected (not probability-based): percentages describe respondents, not all Taiwanese helpers.\n")

    L.append("## Column map and what the revision changed\n")
    L.append("Column numbers are **0-based** (pandas `iloc`). The script verified every number in the brief against the question text "
             f"(all match: {bool(meta['col_check']['match'].all())}).\n")
    L.append(md_table(meta["changes"]) + "\n")
    L.append("### Reliability (Cronbach's alpha): as briefed vs revised\n")
    L.append(md_table(meta["spec_compare"].drop(columns="items")) + "\n")

    L.append("## Correlations among the equation constructs (org respondents; Spearman, BH-FDR)\n")
    rho, pv, qv, nn = corr["model"]
    keys = CONSTRUCTS + ["SIZE"]
    sp = sig_pairs(rho, qv, nn, keys)
    L.append(f"{len(sp)} of {len(keys) * (len(keys) - 1) // 2} construct pairs are significant at q<.05.\n")
    L.append("| Variable 1 | Variable 2 | rho | q | n |\n|---|---|---|---|---|")
    for a, b, r, q, n in sp:
        L.append(f"| {a} | {b} | {r:.2f} | {'<0.001' if q < 0.001 else format(q, '.3f')} | {n} |")
    prho, ppv, pqv, pnn = partial
    spp = sig_pairs(prho, pqv, pnn, CONSTRUCTS)
    L.append(f"\n**Partial correlations** (controlling org size + mission area): {len(spp)} of "
             f"{len(CONSTRUCTS) * (len(CONSTRUCTS) - 1) // 2} construct pairs remain significant at q<.05.\n")

    rho_c, pv_c, qv_c, nn_c = comp
    spc = sig_pairs(rho_c, qv_c, nn_c, list(rho_c.columns))
    L.append(f"All composite measures together: {len(spc)} of {len(rho_c) * (len(rho_c) - 1) // 2} pairs significant (q<.05). "
             "Full tables are in `tables/`.\n")

    for name, (coef, s) in eqs.items():
        L.append(f"## {name}\n")
        extra = f"; Mission block Wald F p={s['mission_p']:.3g}" if "mission_p" in s else ""
        L.append(f"Standardised OLS with HC3-robust SEs, n={s['n']}, R²={s['r2']:.3f}, adj. R²={s['adj_r2']:.3f}, "
                 f"F p={s['F_p']:.2g}{extra}. All coefficients:\n")
        t = coef[["predictor", "std_beta", "ci_low", "ci_high", "p_value", "q_value_FDR", "VIF"]].copy()
        for c in ("p_value", "q_value_FDR"):
            t[c] = t[c].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
        L.append(md_table(t.round(3)) + "\n")
    L.append("## Mediation: predictor -> {Burnout, Job satisfaction} -> Retention\n")
    L.append(f"Parallel mediation, n={med[1]} complete cases, 2,000 bootstrap resamples (percentile 95% CI). "
             "Uses Eq.3 **plus the predictors as direct paths** (a mediation model needs them; Eq.3 as written omits them).\n")
    L.append(md_table(med[0][["predictor", "indirect_via_burnout", "indirect_via_job_sat", "total_indirect",
                              "total_ind_ci_low", "total_ind_ci_high", "direct_effect", "total_effect",
                              "indirect_significant"]].round(3)) + "\n")

    L.append("## Burnout headline numbers\n")
    for col, nm in [("personal_bo", "Personal burnout"), ("work_bo", "Work-related burnout")]:
        s = d[col].dropna()
        L.append(f"- {nm}: mean {s.mean():.1f} (SD {s.std():.1f}, n={len(s)}); "
                 f"{((s >= 50) & (s < 75)).mean() * 100:.0f}% moderate (50-74), {(s >= 75).mean() * 100:.0f}% high (>=75)")
    L.append(f"- >= monthly thoughts of leaving (org respondents): {org['high_leave'].mean() * 100:.0f}%; "
             f"actively searched for jobs: {org['job_search'].mean() * 100:.0f}%.\n")
    L.append("## Items most associated with Burnout (Spearman)\n")
    L.append("| Variable | rho | q | n |\n|---|---|---|---|")
    for _, r in burn_tab.head(10).iterrows():
        L.append(f"| {r['variable']} | {r['rho']:.2f} | {r['q']:.3g} | {int(r['n'])} |")
    L.append("\n## Significant group differences (FDR q<.05)\n")
    sig = gt[gt["q_value_FDR"] < ALPHA]
    if sig.empty:
        L.append("No subgroup difference survived FDR correction.\n")
    else:
        L.append("| Segment | Outcome | Test | p | q | effect | n | Group means |\n|---|---|---|---|---|---|---|---|")
        for _, r in sig.head(15).iterrows():
            L.append(f"| {r['segment']} | {r['outcome']} | {r['test']} | {r['p_value']:.3g} | {r['q_value_FDR']:.3g} | "
                     f"{r['effect_size']} | {r['n']} | {r['group_means']} |")
        L.append("")
    if rf_info:
        L.append("## Random forest: considers leaving at least monthly\n")
        L.append(f"5-fold CV AUC {rf_info['auc_mean']:.2f} ± {rf_info['auc_sd']:.2f} (n={rf_info['n']}). Top drivers:\n")
        for _, r in rf_imp.head(6).iterrows():
            L.append(f"- {r['feature']} (importance {r['perm_importance_auc_drop']:.3f})")
        L.append("")
    L.append("## Method notes\n")
    L.append("- Every construct is the mean of its items after rescaling each item to 0-100 (percent of maximum possible) and aligning direction "
             "(reverse-scored items flipped), so a higher score always means MORE of the named construct (Pay: less pay strain; "
             "Retention: more likely to stay).\n"
             "- Correlations are Spearman (rank-based, suitable for ordinal items); p-values are corrected with Benjamini-Hochberg FDR. "
             "Thresholds were NOT loosened to produce more significant results.\n"
             "- Regressions: z-scored outcome and continuous predictors (standardised betas), 0/1 mission dummies, HC3 robust standard errors. "
             "Mission = 8 service-area dummies (areas with >=10% prevalence; rarer areas are the reference) tested jointly as one block.\n"
             "- Job satisfaction (ProQOL block) was optional, so Eq.2 / Eq.3 / mediation have smaller n than Eq.1.\n"
             "- Cross-sectional, self-selected data: all results are associations, not causal effects.\n")
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
    ap.add_argument("--boot", type=int, default=2000, help="bootstrap resamples for the mediation CIs")
    args = ap.parse_args()

    path = args.input
    if not path:
        found = sorted(glob.glob("*.csv"))
        if not found:
            sys.exit("No CSV found: pass --input path/to/survey.csv")
        path = found[0]
    out = Out(args.out)

    print("\n[1/7] Cleaning & coding data")
    d, meta = load_and_clean(path)
    public = d[[c for c in d.columns if not c.startswith("_")]].copy()
    for c in public.select_dtypes("category").columns:
        public[c] = public[c].astype(object)
    out.save_tab(public, "cleaned_coded_data_anonymised.csv")
    out.save_tab(meta["reliability"], "scale_reliability_legacy_scales.csv", index=False)
    out.save_tab(meta["spec_compare"], "construct_reliability_brief_vs_revised.csv", index=False)
    out.save_tab(meta["item_diag"], "construct_item_diagnostics.csv", index=False)
    out.save_tab(meta["changes"], "construct_changes_and_reasons.csv", index=False)
    out.save_tab(meta["col_check"], "column_map_check.csv", index=False)

    print("\n[2/7] Descriptive statistics")
    num = [k for k in LABELS if k in d.columns]
    desc = d[num].describe().T.rename(index=LABELS)
    desc["missing"] = d[num].isna().sum().values
    out.save_tab(desc.round(3), "descriptive_statistics.csv")

    print("\n[3/7] Descriptive charts (one file per chart)")
    figs_profile(d, out)
    figs_likert(d, out)
    figs_burnout(d, out)
    figs_wellbeing(d, out)
    figs_turnover(d, out)
    figs_hours(d, out)
    figs_eap(d, out)

    print("\n[4/7] Correlations & heatmaps")
    comp = fig_corr_composite(d, out)
    out.save_tab(long_corr(*comp).round(4), "corr_composite_all_pairs.csv", index=False)
    fig_corr_items(d, out)
    fig_demand_vs_resource(d, out)
    fig_segment_heatmap(d, out)
    burn_excl = ["BO", "personal_bo", "work_bo", "total_bo", "RET"]
    burn_tab = fig_correlates(d, "BO", "08_correlations/correlates_of_burnout.png", out,
                              "Correlates of burnout (Spearman rho)", burn_excl)
    out.save_tab(burn_tab.round(4), "correlates_of_burnout.csv", index=False)
    fig_correlates(d, "consider_leaving", "08_correlations/correlates_of_intent_to_leave.png", out,
                   "Correlates of considering leaving (Spearman rho)", ["RET"])
    figs_scatter(d, out)

    print("\n[5/7] Model equations 1-3")
    model_corr = fig_model_correlations(d, out)
    fig_construct_means(d, out)
    fig_alpha_compare(meta, out)
    org = d[d["is_freelancer"] == 0]
    ctrl = ["SIZE"]
    specs = {
        "Equation 1: Burnout": ("BO", PREDICTORS + ["SIZE"], "eq1_burnout"),
        "Equation 2: Job satisfaction": ("JS", PREDICTORS + ["SIZE"], "eq2_job_satisfaction"),
        "Equation 3: Retention": ("RET", ["JS", "BO", "SIZE"], "eq3_retention"),
        "Equation 3b (sensitivity): Retention with all predictors as direct paths": ("RET", ["JS", "BO"] + PREDICTORS + ["SIZE"], "eq3b_retention_full"),
    }
    eqs = {}
    for name, (y, cont, tag) in specs.items():
        coef, summ = ols_fit(org, y, cont, MISSION_KEYS)
        eqs[name] = (coef, summ)
        out.save_tab(coef.round(4), f"model_{tag}.csv", index=False)
        fig_regression(coef, summ, out, f"09_model/{tag}.png", name)
    # Eq.1 on the same cases as Eq.2/3 -> is the smaller job-satisfaction sample driving differences?
    sub_js = org.dropna(subset=["JS"])
    c1b, s1b = ols_fit(sub_js, "BO", PREDICTORS + ["SIZE"], MISSION_KEYS)
    out.save_tab(c1b.round(4), "model_eq1_burnout_on_job_satisfaction_sample.csv", index=False)
    med = mediation_bootstrap(org, PREDICTORS, ["SIZE"] + MISSION_KEYS, B=args.boot)
    out.save_tab(med[0].round(4), "model_mediation_indirect_effects.csv", index=False)
    fig_mediation(med[0], med[1], out)
    rf_imp = rf_info = None
    if not args.no_ml:
        feats = CONSTRUCTS[:-1] + ["hours_actual", "org_tenure", "helping_yrs", "SIZE", "age_ord"] + MISSION_KEYS
        rf_imp, rf_info = random_forest_leave(org, feats)
        if rf_imp is not None:
            out.save_tab(rf_imp.round(4), "random_forest_importance.csv", index=False)
            fig_rf(rf_imp, rf_info, out)

    print("\n[6/7] Group comparisons")
    gt = group_tests(d)
    out.save_tab(gt.round(5), "group_comparison_tests.csv", index=False)

    print("\n[7/7] Writing summary report")
    corr = {"composite": comp, "model": model_corr[:4], "partial": model_corr[4:]}
    write_report(d, meta, out, corr, burn_tab, gt, eqs, med, rf_imp, rf_info)
    print(f"\nDone. Everything is in: {os.path.abspath(out.root)}")


if __name__ == "__main__":
    main()