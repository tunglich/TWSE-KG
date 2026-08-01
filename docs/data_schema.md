# Data Schema — Sentiment_score_all.xlsx

The single data artifact for the TWSE-KG pipeline. Seven sheets, each
corresponding to a paper table or experiment section.

## Sheet: Table2_MarketLevel

| Column | Type | Description |
|--------|------|-------------|
| Horizon | str | "Same-day nowcast" or "Next-day forecast" |
| F1 | float | F1 score |
| Accuracy(%) | float | Directional accuracy |
| AUC | float | ROC-AUC (same-day only) |

## Sheet: Table3_Prediction

| Column | Type | Description |
|--------|------|-------------|
| Ticker | str | TWSE ticker (e.g. "2330") |
| Company | str | Short company name |
| F1(KG) | float | F1 with KG propagation |
| F1(Direct) | float | F1 with direct sentiment only |
| F1(Wide) | float | F1 with market-wide baseline |
| Acc(%) | float | Directional accuracy |
| AUC | float | ROC-AUC |
| F1_Gain | float | F1(KG) − F1(Direct) |

## Sheet: Table4_Coverage

| Column | Type | Description |
|--------|------|-------------|
| Metric | str | Metric name |
| Value | int/float | Numeric value |

## Sheet: Table6_Backtest

| Column | Type | Description |
|--------|------|-------------|
| Portfolio | str | Portfolio name (kg_ls, kg_long, llm_ls, taiex) |
| Ann.Ret(%) | float | Annualized return |
| Sharpe | float | Sharpe ratio |
| MaxDD(%) | float | Maximum drawdown |
| Turnover(%) | int | Annual turnover rate |
| Excess(%) | float | Excess return over TAIEX (kg_long only) |
| IR | float | Information ratio (kg_long only) |

## Sheet: Ablation_Ladder

| Column | Type | Description |
|--------|------|-------------|
| Rung | str | Ladder rung name (MarketWide, Direct, A1, A2, A3, A4, KG) |
| F1 | float | F1 score for this rung |
| SD | float | Standard deviation across R=20 replicates (A1/A2/A3 only) |
| Reps | int | Number of replicates (20 for shuffle rungs, 1 for deterministic) |

## Sheet: 50_Stock_F1_Coverage

| Column | Type | Description |
|--------|------|-------------|
| Ticker | str | TWSE ticker |
| Name | str | Company short name |
| F1(KG) | float | F1 with KG propagation |
| F1(Direct) | float | F1 with direct sentiment only |
| F1(Wide) | float | F1 with market-wide baseline |
| F1_Gain | float | F1(KG) − F1(Direct) |
| Coverage_Mult | float | KG records / direct records |
| Direct_Records | int | Pre-propagation record count |
| KG_Records | int | Post-propagation record count |

## Sheet: Pipeline_Params

| Column | Type | Description |
|--------|------|-------------|
| Parameter | str | Parameter name |
| Value | str/int/float | Parameter value |

## File Location

```
data/Sentiment_score_all.xlsx
```

Regenerate with: `python scripts/export_xlsx.py`
