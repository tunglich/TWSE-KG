# Knowledge Graph Data — Taiwan Supply Chain

This directory contains the Taiwan propagation Knowledge Graph (KG) exported from the Neo4j database behind the ICAIF 2026 paper. The data represents Taiwan-listed company supply-chain and competitive relationships.

## Files

| File | Rows | Description |
|------|------|-------------|
| `companies.csv` | 4,792 | Company nodes with ticker, name, and centrality metrics |
| `supplies_to.csv` | 7,377 | `SUPPLIES_TO` edges (supplier → customer) |
| `competes_with.csv` | 1,725 | `COMPETES_WITH` edges (peer competition) |

## Schema

### `companies.csv`

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | string | 4-digit TWSE/OTC ticker (e.g. `2330`) |
| `name` | string | Company name (Traditional Chinese) |
| `pagerank` | float | PageRank centrality score |
| `betweenness` | float | Betweenness centrality score |
| `theme_pagerank` | float | Theme-level PageRank |
| `theme_degree` | int | Number of theme connections |

### `supplies_to.csv`

| Column | Type | Description |
|--------|------|-------------|
| `source` | string | Supplier ticker |
| `source_name` | string | Supplier name |
| `target` | string | Customer ticker |
| `target_name` | string | Customer name |
| `share` | float | Revenue share % (optional) |
| `via` | string | Product/service description |

### `competes_with.csv`

| Column | Type | Description |
|--------|------|-------------|
| `source` | string | Company A ticker |
| `source_name` | string | Company A name |
| `target` | string | Company B ticker |
| `target_name` | string | Company B name |
| `via` | string | Competitive overlap description |

## Statistics

- **Total nodes**: 4,792 companies (1,105 with `is_twse_listed = 1`)
- **SUPPLIES_TO edges**: 7,377 (directed, supplier → customer)
- **COMPETES_WITH edges**: 1,725 (undirected, stored as directed pairs)
- **Mean out-degree (SUPPLIES_TO)**: ~4.6 per supplier
- **Coverage**: 33 industry sectors

## Node Universe

The final paper scores **1,179 Taiwan-listed firms** (TWSE/TPEx) and uses a multi-market KG snapshot of
**8,127 nodes and 40,237 de-duplicated edges** (September 30, 2026; Table 1(b)). The three files in this directory are
the Taiwan propagation edge list consumed by the pipeline; the full multi-market graph is in `data/kg_global/`.

| Node type | Role |
|-----------|------|
| TWSE/TPEx-listed companies (`is_twse_listed = 1`) | Tier-2 scoring targets; receive daily SprintScore |
| Other nodes (`is_twse_listed = 0`) | Propagation sources / themes only; not scored themselves |

Overseas anchors include companies such as ASML, Apple, NVIDIA, Samsung, and CATL. When a U.S. company (e.g. Apple) has a
strong earnings day, the sentiment propagates through `SUPPLIES_TO` edges to its Taiwanese suppliers (e.g. Hon Hai, Largan).
The pipeline's `--tw50` and `--full-universe` modes both restrict **scoring** to Taiwan-listed nodes; other nodes are used
only as propagation sources.

## Version note (updated 2026-10-20)

The files in this directory were refreshed on 2026-10-20 with the current production KG:

| | Paper snapshot (commit `720561f`) | 2026-10-20 |
|---|---|---|
| Nodes | 4,512 | 4,792 (+280 Taiwan-listed companies that gained edges) |
| `SUPPLIES_TO` | 5,509 | 7,377 (new edges from company disclosures, filings and analyst reports; directions re-verified) |
| `COMPETES_WITH` | 3,246 | 1,725 (generic "same-industry" pairs removed; only named head-to-head competitors kept) |

- Edges whose counterparty has no Taiwan ticker (overseas companies) are not in these three files; see `data/kg_global/` for the full multi-market graph.
- Centrality columns (`pagerank`, `betweenness`, `theme_*`) are from the paper snapshot and are blank for the 280 newly added nodes.
- The paper's reported results are reproduced from the cached scores in `data/Sentiment_score_all.xlsx` (`python run_experiments.py --verify` still passes). To use the exact KG of the paper, check out commit `720561f`.

## Rebuilding the Neo4j Database

### Prerequisites

- Neo4j Desktop ≥ 5.x or Neo4j Community Edition
- Python 3.9+ with `neo4j` package: `pip install neo4j`

### Step 1: Create a new database

In Neo4j Desktop, create a new DBMS (e.g. `TWSE-KG`) and start it.

### Step 2: Import nodes and edges

Run the provided import script:

```bash
python scripts/import_kg_to_neo4j.py \
    --uri bolt://localhost:7687 \
    --user neo4j \
    --password YOUR_PASSWORD \
    --data-dir data/kg
```

This script will:
1. Create `Company` nodes with all properties
2. Create `SUPPLIES_TO` relationships with `share` and `via` properties
3. Create `COMPETES_WITH` relationships with `via` property
4. Build indexes on `ticker` and `name`

### Step 3: Verify

```cypher
MATCH (n:Company) RETURN count(n);          // → 4512
MATCH ()-[r:SUPPLIES_TO]->() RETURN count(r);   // → 5509
MATCH ()-[r:COMPETES_WITH]->() RETURN count(r); // → 3246
```

## Usage in the Pipeline

The computation pipeline (`src/compute_from_csv.py`) reads KG edges directly from these CSV files — **no running Neo4j instance is required** for reproducing paper results:

```python
from lib.pipeline import load_pipeline_results
results = load_pipeline_results()  # reads data/kg/*.csv automatically
```

The Neo4j database is used for interactive graph exploration and the web application (`custanalyz-english`).
