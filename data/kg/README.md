# Knowledge Graph Data — Taiwan Supply Chain

This directory contains the complete Knowledge Graph (KG) data exported from the Neo4j database used in the ICAIF 2026 paper. The data represents Taiwan-listed company supply-chain and competitive relationships.

## Files

| File | Rows | Description |
|------|------|-------------|
| `companies.csv` | 4,512 | Company nodes with ticker, name, and centrality metrics |
| `supplies_to.csv` | 5,509 | `SUPPLIES_TO` edges (supplier → customer) |
| `competes_with.csv` | 3,246 | `COMPETES_WITH` edges (peer competition) |

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

- **Total nodes**: 4,512 companies
- **SUPPLIES_TO edges**: 5,509 (directed, supplier → customer)
- **COMPETES_WITH edges**: 3,246 (undirected, stored as directed pairs)
- **Mean out-degree (SUPPLIES_TO)**: ~2.4 per company
- **Coverage**: 33 industry sectors

## Node Universe: 576 TWSE vs 4,512 Total

The paper reports **576 Taiwan-listed companies** as the scoring universe. The KG contains **4,512 nodes** in total. This discrepancy is intentional and reflects the graph propagation design:

| Node type | Count | Role |
|-----------|-------|------|
| TWSE/OTC-listed companies (scored) | 576 | Tier-2 scoring targets; receive daily SprintScore |
| Overseas anchors (US, JP, KR, CN) | ~3,936 | Propagation sources only; not scored themselves |
| **Total KG nodes** | **4,512** | All nodes used in graph propagation |

Overseas anchors include companies such as ASML, Apple, NVIDIA, Samsung, and CATL. When a US company (e.g. Apple) has a strong earnings day, the sentiment propagates through `SUPPLIES_TO` edges to its Taiwanese suppliers (e.g. Hon Hai, Largan). The `is_twse_listed` column in `companies.csv` distinguishes the two groups.

The `companies.csv` schema includes an `is_twse_listed` flag (1 = TWSE/OTC listed, 0 = overseas anchor). The pipeline's `--tw50` and `--full-universe` modes both restrict **scoring** to TWSE-listed nodes; overseas nodes are used only as propagation sources.

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
