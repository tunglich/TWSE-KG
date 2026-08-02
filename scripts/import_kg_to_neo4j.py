"""
Import KG data from CSV files into Neo4j.

Usage:
    python scripts/import_kg_to_neo4j.py \\
        --uri bolt://localhost:7687 \\
        --user neo4j \\
        --password YOUR_PASSWORD \\
        --data-dir data/kg

This script reads:
    data/kg/companies.csv      → Company nodes
    data/kg/supplies_to.csv    → SUPPLIES_TO relationships
    data/kg/competes_with.csv  → COMPETES_WITH relationships

After import, verify with:
    MATCH (n:Company) RETURN count(n);           -- 4512
    MATCH ()-[r:SUPPLIES_TO]->() RETURN count(r);    -- 5509
    MATCH ()-[r:COMPETES_WITH]->() RETURN count(r);  -- 3246
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _safe_float(val) -> float | None:
    """Convert to float, returning None for NaN/missing."""
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_str(val) -> str | None:
    """Convert to str, returning None for NaN/missing."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("", "nan", "NaN") else s


def import_companies(session, df: pd.DataFrame) -> int:
    """Create Company nodes. Returns number of nodes created."""
    count = 0
    for _, row in df.iterrows():
        ticker = _safe_str(row.get("ticker"))
        if not ticker:
            continue
        props = {
            "ticker": ticker,
            "name": _safe_str(row.get("name")) or ticker,
            "pagerank": _safe_float(row.get("pagerank")),
            "betweenness": _safe_float(row.get("betweenness")),
            "theme_pagerank": _safe_float(row.get("theme_pagerank")),
            "theme_degree": _safe_float(row.get("theme_degree")),
        }
        # Remove None values
        props = {k: v for k, v in props.items() if v is not None}
        session.run(
            "MERGE (c:Company {ticker: $ticker}) SET c += $props",
            ticker=ticker,
            props=props,
        )
        count += 1
    return count


def import_supplies_to(session, df: pd.DataFrame) -> int:
    """Create SUPPLIES_TO relationships. Returns number created."""
    count = 0
    for _, row in df.iterrows():
        src = _safe_str(row.get("source"))
        tgt = _safe_str(row.get("target"))
        if not src or not tgt:
            continue
        # Ensure nodes exist
        session.run("MERGE (:Company {ticker: $t})", t=src)
        session.run("MERGE (:Company {ticker: $t})", t=tgt)
        props: dict = {}
        share = _safe_float(row.get("share"))
        if share is not None:
            props["share"] = share
        via = _safe_str(row.get("via"))
        if via:
            props["via"] = via
        src_name = _safe_str(row.get("source_name"))
        if src_name:
            session.run(
                "MATCH (c:Company {ticker: $t}) SET c.name = $n",
                t=src, n=src_name,
            )
        tgt_name = _safe_str(row.get("target_name"))
        if tgt_name:
            session.run(
                "MATCH (c:Company {ticker: $t}) SET c.name = $n",
                t=tgt, n=tgt_name,
            )
        session.run(
            """
            MATCH (a:Company {ticker: $src}), (b:Company {ticker: $tgt})
            MERGE (a)-[r:SUPPLIES_TO]->(b)
            SET r += $props
            """,
            src=src, tgt=tgt, props=props,
        )
        count += 1
    return count


def import_competes_with(session, df: pd.DataFrame) -> int:
    """Create COMPETES_WITH relationships. Returns number created."""
    count = 0
    for _, row in df.iterrows():
        src = _safe_str(row.get("source"))
        tgt = _safe_str(row.get("target"))
        if not src or not tgt:
            continue
        # Ensure nodes exist
        session.run("MERGE (:Company {ticker: $t})", t=src)
        session.run("MERGE (:Company {ticker: $t})", t=tgt)
        props: dict = {}
        via = _safe_str(row.get("via"))
        if via:
            props["via"] = via
        session.run(
            """
            MATCH (a:Company {ticker: $src}), (b:Company {ticker: $tgt})
            MERGE (a)-[r:COMPETES_WITH]->(b)
            SET r += $props
            """,
            src=src, tgt=tgt, props=props,
        )
        count += 1
    return count


def build_indexes(session) -> None:
    """Create indexes for fast lookup."""
    for stmt in [
        "CREATE INDEX company_ticker IF NOT EXISTS FOR (c:Company) ON (c.ticker)",
        "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
    ]:
        try:
            session.run(stmt)
        except Exception as e:
            print(f"  Index warning: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uri",      default="bolt://localhost:7687")
    ap.add_argument("--user",     default="neo4j")
    ap.add_argument("--password", required=True)
    ap.add_argument("--data-dir", default="data/kg")
    ap.add_argument("--batch",    type=int, default=500,
                    help="Rows per transaction (default 500)")
    args = ap.parse_args()

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: neo4j package not installed. Run: pip install neo4j")
        return 1

    data_dir = Path(args.data_dir)
    companies_csv    = data_dir / "companies.csv"
    supplies_csv     = data_dir / "supplies_to.csv"
    competes_csv     = data_dir / "competes_with.csv"

    for p in (companies_csv, supplies_csv, competes_csv):
        if not p.exists():
            print(f"ERROR: {p} not found")
            return 1

    print(f"Connecting to {args.uri} …")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    try:
        with driver.session() as session:
            # Build indexes first
            print("Building indexes …")
            build_indexes(session)

            # Import companies
            print("Importing companies …")
            df_co = pd.read_csv(companies_csv)
            n_co = import_companies(session, df_co)
            print(f"  → {n_co} Company nodes created/updated")

            # Import SUPPLIES_TO
            print("Importing SUPPLIES_TO edges …")
            df_st = pd.read_csv(supplies_csv)
            n_st = import_supplies_to(session, df_st)
            print(f"  → {n_st} SUPPLIES_TO relationships created/updated")

            # Import COMPETES_WITH
            print("Importing COMPETES_WITH edges …")
            df_cw = pd.read_csv(competes_csv)
            n_cw = import_competes_with(session, df_cw)
            print(f"  → {n_cw} COMPETES_WITH relationships created/updated")

            # Verify
            print("\nVerification:")
            for label, expected in [("Company", n_co)]:
                r = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
                actual = r["c"]
                status = "✓" if actual >= expected * 0.95 else "!"
                print(f"  {status} {label} nodes: {actual} (expected ≥ {expected})")
            for rel, expected in [("SUPPLIES_TO", n_st), ("COMPETES_WITH", n_cw)]:
                r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()
                actual = r["c"]
                status = "✓" if actual >= expected * 0.95 else "!"
                print(f"  {status} {rel} edges: {actual} (expected ≥ {expected})")

    finally:
        driver.close()

    print("\nImport complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
