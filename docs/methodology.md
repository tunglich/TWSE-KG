# Sentiment-to-Score Pipeline: Mathematical Specification

This document provides the mathematical specification of the two-tier
hierarchical sentiment scoring system described in:

> *Cross-Market Sentiment Propagation via Firm-Level Knowledge Graphs*,
> ICAIF 2026.

---

## Architecture

The pipeline has two parallel sides that merge in the Two-Tier Calibration step.

![Pipeline](pipeline_ieee.png)

**Taiwan-side signal construction** uses Stages $1,\ldots,5$ to convert raw
Taiwanese and U.S. news into per-firm daily sentiment features. **Two-tier
predictive calibration** maps those features into market- and stock-level
scores in the bounded interval $[1,100]$.

---

## Fixed Parameters

All parameters below are fixed **ex ante**: they are set before the
2024-2026Q1 held-out window and are not re-tuned on test data.

| Symbol | Value | Role |
|---|---:|---|
| $\beta$ | 0.25 | Taiwan weight in the Tier-1 composite |
| $\lambda_r$ | 0.35 | Repetition-discount decay rate |
| $\lambda_d$ | 0.46 | Carry-over time-decay rate |
| $\gamma$ | 0.5 | KG hop-decay factor |
| $H$ | 2 | Maximum KG propagation depth |
| $\Delta_{\max}$ | 50 | Single-path exposure cap |
| $W$ | 5 days | Carry-over window, $k=0,\ldots,4$ |
| $N$ | 15 | Repetition-discount lookback window, in trading days |

---

## 3.1 Taiwan News Pipeline

### Stage 1: News Classification and LLM Scoring

Each Taiwanese news item passes through a hierarchical LLM classification and
filtering module. The filter removes routine, sponsored, forwarded, and
cross-source near-duplicate reports of the same event. The LLM assigns:

- a top-level class
  $c \in \{\text{macro, market, company, industry, policy, other}\}$; and
- an anchor sentiment score $S_{\mathrm{raw}} \in [1,100]$, where $50$ is
  neutral.

### Stage 2: KG Supply-Chain Impact Propagation

The proprietary firm-level knowledge graph
$\mathcal{G}=(\mathcal{V},\mathcal{E})$ covers 576 TWSE-listed firms plus
overseas anchor nodes such as suppliers, customers, and competitors. Each
directed edge $e=(a,c)\in\mathcal{E}$ carries an exposure weight $w_{a,c}$
fixed by edge type.

| Edge type | Weight $w_{a,c}$ | Sign convention |
|---|---|---|
| `SUPPLIES_TO` | Revenue-share fraction | Same direction as anchor shock |
| `COMPETES_WITH` | Signed halo weight | Opposite for industry-wide demand; same for supply-chain shocks |
| `PRODUCT_LINE` / `TECH_NODE` | Segment-share fraction | Same direction |

**Eq. (1): path contribution**

$$
\begin{aligned}
\Delta p_{a\to c}
&= S_{\mathrm{raw}} \cdot w_{a,c} \cdot \gamma^h, \\
\gamma &= 0.5 .
\end{aligned}
$$

Propagation is limited to $H=2$ hops.

**Eq. (2): path-level exposure cap**

$$
\Delta p_{a\to c}^{\mathrm{capped}}
=
\mathrm{clip}
\left(
\Delta p_{a\to c},
-\Delta_{\max},
+\Delta_{\max}
\right),
\qquad
\Delta_{\max}=50 .
$$

### Stage 3: Impact Scoring with Decay

#### Repetition Discount

Repeated coverage of the same firm within a 15-trading-day lookback window is
discounted to prevent headline-stuffing. Let $t_i$ index prior appearances of
the same firm.

**Eq. (3): cumulative repetition weight**

$$
\begin{aligned}
W_{\mathrm{rep}}
&= \sum_i \exp\{-\lambda_r(t-t_i)\}, \\
\lambda_r &= 0.35 .
\end{aligned}
$$

**Eq. (4): stale-news discount and adjusted score**

$$
\begin{aligned}
f
&= \frac{1}{1+W_{\mathrm{rep}}}, \qquad f\in(0,1], \\
S_{\mathrm{adj}}
&= 50 + (S_{\mathrm{raw}}-50)\cdot f .
\end{aligned}
$$

#### Carry-Over Window

The adjusted score is carried forward over the event day plus four following
trading days using exponential decay.

**Eq. (5): carry-over-adjusted event score**

$$
\begin{aligned}
S_{\mathrm{final}}
&=
50
+ \sum_{k=0}^{4}
\exp(-\lambda_d k)
\left(S_{t-k,\mathrm{adj}}-50\right), \\
\lambda_d &= 0.46 .
\end{aligned}
$$

The carry-over window is

$$
k \in \{0,1,2,3,4\},
$$

where $k=0$ is the event day. The implied decay weights are

$$
\left\{
e^{-0.46k}
\right\}_{k=0}^{4}
\approx
\{1.00,0.63,0.40,0.25,0.16\}.
$$

The result is clipped to $[1,100]$.

### Stage 4: Aggregation to Daily Market Sentiment

All per-event impact scores are aggregated into a single market-level Taiwan
feature using capitalization weights.

**Eq. (6): Taiwan local market aggregate**

$$
\begin{aligned}
\mathrm{score}^{\mathrm{local}}(t)
&=
50
+ \sum_j
\left(TW_{j,t}-50\right)
w_j^{\mathrm{cap}}, \\
w_j^{\mathrm{cap}}
&=
\frac{\mathrm{cap}_j}
{\sum_{j'} \mathrm{cap}_{j'}} .
\end{aligned}
$$

This output feeds Tier-1 calibration only. It is **not** used directly as a
stock-level score.

### Stage 5: Per-Firm SprintScore

SprintScore consolidates all direct and KG-propagated, decay-adjusted Taiwan
event impacts for firm $j$ on date $t$.

**Eq. (7): firm-level Taiwan event score**

$$
TW_{j,t}
=
\mathrm{clip}_{[1,100]}
\left[
50
+ \sum_{c\in\mathcal{E}_{j,t}}
\omega_{c,j,t}
\left(S_c^{\mathrm{final}}-50\right)
\right].
$$

Here, $\mathcal{E}_{j,t}$ is the set of events timestamped before 08:59
Taipei time on day $t$, and $\omega_{c,j,t}$ is the normalized
direct-relevance weight for event $c$ on firm $j$.

---

## 3.2 U.S. News Pipeline

The U.S. pipeline runs in parallel and produces prior-session scores:

$$
\mathrm{US}_{t-1}
\quad \text{and} \quad
\mathrm{US}_{j,t-1}.
$$

The first is the market-level U.S. score and the second is the stock-level
U.S. score for firm $j$. Both are based on the prior U.S. cash session.

**Stage 1** scores the four U.S. equity indexes (SOX, NDX, SPX, DJI) as the
cash-session anchor using the same LLM classifier. After-hours items are
session-aligned so that only information available before the TWSE open enters
the score.

**Stage 2** identifies U.S. anchors: stories with direct commercial links to
TWSE constituents. These anchors are mapped onto the Taiwan universe via
keyword expansion trained on the KG product-line layer. Taiwanese ADRs (TSM,
UMC) are a special case because their intraday U.S. move is directly
informative.

**Stage 3** ranks the 15 most affected TWSE firms by revenue-share strength
with signed impact scores. A separate LLM verifies anchors, direction, and
ranking before scores enter the U.S. aggregate.

---

## 3.3 Two-Tier Hierarchical Sentiment Scoring System

### Tier 1: Market-Level Score

Tier 1 combines two market-level inputs with a fixed blend weight
$\beta=0.25$.

**Eq. (8): Tier-1 composite**

$$
C_t^{(1)}
=
\beta \cdot \mathrm{score}^{\mathrm{local}}(t)
+ (1-\beta)\cdot \mathrm{US}_{t-1},
\qquad
\beta=0.25 .
$$

A logistic calibration maps the composite to an empirical up-move probability.

**Eq. (9): Tier-1 calibrated probability**

$$
p_t
=
\sigma
\left(
\alpha^{(1)}
+ \rho^{(1)} C_t^{(1)}
\right).
$$

The market-level score rescales this calibrated probability to $[1,100]$.

**Eq. (10): Tier-1 market score**

$$
M_t
=
1 + 99p_t
=
1 + 99\cdot
\sigma
\left(
\alpha^{(1)}
+ \rho^{(1)} C_t^{(1)}
\right).
$$

Values near 100 indicate strongly bullish market conviction; values near 1
indicate bearish conviction; 50 is neutral. Parameters $\alpha^{(1)}$ and
$\rho^{(1)}$ are estimated by maximum-likelihood cross-entropy on
walk-forward training folds.

### Tier 2: Stock-Level Score

For each of the 576 TWSE stocks, Tier 2 combines three intentionally separated
inputs under a non-negative simplex constraint.

**Eq. (11): Tier-2 stock composite**

$$
\begin{aligned}
C_{j,t}^{(2)}
&=
a_j \cdot TW_{j,t}
+ b_j \cdot M_t
+ c_j \cdot \mathrm{US}_{j,t-1}, \\
a_j + b_j + c_j &= 1, \\
a_j,b_j,c_j &\ge 0 .
\end{aligned}
$$

A firm-specific logistic calibration produces the stock-level probability.

**Eq. (12): Tier-2 calibrated probability**

$$
p_{j,t}
=
\sigma
\left(
\alpha_j^{(2)}
+ \rho_j^{(2)} C_{j,t}^{(2)}
\right).
$$

The final stock score rescales this probability to $[1,100]$.

**Eq. (13): final stock sentiment score**

$$
S_{j,t}
=
1 + 99p_{j,t}.
$$

Pool-average source weights are approximately

$$
\bar{a}\approx0.18,
\qquad
\bar{b}\approx0.52,
\qquad
\bar{c}\approx0.30 .
$$

Parameters $(a_j,b_j,c_j)$ and $(\alpha_j^{(2)},\rho_j^{(2)})$ are estimated
per stock using the same walk-forward cross-entropy criterion.

$S_{j,t}$ is the **Final Stock Sentiment Score** shown at the bottom of
Figure 2. It is a stock-up probability rescaled to $[1,100]$.

### Per-Day Decision Flow

On date $t$, the information set is

$$
\mathcal{I}_t
=
\{\text{news items timestamped before 08:59 Taipei time on day }t\}.
$$

The per-day scoring sequence is:

$$
\begin{aligned}
\mathcal{I}_t^{\mathrm{TW}}
&\xrightarrow{\mathrm{Stages}\ 1-5}
TW_{j,t}, \\
\mathcal{I}_t^{\mathrm{TW}}
&\xrightarrow{\mathrm{Stage}\ 4}
\mathrm{score}^{\mathrm{local}}(t), \\
\mathcal{I}_{t-1}^{\mathrm{US}}
&\xrightarrow{\mathrm{U.S.\ pipeline}}
\left(\mathrm{US}_{t-1},\mathrm{US}_{j,t-1}\right), \\
\left(\mathrm{score}^{\mathrm{local}}(t),\mathrm{US}_{t-1}\right)
&\xrightarrow{\mathrm{Tier}\ 1}
M_t, \\
\left(TW_{j,t},M_t,\mathrm{US}_{j,t-1}\right)
&\xrightarrow{\mathrm{Tier}\ 2}
S_{j,t}.
\end{aligned}
$$

$S_{j,t}$ is the input feature for downstream trading decisions, including
long-short portfolio construction and position sizing.

---

## Notation Summary

| Symbol | Definition |
|---|---|
| $t$ | TWSE trading day |
| $j$ | TWSE-listed stock index |
| $c$ | News event index |
| $S_{\mathrm{raw}}$ | Raw LLM anchor sentiment score in $[1,100]$ |
| $S_{\mathrm{adj}}$ | Repetition-discounted score |
| $S_{\mathrm{final}}$ | Carry-over-adjusted final event score |
| $TW_{j,t}$ | Per-firm SprintScore, the Stage-5 output |
| $\mathrm{score}^{\mathrm{local}}(t)$ | Capitalization-weighted Taiwan market aggregate |
| $\mathrm{US}_{t-1}$ | Prior-session U.S. market-level score |
| $\mathrm{US}_{j,t-1}$ | Prior-session U.S. stock-level score for firm $j$ |
| $M_t$ | Tier-1 market-level calibrated score in $[1,100]$ |
| $S_{j,t}$ | Final Stock Sentiment Score in $[1,100]$ |
| $\mathcal{E}_{j,t}$ | Events for firm $j$ in $\mathcal{I}_t$ |
| $\omega_{c,j,t}$ | Normalized direct-relevance weight |
| $w_j^{\mathrm{cap}}$ | Capitalization weight for firm $j$ |
| $w_{a,c}$ | KG edge exposure weight from anchor $a$ to firm $c$ |
| $\sigma(\cdot)$ | Logistic sigmoid function |

