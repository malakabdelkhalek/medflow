#!/bin/bash
# Run all loaders in order
# Usage: bash run_loaders.sh
# Requires: DB running via docker compose up -d

set -e
cd "$(dirname "$0")"

echo "=== Step 1: molecules + CYP (RxNorm + ChEMBL) ==="
python3 load_rxnorm_chembl.py

echo "=== Step 2: ANSM interactions ==="
python3 load_ansm_interactions.py

echo "=== All loaders complete ==="
