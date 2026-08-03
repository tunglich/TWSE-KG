# LLM Prompt Templates

This document reproduces the exact prompt templates used in the TWSE-KG pipeline.
All prompts were used with **GPT-4o** (API version `2024-08-01-preview`) unless otherwise noted.

---

## Stage 1 — Hierarchical LLM Filtering and Scoring

The Stage 1 pipeline processes raw news articles in two passes:

### Pass 1: Relevance Filter

```
System:
You are a financial news classifier for Taiwan stock market analysis.
Classify whether the following news article is relevant to the financial
performance or stock price of any Taiwan-listed company.

Respond with a single JSON object:
{
  "relevant": true | false,
  "reason": "<one sentence>"
}

User:
Article: {article_text}
```

**Threshold:** Articles with `relevant: false` are discarded (reduces corpus from ~285K to ~119K articles).

### Pass 2: Sentiment Scoring

```
System:
You are a financial sentiment analyst specializing in Taiwan supply chain companies.
Score the sentiment of the following news article for the specified company.

Rules:
- Score range: 1 (very negative) to 100 (very positive), with 50 as neutral.
- Focus on forward-looking financial impact, not general tone.
- Consider supply chain implications: if a customer wins a large order,
  upstream suppliers should receive a moderately positive score.
- If the article is not directly relevant to the company, return 50.

Respond with a single JSON object:
{
  "ticker": "{ticker}",
  "score": <integer 1-100>,
  "direction": "up" | "down" | "neutral",
  "confidence": "high" | "medium" | "low",
  "rationale": "<one sentence>"
}

User:
Company: {company_name} ({ticker})
Article: {article_text}
Date: {article_date}
```

**Output:** Each scored event is stored as `(date, ticker, score, direction, confidence)`.
The `Total_score.csv` file aggregates daily scores per ticker using a confidence-weighted mean.

---

## Stage 3 — Anchor Direction Verification

After computing the KG-propagated Tier-2 scores, a verification pass checks whether
the predicted direction matches the actual open-to-close price movement for the paper's
five anchor stocks (2330, 2345, 3017, 3711, 6515).

```
System:
You are a financial analyst reviewing a sentiment-based stock direction prediction.
Given the predicted sentiment score and the actual price movement, assess whether
the prediction was correct and identify any systematic biases.

Respond with a single JSON object:
{
  "correct": true | false,
  "predicted_direction": "up" | "down",
  "actual_direction": "up" | "down",
  "score": <float>,
  "notes": "<optional one sentence>"
}

User:
Ticker: {ticker}
Date: {date}
Predicted score: {score} (>50 = up, <50 = down)
Open price: {open_price}
Close price: {close_price}
```

---

## Pre-scored Event Cache

To allow reproduction of all downstream results **without re-running the LLM API**,
we provide a pre-scored event cache covering the full test window (2024-01-02 to 2026-03-31).

The cache is the source of the five CSV files in `data/csv/`:

| File | Description |
|------|-------------|
| `Total_score.csv` | Daily confidence-weighted mean score per ticker |
| `TW_sentiment.csv` | Taiwan-sourced articles only |
| `US_sentiment.csv` | US-sourced articles only (used with 1-day lag) |
| `Open.csv` | Adjusted open prices (TWD) |
| `Close.csv` | Adjusted close prices (TWD) |

**To reproduce paper results from the cache (no LLM API required):**

```bash
# Step 1: Place CSV files in data/csv/ (see data/csv/.gitkeep for layout)
# Step 2: Run the full pipeline
python src/compute_from_csv.py

# To reproduce the paper's exact test window (2024-01-02 to 2025-06-30):
python src/compute_from_csv.py --test-start 2024-01-02 --test-end 2025-06-30
```

**To re-run LLM scoring from scratch** (requires OpenAI API key, ~$200 estimated cost):

```bash
# Not included in this repo due to API cost and rate limits.
# Contact the authors for the raw article corpus or scoring scripts.
```

---

## Model and API Details

| Parameter | Value |
|-----------|-------|
| Model | `gpt-4o` |
| API version | `2024-08-01-preview` |
| Temperature | `0.0` (deterministic) |
| Max tokens | `256` (Pass 1), `512` (Pass 2) |
| Batch size | 50 articles per request |
| Total articles scored | ~118,662 (post-filter) |
| Estimated API cost | ~$180–220 USD |

---

## Reproducibility Note

The LLM scoring step introduces non-determinism at the API level even with `temperature=0`,
because OpenAI may update the model weights between API calls. The pre-scored CSV cache
represents the exact scores used in the paper and is the recommended starting point for
reproduction. Differences of ±0.5 score points may occur if re-scoring from scratch.
