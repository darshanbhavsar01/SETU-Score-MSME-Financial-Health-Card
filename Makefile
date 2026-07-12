# SETU Score — developer workflow (CLAUDE.md §4).
# On Windows (no `make`), run the underlying commands directly, e.g.
#   python -m datagen.generate && python -m datagen.validate_data
#
# PYTHON can be overridden:  make data PYTHON=python3

PYTHON ?= python

.PHONY: help data train test demo deploy clean

help:
	@echo "SETU Score targets:"
	@echo "  make data    - generate synthetic dataset (parquet + sqlite) and validate it"
	@echo "  make train   - train the optional ML risk ranker (step 7)"
	@echo "  make test    - validate data + run pytest (step 5+)"
	@echo "  make demo    - bring the full stack up locally via docker compose (step 9)"
	@echo "  make deploy  - build image + deploy to Cloud Run (step 13)"
	@echo "  make clean   - remove generated data artifacts"

# Step 1: deterministic synthetic data + invariant checks.
data:
	$(PYTHON) -m datagen.generate
	$(PYTHON) -m datagen.validate_data

# Step 7 (optional ML layer). Placeholder until model/train.py lands.
train:
	$(PYTHON) -m model.train

# Step 5+: data validation must pass before the test suite runs.
test: data
	$(PYTHON) -m pytest -q

# Step 9: one-command local stack.
demo:
	docker compose up --build

# Step 13: Cloud Run deploy (see deploy/cloudrun.md).
deploy:
	@echo "See deploy/cloudrun.md — implemented in build-order step 10."

clean:
	$(PYTHON) -c "import shutil, pathlib; \
from backend.app.config import PARQUET_DIR, SQLITE_PATH; \
shutil.rmtree(PARQUET_DIR, ignore_errors=True); \
pathlib.Path(SQLITE_PATH).unlink(missing_ok=True); \
print('cleaned generated data')"
