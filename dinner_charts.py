"""
NPO EAP Presentation Chart Generator (Bilingual with CJK Font Support)
=====================================================================
Generates publication-ready charts for the NPO EAP presentation 
including core survey results and detailed cross-tabulation matrices.

Requirements: matplotlib, seaborn, pandas, numpy
"""
from __future__ import annotations

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import seaborn as sns

# --------------------------------------------------------------------------- #
# Font & Styling Configuration (Ensures Chinese Characters Render Properly)
# --------------------------------------------------------------------------- #
try:
    matplotlib.font_manager._load_fontmanager(try_read_cache=False)
except Exception:
    pass

plt.rcParams["font.sans-serif"] = [
    "Noto Sans TC",         # Linux / Cross-platform open-source CJK font
    "Microsoft JhengHei",   # Windows standard for Traditional Chinese
    "PingFang TC",          # macOS standard for Traditional Chinese
    "Heiti TC",             # Older macOS Chinese font fallback
    "DejaVu Sans"           # Safer fallback than Arial
]
plt.rcParams["axes.unicode_minus"] = False  # Prevent minus signs from showing as boxes

PALETTE = sns.color_palette("deep")

SINGLE = (7.5, 5.0)
WIDE = (9.5, 5.8)
MATRIX = (11.0, 6.5)

class Out:
    """Output directory manager for figures and tables."""
    def __init__(self, root: str = "presentation_output_bilingual"):
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


def barh_counts(ax, series: pd.Series, title: str, color=None, titlesize=12, fontsize=10):
    """Clean horizontal bar chart with bilingual labels and data values."""
    s = series.sort_values()
    bars = ax.barh(s.index.astype(str), s.values, color=color or PALETTE[0])
    for bar in bars:
        width = bar.get_width()
        if width > 0:
            ax.text(width + s.max() * 0.015, bar.get_y() + bar.get_height()/2, 
                    f"{int(width)}", va="center", fontsize=fontsize, fontweight="bold")
    ax.set_xlim(0, max(s.max() * 1.25, 2))
    ax.set_xlabel("使用次數 / Frequency Counts", fontsize=11)
    ax.set_title(title, fontsize=titlesize, loc="left", fontweight="bold")
    ax.grid(axis="y", visible=False)


# --------------------------------------------------------------------------- #
# Chart Generation Functions (Core & Additional Slides)
# --------------------------------------------------------------------------- #
def generate_respondent_pie(out: Out):
    """Slide 8: Post-Test Company Respondents Share (Bilingual)."""
    data = {
        "RE-THINK 環境教育協會\n(RE-THINK Environmental Education Assn.)": 9,
        "台灣童心創意行動協會 / DFC\n(Design for Change Taiwan)": 9,
        "世界和平婦女會台灣總會\n(WFWP Taiwan)": 6
    }
    df = pd.Series(data)
    
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    colors = PALETTE[:3]
    wedges, texts, autotexts = ax.pie(
        df, labels=df.index, autopct="%1.1f%%", startangle=90, 
        colors=colors, wedgeprops=dict(width=0.55, edgecolor="white", linewidth=2.5)
    )
    plt.setp(autotexts, size=11, weight="bold", color="black")
    plt.setp(texts, size=10)
    ax.set_title("NPO EAP 後測機構填答者比例 / Post-Test Respondent Share (總計 n=24)", loc="left", fontweight="bold", fontsize=12)
    
    out.save_fig(fig, "01_overview/company_respondents_donut.png")
    out.save_tab(df.to_frame("respondents"), "company_respondents.csv")


def generate_resource_barcharts(out: Out):
    """Slides 9-12: Bilingual Resource Frequency Counts."""
    resources = [
        "無特別印象 / 未使用\n(No Special Impression / Unused)",
        "諮商補助金\n(Counseling Subsidy)",
        "書籍閱覽\n(Books)",
        "線上課程 (學籽/Hahow)\n(Online Courses)",
        "牌卡: 職能與價值導航\n(Card Decks: Career & Value)",
        "牌卡: 口袋裡的心理師\n(Card Decks: Psychologist in Pocket)",
        "NPO EAP 工作坊\n(NPO EAP Workshop)"
    ]
    
    df = pd.DataFrame({
        "RE-THINK": [1, 1, 1, 3, 0, 4, 7],
        "Design for Change Taiwan (DFC)": [1, 1, 1, 6, 1, 5, 7],
        "婦女會 (WFWP Taiwan)": [0, 0, 1, 4, 5, 3, 5],
    }, index=resources)
    df["Combined"] = df.sum(axis=1)
    
    out.save_tab(df, "organization_resource_counts.csv")

    # 1. RE-THINK Chart
    fig, ax = plt.subplots(figsize=WIDE)
    barh_counts(ax, df["RE-THINK"], "RE-THINK 環境教育協會 — 資源使用頻次\nRE-THINK — Resource Frequency", color=PALETTE[0])
    out.save_fig(fig, "02_resources/rethink_resources.png")

    # 2. Design for Change Taiwan (DFC) Chart
    fig, ax = plt.subplots(figsize=WIDE)
    barh_counts(ax, df["Design for Change Taiwan (DFC)"], "台灣童心創意行動協會 (DFC) — 資源使用頻次\nDesign for Change Taiwan (DFC) — Resource Frequency", color=PALETTE[2])
    out.save_fig(fig, "02_resources/tc_hcaa_resources.png")

    # 3. Women's Federation Chart
    fig, ax = plt.subplots(figsize=WIDE)
    barh_counts(ax, df["婦女會 (WFWP Taiwan)"], "世界和平婦女會台灣總會 — 資源使用頻次\nWFWP Taiwan — Resource Frequency", color=PALETTE[4])
    out.save_fig(fig, "02_resources/wfwp_resources.png")

    # 4. Combined Chart
    fig, ax = plt.subplots(figsize=WIDE)
    barh_counts(ax, df["Combined"], "三家機構合併統計 — 資源使用總頻次 (n=57)\nCombined Organizations — Total Resource Frequency (n=57)", color=PALETTE[3])
    out.save_fig(fig, "02_resources/combined_resources.png")


def generate_satisfaction_chart(out: Out):
    """Slide 13: Organization Satisfaction Summary (Bilingual)."""
    sat_data = pd.DataFrame({
        "有點滿意\n(Somewhat Satisfied)": [8, 3, 2],
        "滿意\n(Satisfied)": [1, 3, 0],
        "非常滿意\n(Very Satisfied)": [0, 2, 4]
    }, index=["RE-THINK", "Design for Change Taiwan\n(DFC)", "世界和平婦女會\n(WFWP Taiwan)"])
    
    out.save_tab(sat_data, "organization_satisfaction.csv")

    fig, ax = plt.subplots(figsize=SINGLE)
    sat_data.plot(kind="bar", stacked=True, ax=ax, color=["#f6c85f", "#8fd19e", "#2e86ab"], edgecolor="white")
    ax.set_ylabel("填答人數 / Number of Respondents", fontsize=11)
    ax.set_title("各機構對安心資源的滿意度分佈\nSatisfaction Distribution by Organization", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, loc="upper right", fontsize=9, title="滿意度 / Satisfaction")
    plt.xticks(rotation=0, ha="center", fontsize=10)
    ax.grid(axis="x", visible=False)
    out.save_fig(fig, "03_satisfaction/satisfaction_by_org.png")


def generate_satisfaction_by_resource_by_org_charts(out: Out):
    """Satisfaction by Resource Used, broken down individually per organization with uniform categories."""
    
    # Standardized list of all 7 resource categories to keep identical layout across all three charts
    standard_resources = [
        "NPO EAP 工作坊\n(Workshop)",
        "牌卡: 口袋裡的心理師\n(Psychologist Card)",
        "牌卡: 職能與價值\n(Career/Value Card)",
        "線上課程\n(Online Courses)",
        "書籍閱覽\n(Books)",
        "諮商補助金\n(Counseling Subsidy)",
        "無特別印象 / 未使用\n(Unused / No Impression)"
    ]
    satisfaction_columns = ["未填答/無法回答\n(Unanswered)", "有點滿意\n(Somewhat)", "滿意\n(Satisfied)", "非常滿意\n(Very Satisfied)"]

    # 1. RE-THINK Satisfaction by Resource (Uniform 7 categories)
    rethink_raw = {
        "NPO EAP 工作坊\n(Workshop)": [0, 5, 2, 0],
        "牌卡: 口袋裡的心理師\n(Psychologist Card)": [0, 3, 1, 0],
        "牌卡: 職能與價值\n(Career/Value Card)": [0, 0, 0, 0],
        "線上課程\n(Online Courses)": [0, 2, 1, 0],
        "書籍閱覽\n(Books)": [0, 1, 0, 0],
        "諮商補助金\n(Counseling Subsidy)": [0, 1, 0, 0],
        "無特別印象 / 未使用\n(Unused / No Impression)": [1, 0, 0, 0]
    }
    rethink_df = pd.DataFrame(rethink_raw, index=satisfaction_columns)[standard_resources].T
    
    out.save_tab(rethink_df, "rethink_satisfaction_by_resource.csv")
    fig, ax = plt.subplots(figsize=MATRIX)
    rethink_df.plot(kind="bar", stacked=True, ax=ax, color=["#d3d3d3", "#f6c85f", "#8fd19e", "#2e86ab"], edgecolor="white")
    ax.set_ylabel("使用人數 / Number of Users", fontsize=11)
    ax.set_title("RE-THINK — 各項安心資源的滿意度分佈\nRE-THINK — Satisfaction Distribution by Resource Used", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, loc="upper right", fontsize=9, title="滿意度 / Satisfaction")
    plt.xticks(rotation=25, ha="right", fontsize=10)
    ax.grid(axis="x", visible=False)
    out.save_fig(fig, "03_satisfaction/rethink_satisfaction_by_resource.png")

    # 2. DFC Satisfaction by Resource (Uniform 7 categories)
    dfc_raw = {
        "NPO EAP 工作坊\n(Workshop)": [0, 3, 2, 2],
        "牌卡: 口袋裡的心理師\n(Psychologist Card)": [0, 2, 2, 1],
        "牌卡: 職能與價值\n(Career/Value Card)": [0, 0, 1, 0],
        "線上課程\n(Online Courses)": [1, 2, 2, 1],
        "書籍閱覽\n(Books)": [0, 1, 0, 0],
        "諮商補助金\n(Counseling Subsidy)": [0, 0, 1, 0],
        "無特別印象 / 未使用\n(Unused / No Impression)": [0, 1, 0, 0]
    }
    dfc_df = pd.DataFrame(dfc_raw, index=satisfaction_columns)[standard_resources].T
    
    out.save_tab(dfc_df, "dfc_satisfaction_by_resource.csv")
    fig, ax = plt.subplots(figsize=MATRIX)
    dfc_df.plot(kind="bar", stacked=True, ax=ax, color=["#d3d3d3", "#f6c85f", "#8fd19e", "#2e86ab"], edgecolor="white")
    ax.set_ylabel("使用人數 / Number of Users", fontsize=11)
    ax.set_title("台灣童心創意行動協會 (DFC) — 各項安心資源的滿意度分佈\nDesign for Change Taiwan — Satisfaction Distribution by Resource Used", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, loc="upper right", fontsize=9, title="滿意度 / Satisfaction")
    plt.xticks(rotation=25, ha="right", fontsize=10)
    ax.grid(axis="x", visible=False)
    out.save_fig(fig, "03_satisfaction/dfc_satisfaction_by_resource.png")

    # 3. WFWP Taiwan Satisfaction by Resource (Uniform 7 categories)
    wfwp_raw = {
        "NPO EAP 工作坊\n(Workshop)": [0, 2, 0, 3],
        "牌卡: 口袋裡的心理師\n(Psychologist Card)": [0, 1, 0, 2],
        "牌卡: 職能與價值\n(Career/Value Card)": [0, 1, 0, 4],
        "線上課程\n(Online Courses)": [0, 1, 0, 3],
        "書籍閱覽\n(Books)": [0, 0, 0, 1],
        "諮商補助金\n(Counseling Subsidy)": [0, 0, 0, 0],
        "無特別印象 / 未使用\n(Unused / No Impression)": [0, 0, 0, 0]
    }
    wfwp_df = pd.DataFrame(wfwp_raw, index=satisfaction_columns)[standard_resources].T
    
    out.save_tab(wfwp_df, "wfwp_satisfaction_by_resource.csv")
    fig, ax = plt.subplots(figsize=MATRIX)
    wfwp_df.plot(kind="bar", stacked=True, ax=ax, color=["#d3d3d3", "#f6c85f", "#8fd19e", "#2e86ab"], edgecolor="white")
    ax.set_ylabel("使用人數 / Number of Users", fontsize=11)
    ax.set_title("世界和平婦女會台灣總會 — 各項安心資源的滿意度分佈\nWFWP Taiwan — Satisfaction Distribution by Resource Used", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, loc="upper right", fontsize=9, title="滿意度 / Satisfaction")
    plt.xticks(rotation=25, ha="right", fontsize=10)
    ax.grid(axis="x", visible=False)
    out.save_fig(fig, "03_satisfaction/wfwp_satisfaction_by_resource.png")


def generate_impression_heatmap(out: Out):
    """Slide 15: Resource with Biggest Impression by Resource Used (Heatmap)."""
    resources_short = [
        "NPO EAP 工作坊", "口袋裡的心理師", "職能與價值牌卡", 
        "線上課程", "書籍閱覽", "諮商補助金", "無特別印象"
    ]
    matrix_data = np.array([
        [13,  0,  2,  3,  0,  1,  0],
        [10,  1,  0,  1,  0,  0,  0],
        [ 4,  0,  1,  0,  0,  0,  1],
        [ 8,  0,  0,  4,  0,  0,  1],
        [ 3,  0,  0,  0,  0,  0,  0],
        [ 2,  0,  0,  0,  0,  0,  0],
        [ 0,  0,  0,  0,  0,  0,  2]
    ])
    df = pd.DataFrame(matrix_data, index=resources_short, columns=resources_short)
    out.save_tab(df, "resource_impression_matrix.csv")

    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(df, annot=True, fmt="d", cmap="Blues", cbar=True, ax=ax, linewidths=.5, annot_kws={"size": 11, "weight": "bold"})
    ax.set_title("資源使用與印象最深刻項目對照矩陣 (Slide 15)\nResource Used vs. Resource with Biggest Impression Matrix", fontsize=12, fontweight="bold", pad=15)
    ax.set_xlabel("印象最深刻的資源 / Resource with Biggest Impression", fontsize=11, fontweight="bold")
    ax.set_ylabel("實際使用過的資源 / Resource Used", fontsize=11, fontweight="bold")
    plt.xticks(rotation=30, ha="right", fontsize=10)
    plt.yticks(rotation=0, fontsize=10)
    out.save_fig(fig, "02_resources/resource_impression_heatmap.png")


# --------------------------------------------------------------------------- #
# Main Pipeline
# --------------------------------------------------------------------------- #
def main():
    print("\n[1/4] 初始化輸出資料夾 (Initializing output directories)...")
    out = Out("presentation_output_bilingual")

    print("\n[2/4] 正在生成參與機構佔比圓餅圖 (Generating Respondent Pie Chart)...")
    generate_respondent_pie(out)

    print("\n[3/4] 正在生成資源使用頻次與滿意度圖表 (Generating Resource & Satisfaction Charts)...")
    generate_resource_barcharts(out)
    generate_satisfaction_chart(out)

    print("\n[4/4] 正在生成進階交叉分析圖表與矩陣 (Generating Advanced Cross-Tabulation Charts & Heatmaps)...")
    generate_satisfaction_by_resource_by_org_charts(out)
    generate_impression_heatmap(out)

    print(f"\n完成！所有圖表與數據表已儲存至: {os.path.abspath(out.root)}\n")


if __name__ == "__main__":
    main()