# TWSE-KG Pipeline Makefile
# ========================
# Reproduce all paper results in the correct stage order.
#
# Usage:
#   make all        — run full pipeline (stages 1-5)
#   make verify     — verify all numbers against paper anchors
#   make smoke      — quick smoke test
#   make data       — regenerate Sentiment_score_all.xlsx
#   make ablation   — run ablation kit selftests
#   make clean      — remove cached files

PYTHON ?= python3

.PHONY: all verify smoke data ablation clean stage1 stage2 stage3 stage4 stage5

all: stage1 stage2 stage3 stage4 stage5
	@echo ""
	@echo "========================================"
	@echo "  All pipeline stages completed."
	@echo "========================================"

stage1:
	$(PYTHON) src/stage1_market_level.py

stage2:
	$(PYTHON) src/stage2_firm_level.py

stage3:
	$(PYTHON) src/stage3_ablation.py

stage4:
	$(PYTHON) src/stage4_backtest.py

stage5:
	$(PYTHON) src/stage5_50stock.py

verify:
	$(PYTHON) src/stage1_market_level.py --verify
	$(PYTHON) src/stage2_firm_level.py --verify
	$(PYTHON) src/stage3_ablation.py --verify
	$(PYTHON) src/stage4_backtest.py --verify
	$(PYTHON) src/stage5_50stock.py --verify
	@echo ""
	@echo "All verifications passed ✓"

smoke:
	$(PYTHON) smoke_test.py

data:
	$(PYTHON) scripts/export_xlsx.py

ablation:
	$(PYTHON) scripts/run_ablation_kit.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
