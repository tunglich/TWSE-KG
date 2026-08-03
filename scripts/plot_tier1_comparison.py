"""
視覺化：全量模式 vs Top-54 模式在 Tier-1 市場級分類的差異
生成三張圖：
  1. F1 / Acc / AUC 三指標橫向比較（含論文值）
  2. 市場情緒信號時序圖（Top-54 vs 全量 vs TAIEX 實際方向）
  3. 每日預測正確率滾動平均（30日）
"""
from __future__ import annotations
import json, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── 載入兩份結果 ──────────────────────────────────────────────────────────
top54 = json.load(open("/tmp/pipeline_results.json"))
full  = json.load(open("/tmp/pipeline_results_full.json"))

# ── 論文值 ────────────────────────────────────────────────────────────────
PAPER = {"f1": 0.7357, "acc": 0.6813, "auc": 0.7170}

# ── 顏色設定 ──────────────────────────────────────────────────────────────
C_TOP54  = "#4C72B0"   # 藍
C_FULL   = "#DD8452"   # 橙
C_PAPER  = "#55A868"   # 綠
C_TAIEX  = "#C44E52"   # 紅

# ═══════════════════════════════════════════════════════════════════════════
# 圖 1：三指標橫向比較（grouped bar）
# ═══════════════════════════════════════════════════════════════════════════
fig1, ax = plt.subplots(figsize=(10, 5.5))
fig1.patch.set_facecolor("#F8F9FA")
ax.set_facecolor("#F8F9FA")

metrics = ["F1", "Acc", "AUC"]
keys    = ["f1", "acc", "auc"]
t2_54   = top54["table2"]
t2_full = full["table2"]

vals_54   = [t2_54[k]   for k in keys]
vals_full = [t2_full[k] for k in keys]
vals_paper= [PAPER[k]   for k in keys]

x     = np.arange(len(metrics))
width = 0.22

bars1 = ax.bar(x - width,     vals_54,    width, label=f"Top-54 mode",  color=C_TOP54,  alpha=0.88, zorder=3)
bars2 = ax.bar(x,             vals_full,  width, label=f"Full-universe (1,878 stocks)", color=C_FULL,  alpha=0.88, zorder=3)
bars3 = ax.bar(x + width,     vals_paper, width, label="Paper (ICAIF 2026)", color=C_PAPER, alpha=0.88, zorder=3)

# 數值標籤
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.005,
                f"{h:.4f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(metrics, fontsize=13)
ax.set_ylim(0.55, 0.88)
ax.set_ylabel("Score", fontsize=12)
ax.set_title("Tier-1 Market-Level Classification: Top-54 vs Full-Universe vs Paper",
             fontsize=13, fontweight="bold", pad=14)
ax.legend(fontsize=10, loc="upper left")
ax.grid(axis="y", alpha=0.4, zorder=0)
ax.spines[["top","right"]].set_visible(False)

# 差異標注箭頭（F1）
delta_f1 = vals_full[0] - vals_54[0]
ax.annotate(f"Δ={delta_f1:+.4f}\n(全量更接近論文)",
            xy=(x[0], vals_full[0] + 0.012),
            xytext=(x[0] + 0.55, vals_full[0] + 0.055),
            arrowprops=dict(arrowstyle="->", color="#333", lw=1.2),
            fontsize=9, color="#333", ha="center")

plt.tight_layout()
out1 = REPO_ROOT / "docs" / "tier1_metrics_comparison.png"
out1.parent.mkdir(exist_ok=True)
fig1.savefig(out1, dpi=150, bbox_inches="tight")
print(f"  Saved: {out1}")

# ═══════════════════════════════════════════════════════════════════════════
# 重新計算時序資料（需要跑 pipeline）
# ═══════════════════════════════════════════════════════════════════════════
import pandas as pd
from sklearn.metrics import f1_score

DEFAULT_CSV_DIR = Path("/home/ubuntu/upload/csv")
DEFAULT_TW50    = Path("/home/ubuntu/upload/pasted_file_bD0Hmu_tw50_backtest_summary.csv")
DEFAULT_INDEX   = Path("/home/ubuntu/upload/pasted_file_qhjAjn_Index.csv")
TEST_START = "2024-01-01"
TEST_END   = "2026-03-31"
BETA = 0.25

tw50_df = pd.read_csv(DEFAULT_TW50)
top50 = [str(t).zfill(4) for t in tw50_df["ticker"].astype(str).str.strip()]

def load_csv(path, tickers, start, end):
    df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    df.columns = [str(c).strip().zfill(4) if str(c).strip().isdigit() and len(str(c).strip()) <= 4
                  else str(c).strip() for c in df.columns]
    if tickers is not None:
        keep = [t for t in tickers if t in df.columns]
        df = df[keep]
    return df.loc[start:end].astype(float)

print("  Loading data for time-series plot...")
total_54   = load_csv(DEFAULT_CSV_DIR / "Total_score.csv", top50, TEST_START, TEST_END)
total_full = load_csv(DEFAULT_CSV_DIR / "Total_score.csv", None,  TEST_START, TEST_END)
us_54      = load_csv(DEFAULT_CSV_DIR / "US_sentiment.csv", top50, TEST_START, TEST_END)
us_full    = load_csv(DEFAULT_CSV_DIR / "US_sentiment.csv", None,  TEST_START, TEST_END)

idx_df = pd.read_csv(DEFAULT_INDEX, parse_dates=["日期"], index_col="日期").sort_index()
taiex  = idx_df["TWA00"].astype(float).loc[TEST_START:TEST_END]
taiex_dir = (taiex.diff() > 0).astype(int)

# 計算 Tier-1 信號
top50_j_54   = [i for i, c in enumerate(total_54.columns)   if c in top50]
top50_j_full = [i for i, c in enumerate(total_full.columns) if c in top50]

# 對齊所有 DataFrame 的日期
common_dates = total_54.index.intersection(us_54.index).intersection(total_full.index).intersection(us_full.index)
total_54   = total_54.reindex(common_dates)
total_full = total_full.reindex(common_dates)
us_54      = us_54.reindex(common_dates)
us_full    = us_full.reindex(common_dates)

top50_j_54   = [i for i, c in enumerate(total_54.columns)   if c in top50]
top50_j_full = [i for i, c in enumerate(total_full.columns) if c in top50]

tw_mkt_54   = np.nanmean(total_54.values[:, top50_j_54],   axis=1)
tw_mkt_full = np.nanmean(total_full.values[:, top50_j_full], axis=1)

us_mkt_54   = np.nanmean(us_54.values,   axis=1)
us_mkt_full = np.nanmean(us_full.values, axis=1)

# 填補 NaN
us_mkt_54   = np.where(np.isnan(us_mkt_54),   50.0, us_mkt_54)
us_mkt_full = np.where(np.isnan(us_mkt_full), 50.0, us_mkt_full)

tier1_54   = BETA * tw_mkt_54   + (1 - BETA) * us_mkt_54
tier1_full = BETA * tw_mkt_full + (1 - BETA) * us_mkt_full

dates = pd.to_datetime(common_dates)

# 對齊 TAIEX
common = dates[dates.isin(taiex_dir.index)]
t1_54_s   = pd.Series(tier1_54,   index=dates).reindex(common)
t1_full_s = pd.Series(tier1_full, index=dates).reindex(common)
taiex_s   = taiex_dir.reindex(common)

pred_54   = (t1_54_s   > 50).astype(int)
pred_full = (t1_full_s > 50).astype(int)

# 每日正確率（1=正確，0=錯誤）
correct_54   = (pred_54   == taiex_s).astype(float)
correct_full = (pred_full == taiex_s).astype(float)

# 30 日滾動 F1（用 rolling accuracy 近似）
roll_acc_54   = correct_54.rolling(30,   min_periods=15).mean()
roll_acc_full = correct_full.rolling(30, min_periods=15).mean()

# ═══════════════════════════════════════════════════════════════════════════
# 圖 2：市場情緒信號時序 + 滾動準確率
# ═══════════════════════════════════════════════════════════════════════════
fig2 = plt.figure(figsize=(14, 9))
fig2.patch.set_facecolor("#F8F9FA")
gs = GridSpec(3, 1, figure=fig2, hspace=0.45)

# 上圖：Tier-1 信號值
ax1 = fig2.add_subplot(gs[0])
ax1.set_facecolor("#F8F9FA")
ax1.plot(common, t1_54_s,   color=C_TOP54, lw=1.2, alpha=0.85, label="Top-54 Tier-1 signal")
ax1.plot(common, t1_full_s, color=C_FULL,  lw=1.2, alpha=0.85, label="Full-universe Tier-1 signal")
ax1.axhline(50, color="#999", lw=0.8, ls="--", label="Threshold (50)")
ax1.fill_between(common, t1_54_s, t1_full_s, alpha=0.12, color="#9467bd", label="Difference")
ax1.set_ylabel("Tier-1 Score", fontsize=10)
ax1.set_title("Tier-1 Market Sentiment Signal: Top-54 vs Full-Universe", fontsize=12, fontweight="bold")
ax1.legend(fontsize=8.5, loc="upper right", ncol=2)
ax1.grid(alpha=0.3); ax1.spines[["top","right"]].set_visible(False)

# 中圖：TAIEX 實際漲跌
ax2 = fig2.add_subplot(gs[1])
ax2.set_facecolor("#F8F9FA")
taiex_ret = taiex.pct_change().reindex(common) * 100
ax2.bar(common, taiex_ret, color=np.where(taiex_ret >= 0, "#2ca02c", "#d62728"),
        alpha=0.6, width=1.5, label="TAIEX daily return (%)")
ax2.set_ylabel("TAIEX Return (%)", fontsize=10)
ax2.set_title("TAIEX Daily Return (Ground Truth)", fontsize=11, fontweight="bold")
ax2.legend(fontsize=8.5); ax2.grid(alpha=0.3); ax2.spines[["top","right"]].set_visible(False)

# 下圖：30日滾動準確率
ax3 = fig2.add_subplot(gs[2])
ax3.set_facecolor("#F8F9FA")
ax3.plot(common, roll_acc_54   * 100, color=C_TOP54, lw=1.5, label=f"Top-54  (overall acc={correct_54.mean()*100:.1f}%)")
ax3.plot(common, roll_acc_full * 100, color=C_FULL,  lw=1.5, label=f"Full-universe (overall acc={correct_full.mean()*100:.1f}%)")
ax3.axhline(50, color="#999", lw=0.8, ls="--", label="Random baseline (50%)")
ax3.fill_between(common, roll_acc_54*100, roll_acc_full*100,
                 where=(roll_acc_full > roll_acc_54), alpha=0.15, color=C_FULL,  label="Full > Top-54")
ax3.fill_between(common, roll_acc_54*100, roll_acc_full*100,
                 where=(roll_acc_full <= roll_acc_54), alpha=0.15, color=C_TOP54, label="Top-54 ≥ Full")
ax3.set_ylabel("30-day Rolling Accuracy (%)", fontsize=10)
ax3.set_title("30-Day Rolling Prediction Accuracy", fontsize=11, fontweight="bold")
ax3.legend(fontsize=8.5, loc="lower right", ncol=2)
ax3.grid(alpha=0.3); ax3.spines[["top","right"]].set_visible(False)
ax3.set_ylim(30, 85)

plt.suptitle("Tier-1 Classification: Top-54 vs Full-Universe (2024-01 to 2026-03)",
             fontsize=13, fontweight="bold", y=1.01)

out2 = REPO_ROOT / "docs" / "tier1_timeseries_comparison.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"  Saved: {out2}")

# ═══════════════════════════════════════════════════════════════════════════
# 圖 3：信號差異分佈（histogram）
# ═══════════════════════════════════════════════════════════════════════════
fig3, axes = plt.subplots(1, 2, figsize=(12, 5))
fig3.patch.set_facecolor("#F8F9FA")

# 左：信號差異分佈
diff = (t1_full_s - t1_54_s).dropna()
ax = axes[0]
ax.set_facecolor("#F8F9FA")
ax.hist(diff, bins=40, color="#9467bd", alpha=0.75, edgecolor="white", lw=0.5)
ax.axvline(0,           color="#333", lw=1.2, ls="--", label="Zero")
ax.axvline(diff.mean(), color=C_FULL, lw=1.5, ls="-",  label=f"Mean={diff.mean():+.3f}")
ax.set_xlabel("Full-universe − Top-54 signal difference", fontsize=10)
ax.set_ylabel("Count (days)", fontsize=10)
ax.set_title("Distribution of Signal Difference\n(Full-universe − Top-54)", fontsize=11, fontweight="bold")
ax.legend(fontsize=9); ax.grid(alpha=0.3); ax.spines[["top","right"]].set_visible(False)

# 右：月度準確率對比
monthly_acc_54   = correct_54.resample("ME").mean() * 100
monthly_acc_full = correct_full.resample("ME").mean() * 100
months = monthly_acc_54.index
x = np.arange(len(months))
w = 0.35
ax = axes[1]
ax.set_facecolor("#F8F9FA")
ax.bar(x - w/2, monthly_acc_54.values,   w, color=C_TOP54, alpha=0.85, label="Top-54")
ax.bar(x + w/2, monthly_acc_full.values, w, color=C_FULL,  alpha=0.85, label="Full-universe")
ax.axhline(50, color="#999", lw=0.8, ls="--")
ax.set_xticks(x)
ax.set_xticklabels([d.strftime("%y-%m") for d in months], rotation=45, ha="right", fontsize=7.5)
ax.set_ylabel("Monthly Accuracy (%)", fontsize=10)
ax.set_title("Monthly Prediction Accuracy\nTop-54 vs Full-Universe", fontsize=11, fontweight="bold")
ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3); ax.spines[["top","right"]].set_visible(False)

plt.tight_layout()
out3 = REPO_ROOT / "docs" / "tier1_signal_distribution.png"
fig3.savefig(out3, dpi=150, bbox_inches="tight")
print(f"  Saved: {out3}")

print("\nAll plots saved.")
