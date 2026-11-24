#!/usr/bin/env python3
"""
2026 Taiwan Helpers' Needs Survey (Well Planet / WPI IQP) -- analysis pipeline, v3.0
====================================================================================

PURPOSE
-------
Reproducible analysis of the Google-Forms export of the 2026 survey.  It

  1. loads and cleans the data **by 0-based column position, with a header-text check** on every
     column so that a re-ordered export fails loudly instead of silently mis-scoring;
  2. builds the nine constructs of a *simplified Job Demands-Resources (JD-R) model*
     (WL, OS, JR, PAY, MA, ID, BO, JS, RET) under three explicitly named specifications;
  3. reports psychometrics (alpha, omega, item-rest r) and an automatic coding audit;
  4. estimates the three structural equations of the brief, **separately for organisation-based and
     self-employed respondents**, with heteroskedasticity-robust (HC3) inference;
  5. treats the non-ignorable-looking missingness in the optional job-satisfaction block with a
     missingness model, multiple imputation (Rubin's rules) and a delta-adjusted tipping-point analysis;
  6. fits parallel mediation (BCa bootstrap, unstandardised indirect effects) as an *associational* path model;
  7. quantifies the **support gap**: what is provided (staff view vs decision-maker view), what is wanted,
     and what is unmet;
  8. validates the numbers against those printed in the IQP project report (Section 4.1.4);
  9. writes tables (CSV), figures (PNG), a run manifest (JSON) and a Markdown report.

THE SIMPLIFIED JD-R MODEL (equations from the brief; all columns are 0-based)
-----------------------------------------------------------------------------
  Eq.1  BO  = b0 + b1 WL + b2 OS + b3 JR + b4 PAY + b5 MA + b6 ID + g1 SIZE + g2 MISSION + e1
  Eq.2  JS  = a0 + a1 WL + a2 OS + a3 JR + a4 PAY + a5 MA + a6 ID + g3 SIZE + g4 MISSION + e2
  Eq.3  RET = d0 + d1 JS + d2 BO + g5 SIZE + g6 MISSION + e3
  (Eq.3b = Eq.3 plus all six predictors; a sensitivity check on direct effects, never a causal decomposition.)

  The brief's notation "PV (Personal Values)" is the UWES-3 work-engagement block (cols 32-34); it is called
  ID ("inner drive") here.  "Job satisfaction" (cols 51, 53, 57) is the ProQOL *compassion satisfaction*
  block; the name JS is kept for continuity with the brief, but it is not a general job-satisfaction scale.

SPECIFICATIONS (see SPECS below)
--------------------------------
  brief_literal : item membership AND reverse-coding exactly as supplied.
  primary       : the brief's membership; ONLY direction errors repaired (cols 12, 29, 30, 31 reversed).
                  Every headline result uses this one.  Rationale: "minimal intervention" -- a sign error is
                  a coding defect, whereas dropping/adding items is an analyst judgement.
  extended      : primary + col 11 added to WL, col 7 dropped from WL (the v2 script's revisions); sensitivity.

PRE-SPECIFIED INFERENTIAL FAMILIES (multiplicity control)
---------------------------------------------------------
  Primary family   : the 14 structural slopes of Eq.1-3 (6 + 6 + 2), per respondent group and per estimation
                     method; Benjamini-Hochberg FDR is applied inside that family only.
  Exploratory      : everything else (correlations, group contrasts, gap tests, subgroup tables).  Each table
                     has its own FDR family and is labelled exploratory; none is confirmatory.

USAGE
-----
    python helper_survey_analysis.py --input survey.csv --out results
    python helper_survey_analysis.py --input survey.csv --out results --boot 5000 --m 50
    python helper_survey_analysis.py --selftest            # numerical unit checks, no data needed

REQUIREMENTS: Python >= 3.10, numpy, pandas, scipy, matplotlib, scikit-learn (for the imputation engine).
statsmodels is NOT required; if it is installed the self-test cross-validates the internal OLS/HC3 against it.

PRIVACY: e-mail, free text, timestamps and county names are never written.  The analysis dataset keeps coarse
demographics (role, age band, gender, region, org size); share it only inside the research team.

CITING / REPRODUCIBILITY: the run manifest records the SHA-256 of the input file, package versions, the random
seed and the command line.  Same input + same seed + same versions => identical tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

try:  # imputation engine is optional at import time so --selftest works everywhere
    from sklearn.experimental import enable_iterative_imputer  # noqa: F401
    from sklearn.impute import IterativeImputer
    from sklearn.linear_model import BayesianRidge
except ImportError:  # pragma: no cover
    IterativeImputer = None

__version__ = "3.0"
LOG = logging.getLogger("helper_survey")

# =============================================================================================== #
# 1. CONFIGURATION
# =============================================================================================== #
SEED = 20260101            # master seed; every random operation derives from it
MIN_PAIR_N = 20            # minimum pairwise-complete N for a correlation
MIN_GROUP_N = 10           # minimum group size for any group statistic
N_IMPUTATIONS = 20         # default number of multiple imputations (>= 20 recommended for FMI up to ~0.3)
N_BOOT = 2000              # default bootstrap resamples
ALPHA_LEVEL = 0.05
DELTA_GRID = (-15, -10, -5, 0, 5, 10, 15)   # tipping-point shifts of imputed JS (0-100 points)
BURNOUT_BINS = [-0.1, 49.99, 74.99, 100.0]  # DESCRIPTIVE bands only (source of the 50/75 cut-offs not verified here; no inference uses them)
BURNOUT_LABELS = ["Low (<50)", "Moderate (50-74)", "High (75+)"]

GROUP_ORG, GROUP_SELF = "Organisation", "Self-employed"

CONSTRUCTS = ["WL", "OS", "JR", "PAY", "MA", "ID", "BO", "JS", "RET"]
PREDICTORS = ["WL", "OS", "JR", "PAY", "MA", "ID"]
MISSION_KW = [("兒童與青少年", "mis_child", "Children & youth"), ("身心障礙", "mis_disab", "Disability"),
              ("高齡與長照", "mis_elder", "Elder & long-term care"), ("教育與學習", "mis_edu", "Education"),
              ("經濟弱勢家庭", "mis_lowinc", "Low-income families"), ("心理健康", "mis_mh", "Mental health"),
              ("社會創新", "mis_policy", "Social innovation / advocacy"), ("婦女與性別", "mis_women", "Women & gender")]
MISSION_KEYS = [k for _, k, _ in MISSION_KW]
ORG_TYPE_DUMMIES = {"Government / commissioned": "ot_gov", "Association / society": "ot_assoc",
                    "Social welfare agency": "ot_welfare", "Social enterprise": "ot_socent"}   # baseline: foundation + rare types

LABELS: dict[str, str] = {
    "WL": "Workload", "OS": "Organisational support", "JR": "Job resources", "PAY": "Pay (high = less strain)",
    "MA": "Mission alignment", "ID": "Inner drive (UWES-3 engagement)", "BO": "Burnout (CBI)",
    "JS": "Job satisfaction (ProQOL CS)", "RET": "Retention", "SIZE": "Organisation size (0-5)",
    "MISSION": "Mission (joint test of 8 dummies)", "work_bo": "Work-related burnout", "personal_bo": "Personal burnout",
    "proqol_bo": "ProQOL burnout", "proqol_sts": "ProQOL secondary traumatic stress", "proqol_cs": "ProQOL compassion satisfaction",
    **{k: l for _, k, l in MISSION_KW},
}

# --------------------------------------------------------------------------------------------- #
# Answer-label -> numeric maps.  Keys are whitespace-stripped / dash-normalised (see norm()).
# --------------------------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Scale:
    """A response scale: label->code mapping and the theoretical (lo, hi) used for 0-100 POMP rescaling."""
    mapping: dict
    lo: float
    hi: float


SCALES: dict[str, Scale] = {
    "distress": Scale({"完全沒有": 0, "輕微": 1, "中等": 2, "嚴重": 3, "非常嚴重": 4}, 0, 4),
    "agree": Scale({"非常不同意": 1, "不同意": 2, "普通": 3, "同意": 4, "非常同意": 5}, 1, 5),
    "leave_freq": Scale({"從未": 0, "一次或兩次": 1, "一個月一次": 2, "一週一次": 3, "每天": 4}, 0, 4),
    "stay": Scale({"確定不會": 1, "應該不會": 2, "不確定": 3, "應該會，但不確定更久以後": 4,
                   "會，而且我打算長期待下去": 5}, 1, 5),
    "yesno": Scale({"有": 1, "無": 0}, 0, 1),
    "uwes": Scale({"從未": 1, "幾乎從不": 2, "很少": 3, "有時": 4, "經常": 5, "非常經常": 6, "總是": 7}, 1, 7),
    "cbi_freq": Scale({"從未或幾乎從未": 1, "不常": 2, "有時候": 3, "常常": 4, "總是": 5}, 1, 5),
    "proqol": Scale({"從未有過": 1, "很少": 2, "有些時候": 3, "經常如此": 4, "總是如此": 5}, 1, 5),
    # hour bands are ORDINAL codes; "no agreement" / "irregular" are deliberately missing (not a band)
    "hours_agreed": Scale({"20小時以下": 1, "21-40小時": 2, "41小時以上": 3}, 1, 3),
    "hours_actual": Scale({"20小時以下": 1, "21-40小時": 2, "41-50小時": 3, "51-60小時": 4, "61小時以上": 5}, 1, 5),
}


@dataclass(frozen=True)
class Item:
    """One survey item.  `col` is the 0-based column of the organisation block; `alt_col` is the identical
    question in the self-employed block.  `anchor` must occur in the header text of both columns."""
    col: int
    key: str
    label: str
    scale: str
    anchor: str
    alt_col: int | None = None


def _cbi(col: int, key: str, label: str, anchor: str) -> Item:
    return Item(col, key, label, "cbi_freq", anchor, col + 41)


def _pq(col: int, key: str, label: str, anchor: str) -> Item:
    return Item(col, key, label, "proqol", anchor, col + 42)


ITEMS: list[Item] = [
    Item(7, "hours_agreed", "Agreed weekly hours (band)", "hours_agreed", "「約定」的每週工時"),
    Item(8, "hours_actual", "Actual hours, past 7 days (band)", "hours_actual", "「過去七天」"),
    Item(9, "d_workload", "Excess workload / uneven division", "distress", "[工作量過大"),
    Item(10, "d_role", "Unclear role definition", "distress", "[角色定位不清"),
    Item(11, "d_skill", "Demands exceed training", "distress", "[工作要求的能力超出"),
    Item(12, "d_coworker", "Difficulty with colleagues", "distress", "[與同事溝通困難]"),
    Item(13, "d_supervisor", "Difficulty with supervisor", "distress", "[與主管溝通困難]"),
    Item(14, "d_client", "Client boundaries / emotional load", "distress", "[與服務對象之間的界線"),
    Item(15, "d_career", "Limited career path", "distress", "[職涯發展受限"),
    Item(16, "d_pay", "Pay / conditions unsustainable", "distress", "[薪資與勞動條件"),
    Item(17, "d_values", "Values misaligned with org", "distress", "[個人價值觀與機構方向不契合]"),
    Item(18, "r_clear", "Clear expectations", "agree", "[我清楚知道工作上對我的期待"),
    Item(19, "r_autonomy", "Control over how I work", "agree", "[我能掌控自己執行工作的方式]"),
    Item(20, "r_coworker", "Colleague support", "agree", "[工作遇到困難時，同事會幫助我]"),
    Item(21, "r_supervisor", "Supervisor support", "agree", "[工作遇到困難時，主管會支持我]"),
    Item(22, "r_recognition", "Recognition", "agree", "[我的貢獻在工作中有獲得足夠的肯定"),
    Item(23, "r_wlb", "Org supports work-life balance", "agree", "[我的組織支持工作與個人生活"),
    Item(24, "r_voice", "Free to voice concerns", "agree", "[我可以自由地向組織的管理層表達"),
    Item(25, "r_skilldev", "Skill-development opportunity", "agree", "[我在工作中有機會進一步發展"),
    Item(26, "r_careertalk", "Career talks with leadership", "agree", "[我的主管或組織負責人，會與我討論職涯"),
    Item(27, "consider_leaving", "Frequency of seriously considering leaving", "leave_freq", "多常認真考慮離開"),
    Item(28, "expect_stay", "Expect to stay one more year", "stay", "你預期一年後"),
    Item(29, "job_search", "Searched for other jobs", "yesno", "[主動搜尋其他工作機會]"),
    Item(30, "resume", "Updated CV", "yesno", "[更新你的履歷]"),
    Item(31, "applied", "Applied elsewhere", "yesno", "[申請其他工作機會]"),
    Item(32, "u_energy", "Full of energy", "uwes", "[在工作時，我感到充滿能量。]", 73),
    Item(33, "u_passion", "Passionate about work", "uwes", "[我對我的工作充滿熱忱。]", 74),
    Item(34, "u_absorbed", "Absorbed in work", "uwes", "[我沉浸在我的工作中。]", 75),
    _cbi(35, "b1", "Often tired", "[你常覺得疲勞嗎"),
    _cbi(36, "b2", "Physically drained", "[你常覺得身體上體力透支嗎"),
    _cbi(37, "b3", "Emotionally drained", "[你常覺得情緒上心力交瘁嗎"),
    _cbi(38, "b4", "'Cannot take it anymore'", "我快要撐不下去了"),
    _cbi(39, "b5", "Completely exhausted", "[你常覺得精疲力竭嗎"),
    _cbi(40, "b6", "Weak / about to get sick", "[你常常覺得虛弱"),
    _cbi(41, "w1", "Work emotionally draining", "[你的工作會令人情緒上心力交瘁嗎"),
    _cbi(42, "w2", "Work: about to collapse", "[你的工作會讓你覺得快要累垮了嗎"),
    _cbi(43, "w3", "Work is frustrating", "[你的工作會讓你覺得挫折嗎"),
    _cbi(44, "w4", "Drained after a work day", "[工作一整天之後"),
    _cbi(45, "w5", "Dread another work day", "[上班之前只要想到"),
    _cbi(46, "w6", "Every work hour is an ordeal", "[上班時你會覺得每一刻都很難熬嗎"),
    _cbi(47, "w7", "Energy left for friends/family", "[不工作的時候"),
    _pq(49, "sts1", "Affected by traumatised clients", "[我想我已經被這些我所幫助"),
    _pq(50, "bo1", "Feel trapped by helping work", "[從事助人的工作讓我感到陷入困境"),
    _pq(51, "cs1", "I like helping work", "[我喜歡從事助人的工作"),
    _pq(52, "sts2", "Depressed by traumatised clients", "[我所幫助的嚴重創傷經驗者讓我感到沮喪"),
    _pq(53, "cs2", "Work satisfies me", "[我的工作使我感到滿意"),
    _pq(54, "bo2", "Exhausted because I am a helper", "[我覺得筋疲力竭，因為"),
    _pq(55, "bo3", "Overwhelmed by endless workload", "[我覺得很受不了"),
    _pq(56, "sts3", "Intrusive / frightening thoughts", "[由於我助人的結果"),
    _pq(57, "cs3", "Glad I chose this work", "[我很高興我選擇了做這份工作"),
]
ITEM_BY_KEY = {i.key: i for i in ITEMS}
LABELS.update({i.key: i.label for i in ITEMS})

# Profile / free-choice columns: key -> (0-based column, header anchor)
PROFILE_COLS = {
    "type": (1, "工作型態"), "org_type": (2, "機構的性質"), "size": (3, "全職人數"), "mission": (4, "主要服務領域"),
    "helping_yrs": (5, "助人工作總年資"), "tenure": (6, "機構的總年資"), "role": (58, "角色"),
    "sup_have_staff": (59, "就你所知"), "sup_want_staff": (60, "最希望機構增加"), "bar_staff": (61, "還沒有建立"),
    "sup_have_dm": (62, "你的機構目前有以下哪些支持制度"), "sup_want_dm": (63, "最希望為你的機構增加"),
    "bar_dm": (64, "導入這類方案"), "prog_interest": (66, "免費的支持方案"), "dm_attitude": (67, "決策者"),
    "helping_yrs_self": (69, "助人工作總年資"), "challenge_1": (70, "第一大挑戰"), "challenge_2": (71, "第二大挑戰"),
    "challenge_3": (72, "第三大挑戰"), "gender": (101, "性別"), "age": (102, "年齡"), "county": (103, "縣市"),
}

SIZE_ORDER = ["1-4人", "5-10人", "11-15人", "16-30人", "31-50人", "51人以上"]
SIZE_LABEL = ["1-4", "5-10", "11-15", "16-30", "31-50", "51+"]
TENURE_ORDER = ["1年以內", "1年以上，未滿3年", "3年以上，未滿5年", "5年以上，未滿8年", "8年以上，未滿15年", "15年以上"]
TENURE_LABEL = ["<1 yr", "1-3 yrs", "3-5 yrs", "5-8 yrs", "8-15 yrs", "15+ yrs"]
AGE_ORDER = ["18-24歲", "25-29歲", "30-34歲", "35-39歲", "40-49歲", "50歲以上"]
AGE_LABEL = ["18-24", "25-29", "30-34", "35-39", "40-49", "50+"]
RULES_TYPE = [("獨立工作者", "Freelancer / independent"), ("同時有機構工作", "Org + personal projects"),
              ("隸屬於一個機構", "Org-affiliated")]
RULES_ORG = [("財團法人基金會", "Foundation"), ("政府部門", "Government / commissioned"), ("社團法人", "Association / society"),
             ("社會福利機構", "Social welfare agency"), ("社會企業", "Social enterprise"), ("地方創生", "Community / regional team")]
RULES_ROLE = [("創辦人", "Founder / decision-maker"), ("中階", "Mid-level manager"), ("第一線", "Frontline helper"),
              ("行政", "Admin / project / finance"), ("人資", "HR / training")]
RULES_GENDER = [("非二元", "Non-binary / other"), ("女性", "Female"), ("男性", "Male"), ("不願透露", "Prefer not to say")]
COUNTY_EN = {"臺北市": "Taipei", "新北市": "New Taipei", "基隆市": "Keelung", "桃園市": "Taoyuan", "新竹市": "Hsinchu City",
             "新竹縣": "Hsinchu County", "苗栗縣": "Miaoli", "臺中市": "Taichung", "彰化縣": "Changhua", "南投縣": "Nantou",
             "雲林縣": "Yunlin", "嘉義市": "Chiayi City", "嘉義縣": "Chiayi County", "臺南市": "Tainan", "高雄市": "Kaohsiung",
             "屏東縣": "Pingtung", "宜蘭縣": "Yilan", "花蓮縣": "Hualien", "臺東縣": "Taitung", "澎湖縣": "Penghu",
             "金門縣": "Kinmen", "連江縣": "Lienchiang"}

# --------------------------------------------------------------------------------------------- #
# Construct specifications.   (item key, reverse-scored?)   Reverse => 100 - POMP.
# --------------------------------------------------------------------------------------------- #
_BO_ITEMS = [(f"b{i}", 0) for i in range(1, 7)] + [(f"w{i}", 0) for i in range(1, 7)] + [("w7", 1)]
SPEC_BRIEF_LITERAL: dict[str, list[tuple[str, int]]] = {
    "WL": [("hours_agreed", 0), ("hours_actual", 0), ("d_workload", 0), ("d_role", 0), ("d_client", 0)],     # cols 7,8,9,10,14
    "OS": [("d_coworker", 0), ("d_supervisor", 1), ("r_coworker", 0), ("r_supervisor", 0), ("r_recognition", 0),
           ("r_wlb", 0), ("r_voice", 0)],                                                                       # cols 12,13r,20-24
    "JR": [("d_career", 1), ("r_clear", 0), ("r_autonomy", 0), ("r_skilldev", 0), ("r_careertalk", 0)],      # cols 15r,18,19,25,26
    "PAY": [("d_pay", 1)],                                                                                      # col 16r
    "MA": [("d_values", 1)],                                                                                    # col 17r
    "ID": [("u_energy", 0), ("u_passion", 0), ("u_absorbed", 0)],                                              # cols 32-34
    "BO": _BO_ITEMS,                                                                                            # cols 35-47, 47r
    "JS": [("cs1", 0), ("cs2", 0), ("cs3", 0)],                                                                 # cols 51,53,57
    "RET": [("consider_leaving", 1), ("expect_stay", 0), ("job_search", 0), ("resume", 0), ("applied", 0)],   # cols 27r,28-31
}
SPEC_PRIMARY = {k: list(v) for k, v in SPEC_BRIEF_LITERAL.items()}
SPEC_PRIMARY["OS"][0] = ("d_coworker", 1)      # col 12 is a 'difficulty' item like col 13 -> must be reversed too
SPEC_PRIMARY["RET"] = [("consider_leaving", 1), ("expect_stay", 0), ("job_search", 1), ("resume", 1), ("applied", 1)]
SPEC_EXTENDED = {k: list(v) for k, v in SPEC_PRIMARY.items()}
SPEC_EXTENDED["WL"] = [("hours_actual", 0), ("d_workload", 0), ("d_role", 0), ("d_skill", 0), ("d_client", 0)]
SPECS = {"brief_literal": SPEC_BRIEF_LITERAL, "primary": SPEC_PRIMARY, "extended": SPEC_EXTENDED}
SPEC_NOTES = {
    "OS col 12": "Difficulty with colleagues is a distress item (higher = worse) exactly like col 13, which the brief already "
                 "reverses; left unreversed it correlates negatively with every other support item (see coding audit).",
    "RET cols 29-31": "Coded 1 = yes = looking to leave, so they must be reversed like col 27; as briefed the scale has "
                      "alpha near zero because the items cancel each other.",
    "WL col 11 / col 7": "(extended spec only) col 11 was unassigned in the brief and correlates with the other demand items; "
                         "col 7 is a contract term, not a load, and 'no agreement' is missing.",
    "ID (PV)": "Cols 32-34 are the UWES-3 engagement items, not 'personal values'.",
    "JS": "Cols 51/53/57 are ProQOL compassion-satisfaction items in an OPTIONAL block preceded by a trauma warning.",
}
MIN_FRAC = {"PAY": 1.0, "MA": 1.0, "ID": 1.0, "JS": 1.0}   # all other composites: >= 50% of items answered

# Values printed in the IQP report (Section 4.1.4) -- the benchmark for the validation step.
# standardised betas; (n, R2) per equation.
# NOTE: the IQP report does not state whether its significance stars came from classical or robust (HC3) standard errors.
# Betas, n and R2 are unaffected by that choice; star agreement near p = .05 (e.g. Eq.2 OS and JR, p = .04) may be.
IQP_BENCHMARK = {
    "Eq1_BO": {"n": 264, "r2": 0.504, "beta": {"WL": 0.393, "OS": 0.253, "JR": 0.059, "PAY": -0.023, "MA": -0.010,
                                                "ID": -0.278, "SIZE": -0.016}},
    "Eq2_JS": {"n": 199, "r2": 0.506, "beta": {"WL": 0.026, "OS": -0.189, "JR": 0.186, "PAY": 0.034, "MA": 0.078,
                                                "ID": 0.596, "SIZE": -0.056}},
    "Eq3_RET": {"n": 203, "r2": 0.143, "beta": {"JS": 0.061, "BO": -0.287, "SIZE": -0.074}},
}
IQP_SIG = {"Eq1_BO": {"WL": "***", "OS": "**", "ID": "***"}, "Eq2_JS": {"OS": "*", "JR": "*", "ID": "***"},
           "Eq3_RET": {"BO": "***"}}


# =============================================================================================== #
# 2. GENERIC HELPERS
# =============================================================================================== #
def norm(v):
    """Strip all whitespace and normalise dash variants so label matching is robust to typing differences."""
    if pd.isna(v):
        return np.nan
    return re.sub(r"\s+", "", str(v)).replace("–", "-").replace("—", "-").replace("－", "-")


def label_rules(series: pd.Series, rules: Sequence[tuple[str, str]], default: str = "Other") -> pd.Series:
    """First-substring-match labelling; NaN stays NaN."""
    def f(v):
        if pd.isna(v):
            return np.nan
        return next((lab for kw, lab in rules if kw in str(v)), default)
    return series.map(f)


def ordinal(series: pd.Series, order: list[str], labels: list[str]) -> tuple[pd.Series, pd.Series]:
    """Return (numeric ordinal code, ordered labelled Categorical)."""
    n = series.map(norm)
    code = n.map({norm(k): i for i, k in enumerate(order)}).astype(float)
    cat = pd.Categorical(n.map({norm(k): l for k, l in zip(order, labels)}), categories=labels, ordered=True)
    return code, pd.Series(cat, index=series.index)


def pomp(s: pd.Series, lo: float, hi: float, reverse: bool = False) -> pd.Series:
    """Percent Of Maximum Possible: linear rescale to 0-100 (Cohen et al., 1999); reverse => 100 - x."""
    x = (s - lo) / (hi - lo) * 100.0
    return 100.0 - x if reverse else x


def row_mean(frame: pd.DataFrame, min_frac: float = 0.5) -> pd.Series:
    """Mean of available items, defined only if at least ceil(k * min_frac) items are present (prorating)."""
    ok = frame.notna().sum(axis=1) >= math.ceil(frame.shape[1] * min_frac)
    return frame.mean(axis=1).where(ok)


def bh_fdr(p: Iterable[float]) -> np.ndarray:
    """Benjamini-Hochberg (1995) adjusted p-values; NaN-safe; valid under independence / PRDS."""
    p = np.asarray(list(p), dtype=float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    if pv.size == 0:
        return q
    order = np.argsort(pv)
    ranked = pv[order] * pv.size / (np.arange(pv.size) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adj = np.empty_like(pv)
    adj[order] = np.minimum(ranked, 1.0)
    q[ok] = adj
    return q


def stars(q: float) -> str:
    if pd.isna(q):
        return ""
    return "***" if q < 0.001 else "**" if q < 0.01 else "*" if q < 0.05 else ""


def wilson_ci(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for a proportion (better than Wald for small n / extreme p)."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (centre - half, centre + half)


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Newcombe (1998) hybrid-score CI for p1 - p2 (method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1)
    l2, u2 = wilson_ci(k2, n2)
    d = p1 - p2
    return (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def md_table(df: pd.DataFrame, fmt: str = "{:.3g}") -> str:
    """Minimal Markdown table writer (avoids the optional `tabulate` dependency)."""
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, (float, np.floating)) and pd.notna(v)
                 else ("" if pd.isna(v) else str(v)) for v in r.values]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


class Output:
    """Output-directory manager: every table is a CSV (UTF-8 with BOM for Excel); every figure its own PNG."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.fig_dir, self.tab_dir = self.root / "figures", self.root / "tables"
        self.fig_dir.mkdir(parents=True, exist_ok=True)
        self.tab_dir.mkdir(parents=True, exist_ok=True)
        self.tables: dict[str, pd.DataFrame] = {}

    def table(self, df: pd.DataFrame, name: str, index: bool = False) -> pd.DataFrame:
        df.to_csv(self.tab_dir / f"{name}.csv", index=index, encoding="utf-8-sig")
        self.tables[name] = df
        LOG.info("table  %s (%d rows)", name, len(df))
        return df

    def figure(self, fig, name: str) -> None:
        path = self.fig_dir / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        LOG.info("figure %s", name)


# =============================================================================================== #
# 3. LOADING, LAYOUT VERIFICATION, CLEANING
# =============================================================================================== #
class LayoutError(RuntimeError):
    """Raised when a column does not carry the header text the specification expects."""


def verify_layout(raw: pd.DataFrame) -> pd.DataFrame:
    """Check every positional column against its header anchor.  Returns an audit table; raises LayoutError
    on any mismatch (a shifted export would otherwise silently score the wrong questions)."""
    rows, bad = [], []
    checks = [(i.col, i.key, i.anchor) for i in ITEMS] + [(i.alt_col, i.key + " (self-employed copy)", i.anchor)
                                                          for i in ITEMS if i.alt_col is not None]
    checks += [(c, k, a) for k, (c, a) in PROFILE_COLS.items()]
    for col, key, anchor in checks:
        header = str(raw.columns[col]) if col < raw.shape[1] else ""
        ok = anchor in header
        rows.append({"column_0based": col, "key": key, "anchor": anchor, "header_found": header[:70], "ok": ok})
        if not ok:
            bad.append(f"col {col} ({key}): expected '{anchor}' in header, found '{header[:60]}'")
    if bad:
        raise LayoutError("Questionnaire layout differs from the specification:\n  " + "\n  ".join(bad))
    LOG.info("layout check passed for %d columns", len(rows))
    return pd.DataFrame(rows)


# Answer labels that legitimately mean "no value" (not applicable / no fixed hours / no agreement).  They become
# missing on purpose and are NOT counted as coding failures.
NOT_APPLICABLE = {norm(x) for x in ("不適用", "沒有明確約定", "不固定，難以估算")}


def _coded(raw: pd.DataFrame, col: int, scale: str) -> tuple[pd.Series, int]:
    """Map one raw column through a Scale.  Returns (codes, number of non-empty cells with an UNRECOGNISED label);
    declared not-applicable labels are silently missing."""
    s = raw.iloc[:, col].map(norm)
    mapping = {norm(k): v for k, v in SCALES[scale].mapping.items()}
    coded = s.map(mapping).astype(float)
    return coded, int((s.notna() & coded.isna() & ~s.isin(NOT_APPLICABLE)).sum())


def load_and_clean(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Read the CSV and return (analysis dataframe, metadata).  No free text, e-mail or timestamp is retained."""
    raw = pd.read_csv(path)
    LOG.info("loaded %d rows x %d columns", *raw.shape)
    meta: dict = {"n_raw": len(raw), "layout": verify_layout(raw)}
    d = pd.DataFrame(index=raw.index)

    def pc(key: str) -> pd.Series:
        return raw.iloc[:, PROFILE_COLS[key][0]]

    # ---- respondent type and the two analysis groups -------------------------------------------------
    d["respondent_type"] = label_rules(pc("type"), RULES_TYPE)
    d["group"] = np.where(d["respondent_type"] == "Freelancer / independent", GROUP_SELF, GROUP_ORG)
    d["hybrid"] = (d["respondent_type"] == "Org + personal projects").astype(int)
    d["org_type"] = label_rules(pc("org_type"), RULES_ORG)
    for lab, key in ORG_TYPE_DUMMIES.items():           # JS completion varies by organisation type -> missingness / imputation covariates
        d[key] = np.where(d["org_type"].isna(), np.nan, (d["org_type"] == lab).astype(float))
    d["SIZE"], d["size_cat"] = ordinal(pc("size"), SIZE_ORDER, SIZE_LABEL)
    d["helping_yrs"], d["helping_yrs_cat"] = ordinal(pc("helping_yrs").combine_first(pc("helping_yrs_self")),
                                                      TENURE_ORDER, TENURE_LABEL)
    d["org_tenure"], d["org_tenure_cat"] = ordinal(pc("tenure"), TENURE_ORDER, TENURE_LABEL)
    d["age_ord"], d["age_cat"] = ordinal(pc("age"), AGE_ORDER, AGE_LABEL)
    d["role"] = label_rules(pc("role"), RULES_ROLE)
    d["gender"] = label_rules(pc("gender"), RULES_GENDER)
    d["female"] = np.where(d["gender"].isna(), np.nan, (d["gender"] == "Female").astype(float))
    county = pc("county").map(lambda v: COUNTY_EN.get(str(v).strip(), np.nan))   # anything else (typed names) is dropped
    d["_county"] = county                                                       # internal only: used for the cluster-robust sensitivity, never exported
    d["region"] = county.map(lambda v: np.nan if pd.isna(v) else "Taipei metro" if v in ("Taipei", "New Taipei") else "Other")
    d["frontline"] = np.where(d["role"].isna(), np.nan, (d["role"] == "Frontline helper").astype(float))
    d["manager"] = np.where(d["role"].isna(), np.nan, d["role"].isin(["Mid-level manager", "Founder / decision-maker"]).astype(float))

    # ---- mission: multi-select -> one 0/1 dummy per domain (keyword match is delimiter-agnostic) ----------
    dom = pc("mission")
    for kw, key, _ in MISSION_KW:
        d[key] = dom.map(lambda v, kw=kw: np.nan if pd.isna(v) else float(kw in str(v)))
    d["mission_n"] = d[MISSION_KEYS].sum(axis=1).where(dom.notna())

    # ---- item-level coding (organisation block coalesced with the self-employed copy) -----------------------
    unmapped: dict[str, int] = {}
    for it in ITEMS:
        s, bad = _coded(raw, it.col, it.scale)
        if it.alt_col is not None:
            s2, bad2 = _coded(raw, it.alt_col, it.scale)
            s, bad = s.combine_first(s2), bad + bad2
        d[it.key] = s
        if bad:
            unmapped[it.key] = bad
    meta["unmapped_cells"] = unmapped
    if unmapped:
        LOG.warning("cells with an unrecognised answer label (set to missing): %s", unmapped)

    # ---- raw multi-select text kept ONLY for the support-gap module (no free-text columns) -----------------
    for k in ("sup_have_staff", "sup_want_staff", "bar_staff", "sup_have_dm", "sup_want_dm", "bar_dm",
              "prog_interest", "dm_attitude", "challenge_1", "challenge_2", "challenge_3"):
        d["_" + k] = pc(k)
    d["support_branch"] = np.where(pc("sup_have_staff").notna(), "Staff", np.where(pc("sup_have_dm").notna(), "Decision-maker", None))

    # ---- sub-scale composites that do not belong to the JD-R equations -----------------------------------
    d["personal_bo"] = composite(d, [(f"b{i}", 0) for i in range(1, 7)])
    d["work_bo"] = composite(d, [(f"w{i}", 0) for i in range(1, 7)] + [("w7", 1)])
    d["personal_bo_level"] = pd.cut(d["personal_bo"], BURNOUT_BINS, labels=BURNOUT_LABELS)
    d["work_bo_level"] = pd.cut(d["work_bo"], BURNOUT_BINS, labels=BURNOUT_LABELS)
    d["proqol_cs"] = composite(d, [("cs1", 0), ("cs2", 0), ("cs3", 0)], 1.0)
    d["proqol_bo"] = composite(d, [("bo1", 0), ("bo2", 0), ("bo3", 0)], 1.0)
    d["proqol_sts"] = composite(d, [("sts1", 0), ("sts2", 0), ("sts3", 0)], 1.0)
    return d, meta


# =============================================================================================== #
# 4. SCORING
# =============================================================================================== #
def item_frame(d: pd.DataFrame, items: Sequence[tuple[str, int]]) -> pd.DataFrame:
    """Direction-aligned (higher = more of the construct) 0-100 POMP item frame."""
    return pd.DataFrame({k: pomp(d[k], SCALES[ITEM_BY_KEY[k].scale].lo, SCALES[ITEM_BY_KEY[k].scale].hi, bool(r))
                         for k, r in items})


def composite(d: pd.DataFrame, items: Sequence[tuple[str, int]], min_frac: float = 0.5) -> pd.Series:
    return row_mean(item_frame(d, items), min_frac)


def build_constructs(d: pd.DataFrame, spec: dict[str, list[tuple[str, int]]], strict: bool = False) -> pd.DataFrame:
    """All nine JD-R constructs (0-100, direction: high = more of the named construct) under one specification.
    strict=True requires ALL items of every composite (sensitivity to the min_frac prorating rule)."""
    return pd.DataFrame({c: composite(d, spec[c], 1.0 if strict else MIN_FRAC.get(c, 0.5)) for c in CONSTRUCTS})


def with_spec(d: pd.DataFrame, spec_name: str, strict: bool = False) -> pd.DataFrame:
    """Copy of `d` whose nine construct columns are scored under the named specification."""
    out = d.drop(columns=[c for c in CONSTRUCTS if c in d.columns]).copy()
    return pd.concat([out, build_constructs(d, SPECS[spec_name], strict)], axis=1)


# =============================================================================================== #
# 5. PSYCHOMETRICS
# =============================================================================================== #
def cronbach_alpha(items: pd.DataFrame) -> tuple[float, int]:
    """Cronbach's alpha on complete cases.  For 0/1 items this equals KR-20.  Returns (alpha, n_complete)."""
    x = items.dropna()
    k = x.shape[1]
    if len(x) < MIN_GROUP_N or k < 2:
        return np.nan, len(x)
    tot_var = x.sum(axis=1).var(ddof=1)
    if tot_var <= 0:
        return np.nan, len(x)
    return (k / (k - 1)) * (1 - x.var(axis=0, ddof=1).sum() / tot_var), len(x)


def one_factor_loadings(corr: np.ndarray, max_iter: int = 500, tol: float = 1e-7) -> np.ndarray:
    """Principal-axis one-factor loadings (iterated communalities; Heywood cases clipped)."""
    k = corr.shape[0]
    try:
        h = 1 - 1 / np.diag(np.linalg.inv(corr))        # squared multiple correlations as starting communalities
    except np.linalg.LinAlgError:
        h = np.full(k, 0.5)
    h = np.clip(h, 0.05, 0.99)
    load = np.sqrt(h)
    for _ in range(max_iter):
        red = corr.copy()
        np.fill_diagonal(red, h)
        w, v = np.linalg.eigh(red)
        load = v[:, -1] * math.sqrt(max(w[-1], 1e-12))
        if load.sum() < 0:
            load = -load
        h_new = np.clip(load ** 2, 0.005, 0.995)
        if np.max(np.abs(h_new - h)) < tol:
            h = h_new
            break
        h = h_new
    return np.clip(load, -0.995, 0.995)


def omega_total(items: pd.DataFrame) -> float:
    """McDonald's omega-total from a one-factor model on Pearson correlations (complete cases).
    NOTE: for the 13-item burnout composite (two sub-dimensions) a one-factor omega is a lower bound; ordinal /
    polychoric CFA (e.g. lavaan WLSMV) is the recommended confirmation and is outside this script's scope."""
    x = items.dropna()
    if x.shape[1] < 3 or len(x) < MIN_GROUP_N or (x.std() == 0).any():
        return np.nan
    lam = one_factor_loadings(np.corrcoef(x.values.T))
    num = lam.sum() ** 2
    return float(num / (num + (1 - lam ** 2).sum()))


def tucker_phi(a: np.ndarray, b: np.ndarray) -> float:
    """Tucker's congruence coefficient between two loading vectors (>= .95 = 'equal', .85-.94 = fair similarity)."""
    return float(np.sum(a * b) / math.sqrt(np.sum(a ** 2) * np.sum(b ** 2)))


def alpha_boot_ci(items: pd.DataFrame, rng: np.random.Generator, B: int = 500) -> tuple[float, float]:
    x = items.dropna().values
    if x.shape[0] < MIN_GROUP_N or x.shape[1] < 2:
        return (np.nan, np.nan)
    vals = []
    for _ in range(B):
        s = x[rng.integers(0, len(x), len(x))]
        tv = s.sum(axis=1).var(ddof=1)
        if tv > 0:
            vals.append(s.shape[1] / (s.shape[1] - 1) * (1 - s.var(axis=0, ddof=1).sum() / tv))
    return tuple(np.percentile(vals, [2.5, 97.5])) if vals else (np.nan, np.nan)


def reliability_table(d: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Alpha (with bootstrap CI), omega-total and mean inter-item r for every multi-item construct, every
    specification, in the organisation group and (where n >= MIN_GROUP_N) the self-employed group."""
    rows = []
    for spec_name, spec in SPECS.items():
        for cons in CONSTRUCTS:
            if len(spec[cons]) < 2:
                continue
            for grp in (GROUP_ORG, GROUP_SELF):
                fr = item_frame(d[d["group"] == grp], spec[cons])
                if fr.notna().all(axis=1).sum() < MIN_GROUP_N:
                    continue
                a, n = cronbach_alpha(fr)
                lo, hi = alpha_boot_ci(fr, rng)
                cm = fr.dropna().corr().values
                rows.append({"spec": spec_name, "group": grp, "construct": cons, "k_items": fr.shape[1],
                             "alpha": a, "alpha_ci_low": lo, "alpha_ci_high": hi, "omega_total": omega_total(fr),
                             "mean_inter_item_r": cm[np.triu_indices_from(cm, 1)].mean(), "n_complete": n})
    return pd.DataFrame(rows)


def coding_audit(d: pd.DataFrame) -> pd.DataFrame:
    """Automatic direction audit.  For each item: Spearman correlation with the mean of the other items of its
    construct (after the specification's reverse-coding).  A NEGATIVE value flags a probable coding/direction error;
    this is how cols 12 and 29-31 were identified.  Organisation group only (the only group with all constructs)."""
    org = d[d["group"] == GROUP_ORG]
    rows = []
    for spec_name, spec in SPECS.items():
        for cons in CONSTRUCTS:
            if len(spec[cons]) < 2:
                continue
            fr = item_frame(org, spec[cons])
            for k, rev in spec[cons]:
                rest = fr.drop(columns=k)
                sub = pd.concat([fr[k], rest.mean(axis=1)], axis=1).dropna()
                r = stats.spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])[0] if len(sub) >= MIN_PAIR_N and sub.iloc[:, 0].nunique() > 1 else np.nan
                a_del = cronbach_alpha(rest)[0] if rest.shape[1] > 1 else np.nan
                rows.append({"spec": spec_name, "construct": cons, "item": k, "column_0based": ITEM_BY_KEY[k].col,
                             "question": ITEM_BY_KEY[k].label, "reversed": bool(rev), "item_rest_rho": r,
                             "alpha_if_deleted": a_del,
                             "flag": "CHECK DIRECTION (negative item-rest r)" if pd.notna(r) and r < 0 else
                                     "weak item (r < .20)" if pd.notna(r) and r < 0.20 else ""})
    return pd.DataFrame(rows)


# =============================================================================================== #
# 6. REGRESSION ENGINE  (OLS + HC3 / cluster-robust, diagnostics, logistic, Rubin pooling)
# =============================================================================================== #
@dataclass
class OLSFit:
    """Result of fit_ols.  All inference is heteroskedasticity-robust (HC3) unless `cluster` was supplied (CR1)."""
    y: str
    names: list[str]            # slope names (no intercept)
    beta: np.ndarray            # intercept first, raw units of y
    cov: np.ndarray             # robust covariance of beta
    df: float                   # residual df (n-k) or G-1 for cluster-robust
    n: int
    r2: float
    adj_r2: float
    sd_x: np.ndarray            # SD of each slope (1.0 for 0/1 dummies, which are never standardised)
    sd_y: float
    X: np.ndarray
    resid: np.ndarray
    hat: np.ndarray
    binary: list[bool]

    @property
    def se(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))

    @property
    def std_scale(self) -> np.ndarray:
        """Multiply raw slopes (and their SEs) by this to obtain standardised ones (y in SD units; x in SD units
        except dummies)."""
        return self.sd_x / self.sd_y

    def table(self) -> pd.DataFrame:
        tc = stats.t.ppf(0.975, self.df)
        b, se = self.beta[1:], self.se[1:]
        t = b / se
        sc = self.std_scale
        return pd.DataFrame({"outcome": self.y, "key": self.names, "predictor": [LABELS.get(c, c) for c in self.names],
                             "b_raw": b, "se_raw": se, "std_beta": b * sc, "se_std": se * sc,
                             "ci_low": (b - tc * se) * sc, "ci_high": (b + tc * se) * sc,
                             "t": t, "p": 2 * stats.t.sf(np.abs(t), self.df), "n": self.n})

    def wald(self, names: Sequence[str]) -> tuple[float, float, int]:
        """Joint HC3-Wald F test that all listed slopes are zero (F approximation with q and df degrees of freedom)."""
        idx = [1 + self.names.index(c) for c in names]
        b = self.beta[idx]
        W = float(b @ np.linalg.pinv(self.cov[np.ix_(idx, idx)]) @ b)
        F = W / len(idx)
        return F, float(stats.f.sf(F, len(idx), self.df)), len(idx)


def fit_ols(df: pd.DataFrame, y: str, xs: Sequence[str], cluster: pd.Series | None = None) -> OLSFit:
    """OLS on complete cases with HC3 robust covariance (MacKinnon & White 1985; Long & Ervin 2000: preferred for
    n < 250).  With `cluster`, a CR1 cluster-robust covariance and G-1 df are used instead."""
    xs = list(xs)
    cols = [y] + xs
    sub = df[cols].dropna()
    if cluster is not None:
        sub = sub.join(cluster.rename("_cl"), how="inner").dropna(subset=["_cl"])
    n = len(sub)
    X = np.column_stack([np.ones(n), sub[xs].values.astype(float)])
    yv = sub[y].values.astype(float)
    k = X.shape[1]
    if n <= k + 2:
        raise ValueError(f"too few observations ({n}) for {k} parameters in model for {y}")
    XtXi = np.linalg.pinv(X.T @ X)
    beta = XtXi @ X.T @ yv
    e = yv - X @ beta
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    if cluster is None:
        meat = (X.T * (e ** 2 / np.clip(1 - h, 1e-8, None) ** 2)) @ X                  # HC3
        cov, dof = XtXi @ meat @ XtXi, float(n - k)
    else:
        g = sub["_cl"].values
        meat = np.zeros((k, k))
        groups = np.unique(g)
        for gi in groups:
            s = X[g == gi].T @ e[g == gi]
            meat += np.outer(s, s)
        G = len(groups)
        cov = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))                  # CR1
        dof = float(G - 1)
    ss_res, ss_tot = float(e @ e), float(((yv - yv.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot
    binary = [set(np.unique(sub[c].values)) <= {0.0, 1.0} for c in xs]
    sd_x = np.array([1.0 if b else sub[c].std(ddof=1) for c, b in zip(xs, binary)])
    return OLSFit(y, xs, beta, cov, dof, n, r2, 1 - (1 - r2) * (n - 1) / (n - k), sd_x, float(sub[y].std(ddof=1)),
                  X, e, h, binary)


def vif_values(fit: OLSFit) -> np.ndarray:
    """Variance inflation factors; zero-variance columns (a rare dummy constant in a sub-sample) get NaN instead of crashing."""
    Xs = fit.X[:, 1:]
    ok = Xs.std(0) > 0
    out = np.full(Xs.shape[1], np.nan)
    if ok.sum() > 1:
        out[ok] = np.diag(np.linalg.pinv(np.corrcoef(Xs[:, ok].T)))
    elif ok.sum() == 1:
        out[ok] = 1.0
    return out


def robustness_value(t: np.ndarray | float, df: np.ndarray | float) -> np.ndarray:
    """Cinelli & Hazlett (2020) robustness value RV(q=1): the share of residual variance that an unmeasured confounder would
    have to explain BOTH in the exposure and in the outcome to bring the coefficient to zero.  RV = (sqrt(f^4 + 4 f^2) - f^2)/2,
    f = |t|/sqrt(df).  Larger = harder to explain away.  Valid for OLS coefficients (here: with HC3 t-values)."""
    f = np.abs(np.asarray(t, dtype=float)) / np.sqrt(np.asarray(df, dtype=float))
    return 0.5 * (np.sqrt(f ** 4 + 4 * f ** 2) - f ** 2)


def diagnostics(fit: OLSFit) -> dict:
    """Model diagnostics: VIF, condition number, Koenker-Breusch-Pagan, Ramsey RESET, Cook's D, studentised residuals."""
    n, k = fit.X.shape
    Xs = fit.X[:, 1:]
    vif = vif_values(fit)
    Z = (Xs - Xs.mean(0)) / np.where(Xs.std(0) == 0, 1, Xs.std(0))
    e2 = fit.resid ** 2
    aux = np.linalg.lstsq(fit.X, e2, rcond=None)[0]
    r2_aux = 1 - ((e2 - fit.X @ aux) ** 2).sum() / ((e2 - e2.mean()) ** 2).sum()
    bp_p = float(stats.chi2.sf(n * r2_aux, k - 1))
    yhat = fit.X @ fit.beta
    Xa = np.column_stack([fit.X, yhat ** 2, yhat ** 3])
    rss0 = float(fit.resid @ fit.resid)
    ba = np.linalg.lstsq(Xa, yhat + fit.resid, rcond=None)[0]
    rss1 = float(((yhat + fit.resid - Xa @ ba) ** 2).sum())
    reset_p = float(stats.f.sf(((rss0 - rss1) / 2) / (rss1 / (n - k - 2)), 2, n - k - 2)) if rss1 > 0 else np.nan
    s2 = rss0 / (n - k)
    cook = fit.resid ** 2 * fit.hat / (k * s2 * (1 - fit.hat) ** 2)
    stud = fit.resid / np.sqrt(s2 * (1 - fit.hat))
    return {"n": n, "k_params": k, "max_VIF": float(vif.max()), "condition_number": float(np.linalg.cond(Z)),
            "BP_heterosk_p": bp_p, "RESET_p": reset_p, "n_cook_gt_4_over_n": int((cook > 4 / n).sum()),
            "max_abs_stud_resid": float(np.abs(stud).max())}


def _expit(z):
    return 1 / (1 + np.exp(-z))


def fit_logit(X: np.ndarray, y: np.ndarray, ridge: float = 1e-6, iters: int = 100) -> dict:
    """Logistic regression by IRLS (intercept must be column 0 of X).  Tiny ridge guards against separation."""
    if y.sum() < 5 or (1 - y).sum() < 5:
        raise ValueError("logit needs at least 5 events and 5 non-events")
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = _expit(X @ b)
        W = np.clip(p * (1 - p), 1e-9, None)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p) - ridge * b)
        b += step
        if np.max(np.abs(step)) < 1e-9:
            break
    p = _expit(X @ b)
    ll = float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))
    p0 = y.mean()
    ll0 = float(len(y) * (p0 * math.log(p0) + (1 - p0) * math.log(1 - p0)))
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ (X * np.clip(p * (1 - p), 1e-9, None)[:, None]) + ridge * np.eye(X.shape[1]))))
    pos, neg = p[y == 1], p[y == 0]
    auc = float(stats.mannwhitneyu(pos, neg).statistic / (len(pos) * len(neg)))
    lr = 2 * (ll - ll0)
    return {"coef": b, "se": se, "p": 2 * stats.norm.sf(np.abs(b / se)), "loglik": ll, "lr_chi2": lr,
            "lr_df": X.shape[1] - 1, "lr_p": float(stats.chi2.sf(lr, X.shape[1] - 1)),
            "mcfadden_r2": 1 - ll / ll0, "auc": auc, "n": len(y)}


def pool_rubin(estimates: list[np.ndarray], variances: list[np.ndarray], df_complete: float) -> pd.DataFrame:
    """Rubin's (1987) rules with the Barnard-Rubin (1999) small-sample df.  `estimates`/`variances` are lists over the
    m imputations of per-parameter vectors (variance = squared SE).  Returns est, se, df, t, p, FMI, RIV."""
    Q = np.array(estimates)
    U = np.array(variances)
    m = Q.shape[0]
    qbar, ubar = Q.mean(0), U.mean(0)
    b = Q.var(0, ddof=1) if m > 1 else np.zeros_like(qbar)
    t = ubar + (1 + 1 / m) * b
    with np.errstate(divide="ignore", invalid="ignore"):
        lam = np.where(t > 0, (1 + 1 / m) * b / t, 0.0)
        r = np.where(ubar > 0, (1 + 1 / m) * b / ubar, 0.0)
        df_old = np.where(lam > 0, (m - 1) / lam ** 2, np.inf)
        df_obs = (df_complete + 1) / (df_complete + 3) * df_complete * (1 - lam)
        df_adj = np.where(np.isfinite(df_old), df_old * df_obs / (df_old + df_obs), df_obs)
        fmi = np.where(np.isfinite(df_old), (r + 2 / (df_old + 3)) / (r + 1), 0.0)
    se = np.sqrt(t)
    tv = qbar / se
    return pd.DataFrame({"est": qbar, "se": se, "df": df_adj, "t": tv, "p": 2 * stats.t.sf(np.abs(tv), df_adj),
                         "fmi": fmi, "riv": r})


# =============================================================================================== #
# 7. RESAMPLING UTILITIES
# =============================================================================================== #
def bca_interval(theta_hat: np.ndarray, boot: np.ndarray, jack: np.ndarray, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Bias-corrected and accelerated bootstrap CI (Efron 1987), vectorised over parameters.
    boot: (B, p) bootstrap replicates; jack: (n, p) leave-one-out estimates."""
    z0 = stats.norm.ppf(np.clip((boot < theta_hat).mean(0) + 0.5 * (boot == theta_hat).mean(0), 1e-6, 1 - 1e-6))
    d = jack.mean(0) - jack
    den = 6 * (np.sum(d ** 2, axis=0) ** 1.5)
    a = np.where(den > 0, np.sum(d ** 3, axis=0) / np.where(den > 0, den, 1), 0.0)
    lo, hi = np.empty_like(theta_hat), np.empty_like(theta_hat)
    for j in range(boot.shape[1]):
        out = []
        for zq in (stats.norm.ppf(alpha / 2), stats.norm.ppf(1 - alpha / 2)):
            adj = stats.norm.cdf(z0[j] + (z0[j] + zq) / (1 - a[j] * (z0[j] + zq)))
            out.append(np.percentile(boot[:, j], 100 * np.clip(adj, 0.001, 0.999)))
        lo[j], hi[j] = out
    return lo, hi


def rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    """Rank-biserial correlation r = 2U/(n1 n2) - 1 (= Cliff's delta); positive => x tends to exceed y."""
    u = stats.mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2 * u / (len(x) * len(y)) - 1)


def rank_biserial_ci(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, B: int = 1000) -> tuple[float, float]:
    vals = [rank_biserial(rng.choice(x, len(x)), rng.choice(y, len(y))) for _ in range(B)]
    return tuple(np.percentile(vals, [2.5, 97.5]))


# =============================================================================================== #
# 8. THE SIMPLIFIED JD-R EQUATIONS
# =============================================================================================== #
CONTROLS = ["SIZE"] + MISSION_KEYS
EQUATIONS: dict[str, tuple[str, list[str]]] = {
    "Eq1_BO": ("BO", PREDICTORS + CONTROLS),
    "Eq2_JS": ("JS", PREDICTORS + CONTROLS),
    "Eq3_RET": ("RET", ["JS", "BO"] + CONTROLS),
    "Eq3b_RET": ("RET", ["JS", "BO"] + PREDICTORS + CONTROLS),     # sensitivity only (see module docstring)
    # --- sensitivity equations (never in the primary family) ---------------------------------------------------
    # ID (engagement) and JS (compassion satisfaction) are both affective, same-questionnaire scales: dropping ID shows how much of
    # the Eq.1/Eq.2 pattern (e.g. the sign of OS) depends on that overlap.
    "Eq1x_BO_noID": ("BO", [p for p in PREDICTORS if p != "ID"] + CONTROLS),
    "Eq2x_JS_noID": ("JS", [p for p in PREDICTORS if p != "ID"] + CONTROLS),
    # burnout split into its two CBI sub-dimensions so that mixing personal and work-related burnout cannot mask work-specific effects
    "Eq1w_workBO": ("work_bo", PREDICTORS + CONTROLS),
    "Eq1p_personalBO": ("personal_bo", PREDICTORS + CONTROLS),
    "Eq3w_RET_workBO": ("RET", ["JS", "work_bo"] + CONTROLS),
    "Eq3p_RET_personalBO": ("RET", ["JS", "personal_bo"] + CONTROLS),
}
STRUCTURAL = {"Eq1_BO": PREDICTORS, "Eq2_JS": PREDICTORS, "Eq3_RET": ["JS", "BO"]}   # the 14 primary-family slopes
IMPUTE_AUX = ["age_ord", "helping_yrs", "org_tenure", "frontline", "manager", "female", "hybrid"] + list(ORG_TYPE_DUMMIES.values())
BINARY_AUX = ["frontline", "manager", "female", "hybrid"] + list(ORG_TYPE_DUMMIES.values())   # rounded back to 0/1 after imputation


def fit_equations(df: pd.DataFrame, cluster: pd.Series | None = None) -> dict[str, OLSFit]:
    return {name: fit_ols(df, y, xs, cluster) for name, (y, xs) in EQUATIONS.items()}


def _mark_primary_family(coef: pd.DataFrame) -> pd.DataFrame:
    """BH-FDR across the 14 pre-specified structural slopes; controls and Eq.3b are outside the family (q = NaN)."""
    coef = coef.copy()
    coef["primary_family"] = [(e in STRUCTURAL and k in STRUCTURAL[e]) for e, k in zip(coef["equation"], coef["key"])]
    coef["q_fdr_primary"] = np.nan
    fam = coef["primary_family"]
    coef.loc[fam, "q_fdr_primary"] = bh_fdr(coef.loc[fam, "p"].values)
    coef["sig"] = coef["q_fdr_primary"].map(stars)
    return coef


def tidy_cc(fits: dict[str, OLSFit]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coefficient and model-summary tables for complete-case fits."""
    coefs, summ = [], []
    for name, f in fits.items():
        t = f.table()
        t.insert(0, "equation", name)
        dg = diagnostics(f)
        t["VIF"] = vif_values(f)
        t["robustness_value"] = robustness_value(t["t"].values, f.df)      # Cinelli-Hazlett RV (confounding sensitivity)
        coefs.append(t)
        Fo, po, _ = f.wald(f.names)
        Fm, pm, _ = f.wald(MISSION_KEYS) if all(k in f.names for k in MISSION_KEYS) else (np.nan, np.nan, 0)
        summ.append({"equation": name, "outcome": f.y, "n": f.n, "r2": f.r2, "adj_r2": f.adj_r2, "wald_F_all": Fo,
                     "wald_p_all": po, "mission_block_F": Fm, "mission_block_p": pm, **{k: v for k, v in dg.items() if k not in ("n",)}})
    return _mark_primary_family(pd.concat(coefs, ignore_index=True)), pd.DataFrame(summ)


def tidy_mi(fit_lists: list[dict[str, OLSFit]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pool the m per-imputation fits with Rubin's rules.  RAW coefficients and their variances are pooled; standardised betas are
    then derived from the pooled raw estimate with SDs averaged over imputations (pooling ratios that use each imputation's own SD
    is not strictly valid).  Inference (t, p, CI) comes from the pooled raw estimate; VIF is averaged over imputations."""
    coefs, summ = [], []
    for name in EQUATIONS:
        fits = [fl[name] for fl in fit_lists]
        tabs = [f.table() for f in fits]
        f0 = fits[0]
        dfc = f0.n - len(f0.beta)
        pr = pool_rubin([t["b_raw"].values for t in tabs], [t["se_raw"].values ** 2 for t in tabs], dfc)
        sc = np.mean([f.sd_x for f in fits], axis=0) / np.mean([f.sd_y for f in fits])
        tc = stats.t.ppf(0.975, pr["df"].values)
        out = pd.DataFrame({"equation": name, "outcome": f0.y, "key": f0.names,
                            "predictor": [LABELS.get(c, c) for c in f0.names], "b_raw": pr["est"], "se_raw": pr["se"],
                            "std_beta": pr["est"] * sc, "se_std": pr["se"] * sc,
                            "ci_low": (pr["est"] - tc * pr["se"]) * sc, "ci_high": (pr["est"] + tc * pr["se"]) * sc,
                            "t": pr["t"], "p": pr["p"], "n": f0.n, "fmi": pr["fmi"],
                            "VIF": np.nanmean([vif_values(f) for f in fits], axis=0),
                            "robustness_value": robustness_value(pr["t"].values, pr["df"].values)})
        coefs.append(out)
        summ.append({"equation": name, "outcome": f0.y, "n": f0.n, "r2": np.mean([f.r2 for f in fits]),
                     "adj_r2": np.mean([f.adj_r2 for f in fits]), "m_imputations": len(fits)})
    return _mark_primary_family(pd.concat(coefs, ignore_index=True)), pd.DataFrame(summ)


# =============================================================================================== #
# 9. MISSING DATA: diagnostics, multiple imputation, delta-adjusted sensitivity
# =============================================================================================== #
MISSING_COVARIATES = PREDICTORS + ["BO", "RET", "SIZE", "age_ord", "helping_yrs", "org_tenure", "frontline", "manager",
                                   "female", "hybrid"] + list(ORG_TYPE_DUMMIES.values())


def js_missingness(org: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Who skipped the optional ProQOL block (JS missing)?  Returns (univariate comparison, multivariable logit).
    A predictable pattern rules out MCAR; it can NEVER distinguish MAR from MNAR (the unobserved JS values are,
    by definition, unobserved) -- hence the delta-adjusted sensitivity analysis below."""
    miss = org["JS"].isna().astype(float)
    rows = []
    for c in MISSING_COVARIATES:
        a, b = org.loc[miss == 0, c].dropna(), org.loc[miss == 1, c].dropna()
        if len(a) < MIN_GROUP_N or len(b) < 5:
            continue
        sp = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
        rows.append({"covariate": c, "label": LABELS.get(c, c), "n_JS_observed": len(a), "n_JS_missing": len(b),
                     "mean_observed": a.mean(), "mean_missing": b.mean(),
                     "std_mean_diff_(obs-miss)": (a.mean() - b.mean()) / sp if sp > 0 else np.nan,
                     "mannwhitney_p": stats.mannwhitneyu(a, b).pvalue})
    uni = pd.DataFrame(rows)
    uni["q_fdr"] = bh_fdr(uni["mannwhitney_p"].values)
    cov = [c for c in MISSING_COVARIATES if org[c].nunique() > 1]
    sub = org[cov].assign(_m=miss).dropna()
    if sub["_m"].sum() < 5 or (1 - sub["_m"]).sum() < 5:      # degenerate: nobody (or everybody) skipped JS in this sample
        return uni, pd.DataFrame()
    Z = (sub[cov] - sub[cov].mean()) / sub[cov].std(ddof=0)
    X = np.column_stack([np.ones(len(Z)), Z.values])
    fit = fit_logit(X, sub["_m"].values)
    lg = pd.DataFrame({"covariate": ["(intercept)"] + cov, "log_odds_per_SD": fit["coef"], "se": fit["se"], "p": fit["p"]})
    lg["odds_ratio"] = np.exp(lg["log_odds_per_SD"])
    lg["or_ci_low"] = np.exp(lg["log_odds_per_SD"] - 1.96 * lg["se"])
    lg["or_ci_high"] = np.exp(lg["log_odds_per_SD"] + 1.96 * lg["se"])
    for k in ("auc", "lr_chi2", "lr_df", "lr_p", "mcfadden_r2", "n"):
        lg[f"model_{k}"] = fit[k]
    lg["events_missing"] = int(sub["_m"].sum())
    return uni, lg


def make_imputations(org: pd.DataFrame, m: int, seed: int) -> tuple[list[pd.DataFrame], pd.Series]:
    """m stochastic-regression (Bayesian-ridge, posterior-sampled) chained-equation imputations of the model constructs
    + controls, with auxiliary variables.  Returns (completed frames, boolean mask of originally-missing JS).
    Imputation model uses the organisation sample only (self-employed lack these constructs by design).
    LIMITATION: imputes composites (not items); linear-Gaussian chained equations, no predictive mean matching."""
    if IterativeImputer is None:
        raise RuntimeError("scikit-learn is required for multiple imputation (pip install scikit-learn)")
    cols = CONSTRUCTS + ["SIZE"] + MISSION_KEYS + IMPUTE_AUX
    X = org[cols].astype(float)
    keep = [c for c in cols if X[c].nunique(dropna=True) > 1]
    lo = np.array([0.0] * len(keep))
    hi = np.array([100.0 if c in CONSTRUCTS else 5.0 if c in ("SIZE", "age_ord", "helping_yrs", "org_tenure") else 1.0 for c in keep])
    frames = []
    for i in range(m):
        imp = IterativeImputer(estimator=BayesianRidge(), sample_posterior=True, max_iter=20, tol=1e-3,
                               random_state=seed + i, min_value=lo, max_value=hi, skip_complete=True)
        arr = pd.DataFrame(imp.fit_transform(X[keep]), index=X.index, columns=keep)
        for c in BINARY_AUX:
            if c in arr:
                arr[c] = arr[c].round().clip(0, 1)          # auxiliary indicators stay 0/1 instead of fractional
        f = org.copy()
        f[keep] = arr
        frames.append(f)
    return frames, org["JS"].isna()


def delta_shift(frames: list[pd.DataFrame], mask: pd.Series, delta: float) -> list[pd.DataFrame]:
    """Delta-adjustment (pattern-mixture sensitivity): add `delta` points to every IMPUTED JS value, clipped to 0-100."""
    out = []
    for f in frames:
        g = f.copy()
        g.loc[mask, "JS"] = (g.loc[mask, "JS"] + delta).clip(0, 100)
        out.append(g)
    return out


def tipping_point(frames: list[pd.DataFrame], mask: pd.Series) -> pd.DataFrame:
    """Re-estimate Eq.2 and Eq.3 after shifting imputed JS by each delta in DELTA_GRID; pooled by Rubin's rules."""
    rows = []
    for delta in DELTA_GRID:
        shifted = delta_shift(frames, mask, delta)
        coef, _ = tidy_mi([fit_equations(f) for f in shifted])
        sel = coef[((coef["equation"] == "Eq2_JS") & coef["key"].isin(PREDICTORS)) | ((coef["equation"] == "Eq3_RET") & coef["key"].isin(["JS", "BO"]))]
        for _, r in sel.iterrows():
            rows.append({"delta_imputed_JS": delta, "equation": r["equation"], "key": r["key"], "std_beta": r["std_beta"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"], "p": r["p"]})
    return pd.DataFrame(rows)


# =============================================================================================== #
# 10. ASSOCIATIONAL PARALLEL MEDIATION  X -> {BO, JS} -> RET  (UNSTANDARDISED; 0-100 points)
# =============================================================================================== #
def _mediation_vector(arr: np.ndarray, k: int) -> np.ndarray:
    """arr columns: [X_1..X_k, controls..., BO, JS, RET].  Returns
    [ind_BO(k), ind_JS(k), ind_total(k), direct(k), total(k), contrast_BO_minus_JS(k), b_BO, b_JS]."""
    n, p = arr.shape
    nc = p - k - 3
    X, C = arr[:, :k], arr[:, k:k + nc]
    bo, js, ret = arr[:, -3], arr[:, -2], arr[:, -1]
    one = np.ones((n, 1))
    base = np.hstack([one, X, C])
    G = base.T @ base
    coef_bo = np.linalg.solve(G, base.T @ bo)
    coef_js = np.linalg.solve(G, base.T @ js)
    coef_tot = np.linalg.solve(G, base.T @ ret)
    full = np.hstack([one, bo[:, None], js[:, None], X, C])
    cf = np.linalg.solve(full.T @ full, full.T @ ret)
    a1, a2 = coef_bo[1:1 + k], coef_js[1:1 + k]
    b1, b2, direct = cf[1], cf[2], cf[3:3 + k]
    return np.concatenate([a1 * b1, a2 * b2, a1 * b1 + a2 * b2, direct, coef_tot[1:1 + k], a1 * b1 - a2 * b2, [b1, b2]])


def mediation(frames: list[pd.DataFrame], B: int, seed: int, bca: bool) -> tuple[pd.DataFrame, int]:
    """Parallel mediation.  One frame (complete case): BCa bootstrap CI.  Several frames (MI): bootstrap WITHIN each imputation
    gives that imputation's sampling variance; point estimates and variances are then pooled with Rubin's rules (so between-
    imputation variance is propagated) and the CI is est +/- t(df)*SE.  A stacked-percentile CI is kept alongside for comparison.
    NOTE: the complete-case sample (rows with JS observed AND all predictors) is smaller than Eq.3's (n = 203), so b_BO / b_JS
    here can differ slightly from the Eq.3 coefficients, which condition on fewer variables."""
    xs = PREDICTORS
    k = len(xs)
    cols = xs + CONTROLS + ["BO", "JS", "RET"]
    rng = np.random.default_rng(seed)
    arrays = [f[cols].dropna().values.astype(float) for f in frames]
    m = len(arrays)
    names = [f"{kind}|{x}" for kind in ("ind_BO", "ind_JS", "ind_total", "direct", "total", "contrast_BO_minus_JS") for x in xs] + ["b_BO", "b_JS"]
    n_used = int(np.mean([len(a) for a in arrays]))
    if m == 1:
        a = arrays[0]
        point = _mediation_vector(a, k)
        draws = np.array([_mediation_vector(a[rng.integers(0, len(a), len(a))], k) for _ in range(B)])
        jack = np.array([_mediation_vector(np.delete(a, i, axis=0), k) for i in range(len(a))])
        lo, hi = bca_interval(point, draws, jack) if bca else np.percentile(draws, [2.5, 97.5], axis=0)
        out = pd.DataFrame({"effect": names, "estimate": point, "ci_low": lo, "ci_high": hi, "fmi": np.nan})
        method = "BCa bootstrap" if bca else "percentile bootstrap"
    else:
        per = max(200, B // m)
        pts, var_w, stacked = [], [], []
        for a in arrays:
            n = len(a)
            dr = np.array([_mediation_vector(a[rng.integers(0, n, n)], k) for _ in range(per)])
            pts.append(_mediation_vector(a, k))
            var_w.append(dr.var(axis=0, ddof=1))
            stacked.append(dr)
        pooled = pool_rubin(pts, var_w, df_complete=n_used - 1)
        tc = stats.t.ppf(0.975, pooled["df"].values)
        slo, shi = np.percentile(np.vstack(stacked), [2.5, 97.5], axis=0)
        out = pd.DataFrame({"effect": names, "estimate": pooled["est"], "ci_low": pooled["est"] - tc * pooled["se"],
                            "ci_high": pooled["est"] + tc * pooled["se"], "fmi": pooled["fmi"],
                            "ci_low_stacked_percentile": slo, "ci_high_stacked_percentile": shi})
        method = "Rubin's rules (bootstrap within-imputation variance)"
    out["ci_excludes_0"] = (out["ci_low"] > 0) | (out["ci_high"] < 0)
    out["ci_method"] = method
    out["n"] = n_used
    out["kind"] = out["effect"].str.split("|").str[0]
    out["predictor"] = out["effect"].str.split("|").str[1]
    return out, n_used


def buffering_tests(org: pd.DataFrame) -> pd.DataFrame:
    """EXPLORATORY JD-R buffering: does a resource weaken the demand-burnout / demand-satisfaction link?  Adds WL x OS and WL x JR
    (SD-scaled, product of z-scores) to the primary equation, one at a time.  BH-FDR over the 4 tests."""
    rows = []
    z = org.copy()
    for c in ("WL", "OS", "JR"):
        z["z" + c] = (z[c] - z[c].mean()) / z[c].std(ddof=1)
    for y in ("BO", "JS"):
        for res in ("OS", "JR"):
            z["WLx" + res] = z["zWL"] * z["z" + res]
            f = fit_ols(z, y, PREDICTORS + CONTROLS + ["WLx" + res])
            t = f.table()
            r = t[t["key"] == "WLx" + res].iloc[0]
            rows.append({"outcome": y, "interaction": f"Workload x {LABELS[res]}", "std_beta": r["std_beta"], "ci_low": r["ci_low"],
                         "ci_high": r["ci_high"], "p": r["p"], "n": f.n})
    out = pd.DataFrame(rows)
    out["q_fdr"] = bh_fdr(out["p"].values)
    return out


def cluster_summary(org: pd.DataFrame) -> pd.DataFrame:
    """How trustworthy is a county-clustered SE?  Number of clusters, size spread and effective number of clusters (1/sum share^2)."""
    c = org["_county"].dropna().value_counts()
    share = c / c.sum()
    return pd.DataFrame([{"n_respondents": int(c.sum()), "n_counties": len(c), "largest_county_share": float(share.iloc[0]),
                          "smallest_county_n": int(c.min()), "median_county_n": float(c.median()),
                          "effective_n_clusters": float(1 / (share ** 2).sum()),
                          "note": "few effective clusters: CR1 county-clustered SEs are anti-conservative here; indicative only. "
                                  "Employer-level clustering cannot be modelled (no organisation ID)."}])


# =============================================================================================== #
# 11. ORGANISATION vs SELF-EMPLOYED
# =============================================================================================== #
COMPARE_VARS = ["BO", "work_bo", "personal_bo", "ID", "JS", "proqol_bo", "proqol_sts"]
REDUCED_EQS = {"R1_BO~ID": ("BO", ["ID"]), "R2_JS~ID": ("JS", ["ID"]), "R3_BO~ID+JS": ("BO", ["ID", "JS"])}
REDUCED_CONTROLS = ["age_ord", "helping_yrs"]       # observed in BOTH groups (org SIZE/MISSION do not exist for the self-employed)


def group_comparison(d: pd.DataFrame, rng: np.random.Generator, exclude_hybrid: bool = False) -> pd.DataFrame:
    """Organisation vs self-employed on the outcomes measured in both blocks.  Mann-Whitney U, rank-biserial r with
    bootstrap CI, BH-FDR across the family.  Exploratory family (7 contrasts)."""
    o = d[d["group"] == GROUP_ORG]
    if exclude_hybrid:
        o = o[o["hybrid"] == 0]
    s = d[d["group"] == GROUP_SELF]
    rows = []
    for v in COMPARE_VARS:
        a, b = o[v].dropna().values, s[v].dropna().values
        if len(a) < MIN_GROUP_N or len(b) < MIN_GROUP_N:
            continue
        rb = rank_biserial(b, a)
        lo, hi = rank_biserial_ci(b, a, rng)
        rows.append({"variable": v, "label": LABELS[v], "n_org": len(a), "mean_org": a.mean(), "sd_org": a.std(ddof=1),
                     "median_org": np.median(a), "n_self": len(b), "mean_self": b.mean(), "sd_self": b.std(ddof=1),
                     "median_self": np.median(b), "mean_diff_self_minus_org": b.mean() - a.mean(),
                     "mannwhitney_p": stats.mannwhitneyu(b, a).pvalue, "rank_biserial_self_vs_org": rb,
                     "rb_ci_low": lo, "rb_ci_high": hi})
    out = pd.DataFrame(rows)
    out["q_fdr"] = bh_fdr(out["mannwhitney_p"].values)
    out["sample"] = "organisation excl. hybrid" if exclude_hybrid else "organisation incl. hybrid"
    return out


def reduced_models(d: pd.DataFrame) -> pd.DataFrame:
    """The part of the JD-R model that exists in BOTH groups (ID, BO, JS), fitted separately per group, plus a pooled
    model testing whether the slope differs by group (interaction, raw 0-100 units, HC3)."""
    rows = []
    for gname, sub in ((GROUP_ORG, d[d["group"] == GROUP_ORG]), (GROUP_SELF, d[d["group"] == GROUP_SELF])):
        for eq, (y, xs) in REDUCED_EQS.items():
            f = fit_ols(sub, y, xs + REDUCED_CONTROLS)
            t = f.table()
            t.insert(0, "equation", eq)
            t.insert(0, "group", gname)
            t["r2"] = f.r2
            rows.append(t)
    out = pd.concat(rows, ignore_index=True)
    out["scope"] = "separate fit per group"
    inter = []
    pooled = d.copy()
    pooled["self"] = (pooled["group"] == GROUP_SELF).astype(float)
    for eq, (y, xs) in REDUCED_EQS.items():
        for x in xs:
            pooled[f"{x}_x_self"] = pooled[x] * pooled["self"]
        names = xs + ["self"] + [f"{x}_x_self" for x in xs] + REDUCED_CONTROLS
        f = fit_ols(pooled, y, names)
        t = f.table()
        t = t[t["key"].str.endswith("_x_self")].copy()
        t.insert(0, "equation", eq)
        t.insert(0, "group", "pooled (interaction)")
        t["scope"] = "difference in raw slope: self-employed minus organisation"
        inter.append(t)
    both = pd.concat([out] + inter, ignore_index=True)
    both["q_fdr_within_table"] = bh_fdr(both["p"].values)
    return both


# =============================================================================================== #
# 12. VALIDATION AGAINST THE IQP REPORT
# =============================================================================================== #
def validate_against_iqp(tables: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare standardised betas / n / R2 printed in the IQP report with this pipeline.
    `tables` maps a label ('brief_literal CC', 'primary CC', 'primary MI') to (coef table, summary table)."""
    rows, srows = [], []
    for label, (coef, summ) in tables.items():
        for eq, bench in IQP_BENCHMARK.items():
            s = summ[summ["equation"] == eq].iloc[0]
            srows.append({"pipeline": label, "equation": eq, "n_iqp": bench["n"], "n_here": s["n"], "r2_iqp": bench["r2"],
                          "r2_here": s["r2"], "r2_diff": s["r2"] - bench["r2"]})
            for key, b_iqp in bench["beta"].items():
                r = coef[(coef["equation"] == eq) & (coef["key"] == key)]
                if r.empty:
                    continue
                r = r.iloc[0]
                star = IQP_SIG.get(eq, {}).get(key, "")
                rows.append({"pipeline": label, "equation": eq, "term": key, "beta_iqp": b_iqp, "iqp_stars": star,
                             "beta_here": r["std_beta"], "diff": r["std_beta"] - b_iqp,
                             "same_sign": np.sign(b_iqp) == np.sign(r["std_beta"]),
                             "here_p": r["p"], "significant_here_p<.05": r["p"] < 0.05,
                             "significance_agrees": (r["p"] < 0.05) == bool(star)})
    det, sm = pd.DataFrame(rows), pd.DataFrame(srows)
    agg = det.groupby("pipeline").agg(n_terms=("term", "size"), mean_abs_diff=("diff", lambda x: np.abs(x).mean()),
                                      max_abs_diff=("diff", lambda x: np.abs(x).max()), sign_agreement=("same_sign", "mean"),
                                      significance_agreement=("significance_agrees", "mean")).reset_index()
    agg["corr_beta"] = [np.corrcoef(det.loc[det["pipeline"] == p, "beta_iqp"], det.loc[det["pipeline"] == p, "beta_here"])[0, 1]
                        for p in agg["pipeline"]]
    return det, pd.concat([agg.assign(section="aggregate"), sm.assign(section="model-level")], ignore_index=True)


# =============================================================================================== #
# 13. THE SUPPORT GAP: what is PROVIDED, what is WANTED, what DECISION-MAKERS report
# =============================================================================================== #
# Two questionnaire branches exist (verified from the data, see `branch_audit`):
#   * Staff branch (cols 59-61): frontline, admin, mid-level managers  -> "what exists as far as I know" / "what I want"
#   * Decision-maker branch (cols 62-64): founders / board / executives and HR -> "what my organisation has" / "what I want to add"
# The two branches are different PEOPLE in (mostly) different organisations: no organisation identifier exists, so
# staff-vs-decision-maker contrasts are between independent samples, NOT matched pairs, and the decision-maker branch
# is small (n = 28).  Treat those contrasts as indicative.
@dataclass(frozen=True)
class SupportItem:
    key: str
    label: str
    supply_kw: str | None      # regex matched against the 'currently available' answer (None = option not asked)
    demand_kw: str | None      # regex matched against the 'most wanted (pick <= 3)' answer (None = option not asked)
    note: str = ""


SUPPORT_ITEMS = [
    SupportItem("counselling", "Individual counselling", "個別心理諮詢", "個別心理諮詢"),
    SupportItem("group_relief", "Group stress relief", "團體減壓", "團體減壓"),
    SupportItem("supervision", "Supervision / coaching", "督導或教練", "督導或教練"),
    SupportItem("leadership", "Leadership & management training", "領導力", "領導力"),
    SupportItem("skills", "Professional skills training", "專業職能培訓", "專業職能培訓"),
    SupportItem("career", "Career development", "職涯發展", "職涯發展",
                "APPROXIMATE match: supply option = a promotion/career SYSTEM, demand option = long-term career DISCUSSIONS"),
    SupportItem("communication", "Internal communication", "內部溝通", "內部溝通"),
    SupportItem("flexible", "Flexible / remote work", "彈性工時|遠距", None, "not offered as a 'wanted' option (write-ins only)"),
    SupportItem("allowance", "Acting-position allowance", "職務代理津貼", "職務代理津貼", "not asked in the decision-maker supply list"),
    SupportItem("finance", "Personal / family financial planning", None, "財務規劃", "not asked in any 'currently available' list"),
]
NONE_SUPPLY, NONE_DEMAND = "以上皆無", "目前不需要額外支"
DM_SUPPLY_NOT_ASKED = {"finance", "allowance"}

BARRIERS = [  # (staff regex, decision-maker regex, English label, directly comparable?)
    ("預算不足", "預算不足", "Insufficient budget", True),
    ("沒有人有餘力", "沒有專人", "No one has capacity / owner", True),
    ("決策者不認為", None, "Decision-makers see no need (staff view only)", False),
    ("不知道從哪裡開始", None, "Don't know where to start (staff view only)", False),
    ("被視為抱怨", "擔心夥伴意願低", "Fear of complaint (staff) / awkward, low uptake (DM)", False),
    ("規模太小", "市場上沒有適合", "Org too small (staff) / no programme for micro-orgs (DM)", False),
    (None, "內部需求不明確", "Unclear internal needs (DM view only)", False),
    (None, "不了解這類方案", "Unclear programme benefits (DM view only)", False),
    (None, "董事會", "Board not supportive (DM view only)", False),
    ("我不確定", None, "Not sure (staff view only)", False),
    (None, "沒有特別顧慮", "No particular concern (DM view only)", False),
]
INTEREST_RULES = [("非常希望", "Very much, we need it"), ("餘力", "Yes, but unsure of capacity"), ("可有可無", "Fine / optional"),
                  ("不太希望", "Not interested (other priorities)"), ("不確定", "Not sure")]
ATTITUDE_RULES = [("很積極", "Enthusiastic"), ("擔心成本", "Interested but worried about cost / workload"),
                  ("不需要", "May think it unnecessary"), ("不是時候", "Not the right time"), ("自己就是決策者", "I am the decision-maker"),
                  ("不確定", "Not sure")]
CHALLENGE_RULES = [("收入不穩定", "Unstable income"), ("專業水準", "Cannot judge own professional level"),
                   ("督導或專業回饋", "No supervision / professional feedback"), ("沒有同儕", "No peers to discuss with"),
                   ("界線模糊", "Blurred work-life boundary"), ("合作機構", "Cannot find partner organisations"),
                   ("長期方向", "Unsure about long-term direction"), ("把關工作量", "Nobody guards my workload"), ("其他", "Other")]


def _has(series: pd.Series, pattern: str | None, none_label: str | None = None) -> pd.Series:
    """Boolean Series: does the multi-select answer contain `pattern`?  NaN where unanswered."""
    if pattern is None:
        return pd.Series(np.nan, index=series.index)
    out = series.map(lambda v: np.nan if pd.isna(v) or str(v).strip() == "" else float(re.search(pattern, str(v)) is not None))
    return out


def _prop(x: pd.Series) -> tuple[float, int, int, float, float]:
    x = x.dropna()
    k, n = int(x.sum()), len(x)
    lo, hi = wilson_ci(k, n) if n else (np.nan, np.nan)
    return (k / n * 100 if n else np.nan, k, n, lo * 100, hi * 100)


def support_gap(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build the provision / need / decision-maker tables.  All percentages are of respondents in the branch who
    answered that question.  'Wanted' is capped at three picks, so a respondent NOT selecting an item does not
    prove they do not want it -> 'wanted' is a lower bound on need, and provided-but-not-wanted is not a surplus."""
    staff = d[d["support_branch"] == "Staff"]
    dm = d[d["support_branch"] == "Decision-maker"]
    rows, ind = [], {}
    for it in SUPPORT_ITEMS:
        hs, ws = _has(staff["_sup_have_staff"], it.supply_kw), _has(staff["_sup_want_staff"], it.demand_kw)
        hd = _has(dm["_sup_have_dm"], None if it.key in DM_SUPPLY_NOT_ASKED else it.supply_kw)
        wd = _has(dm["_sup_want_dm"], it.demand_kw)
        ind[it.key] = (hs, ws)
        r = {"key": it.key, "item": it.label, "comparability_note": it.note}
        for tag, ser in (("staff_provided", hs), ("dm_provided", hd), ("staff_wanted", ws), ("dm_wanted", wd)):
            p, k, n, lo, hi = _prop(ser)
            r.update({f"{tag}_pct": p, f"{tag}_k": k, f"{tag}_n": n, f"{tag}_ci_low": lo, f"{tag}_ci_high": hi})
        both = pd.concat([hs, ws], axis=1, keys=["have", "want"]).dropna()
        if len(both):
            r["staff_unmet_pct"] = ((both["want"] == 1) & (both["have"] == 0)).mean() * 100          # wants it, org lacks it
            r["staff_met_pct"] = ((both["want"] == 1) & (both["have"] == 1)).mean() * 100            # wants it, org has it
            r["staff_provided_not_selected_pct"] = ((both["want"] == 0) & (both["have"] == 1)).mean() * 100
            wanters = (both["want"] == 1).sum()
            r["pct_of_wanters_whose_org_lacks_it"] = ((both["want"] == 1) & (both["have"] == 0)).sum() / wanters * 100 if wanters else np.nan
        r["staff_wanted_minus_provided_pp"] = r.get("staff_wanted_pct", np.nan) - r.get("staff_provided_pct", np.nan)
        # contrasts, staff vs decision-makers (independent samples; Newcombe CI, Fisher exact)
        for tag in ("provided", "wanted"):
            ks, ns, kd, nd = r[f"staff_{tag}_k"], r[f"staff_{tag}_n"], r[f"dm_{tag}_k"], r[f"dm_{tag}_n"]
            if ns and nd:
                lo, hi = newcombe_diff_ci(ks, ns, kd, nd)
                r[f"{tag}_diff_staff_minus_dm_pp"] = (ks / ns - kd / nd) * 100
                r[f"{tag}_diff_ci_low"], r[f"{tag}_diff_ci_high"] = lo * 100, hi * 100
                r[f"{tag}_fisher_p"] = stats.fisher_exact([[ks, ns - ks], [kd, nd - kd]])[1]
        rows.append(r)
    gap = pd.DataFrame(rows)
    for tag in ("provided", "wanted"):
        gap[f"{tag}_fisher_q_fdr"] = bh_fdr(gap[f"{tag}_fisher_p"].values) if f"{tag}_fisher_p" in gap else np.nan
    gap["rank_by_staff_unmet"] = gap["staff_unmet_pct"].rank(ascending=False, method="min")
    gap = gap.sort_values("staff_unmet_pct", ascending=False, na_position="last").reset_index(drop=True)

    # --- by staff role: provision / want / unmet -------------------------------------------------------------
    rr = []
    for role in ("Frontline helper", "Admin / project / finance", "Mid-level manager"):
        sub = staff[staff["role"] == role]
        if len(sub) < MIN_GROUP_N:
            continue
        for it in SUPPORT_ITEMS:
            if it.supply_kw is None or it.demand_kw is None:
                continue
            both = pd.concat([_has(sub["_sup_have_staff"], it.supply_kw), _has(sub["_sup_want_staff"], it.demand_kw)],
                             axis=1, keys=["have", "want"]).dropna()          # complete pairs only: same denominator as the overall table
            if both.empty:
                continue
            rr.append({"role": role, "n": len(both), "item": it.label, "provided_pct": both["have"].mean() * 100,
                       "wanted_pct": both["want"].mean() * 100, "unmet_pct": ((both["want"] == 1) & (both["have"] == 0)).mean() * 100})
    by_role = pd.DataFrame(rr)

    # --- how many supports exist vs the JD-R outcomes (exploratory Spearman) -----------------------------------
    cnt = pd.DataFrame({it.key: _has(staff["_sup_have_staff"], it.supply_kw) for it in SUPPORT_ITEMS if it.supply_kw})
    n_sup = cnt.sum(axis=1).where(cnt.notna().all(axis=1))
    sc = []
    for v in ["OS", "JR", "WL", "BO", "RET"]:
        sub = pd.concat([n_sup.rename("n_sup"), staff[v]], axis=1).dropna()
        if len(sub) >= MIN_PAIR_N:
            rho, p = stats.spearmanr(sub["n_sup"], sub[v])
            sc.append({"outcome": LABELS[v], "spearman_rho": rho, "p": p, "n": len(sub)})
    cnt_tab = pd.DataFrame(sc)
    if len(cnt_tab):
        cnt_tab["q_fdr"] = bh_fdr(cnt_tab["p"].values)
        cnt_tab["predictor"] = "Number of supports staff say exist (0-9)"

    # --- barriers ----------------------------------------------------------------------------------------------
    brow = []
    for s_kw, d_kw, lab, comp in BARRIERS:
        r = {"barrier": lab, "directly_comparable": comp}
        for tag, ser, kw in (("staff", staff["_bar_staff"], s_kw), ("dm", dm["_bar_dm"], d_kw)):
            p, k, n, lo, hi = _prop(_has(ser, kw))
            r.update({f"{tag}_pct": p, f"{tag}_k": k, f"{tag}_n": n})
        if comp:
            r["fisher_p"] = stats.fisher_exact([[r["staff_k"], r["staff_n"] - r["staff_k"]], [r["dm_k"], r["dm_n"] - r["dm_k"]]])[1]
        brow.append(r)
    barriers = pd.DataFrame(brow)
    barriers["q_fdr"] = bh_fdr(barriers["fisher_p"].values) if "fisher_p" in barriers else np.nan

    # --- programme interest and expected decision-maker attitude, by branch ------------------------------------
    def tab(col: str, rules) -> pd.DataFrame:
        t = d.assign(_lab=label_rules(d[col], rules, "Other")).dropna(subset=["_lab", "support_branch"])
        ct = pd.crosstab(t["_lab"], t["support_branch"])
        pct = ct.div(ct.sum(axis=0), axis=1) * 100
        out = ct.join(pct, lsuffix="_n", rsuffix="_pct")
        out.index.name = "answer"
        return out.reset_index()

    return {"support_gap": gap, "support_gap_by_role": by_role, "support_count_vs_outcomes": cnt_tab,
            "barriers": barriers, "programme_interest": tab("_prog_interest", INTEREST_RULES),
            "decision_maker_attitude": tab("_dm_attitude", ATTITUDE_RULES)}


def branch_audit(d: pd.DataFrame) -> pd.DataFrame:
    """Who answered which support branch (justifies treating cols 59-61 as 'staff' and 62-64 as 'decision-maker')."""
    t = pd.crosstab(d["role"].fillna("(self-employed: no role)"), d["support_branch"].fillna("none"))
    t.index.name = "role"
    return t.reset_index()


def role_profile(d: pd.DataFrame) -> pd.DataFrame:
    """Do managers have more (or fewer) resources than frontline staff?  Construct means by role, organisation group,
    with a Kruskal-Wallis test per construct (exploratory; BH-FDR over the family)."""
    org = d[d["group"] == GROUP_ORG]
    roles = [r for r in ("Frontline helper", "Admin / project / finance", "Mid-level manager", "Founder / decision-maker")
             if (org["role"] == r).sum() >= MIN_GROUP_N]
    rows = []
    for c in ["WL", "OS", "JR", "PAY", "MA", "ID", "BO", "JS", "RET"]:
        groups = [org.loc[org["role"] == r, c].dropna() for r in roles]
        ok = [g for g in groups if len(g) >= MIN_GROUP_N]
        if len(ok) < 2:
            continue
        h, p = stats.kruskal(*ok)
        row = {"construct": LABELS[c], "kruskal_H": h, "p": p, "epsilon_sq": h / (sum(len(g) for g in ok) - 1)}
        for r, g in zip(roles, groups):
            row[f"{r} mean (n)"] = f"{g.mean():.1f} ({len(g)})" if len(g) else ""
        rows.append(row)
    out = pd.DataFrame(rows)
    out["q_fdr"] = bh_fdr(out["p"].values)
    return out


def selfemployed_challenges(d: pd.DataFrame) -> pd.DataFrame:
    """Top-3 challenges named by self-employed respondents: % naming each at any rank and % naming it first."""
    s = d[d["group"] == GROUP_SELF]
    rows = []
    cols = ["_challenge_1", "_challenge_2", "_challenge_3"]
    labs = {c: label_rules(s[c], CHALLENGE_RULES, "Other") for c in cols}
    for _, lab in CHALLENGE_RULES:
        anyr = pd.concat([labs[c] == lab for c in cols], axis=1).any(axis=1)
        k, n = int(anyr.sum()), len(s)
        lo, hi = wilson_ci(k, n)
        rows.append({"challenge": lab, "named_any_rank_n": k, "named_any_rank_pct": k / n * 100,
                     "ci_low": lo * 100, "ci_high": hi * 100, "ranked_first_n": int((labs["_challenge_1"] == lab).sum()), "n_respondents": n})
    return pd.DataFrame(rows).sort_values("named_any_rank_n", ascending=False)


# =============================================================================================== #
# 14. ROBUSTNESS GRID  (specification x sample x estimator)
# =============================================================================================== #
SAMPLES: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "org_incl_hybrid": lambda x: x[x["group"] == GROUP_ORG],
    "org_excl_hybrid": lambda x: x[(x["group"] == GROUP_ORG) & (x["hybrid"] == 0)],
}
PRIMARY_KEY = ("primary", "org_incl_hybrid", "complete-case")


def robustness_grid(d: pd.DataFrame, m: int, seed: int) -> tuple[dict, dict]:
    """Fit Eq.1-3b for every (specification, sample) by complete-case; for the primary specification also by multiple
    imputation (both samples) and with county-clustered SEs (sensitivity; few effective clusters -> indicative only).
    Returns ({(spec, sample, method): (coef, summary)}, {sample: (imputed frames, JS-missing mask)})."""
    fits: dict = {}
    imputed: dict = {}
    for spec in SPECS:
        ds = with_spec(d, spec)
        for sname, sel in SAMPLES.items():
            org = sel(ds)
            fits[(spec, sname, "complete-case")] = tidy_cc(fit_equations(org))
            if spec == "primary":
                frames, mask = make_imputations(org, m, seed)
                imputed[sname] = (frames, mask)
                fits[(spec, sname, "multiple imputation")] = tidy_mi([fit_equations(f) for f in frames])
                fits[(spec, sname, "county-clustered SE")] = tidy_cc(fit_equations(org, cluster=org["_county"]))
    dstrict = with_spec(d, "primary", strict=True)          # sensitivity to the prorating (min_frac) rule: every item required
    for sname, sel in SAMPLES.items():
        fits[("primary_strict", sname, "complete-case")] = tidy_cc(fit_equations(sel(dstrict)))
    return fits, imputed


def robustness_tables(fits: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    long = []
    for (spec, sample, method), (coef, _) in fits.items():
        long.append(coef.assign(spec=spec, sample=sample, method=method))
    long = pd.concat(long, ignore_index=True)
    ref = long[(long["spec"] == PRIMARY_KEY[0]) & (long["sample"] == PRIMARY_KEY[1]) & (long["method"] == PRIMARY_KEY[2])]
    rows = []
    for _, r in ref[ref["primary_family"]].iterrows():
        v = long[(long["equation"] == r["equation"]) & (long["key"] == r["key"]) & (long["spec"] != "brief_literal")]
        lit = long[(long["equation"] == r["equation"]) & (long["key"] == r["key"]) & (long["spec"] == "brief_literal")
                   & (long["method"] == "complete-case") & (long["sample"] == "org_incl_hybrid")]
        rows.append({"equation": r["equation"], "term": r["key"], "primary_std_beta": r["std_beta"], "primary_p": r["p"],
                     "n_variants": len(v), "share_same_sign": float((np.sign(v["std_beta"]) == np.sign(r["std_beta"])).mean()),
                     "share_p<.05": float((v["p"] < 0.05).mean()), "primary_p<.05": bool(r["p"] < 0.05),
                     "min_std_beta": v["std_beta"].min(), "max_std_beta": v["std_beta"].max(),
                     "brief_literal_std_beta": lit["std_beta"].iloc[0] if len(lit) else np.nan,
                     "brief_literal_p": lit["p"].iloc[0] if len(lit) else np.nan})
    return long, pd.DataFrame(rows)


# =============================================================================================== #
# 15. FIGURES  (English labels only; every chart is its own PNG so it can be dropped into a document)
# =============================================================================================== #
C_ORG, C_SELF, C_GREY = "#2b6cb0", "#dd6b20", "#8a8a8a"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
                     "font.size": 9, "axes.titleweight": "bold", "axes.titlesize": 10.5})


def fig_reliability(rel: pd.DataFrame, out: Output) -> None:
    r = rel[rel["group"] == GROUP_ORG]
    cons = [c for c in CONSTRUCTS if c in r["construct"].values]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    w = 0.26
    for i, (spec, col) in enumerate((("brief_literal", C_GREY), ("primary", C_ORG), ("extended", "#38a169"))):
        v = r[r["spec"] == spec].set_index("construct")["alpha"].reindex(cons)
        ax.bar(np.arange(len(cons)) + (i - 1) * w, v.values, w, label=spec, color=col)
    ax.axhline(0.7, ls="--", c="k", lw=0.7)
    ax.set_xticks(np.arange(len(cons)))
    ax.set_xticklabels(cons)
    ax.set_ylabel("Cronbach's alpha (organisation group)")
    ax.set_title("Scale reliability by specification (dashed = .70)")
    ax.legend(frameon=False)
    out.figure(fig, "01_reliability_by_specification")


def fig_corr(ds: pd.DataFrame, out: Output) -> pd.DataFrame:
    org = ds[ds["group"] == GROUP_ORG]
    keys = CONSTRUCTS + ["SIZE"]
    n = len(keys)
    rho, pv = np.full((n, n), np.nan), np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i, n):
            sub = org[[keys[i], keys[j]]].dropna()
            if i == j:
                rho[i, j], pv[i, j] = 1.0, 0.0
            elif len(sub) >= MIN_PAIR_N:
                rho[i, j], pv[i, j] = stats.spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
                rho[j, i], pv[j, i] = rho[i, j], pv[i, j]
    iu = np.triu_indices(n, 1)
    q = np.full((n, n), np.nan)
    q[iu] = bh_fdr(pv[iu])
    q = np.where(np.isnan(q), q.T, q)
    fig, ax = plt.subplots(figsize=(7.4, 6.4))
    im = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(rho[i, j]):
                ax.text(j, i, f"{rho[i, j]:.2f}{stars(q[i, j])}", ha="center", va="center", fontsize=7.5,
                        color="white" if abs(rho[i, j]) > 0.6 else "black")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(keys, rotation=45, ha="right")
    ax.set_yticklabels(keys)
    ax.grid(False)
    fig.colorbar(im, shrink=0.75, label="Spearman rho")
    ax.set_title("Construct correlations, organisation group\n(exploratory; * q<.05, ** q<.01, *** q<.001, BH-FDR)")
    out.figure(fig, "02_construct_correlations")
    return pd.DataFrame(rho, index=keys, columns=keys).join(pd.DataFrame(q, index=keys, columns=[f"q_{k}" for k in keys]))


def fig_group_means(ds: pd.DataFrame, out: Output) -> None:
    vars_ = [v for v in COMPARE_VARS]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    for i, (g, c, off) in enumerate(((GROUP_ORG, C_ORG, -0.15), (GROUP_SELF, C_SELF, 0.15))):
        sub = ds[ds["group"] == g]
        mu = np.array([sub[v].mean() for v in vars_])
        ns = np.array([sub[v].notna().sum() for v in vars_])
        se = np.array([sub[v].std(ddof=1) / math.sqrt(max(n, 1)) for v, n in zip(vars_, ns)])
        ci = stats.t.ppf(0.975, np.maximum(ns - 1, 1)) * se
        ax.errorbar(mu, np.arange(len(vars_)) + off, xerr=ci, fmt="o", color=c, capsize=3, label=f"{g} (n={int(ns.max())})")
    ax.set_yticks(range(len(vars_)))
    ax.set_yticklabels([LABELS[v] for v in vars_])
    ax.invert_yaxis()
    ax.set_xlabel("Mean score, 0-100 (95% CI)")
    ax.set_title("Organisation vs self-employed: outcomes measured in both blocks")
    ax.legend(frameon=False, loc="lower right")
    out.figure(fig, "03_group_comparison_means")


def fig_forest_equations(fits: dict, out: Output) -> None:
    variants = [(("brief_literal", "org_incl_hybrid", "complete-case"), "As briefed (literal)", C_GREY, -0.27),
                (("primary", "org_incl_hybrid", "complete-case"), "Primary, complete-case", C_ORG, -0.09),
                (("primary", "org_incl_hybrid", "multiple imputation"), "Primary, multiple imputation", "#38a169", 0.09),
                (("extended", "org_incl_hybrid", "complete-case"), "Extended items, complete-case", "#805ad5", 0.27)]
    for eq, title in (("Eq1_BO", "Eq.1  Burnout"), ("Eq2_JS", "Eq.2  Job satisfaction"), ("Eq3_RET", "Eq.3  Retention")):
        keys = STRUCTURAL[eq]
        fig, ax = plt.subplots(figsize=(7.2, 1.2 + 0.85 * len(keys)))
        for key, lab, col, off in variants:
            coef = fits[key][0]
            t = coef[(coef["equation"] == eq) & coef["key"].isin(keys)].set_index("key").reindex(keys)
            y = np.arange(len(keys)) + off
            ax.errorbar(t["std_beta"], y, xerr=[t["std_beta"] - t["ci_low"], t["ci_high"] - t["std_beta"]], fmt="o", ms=4,
                        color=col, capsize=2, label=lab)
        ax.axvline(0, c="k", lw=0.8)
        ax.set_yticks(range(len(keys)))
        ax.set_yticklabels([LABELS[k] for k in keys])
        ax.invert_yaxis()
        ax.set_xlabel("Standardised beta (95% CI; HC3-robust)")
        ax.set_title(f"{title} - organisation group")
        ax.legend(frameon=False, fontsize=7.5, loc="best")
        out.figure(fig, f"04_{eq}_coefficients")


def fig_missingness(uni: pd.DataFrame, out: Output) -> None:
    t = uni.sort_values("std_mean_diff_(obs-miss)")
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = np.where(t["q_fdr"] < 0.05, C_SELF, C_GREY)
    ax.scatter(t["std_mean_diff_(obs-miss)"], t["label"], c=colors, s=40)
    ax.axvline(0, c="k", lw=0.8)
    for x in (-0.2, 0.2):
        ax.axvline(x, ls=":", c="grey", lw=0.8)
    ax.set_xlabel("Standardised mean difference: JS answered minus JS skipped")
    ax.set_title("Who skipped the optional ProQOL block? (orange = q<.05)")
    out.figure(fig, "05_js_missingness_balance")


def fig_tipping(tp: pd.DataFrame, out: Output) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, key, title in zip(axes, ("JS", "BO"), ("JS -> Retention", "BO -> Retention")):
        t = tp[(tp["equation"] == "Eq3_RET") & (tp["key"] == key)]
        ax.plot(t["delta_imputed_JS"], t["std_beta"], "o-", color=C_ORG)
        ax.fill_between(t["delta_imputed_JS"], t["ci_low"], t["ci_high"], alpha=0.2, color=C_ORG)
        ax.axhline(0, c="k", lw=0.8)
        ax.set_title(title)
        ax.set_xlabel("Shift applied to imputed JS (0-100 points)")
    axes[0].set_ylabel("Pooled standardised beta (95% CI)")
    fig.suptitle("Tipping-point analysis: skipped-JS respondents differ from observed by delta", fontsize=10, fontweight="bold")
    out.figure(fig, "06_delta_tipping_point")


def fig_mediation(med_cc: pd.DataFrame, med_mi: pd.DataFrame, out: Output) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    for ax, kind, title in zip(axes, ("ind_BO", "ind_JS", "ind_total"), ("Indirect via burnout", "Indirect via job satisfaction", "Total indirect")):
        for med, col, off, lab in ((med_cc, C_ORG, -0.12, "complete-case (BCa)"), (med_mi, "#38a169", 0.12, "imputed (percentile)")):
            t = med[med["kind"] == kind].set_index("predictor").reindex(PREDICTORS)
            ax.errorbar(t["estimate"], np.arange(len(PREDICTORS)) + off, xerr=[t["estimate"] - t["ci_low"], t["ci_high"] - t["estimate"]],
                        fmt="o", ms=4, color=col, capsize=2, label=lab)
        ax.axvline(0, c="k", lw=0.8)
        ax.set_title(title)
        ax.set_xlabel("Effect on RET per 1 point of X")
    axes[0].set_yticks(range(len(PREDICTORS)))
    axes[0].set_yticklabels(PREDICTORS)
    axes[0].invert_yaxis()
    axes[0].legend(frameon=False, fontsize=7.5)
    fig.suptitle("Associational parallel mediation X -> {BO, JS} -> RET (unstandardised, 95% CI)", fontsize=10, fontweight="bold")
    out.figure(fig, "07_mediation_indirect_effects")


def fig_validation(det: pd.DataFrame, out: Output) -> None:
    fig, ax = plt.subplots(figsize=(5.8, 5.6))
    for pipe, col, mk in (("extended CC", "#805ad5", "o"), ("primary CC", C_ORG, "s")):
        t = det[det["pipeline"] == pipe]
        ax.scatter(t["beta_iqp"], t["beta_here"], c=col, marker=mk, s=38, label=pipe, alpha=0.85)
    bad = det[(det["pipeline"] == "extended CC") & (~det["same_sign"])]
    for _, r in bad.iterrows():
        ax.annotate(f"{r['equation'].split('_')[0]} {r['term']}: sign differs", (r["beta_iqp"], r["beta_here"]),
                    xytext=(8, -14), textcoords="offset points", fontsize=8, arrowprops={"arrowstyle": "-", "color": "k"})
    lim = [-0.7, 0.7]
    ax.plot(lim, lim, "k--", lw=0.8)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("Standardised beta printed in the IQP report")
    ax.set_ylabel("Standardised beta recomputed here")
    ax.set_title("Validation against the IQP report")
    ax.legend(frameon=False)
    out.figure(fig, "08_validation_vs_iqp_report")


def fig_gap_dumbbell(gap: pd.DataFrame, out: Output) -> None:
    t = gap.dropna(subset=["staff_provided_pct", "staff_wanted_pct"]).sort_values("staff_unmet_pct")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    y = np.arange(len(t))
    ax.hlines(y, t["staff_provided_pct"], t["staff_wanted_pct"], color="#cbd5e0", lw=3, zorder=1)
    ax.scatter(t["staff_provided_pct"], y, s=55, color=C_ORG, label="Provided (staff say it exists)", zorder=2)
    ax.scatter(t["staff_wanted_pct"], y, s=55, color=C_SELF, label="Wanted (top-3 pick)", zorder=2)
    for yi, (_, r) in zip(y, t.iterrows()):
        ax.text(max(r["staff_provided_pct"], r["staff_wanted_pct"]) + 2.5, yi, f"unmet {r['staff_unmet_pct']:.0f}%", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(t["item"])
    ax.set_xlim(0, 80)
    ax.set_xlabel(f"% of staff respondents (n={int(t['staff_provided_n'].max())})")
    ax.set_title("Provision vs need, staff view\n'unmet' = wants it AND their organisation lacks it")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8)
    out.figure(fig, "09_gap_staff_provided_vs_wanted")


def fig_gap_four_way(gap: pd.DataFrame, out: Output) -> None:
    t = gap.sort_values("staff_unmet_pct")
    fig, ax = plt.subplots(figsize=(9, 5.6))
    y = np.arange(len(t))
    h = 0.2
    series = [("staff_provided_pct", "Staff: provided", C_ORG, 1.5), ("dm_provided_pct", "Decision-makers: provided", "#90cdf4", 0.5),
              ("staff_wanted_pct", "Staff: wanted", C_SELF, -0.5), ("dm_wanted_pct", "Decision-makers: wanted", "#fbd38d", -1.5)]
    for col, lab, c, k in series:
        ax.barh(y + k * h, t[col].fillna(0), h, color=c, label=lab)
        for yi, v in zip(y, t[col]):
            if pd.isna(v):
                ax.text(0.8, yi + k * h, "not asked", va="center", fontsize=6, color="#666")
    ax.set_yticks(y)
    ax.set_yticklabels(t["item"])
    ax.set_xlabel("% of respondents in branch (staff n=241, decision-makers n=28)")
    ax.set_title("Provided vs wanted: staff and decision-makers")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=4)
    out.figure(fig, "10_gap_four_way")


def fig_barriers(b: pd.DataFrame, out: Output) -> None:
    t = b.copy()
    t["m"] = t[["staff_pct", "dm_pct"]].max(axis=1)
    t = t.sort_values("m")
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(t))
    ax.barh(y + 0.2, t["staff_pct"].fillna(0), 0.38, color=C_ORG, label="Staff (why no system exists)")
    ax.barh(y - 0.2, t["dm_pct"].fillna(0), 0.38, color=C_SELF, label="Decision-makers (what constrains adoption)")
    ax.set_yticks(y)
    ax.set_yticklabels(t["barrier"], fontsize=7.5)
    ax.set_xlabel("% of respondents in branch (option not offered to the other branch shows 0)")
    ax.set_title("Barriers: staff vs decision-makers (only budget and capacity are like-for-like)")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    out.figure(fig, "11_barriers_staff_vs_decision_makers")


def fig_challenges(ch: pd.DataFrame, out: Output) -> None:
    t = ch.sort_values("named_any_rank_pct")
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.barh(t["challenge"], t["named_any_rank_pct"], color=C_SELF, xerr=[t["named_any_rank_pct"] - t["ci_low"], t["ci_high"] - t["named_any_rank_pct"]], capsize=2)
    ax.set_xlabel(f"% of self-employed respondents naming it in their top 3 (n={int(t['n_respondents'].iloc[0])}; 95% Wilson CI)")
    ax.set_title("Self-employed: top challenges")
    out.figure(fig, "12_self_employed_challenges")


# =============================================================================================== #
# 15b. DONOR PACK: plain-language charts (one message per chart, no statistics jargon)
# =============================================================================================== #
# Design rules, chosen after donors found the technical figures hard to read:
#   * the TITLE states the finding in a sentence, computed from the data (so it can never contradict the chart);
#   * values are written on the bars; no betas, CIs, q-values, VIFs or axes that need explaining;
#   * at most two or three colours, large type, a one-line "how to read" under the title, and an honest footnote;
#   * wording says "goes together with", never "causes".
D_TEAL, D_ORANGE, D_RED, D_AMBER, D_GREEN, D_GREY = "#2c7a7b", "#dd6b20", "#c53030", "#d69e2e", "#38a169", "#a0aec0"


def _donor_axes(figsize=(9, 5.2), left: float = 0.05, bottom: float = 0.18):
    """Axes with no clutter.  `left` reserves room for long category labels so the title can align with the figure edge."""
    fig, ax = plt.subplots(figsize=figsize)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.grid(False)
    ax.tick_params(axis="both", labelsize=12, length=0)
    fig.subplots_adjust(left=left, right=0.97, bottom=bottom)
    return fig, ax


def _donor_title(fig, ax, title: str, how: str, foot: str) -> None:
    """Finding-as-title, a one-line 'how to read', and an honest footnote, laid out in figure coordinates so they never overlap."""
    import textwrap
    h = fig.get_figheight()
    lines = textwrap.wrap(title, 58)
    fig.text(0.01, 0.995, "\n".join(lines), fontsize=16, fontweight="bold", ha="left", va="top", linespacing=1.15)
    y_how = 0.995 - len(lines) * 16 * 1.3 / 72 / h - 0.012
    how_lines = textwrap.wrap(how, 100)
    fig.text(0.01, y_how, "\n".join(how_lines), fontsize=11, color="#4a5568", ha="left", va="top")
    y_top = y_how - len(how_lines) * 11 * 1.4 / 72 / h - 0.045
    fig.subplots_adjust(top=y_top)
    fig.text(0.01, 0.005, "\n".join(textwrap.wrap(foot, 120)), fontsize=8.5, color="#718096", ha="left", va="bottom")


def _foot(n_text: str) -> str:
    return (f"Source: 2026 Taiwan Helpers' Needs Survey ({n_text}). Volunteer sample, so results describe these respondents, "
            "not all helpers. Shows what goes together, not what causes what.")


def donor_figures(ds: pd.DataFrame, tabs: dict, out: Output) -> list[str]:
    """Write the donor pack to figures/donor/ and return the key-message sentences (also saved as donor_key_messages.md)."""
    msgs: list[str] = []
    org, selfe = ds[ds["group"] == GROUP_ORG], ds[ds["group"] == GROUP_SELF]

    # 1. burnout levels ------------------------------------------------------------------------------------------------
    def levels(g):
        c = pd.cut(g["BO"].dropna(), BURNOUT_BINS, labels=BURNOUT_LABELS)
        return (c.value_counts(normalize=True).reindex(BURNOUT_LABELS) * 100).values, int(c.notna().sum())
    lo_o, n_o = levels(org)
    lo_s, n_s = levels(selfe)
    fig, ax = _donor_axes((9, 4.4), left=0.24, bottom=0.34)
    for yi, vals in enumerate((lo_s, lo_o)):
        left = 0
        for v, c in zip(vals, (D_GREEN, D_AMBER, D_RED)):
            ax.barh(yi, v, left=left, color=c, height=0.55)
            if v >= 6:
                ax.text(left + v / 2, yi, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=13, fontweight="bold")
            left += v
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Self-employed\n(n=%d)" % n_s, "Working in an\norganisation (n=%d)" % n_o])
    ax.set_xticks([])
    ax.set_xlim(0, 100)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in (D_GREEN, D_AMBER, D_RED)], labels=["Low", "Moderate", "High"],
              ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.02), fontsize=11)
    mod_hi = 100 - lo_o[0]
    _donor_title(fig, ax, f"{mod_hi:.0f}% of helpers working in organisations report moderate or high burnout",
                 "Each bar = 100% of respondents in that group, split by burnout level (from a 13-question scale).", _foot(f"n={n_o + n_s}"))
    out.figure(fig, "donor/D1_burnout_levels")
    msgs.append(f"{mod_hi:.0f}% of organisation-based helpers report moderate or high burnout (self-employed: {100 - lo_s[0]:.0f}%).")

    # 2. burnout and thinking of leaving -------------------------------------------------------------------------------
    t = org.dropna(subset=["BO", "consider_leaving"]).copy()
    t["band"] = pd.cut(t["BO"], BURNOUT_BINS, labels=BURNOUT_LABELS)
    g = t.groupby("band", observed=True)["consider_leaving"].agg(lambda s: (s >= 2).mean() * 100)
    ns = t.groupby("band", observed=True).size()
    fig, ax = _donor_axes((8, 4.8))
    bars = ax.bar(range(3), g.values, color=(D_GREEN, D_AMBER, D_RED), width=0.6)
    for i, (v, n) in enumerate(zip(g.values, ns.values)):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=15, fontweight="bold")
        ax.text(i, -6, f"n={n}", ha="center", fontsize=10, color="#718096")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Low burnout", "Moderate burnout", "High burnout"])
    ax.set_yticks([])
    ax.set_ylim(-9, max(g.values) * 1.2)
    _donor_title(fig, ax, f"Helpers with high burnout are far more likely to be thinking of leaving ({g.iloc[-1]:.0f}% vs {g.iloc[0]:.0f}%)",
                 "% who seriously considered leaving their organisation at least once a month in the past 6 months.", _foot(f"organisation-based, n={int(ns.sum())}"))
    out.figure(fig, "donor/D2_burnout_and_leaving")
    msgs.append(f"{g.iloc[-1]:.0f}% of highly burned-out helpers seriously consider leaving at least monthly, versus {g.iloc[0]:.0f}% of those with low burnout.")

    # 3. what goes together with burnout ----------------------------------------------------------------------------------
    cc = tabs["primary_cc_coefficients"]
    e1 = cc[(cc["equation"] == "Eq1_BO") & cc["primary_family"]].set_index("key")
    plain = {"WL": "Heavier workload", "OS": "More support from the organisation", "JR": "More job resources (autonomy, growth, clarity)",
             "PAY": "Better pay and conditions", "MA": "Better fit with the organisation's mission", "ID": "More energy and enthusiasm for the work"}
    short = {"WL": "a heavy workload", "OS": "good organisational support", "JR": "good job resources", "PAY": "good pay and conditions",
             "MA": "a good mission fit", "ID": "enthusiasm for the work"}
    e1 = e1.reindex(sorted(PREDICTORS, key=lambda k: abs(e1.loc[k, "std_beta"])))
    fig, ax = _donor_axes((10, 5), left=0.40)
    sig_up, sig_dn = [], []
    for i, (k, r) in enumerate(e1.iterrows()):
        sig = r["q_fdr_primary"] < 0.05
        col = (D_RED if r["std_beta"] > 0 else D_GREEN) if sig else D_GREY
        ax.barh(i, r["std_beta"], color=col, height=0.6)
        if not sig:
            ax.text(r["std_beta"] + (0.01 if r["std_beta"] >= 0 else -0.01), i, "no clear link", va="center",
                    ha="left" if r["std_beta"] >= 0 else "right", fontsize=10, color="#718096")
        if sig:
            (sig_up if r["std_beta"] > 0 else sig_dn).append(short[k])
    ax.axvline(0, color="#2d3748", lw=1)
    ax.set_yticks(range(len(e1)))
    ax.set_yticklabels([plain[k] for k in e1.index])
    ax.set_xticks([])
    lim = max(abs(e1["std_beta"])) * 1.25
    ax.set_xlim(-lim, lim)
    ax.text(-lim * 0.98, len(e1) - 0.35, "goes with LESS burnout", color=D_GREEN, fontsize=12, fontweight="bold", va="bottom")
    ax.text(lim * 0.98, len(e1) - 0.35, "goes with MORE burnout", color=D_RED, fontsize=12, fontweight="bold", va="bottom", ha="right")
    _j = lambda xs: " and ".join([", ".join(xs[:-1]), xs[-1]] if len(xs) > 1 else xs)
    head = "; ".join([f"{_j(sig_up)} goes with more burnout" if sig_up else "", f"{_j(sig_dn)} go with less" if sig_dn else ""]).strip("; ")
    _donor_title(fig, ax, head[0].upper() + head[1:] if head else "No factor stands out clearly",
                 "Longer bar = stronger link. Grey = no clear link once the other factors are taken into account.", _foot(f"organisation-based, n={int(e1['n'].iloc[0])}"))
    ax.set_ylim(-0.6, len(e1) + 0.3)
    out.figure(fig, "donor/D3_what_goes_with_burnout")
    msgs.append((head[0].upper() + head[1:] if head else "No single factor stands out") + ".")

    # 4. unmet needs ---------------------------------------------------------------------------------------------------------
    gap = tabs["support_gap"].dropna(subset=["staff_unmet_pct"]).sort_values("staff_unmet_pct")
    fig, ax = _donor_axes((10, 5), left=0.34)
    ax.barh(gap["item"], gap["staff_unmet_pct"], color=D_ORANGE, height=0.62)
    for i, v in enumerate(gap["staff_unmet_pct"]):
        ax.text(v + 0.6, i, f"{v:.0f}%", va="center", fontsize=13, fontweight="bold")
    ax.set_xticks([])
    ax.set_xlim(0, gap["staff_unmet_pct"].max() * 1.18)
    top = gap.iloc[::-1]["item"].tolist()
    _donor_title(fig, ax, f"{top[0]} and {top[1].lower()} are the most common support gaps",
                 "% of staff who chose this as a top-3 wish AND say their organisation does not offer it.", _foot(f"staff n={int(gap['staff_provided_n'].max())}"))
    out.figure(fig, "donor/D4_unmet_needs")
    msgs.append(f"Largest support gaps (staff want it, organisation lacks it): {top[0]} ({gap.iloc[-1]['staff_unmet_pct']:.0f}%) and {top[1]} ({gap.iloc[-2]['staff_unmet_pct']:.0f}%).")

    # 5. staff vs leaders: what exists -----------------------------------------------------------------------------------------
    gp = tabs["support_gap"].dropna(subset=["staff_provided_pct", "dm_provided_pct"]).copy()
    gp["diff"] = gp["dm_provided_pct"] - gp["staff_provided_pct"]
    gp = gp.sort_values("diff")
    fig, ax = _donor_axes((10, 5.8), left=0.34, bottom=0.26)
    y = np.arange(len(gp))
    ax.barh(y + 0.19, gp["staff_provided_pct"], 0.36, color=D_TEAL, label="Staff say it exists")
    ax.barh(y - 0.19, gp["dm_provided_pct"], 0.36, color=D_ORANGE, label="Leaders say it exists")
    for yi, a, b in zip(y, gp["staff_provided_pct"], gp["dm_provided_pct"]):
        ax.text(a + 1, yi + 0.19, f"{a:.0f}%", va="center", fontsize=10)
        ax.text(b + 1, yi - 0.19, f"{b:.0f}%", va="center", fontsize=10)
    ax.set_yticks(y)
    ax.set_yticklabels(gp["item"])
    ax.set_xticks([])
    ax.set_xlim(0, 80)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, fontsize=11)
    n_big = int((gp["diff"].abs() >= 10).sum())
    _donor_title(fig, ax, f"Staff and leaders disagree on what support exists ({n_big} of {len(gp)} differ by 10+ points)",
                 "% of respondents saying their organisation currently offers each support.",
                 _foot(f"staff n={int(gp['staff_provided_n'].max())}, leaders n={int(gp['dm_provided_n'].max())}") + " Only 28 leaders answered: treat as a signal.")
    out.figure(fig, "donor/D5_staff_vs_leaders_what_exists")
    msgs.append(f"Staff and leaders differ by 10+ points on {n_big} of {len(gp)} supports (only 28 leaders answered).")

    # 6. attitude of decision-makers --------------------------------------------------------------------------------------------
    at = tabs["decision_maker_attitude"].set_index("answer")
    groups = {"Enthusiastic": ["Enthusiastic"], "Interested, but worried\nabout cost or workload": ["Interested but worried about cost / workload"],
              "Might see it as unnecessary\nor not the right time": ["May think it unnecessary", "Not the right time"],
              "Not sure / the respondent\nis the decision-maker": ["Not sure", "I am the decision-maker"]}
    cols_ = ("Staff_pct", "Decision-maker_pct")
    mat = np.array([[at.reindex(v)[c].fillna(0).sum() for c in cols_] for v in groups.values()])
    fig, ax = _donor_axes((10, 4.8), left=0.22, bottom=0.40)
    colors_ = (D_GREEN, D_AMBER, D_RED, D_GREY)
    for yi, ci in enumerate((0, 1)):
        left = 0
        for v, c in zip(mat[:, ci], colors_):
            ax.barh(yi, v, left=left, color=c, height=0.55)
            if v >= 5:
                ax.text(left + v / 2, yi, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
            left += v
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["What STAFF expect\nleaders will think", "What LEADERS\nsay themselves"])
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.set_xlim(0, 100)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in colors_], labels=list(groups), ncol=2, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.02), fontsize=9.5)
    _donor_title(fig, ax, f"Only {mat[0, 0]:.0f}% of staff expect their leaders to be enthusiastic; {mat[0, 1]:.0f}% of leaders say they are",
                 "Attitude toward introducing a free staff-support programme.", _foot("staff n=148, leaders n=22") + " Leaders: small group.")
    out.figure(fig, "donor/D6_leader_attitude")
    msgs.append(f"{mat[0, 0]:.0f}% of staff expect leaders to be enthusiastic about a support programme; {mat[0, 1]:.0f}% of leaders say they are. "
                f"{mat[2, 0]:.0f}% of staff expect leaders to see it as unnecessary or ill-timed, versus {mat[2, 1]:.0f}% of leaders.")

    # 7. seniority gradient -----------------------------------------------------------------------------------------------------
    roles = ["Frontline helper", "Admin / project / finance", "Mid-level manager", "Founder / decision-maker"]
    nice = ["Frontline\nstaff", "Admin / project\n/ finance", "Mid-level\nmanagers", "Founders /\nexecutives"]
    rr = [(r, nm) for r, nm in zip(roles, nice) if (org["role"] == r).sum() >= MIN_GROUP_N]
    jr = [org.loc[org["role"] == r, "JR"].mean() for r, _ in rr]
    bo = [org.loc[org["role"] == r, "BO"].mean() for r, _ in rr]
    fig, ax = _donor_axes((9.5, 5))
    x = np.arange(len(rr))
    ax.bar(x - 0.19, jr, 0.36, color=D_TEAL, label="Job resources (higher = more)")
    ax.bar(x + 0.19, bo, 0.36, color=D_RED, label="Burnout (higher = worse)")
    for xi, a, b in zip(x, jr, bo):
        ax.text(xi - 0.19, a + 1.5, f"{a:.0f}", ha="center", fontsize=12, fontweight="bold")
        ax.text(xi + 0.19, b + 1.5, f"{b:.0f}", ha="center", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([nm for _, nm in rr])
    ax.set_yticks([])
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=11, bbox_to_anchor=(0, 1.0))
    jr_min, bo_max = rr[int(np.argmin(jr))][0], rr[int(np.argmax(bo))][0]
    head = ("Frontline staff have the fewest job resources and the highest burnout" if jr_min == bo_max == "Frontline helper"
            else "Job resources and burnout differ by seniority")
    _donor_title(fig, ax, head, "Average scores (0-100) by role. Resources = clear expectations, control over work, skill growth, career talks.",
                 _foot(f"organisation-based, n={len(org)}"))
    out.figure(fig, "donor/D7_resources_and_burnout_by_role")
    msgs.append(f"{head}: job resources {jr[0]:.0f}/100 and burnout {bo[0]:.0f}/100 for frontline staff.")

    # 8. self-employed vs organisation -------------------------------------------------------------------------------------------
    vars_ = [("BO", "Burnout\n(lower is better)"), ("ID", "Energy and enthusiasm\nfor work (higher is better)"),
             ("JS", "Satisfaction with\nhelping work (higher is better)")]
    fig, ax = _donor_axes((9.5, 4.8))
    x = np.arange(len(vars_))
    mo = [org[v].mean() for v, _ in vars_]
    ms = [selfe[v].mean() for v, _ in vars_]
    ax.bar(x - 0.19, mo, 0.36, color=D_TEAL, label=f"Working in an organisation")
    ax.bar(x + 0.19, ms, 0.36, color=D_ORANGE, label="Self-employed")
    for xi, a, b in zip(x, mo, ms):
        ax.text(xi - 0.19, a + 1.5, f"{a:.0f}", ha="center", fontsize=13, fontweight="bold")
        ax.text(xi + 0.19, b + 1.5, f"{b:.0f}", ha="center", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([l for _, l in vars_])
    ax.set_yticks([])
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=11, bbox_to_anchor=(0, 1.0))
    _donor_title(fig, ax, "Self-employed helpers report less burnout and more enthusiasm for their work",
                 "Average score out of 100.", _foot(f"organisation n={len(org)}, self-employed n={len(selfe)}"))
    out.figure(fig, "donor/D8_self_employed_vs_organisation")
    msgs.append(f"Self-employed helpers average {ms[0]:.0f}/100 on burnout versus {mo[0]:.0f} in organisations, and {ms[1]:.0f} versus {mo[1]:.0f} on enthusiasm for work.")

    # 9. self-employed challenges ---------------------------------------------------------------------------------------------------
    ch = tabs["selfemployed_challenges"]
    ch = ch[ch["challenge"] != "Other"].sort_values("named_any_rank_pct").tail(5)
    fig, ax = _donor_axes((10, 4.2), left=0.42)
    ax.barh(ch["challenge"], ch["named_any_rank_pct"], color=D_ORANGE, height=0.6)
    for i, v in enumerate(ch["named_any_rank_pct"]):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=13, fontweight="bold")
    ax.set_xticks([])
    ax.set_xlim(0, 85)
    top = ch.iloc[-1]
    _donor_title(fig, ax, f"{top['challenge']} is the top challenge for self-employed helpers ({top['named_any_rank_pct']:.0f}%)",
                 "% of self-employed respondents who named it among their three biggest challenges.", _foot(f"self-employed n={int(top['n_respondents'])}"))
    out.figure(fig, "donor/D9_self_employed_challenges")
    msgs.append(f"{top['challenge']} is named by {top['named_any_rank_pct']:.0f}% of self-employed helpers among their top three challenges.")

    md = ["# Key messages for donors (auto-generated from the data)\n",
          *[f"{i}. {m}" for i, m in enumerate(msgs, 1)],
          "\n*All figures: volunteer sample; they describe the people who answered and show what goes together, not what causes what.*"]
    (out.root / "donor_key_messages.md").write_text("\n".join(md), encoding="utf-8")
    return msgs


# =============================================================================================== #
# 16. ASSUMPTIONS REGISTER  (written to the report so every assumption can be critiqued)
# =============================================================================================== #
ASSUMPTIONS = [
    ("A1", "Questionnaire layout is stable", "all", "Every positional column is verified against header text; a mismatch aborts the run (LayoutError)."),
    ("A2", "Direction of every item is correct after reverse-coding", "scoring",
     "coding_audit.csv flags negative item-rest correlations. This found cols 12 and 29-31 mis-directed in the brief; 'primary' repairs ONLY these."),
    ("A3", "'Not applicable', 'no agreement on hours' and 'irregular hours' are missing, not low/mid values", "scoring",
     "Declared in NOT_APPLICABLE; not recoded to a number. Affects cols 7, 8 and the N/A answers on demand/resource items."),
    ("A4", "Ordinal items are equal-interval after POMP rescaling to 0-100 and averaged", "all composites",
     "Not testable from these data. Exploratory associations use Spearman; ordinal CFA (WLSMV) is the recommended confirmation (outside this script)."),
    ("A5", "Items in a composite are essentially unidimensional / tau-equivalent", "reliability",
     "Alpha AND omega-total reported on PEARSON correlations of 3-7-point ordinal (and binary) items, which biases loadings and omega DOWNWARD "
     "relative to polychoric/tetrachoric estimates. The 13-item burnout composite mixes personal and work-related burnout; Eq.1w/1p/3w/3p re-fit the equations with each sub-scale."),
    ("A6", "Item non-response inside a composite is MAR given the other items", "row_mean",
     "Composite defined if >= 50% of items answered (100% for PAY, MA, ID, JS). Missingness inside composites is tiny (<= 3 respondents per item)."),
    ("A7", "Single-item PAY and MA carry no measurement error", "Eq.1-3",
     "UNTESTABLE with one item; slopes for PAY and MA are probably attenuated toward zero. Treat their null results as inconclusive."),
    ("A8", "Linear, additive conditional means; no interactions", "OLS",
     "Ramsey RESET reported per model. Demand x resource buffering is NOT tested because the brief's equations contain no interaction terms."),
    ("A9", "Observations are independent", "OLS, bootstrap",
     "VIOLATION POSSIBLE: no organisation identifier exists, so clustering by employer cannot be modelled. County-clustered SEs are a weak "
     "sensitivity (cluster_summary.csv: ~20 counties but only ~4.5 EFFECTIVE clusters, Taipei/New Taipei dominate; CR1 is anti-conservative). HC3 does NOT correct clustering."),
    ("A10", "Heteroskedasticity is allowed; mean model is correctly specified", "HC3",
     "Koenker-BP reported; HC3 used (preferred for n < 250). Cook's D counts reported; no observation was deleted."),
    ("A11", "Collinearity is not severe", "OLS", "VIF and condition number reported per model (rule of thumb: VIF > 5 would be flagged)."),
    ("A12", "Mission = 8 overlapping multi-select dummies (each vs 'not selected'); SIZE is linear on its 0-5 order", "controls",
     "Joint Wald test of the dummy block per equation; the dummies are NOT mutually exclusive categories. Free-text 'other' mission answers are ignored."),
    ("A13", "Skipping the optional ProQOL block is MAR given observed covariates (incl. role)", "multiple imputation",
     "UNTESTABLE (MAR vs MNAR). missingness model shows skipping is strongly predictable (role); tipping-point analysis shows how large an "
     "MNAR shift in JS would be needed to change conclusions. Complete-case answers a different estimand (respondents who answered)."),
    ("A14", "The imputation model is adequate", "MI",
     "Bayesian-ridge chained equations on composites, m imputations, posterior sampling, bounds enforced, auxiliary variables (incl. org-type, role) "
     "included; binary auxiliaries are rounded to 0/1. No predictive-mean matching. Composites, not items, are imputed: because the whole ProQOL block "
     "is skipped together, the other ProQOL items carry no extra information for JS, so item-level MI would add little here. "
     "MI pools RAW coefficients; standardised betas are derived from pooled raw estimates and averaged SDs."),
    ("A15", "Mediation: temporal order X -> M -> Y, and no unmeasured X-M, M-Y, X-Y confounding", "mediation",
     "CROSS-SECTIONAL: order is assumed, never observed. Results are structural ASSOCIATIONS. Confounding sensitivity: Cinelli-Hazlett robustness values "
     "(column RV) for each regression slope; no formal mediation-specific sensitivity (e.g. medsens) is computed."),
    ("A16", "Rows are exchangeable under the bootstrap", "BCa / percentile CI", "Same independence caveat as A9."),
    ("A17", "BH-FDR is valid under independence / positive dependence", "multiplicity",
     "Primary family = 14 structural slopes. Everything else is exploratory with its own FDR family and must be reported as such."),
    ("A18", "Self-reported perceptions of what exists ('as far as you know') approximate what exists", "support gap",
     "Staff may be unaware of existing supports. Decision-maker answers are the better record of supply but n = 28."),
    ("A19", "'Wanted' = chosen among <= 3 picks; not choosing an item does not mean not wanting it", "support gap",
     "'Wanted' is a LOWER BOUND on need; 'provided but not selected' is not evidence of surplus."),
    ("A20", "Supply and demand option lists correspond item-for-item", "support gap",
     "Not exactly: career (system vs discussion) is approximate; flexible work has no demand option; financial planning has no supply option; "
     "allowance is not asked of decision-makers. Gaps are computed only where both sides were asked."),
    ("A21", "Staff and decision-maker samples can be compared as independent groups", "support gap",
     "They are different people in different (unidentified) organisations; no matched-pair analysis is possible."),
    ("A22", "Hybrid respondents (org + personal projects, n = 32) answered the organisational items about their organisational work", "grouping",
     "Pooled with organisation respondents; every model is re-run excluding them (sample = org_excl_hybrid)."),
    ("A23", "Self-employed respondents answered only ID, BO, JS (+ProQOL); WL, OS, JR, PAY, MA, RET, SIZE, MISSION do not exist for them", "group split",
     "The three JD-R structural equations are therefore NOT identified for the self-employed; only the reduced model (ID, BO, JS) can be compared."),
    ("A24", "The sample is non-probability, self-selected (~5% response per the IQP report) and all measures are self-reported", "inference",
     "No population inference, no weights. Common-method variance probably inflates correlations. Descriptive levels are NOT prevalence estimates."),
]


# =============================================================================================== #
# 17. REPORT
# =============================================================================================== #
def _fmt(df: pd.DataFrame, cols: dict[str, str], nd: int = 3) -> pd.DataFrame:
    out = df[list(cols)].rename(columns=cols).copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else (f"{v:.{nd}f}" if abs(v) >= 0.001 or v == 0 else f"{v:.1e}"))
    return out


def _beta_table(cc: pd.DataFrame, mi: pd.DataFrame, eq: str) -> str:
    a = cc[(cc["equation"] == eq)].copy()
    b = mi[(mi["equation"] == eq)].set_index("key")
    a["MI beta"] = a["key"].map(b["std_beta"])
    a["MI p"] = a["key"].map(b["p"])
    a["MI q"] = a["key"].map(b["q_fdr_primary"])
    a["RV %"] = a["robustness_value"] * 100
    a["CI"] = a.apply(lambda r: f"[{r['ci_low']:.2f}, {r['ci_high']:.2f}]", axis=1)
    a["family"] = np.where(a["primary_family"], "primary", "control")
    a["q (primary FDR)"] = a["q_fdr_primary"]
    return md_table(_fmt(a, {"predictor": "Predictor", "std_beta": "Std beta (CC)", "CI": "95% CI", "p": "p", "q (primary FDR)": "q",
                             "MI beta": "Std beta (MI)", "MI p": "p (MI)", "MI q": "q (MI)", "RV %": "Robustness value %", "VIF": "VIF", "family": "Family"}, 3))


def _sensitivity_table(cc: pd.DataFrame) -> str:
    def g(eq: str, key: str) -> str:
        r = cc[(cc["equation"] == eq) & (cc["key"] == key)]
        return f"{r['std_beta'].iloc[0]:.2f} (p={r['p'].iloc[0]:.3f})" if len(r) else ""
    rows = []
    for key in ("WL", "OS", "JR"):
        rows.append((f"Burnout <- {key}", "primary", g("Eq1_BO", key), "without ID", g("Eq1x_BO_noID", key)))
    for key in ("WL", "OS", "JR"):
        rows.append((f"Job satisfaction <- {key}", "primary", g("Eq2_JS", key), "without ID", g("Eq2x_JS_noID", key)))
    for key in ("WL", "OS", "ID"):
        rows.append((f"Burnout <- {key}", "all 13 items", g("Eq1_BO", key), "work-related only / personal only",
                     f"{g('Eq1w_workBO', key)} / {g('Eq1p_personalBO', key)}"))
    rows.append(("Retention <- burnout", "all 13 items", g("Eq3_RET", "BO"), "work-related / personal",
                 f"{g('Eq3w_RET_workBO', 'work_bo')} / {g('Eq3p_RET_personalBO', 'personal_bo')}"))
    return md_table(pd.DataFrame(rows, columns=["Path (std beta)", "Reference", "Reference result", "Variant", "Variant result"]))


def write_report(ctx: dict, out: Output, args: argparse.Namespace) -> None:
    T = out.tables
    cc, summ = T["primary_cc_coefficients"], T["primary_cc_model_summary"]
    mi = T["primary_mi_coefficients"]
    L: list[str] = []
    A = L.append
    A(f"# Taiwan Helpers' Needs Survey 2026 - JD-R analysis report (pipeline v{__version__})\n")
    A("*Auto-generated. Numbers come from `tables/*.csv`; interpretation is deliberately limited to what the estimators can support. "
      "All associations are cross-sectional and from a self-selected, non-probability sample.*\n")
    n = ctx["n"]
    A("## 1. Samples\n")
    A(f"- Responses: **{n['raw']}**; organisation-based **{n['org']}** (of whom **{n['hybrid']}** hybrid: organisation + personal projects); self-employed **{n['self']}**.")
    A(f"- JS (optional ProQOL block) observed for **{n['js_org']}** organisation and **{n['js_self']}** self-employed respondents.")
    A(f"- Support-gap branches: staff **{n['staff']}**, decision-makers (founders/board/HR) **{n['dm']}**.\n")
    A("## 2. Measurement and coding audit\n")
    rel = T["reliability"]
    r = rel[(rel["group"] == GROUP_ORG) & rel["construct"].isin(["OS", "RET", "WL"])].pivot(index="construct", columns="spec", values="alpha")
    A("Cronbach's alpha, organisation group (full table with omega and CIs: `reliability.csv`):\n")
    A(md_table(r.reset_index().round(2)))
    A("\nItems flagged by the automatic direction audit (`coding_audit.csv`):\n")
    fl = T["coding_audit"]
    fl = fl[(fl["flag"].str.startswith("CHECK")) & (fl["spec"] != "extended")]
    A(md_table(fl[["spec", "construct", "item", "column_0based", "item_rest_rho"]].round(2)) if len(fl) else "_none_")
    A("\n`primary` repairs only these direction errors (cols 12, 29, 30, 31). Item membership stays as in the brief. `extended` also moves col 11 into WL "
      "and drops col 7; it is a sensitivity analysis.\n")
    A("## 3. Simplified JD-R equations - organisation group (primary specification)\n")
    A("Standardised betas, HC3-robust 95% CI. 'CC' = complete case; 'MI' = multiple imputation pooled by Rubin's rules. "
      "q = BH-FDR over the **14 primary slopes** (6 + 6 + 2); controls are outside the family.\n")
    for eq, ttl in (("Eq1_BO", "Eq.1 Burnout"), ("Eq2_JS", "Eq.2 Job satisfaction"), ("Eq3_RET", "Eq.3 Retention")):
        s = summ[summ["equation"] == eq].iloc[0]
        A(f"### {ttl}  (n = {int(s['n'])}, R2 = {s['r2']:.3f}, adj. R2 = {s['adj_r2']:.3f}, max VIF = {s['max_VIF']:.2f}, "
          f"BP p = {s['BP_heterosk_p']:.3f}, RESET p = {s['RESET_p']:.3f}, mission-block p = {s['mission_block_p']:.3f})\n")
        A(_beta_table(cc, mi, eq) + "\n")
    s3b = summ[summ["equation"] == "Eq3b_RET"].iloc[0]
    A(f"**Eq.3b** (Eq.3 + all six predictors; n = {int(s3b['n'])}, R2 = {s3b['r2']:.3f}) is a *sensitivity* check on direct effects only. "
      "Adding correlated predictors beside BO and JS can change signs (suppression); individual Eq.3b coefficients must not be read causally. "
      f"On the same {ctx['dr2']['n']} rows, Eq.3 R2 = {ctx['dr2']['r2_eq3']:.3f} and Eq.3b R2 = {ctx['dr2']['r2_eq3b']:.3f} (increment = {ctx['dr2']['delta']:.3f}).\n")
    A("### 3b. Sensitivity of the equations (complete-case, primary specification)\n")
    A("Engagement (ID) and compassion satisfaction (JS) are both affective scales from the same questionnaire, so ID may absorb variance and flip "
      "signs (organisational support correlates POSITIVELY with JS on its own but negatively once ID and JR are controlled). The table shows each path with "
      "and without ID, and with burnout split into its work-related and personal sub-scales.\n")
    A(_sensitivity_table(cc) + "\n")
    A("**Robustness value (RV)** in the tables above: the share of residual variance an unmeasured confounder would have to explain in BOTH the predictor "
      "and the outcome to reduce that coefficient to zero (Cinelli & Hazlett 2020). Higher = harder to explain away; values near 0 are fragile.\n")
    bt = T["buffering_tests_exploratory"]
    A("**Exploratory demand x resource buffering** (workload x support, workload x resources; FDR over 4 tests):\n")
    A(md_table(_fmt(bt, {"outcome": "Outcome", "interaction": "Interaction", "std_beta": "Std beta", "p": "p", "q_fdr": "q", "n": "n"}, 3)) + "\n")
    A("## 4. Missing job-satisfaction block\n")
    lg = T["missingness_logit"]
    A(f"- Logistic model of 'JS skipped': AUC = **{lg['model_auc'].iloc[0]:.2f}**, McFadden R2 = {lg['model_mcfadden_r2'].iloc[0]:.2f}, "
      f"LR p = {lg['model_lr_p'].iloc[0]:.1e}, events = {int(lg['events_missing'].iloc[0])}.")
    top = lg[lg["covariate"] != "(intercept)"].assign(a=lambda x: x["log_odds_per_SD"].abs()).sort_values("a", ascending=False).head(3)
    A("- Strongest predictors (odds ratio per SD): " + "; ".join(f"{LABELS.get(c, c)} OR={o:.2f}" for c, o in zip(top["covariate"], top["odds_ratio"])) + ".")
    role_driven = top["covariate"].iloc[0] in ("frontline", "manager")
    A("- Skipping is therefore **not MCAR**" + (" and is mainly explained by observed role (client-facing staff answered far more often; the block asks about "
      "traumatised clients, which may not apply to admin/management roles), so JS is partly 'not applicable' rather than withheld" if role_driven else "") +
      ". Predictability supports MAR-given-covariates for the imputation, but MAR vs MNAR is untestable; the tipping-point table "
      "(`tipping_point.csv`, Figure 06) shifts imputed JS by -15 ... +15 points. Complete-case and MI answer different estimands "
      "(respondents who answered vs all organisation staff).")
    tp = T["tipping_point"]
    t3 = tp[(tp["equation"] == "Eq3_RET") & (tp["key"] == "JS")]
    A(f"- JS -> Retention pooled beta across the delta grid: min {t3['std_beta'].min():.3f}, max {t3['std_beta'].max():.3f}; "
      f"p ranges {t3['p'].min():.2f}-{t3['p'].max():.2f}.\n")
    A("## 5. Associational mediation  X -> {BO, JS} -> RET\n")
    mc, mm = T["mediation_complete_case"], T["mediation_imputed"]
    tot = mc[mc["kind"] == "ind_total"].set_index("predictor")
    tm = mm[mm["kind"] == "ind_total"].set_index("predictor")
    rows = pd.DataFrame({"Predictor": PREDICTORS,
                         "Total indirect (CC, BCa)": [f"{tot.loc[p, 'estimate']:.3f} [{tot.loc[p, 'ci_low']:.3f}, {tot.loc[p, 'ci_high']:.3f}]" for p in PREDICTORS],
                         "Total indirect (MI)": [f"{tm.loc[p, 'estimate']:.3f} [{tm.loc[p, 'ci_low']:.3f}, {tm.loc[p, 'ci_high']:.3f}]" for p in PREDICTORS]})
    A(md_table(rows))
    A("\nCI methods: complete-case = BCa bootstrap; imputed = Rubin's rules with bootstrap within-imputation variance. The complete-case mediation sample "
      f"(n = {int(mc['n'].iloc[0])}: JS observed and every predictor present) is smaller than Eq.3's (n = {int(summ[summ['equation']=='Eq3_RET'].iloc[0]['n'])}), "
      "so b_BO / b_JS can differ slightly from the Eq.3 coefficients.")
    A("\nUnstandardised: points of RET (0-100) per point of X. Specific indirect effects via BO and via JS, direct and total effects: "
      "`mediation_*.csv`. Interpret as structural associations; see assumption A15.\n")
    A("## 6. Organisation vs self-employed\n")
    gc = T["group_comparison_incl_hybrid"]
    A(md_table(_fmt(gc, {"label": "Outcome", "n_org": "n org", "mean_org": "Mean org", "n_self": "n self", "mean_self": "Mean self",
                         "mean_diff_self_minus_org": "Diff (self-org)", "rank_biserial_self_vs_org": "Rank-biserial",
                         "mannwhitney_p": "p", "q_fdr": "q"}, 3)))
    A("\nExploratory family of 7 contrasts. Sensitivity excluding hybrid respondents: `group_comparison_excl_hybrid.csv`.\n")
    rm = T["reduced_jdr_models"]
    idrow = rm[(rm["key"].isin(["ID", "ID_x_self"])) & (rm["equation"].isin(["R1_BO~ID", "R2_JS~ID"]))]
    A("Part of the JD-R model measurable in **both** groups (ID -> BO, ID -> JS; controls: age band, years in helping work). "
      "Interaction rows test whether the slope differs between groups (raw units):\n")
    A(md_table(_fmt(idrow, {"group": "Group", "equation": "Model", "key": "Term", "b_raw": "b (0-100 units)", "std_beta": "Std beta",
                            "p": "p", "n": "n"}, 3)))
    A("\nThe structural equations Eq.1-3 are **not estimable** for the self-employed (WL, OS, JR, PAY, MA, RET, SIZE, MISSION were not asked; assumption A23). "
      "Their own top challenges are in `selfemployed_challenges.csv` / Figure 12.\n")
    A("## 7. Support gap: provided vs wanted vs decision-makers\n")
    g = T["support_gap"]
    A(md_table(_fmt(g, {"item": "Support", "staff_provided_pct": "Staff: provided %", "dm_provided_pct": "Decision-makers: provided %",
                        "staff_wanted_pct": "Staff: wanted %", "dm_wanted_pct": "Decision-makers: wanted %",
                        "staff_unmet_pct": "Staff unmet % (want, org lacks)", "pct_of_wanters_whose_org_lacks_it": "% of wanters lacking it"}, 1)))
    A("\nSample sizes: staff n = 241, decision-makers n = 28 (independent groups; no matched organisations). Newcombe CIs and Fisher tests: "
      "`support_gap.csv`. Caveats: A18-A21.\n")
    sc = T["support_count_vs_outcomes"]
    if len(sc):
        A("Exploratory association between the number of supports staff say exist and their JD-R scores:\n")
        A(md_table(_fmt(sc, {"outcome": "Outcome", "spearman_rho": "Spearman rho", "n": "n", "q_fdr": "q"}, 3)))
    A("\n**Resource levels by seniority** (organisation group; Kruskal-Wallis, exploratory; `role_profile.csv`):\n")
    A(md_table(T["role_profile"][["construct", "Frontline helper mean (n)", "Admin / project / finance mean (n)", "Mid-level manager mean (n)",
                                  "Founder / decision-maker mean (n)", "q_fdr"]].round(3)))
    A("\n## 8. Validation against the IQP report\n")
    A("The IQP report does not say whether its stars used classical or robust SEs; betas, n and R2 do not depend on that, but star agreement near p = .05 can.\n")
    v = T["validation_summary"]
    agg = v[v["section"] == "aggregate"][["pipeline", "n_terms", "mean_abs_diff", "max_abs_diff", "sign_agreement", "significance_agreement", "corr_beta"]]
    A(md_table(agg.round(3)))
    det = T["validation_detail"]
    ext = det[det["pipeline"] == "extended CC"]
    bad = ext[~ext["same_sign"]]
    A(f"\nUnder the `extended` item set the pipeline reproduces **{int((ext['diff'].abs() < 0.0015).sum())} of {len(ext)}** printed standardised betas "
      "to three decimals, plus every n and R2. " +
      (("The exception(s): " + "; ".join(f"{r['equation']} {r['term']} (report {r['beta_iqp']:+.3f}, recomputed {r['beta_here']:+.3f})" for _, r in bad.iterrows()) +
        ". The magnitude agrees and only the sign differs, i.e. the printed sign looks like a transcription error; the recomputed sign "
        "(more organisational support -> less burnout) is the theoretically coherent one.") if len(bad) else "No sign disagreements.") + "\n")
    A("## 9. Robustness across specification, sample and estimator\n")
    cs = T["cluster_summary"].iloc[0]
    A(f"County clustering: {int(cs['n_counties'])} counties but only {cs['effective_n_clusters']:.1f} effective clusters "
      f"(largest county = {cs['largest_county_share'] * 100:.0f}% of respondents), so county-clustered SEs are indicative only.\n")
    rb = T["robustness_summary"]
    A(md_table(_fmt(rb, {"equation": "Eq", "term": "Term", "primary_std_beta": "Primary beta", "share_same_sign": "Same sign (share)",
                         "share_p<.05": "p<.05 (share)", "min_std_beta": "Min beta", "max_std_beta": "Max beta",
                         "brief_literal_std_beta": "Beta, brief-literal"}, 3)))
    A("\nVariants: 2 non-literal specifications + strict (all-items-required) scoring, x 2 samples x complete-case, plus MI and county-clustered SE for the primary specification "
      "(`robustness_all_estimates.csv`). `brief_literal` is shown separately because its retention scale is internally inconsistent (alpha ~ 0).\n")
    A("## 10. Assumptions register\n")
    A(md_table(pd.DataFrame(ASSUMPTIONS, columns=["ID", "Assumption", "Used in", "How it is handled / checked"])))
    A("\n## 11. What this analysis cannot establish\n")
    A("- Causal or temporal claims (cross-sectional design; A15).\n- Population prevalence or representativeness (A24).\n"
      "- Clustering within employers (A9) and formal measurement invariance across groups (ordinal CFA needed; only loading congruence is provided: `loading_congruence.csv`).\n"
      "- Effects of single-item predictors PAY and MA (A7).\n")
    (out.root / "report.md").write_text("\n".join(L), encoding="utf-8")
    LOG.info("report written: %s", out.root / "report.md")


def loading_congruence(ds: pd.DataFrame) -> pd.DataFrame:
    """Configural-similarity diagnostic (NOT formal invariance): Tucker's phi between one-factor loadings of the same scale
    in the organisation and self-employed groups."""
    rows = []
    for cons in ("ID", "BO", "JS"):
        fr_o = item_frame(ds[ds["group"] == GROUP_ORG], SPEC_PRIMARY[cons]).dropna()
        fr_s = item_frame(ds[ds["group"] == GROUP_SELF], SPEC_PRIMARY[cons]).dropna()
        if len(fr_o) < MIN_GROUP_N or len(fr_s) < MIN_GROUP_N or fr_o.shape[1] < 3:
            continue
        lo_, ls_ = one_factor_loadings(np.corrcoef(fr_o.values.T)), one_factor_loadings(np.corrcoef(fr_s.values.T))
        rows.append({"scale": cons, "n_org": len(fr_o), "n_self": len(fr_s), "tucker_phi": tucker_phi(lo_, ls_),
                     "interpretation": "equal (>=.95)" if tucker_phi(lo_, ls_) >= 0.95 else "fair (.85-.94)" if tucker_phi(lo_, ls_) >= 0.85 else "dissimilar"})
    return pd.DataFrame(rows)


# =============================================================================================== #
# 18. SELF-TEST  (python helper_survey_analysis.py --selftest)
# =============================================================================================== #
def run_selftest() -> int:
    """Numerical unit checks of the statistical building blocks against closed-form / simulated truths."""
    fails: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            fails.append(name)

    rng = np.random.default_rng(7)
    check("bh_fdr known example", np.allclose(bh_fdr([0.01, 0.04, 0.03, 0.005]), [0.02, 0.04, 0.04, 0.02]))
    check("bh_fdr NaN-safe", np.isnan(bh_fdr([0.01, np.nan])[1]))
    lo, hi = wilson_ci(10, 20)
    check("wilson_ci(10,20)", abs(lo - 0.2993) < 1e-3 and abs(hi - 0.7007) < 1e-3)
    check("pomp", pomp(pd.Series([1, 3, 5]), 1, 5).tolist() == [0.0, 50.0, 100.0] and pomp(pd.Series([1.0]), 1, 5, True).iloc[0] == 100.0)
    check("row_mean min_frac", row_mean(pd.DataFrame({"a": [1, np.nan], "b": [3, np.nan]}), 1.0).isna().iloc[1])
    x = rng.normal(size=(500, 1))
    items = pd.DataFrame(x + 0.0 * rng.normal(size=(500, 4)))
    check("alpha: identical items -> 1", abs(cronbach_alpha(items)[0] - 1) < 1e-9)
    check("alpha: independent items -> ~0", abs(cronbach_alpha(pd.DataFrame(rng.normal(size=(4000, 5))))[0]) < 0.06)

    f_true = rng.normal(size=6000)
    sim = pd.DataFrame({i: 0.7 * f_true + math.sqrt(1 - 0.49) * rng.normal(size=6000) for i in range(5)})
    om_true = (5 * 0.7) ** 2 / ((5 * 0.7) ** 2 + 5 * (1 - 0.49))
    check("omega recovers one-factor truth", abs(omega_total(sim) - om_true) < 0.02, f"({omega_total(sim):.3f} vs {om_true:.3f})")
    check("robustness value: |t|=sqrt(df) -> RV=(sqrt5-1)/2", abs(float(robustness_value(10.0, 100.0)) - (math.sqrt(5) - 1) / 2) < 1e-12)
    check("robustness value is 0 for t=0 and rises with |t|", float(robustness_value(0.0, 50)) == 0 and robustness_value(5.0, 50) > robustness_value(2.0, 50))
    try:
        fit_logit(np.column_stack([np.ones(30), rng.normal(size=30)]), np.zeros(30))
        check("logit rejects degenerate outcome", False)
    except ValueError:
        check("logit rejects degenerate outcome", True)
    dfc = pd.DataFrame({"y": rng.normal(size=40), "a": rng.normal(size=40), "const": 1.0})
    check("VIF survives a constant column", bool(np.isnan(vif_values(fit_ols(dfc, "y", ["a", "const"])))[1]))
    check("tucker_phi identical", abs(tucker_phi(np.array([.5, .6]), np.array([.5, .6])) - 1) < 1e-12)

    n = 300
    Xs = rng.normal(size=(n, 3))
    yv = 1 + Xs @ [0.5, -0.3, 0.0] + rng.normal(size=n) * np.exp(0.7 * Xs[:, 0])
    df = pd.DataFrame(Xs, columns=list("abc")).assign(y=yv)
    fit = fit_ols(df, "y", list("abc"))
    Xd = np.column_stack([np.ones(n), Xs])
    XtXi = np.linalg.inv(Xd.T @ Xd)
    b = XtXi @ Xd.T @ yv
    e = yv - Xd @ b
    h = np.diag(Xd @ XtXi @ Xd.T)
    V = XtXi @ (Xd.T @ np.diag(e ** 2 / (1 - h) ** 2) @ Xd) @ XtXi
    check("OLS coefficients", np.allclose(fit.beta, b))
    check("HC3 covariance equals brute-force formula", np.allclose(fit.cov, V))
    check("standardised beta = b*sd_x/sd_y", np.allclose(fit.table()["std_beta"], b[1:] * Xs.std(0, ddof=1) / yv.std(ddof=1)))
    try:  # cross-validate against statsmodels when it happens to be installed
        import statsmodels.api as sm
        sm_fit = sm.OLS(yv, Xd).fit(cov_type="HC3")
        check("HC3 equals statsmodels", np.allclose(sm_fit.bse, fit.se, rtol=1e-8))
    except ImportError:
        print("  [SKIP] statsmodels not installed (cross-validation skipped)")
    cl = pd.Series(np.arange(n), index=df.index)
    cr = fit_ols(df, "y", list("abc"), cluster=cl)
    check("cluster-robust with singleton clusters ~ HC1-scale", np.all(cr.se > 0.7 * fit.se) and np.all(cr.se < 1.3 * fit.se))
    dg = diagnostics(fit)
    check("heteroskedasticity detected by Koenker-BP", dg["BP_heterosk_p"] < 0.05, f"(p={dg['BP_heterosk_p']:.4f})")

    pr = pool_rubin([np.array([1.0]), np.array([1.2])], [np.array([0.04]), np.array([0.04])], 1e6)
    check("Rubin pooling (T = .04 + 1.5*.02)", abs(pr["se"].iloc[0] ** 2 - 0.07) < 1e-9 and abs(pr["est"].iloc[0] - 1.1) < 1e-12)
    check("Rubin m=1 reduces to complete-data", abs(pool_rubin([np.array([2.0])], [np.array([0.25])], 100)["se"].iloc[0] - 0.5) < 1e-12)

    Z = np.column_stack([np.ones(2000), rng.normal(size=(2000, 2))])
    yb = (rng.random(2000) < _expit(Z @ [-0.5, 1.0, 0.0])).astype(float)
    lg = fit_logit(Z, yb)
    check("logit recovers coefficients", np.allclose(lg["coef"], [-0.5, 1.0, 0.0], atol=0.2) and lg["auc"] > 0.65)

    s = rng.normal(5, 2, size=60)
    bt = np.array([[rng.choice(s, 60).mean()] for _ in range(3000)])
    jk = np.array([[np.delete(s, i).mean()] for i in range(60)])
    blo, bhi = bca_interval(np.array([s.mean()]), bt, jk)
    tci = stats.t.interval(0.95, 59, s.mean(), s.std(ddof=1) / math.sqrt(60))
    check("BCa interval close to t interval for a mean", abs(blo[0] - tci[0]) < 0.15 and abs(bhi[0] - tci[1]) < 0.15)

    m_ = 40000
    X1 = rng.normal(size=m_)
    BO = 0.5 * X1 + rng.normal(size=m_)
    JS = rng.normal(size=m_)
    RET = 0.4 * BO + 0.1 * X1 + rng.normal(size=m_)
    vec = _mediation_vector(np.column_stack([X1, BO, JS, RET]), 1)
    check("mediation recovers a*b=.20 and direct=.10", abs(vec[0] - 0.2) < 0.02 and abs(vec[3] - 0.1) < 0.02, f"(ind={vec[0]:.3f}, direct={vec[3]:.3f})")

    fr = pd.DataFrame({"JS": [50.0, np.nan]})
    check("delta_shift clips at 100", delta_shift([fr.assign(JS=[99.0, np.nan])], pd.Series([False, True]), 10)[0]["JS"].iloc[0] == 99.0)
    shifted = delta_shift([pd.DataFrame({"JS": [95.0, 20.0]})], pd.Series([True, False]), 10)[0]["JS"].tolist()
    check("delta_shift only shifts imputed cells", shifted == [100.0, 20.0])
    try:
        verify_layout(pd.DataFrame(columns=[f"x{i}" for i in range(108)]))
        check("layout check rejects wrong headers", False)
    except LayoutError:
        check("layout check rejects wrong headers", True)
    print(f"\n{len(fails)} failure(s)" if fails else "\nall self-tests passed")
    return 1 if fails else 0


# =============================================================================================== #
# 19. MANIFEST + MAIN
# =============================================================================================== #
def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out: Output, args: argparse.Namespace) -> None:
    import datetime
    import scipy
    pkgs = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__}
    try:
        import sklearn
        pkgs["scikit-learn"] = sklearn.__version__
    except ImportError:
        pass
    man = {"pipeline_version": __version__, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "input_file": str(args.input), "input_sha256": sha256(args.input),
           "script_sha256": sha256(__file__) if "__file__" in globals() else None, "seed": args.seed, "n_bootstrap": args.boot,
           "n_imputations": args.m, "command_line": " ".join(sys.argv), "packages": pkgs}
    (out.root / "run_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")


def export_analysis_dataset(ds: pd.DataFrame, out: Output) -> None:
    """Analysis dataset without identifiers/free text: underscore-prefixed (raw text, county) columns are dropped."""
    keep = [c for c in ds.columns if not c.startswith("_")]
    exp = ds[keep].copy()
    exp.insert(0, "respondent_id", np.arange(1, len(exp) + 1))
    out.table(exp, "analysis_dataset_primary_spec")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analyse the 2026 Taiwan Helpers' Needs Survey (simplified JD-R model).")
    ap.add_argument("--input", "-i", help="survey CSV (default: first *.csv in the working directory)")
    ap.add_argument("--out", "-o", default="analysis_output", help="output directory")
    ap.add_argument("--boot", type=int, default=N_BOOT, help="bootstrap resamples (default %(default)s)")
    ap.add_argument("--m", type=int, default=N_IMPUTATIONS, help="number of multiple imputations (default %(default)s)")
    ap.add_argument("--seed", type=int, default=SEED, help="master random seed (default %(default)s)")
    ap.add_argument("--no-figures", action="store_true", help="skip figure generation")
    ap.add_argument("--selftest", action="store_true", help="run numerical self-tests and exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    if args.selftest:
        return run_selftest()
    if args.input is None:
        cands = sorted(Path(".").glob("*.csv"))
        if not cands:
            ap.error("no --input given and no *.csv found in the working directory")
        args.input = str(cands[0])
    out = Output(args.out)
    rng = np.random.default_rng(args.seed)

    LOG.info("[1/9] load, verify layout, clean")
    d, meta = load_and_clean(args.input)
    out.table(meta["layout"], "layout_check")
    ds = with_spec(d, "primary")
    export_analysis_dataset(ds, out)
    org_mask = ds["group"] == GROUP_ORG
    ctx = {"n": {"raw": len(d), "org": int(org_mask.sum()), "hybrid": int(d.loc[org_mask, "hybrid"].sum()), "self": int((~org_mask).sum()),
                 "js_org": int(ds.loc[org_mask, "JS"].notna().sum()), "js_self": int(ds.loc[~org_mask, "JS"].notna().sum()),
                 "staff": int((d["support_branch"] == "Staff").sum()), "dm": int((d["support_branch"] == "Decision-maker").sum())}}

    rows3b = ds.loc[org_mask, ["RET", "JS", "BO"] + PREDICTORS + CONTROLS].dropna()
    r2a, r2b = fit_ols(rows3b, "RET", EQUATIONS["Eq3_RET"][1]).r2, fit_ols(rows3b, "RET", EQUATIONS["Eq3b_RET"][1]).r2
    ctx["dr2"] = {"n": len(rows3b), "r2_eq3": r2a, "r2_eq3b": r2b, "delta": r2b - r2a}

    LOG.info("[2/9] psychometrics and coding audit")
    rel = out.table(reliability_table(d, rng), "reliability")
    out.table(coding_audit(d), "coding_audit")
    out.table(loading_congruence(ds), "loading_congruence")
    out.table(pd.DataFrame([(k, v) for k, v in SPEC_NOTES.items()], columns=["item", "note"]), "specification_notes")

    LOG.info("[3/9] JD-R equations: specification x sample x estimator grid (includes %d imputations)", args.m)
    fits, imputed = robustness_grid(d, args.m, args.seed)
    prim = fits[PRIMARY_KEY]
    out.table(prim[0], "primary_cc_coefficients")
    out.table(prim[1], "primary_cc_model_summary")
    out.table(fits[("primary", "org_incl_hybrid", "multiple imputation")][0], "primary_mi_coefficients")
    out.table(fits[("primary", "org_incl_hybrid", "multiple imputation")][1], "primary_mi_model_summary")
    long, rsum = robustness_tables(fits)
    out.table(long, "robustness_all_estimates")
    out.table(rsum, "robustness_summary")

    LOG.info("[4/9] missingness model and delta-adjusted tipping point")
    org = ds[org_mask]
    uni, lg = js_missingness(org)
    out.table(uni, "missingness_univariate")
    out.table(lg, "missingness_logit")
    frames, mask = imputed["org_incl_hybrid"]
    tp = out.table(tipping_point(frames, mask), "tipping_point")

    out.table(buffering_tests(org), "buffering_tests_exploratory")
    out.table(cluster_summary(org), "cluster_summary")

    LOG.info("[5/9] associational mediation (B=%d)", args.boot)
    med_cc, _ = mediation([org], args.boot, args.seed, bca=True)
    med_mi, _ = mediation(frames, args.boot, args.seed, bca=False)
    out.table(med_cc, "mediation_complete_case")
    out.table(med_mi, "mediation_imputed")

    LOG.info("[6/9] organisation vs self-employed")
    out.table(group_comparison(ds, rng), "group_comparison_incl_hybrid")
    out.table(group_comparison(ds, rng, exclude_hybrid=True), "group_comparison_excl_hybrid")
    out.table(reduced_models(ds), "reduced_jdr_models")
    ch = out.table(selfemployed_challenges(ds), "selfemployed_challenges")
    prof = []
    for g in (GROUP_ORG, GROUP_SELF):
        sub = ds[ds["group"] == g]
        for col, lab in (("role", "Role"), ("gender", "Gender"), ("age_cat", "Age"), ("region", "Region"), ("helping_yrs_cat", "Years in helping work")):
            vc = sub[col].astype(object).value_counts(dropna=False)
            prof += [{"group": g, "variable": lab, "level": str(k), "n": int(v), "pct": v / len(sub) * 100} for k, v in vc.items()]
    out.table(pd.DataFrame(prof), "sample_profile")

    LOG.info("[7/9] support gap")
    out.table(branch_audit(d), "support_branch_audit")
    gap_tabs = support_gap(ds)
    for name, tab in gap_tabs.items():
        out.table(tab, name)
    out.table(role_profile(ds), "role_profile")

    LOG.info("[8/9] validation against the IQP report")
    val = {"brief_literal CC": fits[("brief_literal", "org_incl_hybrid", "complete-case")],
           "primary CC": prim, "primary MI": fits[("primary", "org_incl_hybrid", "multiple imputation")],
           "extended CC": fits[("extended", "org_incl_hybrid", "complete-case")]}
    det, vsum = validate_against_iqp(val)
    out.table(det, "validation_detail")
    out.table(vsum, "validation_summary")

    if not args.no_figures:
        LOG.info("[9/9] figures")
        fig_reliability(rel, out)
        corr = fig_corr(ds, out)
        out.table(corr.reset_index(names="construct"), "construct_correlations_spearman")
        fig_group_means(ds, out)
        fig_forest_equations(fits, out)
        fig_missingness(uni, out)
        fig_tipping(tp, out)
        fig_mediation(med_cc, med_mi, out)
        fig_validation(det, out)
        fig_gap_dumbbell(gap_tabs["support_gap"], out)
        fig_gap_four_way(gap_tabs["support_gap"], out)
        fig_barriers(gap_tabs["barriers"], out)
        fig_challenges(ch, out)
        LOG.info("donor pack (plain-language charts)")
        donor_figures(ds, out.tables, out)
    write_report(ctx, out, args)
    write_manifest(out, args)
    LOG.info("done -> %s", out.root.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())