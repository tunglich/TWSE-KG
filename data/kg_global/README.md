# Global Supply-Chain Knowledge Graph (multi-market, 2026-10-20)

Companion to `data/kg/` (the Taiwan-only propagation graph used by the pipeline). This directory exports the full
multi-market graph behind the web application's supply-chain pages: Taiwan-listed companies plus overseas companies
(U.S., Japan, Korea, mainland China / Hong Kong, Europe and others), compiled from company disclosures, filings and
curated supplier / customer / competitor / investment profiles. **It is not used by the paper's experiments.**

## Files

| File | Rows | Description |
|---|---|---|
| `nodes.csv` | 5,500 | One row per company page (`key`, display `name` = "Chinese (English, ticker)", `industry`, `is_tw_listed`) |
| `supplies_to.csv` | 66,351 | Supplier → customer edges; 53,575 have both ends resolved to a node `key` |
| `competes_with.csv` | 5,272 | Named competitor pairs (with the battlefield when known) |
| `investments.csv` | 8,054 | Parent → investee (subsidiary / affiliate) with ownership %; 630 investees resolved to a node |

## Schema

- `nodes.csv`: `key` (4-digit code for Taiwan-listed companies; ticker or normalised name for overseas companies), `name`,
  `industry`, `is_tw_listed` (1/0), `has_page` (always 1).
- `supplies_to.csv`: `source_key`, `source_name`, `target_key`, `target_name`, `share_pct` (customer's share of the
  supplier's revenue when disclosed or estimated), `via` (product / service), `origin`
  (`customer_list_of_source` = from the supplier's customer list; `supplier_list_of_target` = from the customer's supplier list).
  An empty key means the counterparty is not a node in this graph (e.g. a private supplier or a customer segment).
- `competes_with.csv`: `source_key`, `source_name`, `target_key`, `target_name`, `battlefield`.
- `investments.csv`: `parent_key`, `parent_name`, `investee_key`, `investee_name`, `share_pct`, `relation`.

## Notes

- Revenue / procurement shares are mostly estimates and should be read as relative magnitudes.
- The same company may appear under several spellings in source profiles; they are merged into a single node
  (e.g. `NVDA` = Nvidia = its Chinese name). Display names follow the convention "Taiwanese common Chinese name (English, ticker)".
