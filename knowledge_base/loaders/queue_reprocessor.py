"""
Reprocess unresolved brand queue.

Reads unresolved_review_queue.csv and attempts to resolve brand names to INNs
using the normalize_brand module. Generates two outputs:
  - resolved_brands.csv (successfully mapped)
  - still_unresolved_brands.csv (still can't resolve)
"""

import csv
import os
import sys
from pathlib import Path

# Add loaders directory to path for normalize_brand import
sys.path.insert(0, os.path.dirname(__file__))
from normalize_brand import resolve_brand_to_inn

QUEUE_PATH = os.path.join(
    os.path.dirname(__file__), "../sources/unresolved_review_queue.csv"
)
MAPPING_PATH = os.path.join(
    os.path.dirname(__file__), "../sources/dataset/tunisian_brand_mapping_clean.csv"
)
OUTPUT_DIR = os.path.dirname(QUEUE_PATH)

resolved_count = 0
unresolved_count = 0
resolved_rows = []
unresolved_rows = []

print(f"Reprocessing brand queue from {QUEUE_PATH}...")

if not os.path.exists(QUEUE_PATH):
    print(f"Queue file not found: {QUEUE_PATH}")
    sys.exit(1)

with open(QUEUE_PATH, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    
    for row in reader:
        brand_name = row.get("brand_name", "").strip()
        full_label = row.get("full_label", "").strip()
        
        # Try to resolve the brand
        inn = resolve_brand_to_inn(brand_name or full_label, MAPPING_PATH)
        
        if inn:
            # Success: add to resolved list
            resolved_row = row.copy()
            resolved_row["resolved_inn"] = inn
            resolved_row["resolution_method"] = "normalize_brand.resolve_brand_to_inn"
            resolved_rows.append(resolved_row)
            resolved_count += 1
        else:
            # Still unresolved
            unresolved_rows.append(row)
            unresolved_count += 1

# Write resolved brands
resolved_path = os.path.join(OUTPUT_DIR, "resolved_brands.csv")
if resolved_rows:
    with open(resolved_path, "w", newline="", encoding="utf-8") as f:
        fieldnames_out = fieldnames + ["resolved_inn", "resolution_method"]
        writer = csv.DictWriter(f, fieldnames=fieldnames_out)
        writer.writeheader()
        writer.writerows(resolved_rows)
    print(f"\n✓ Resolved: {resolved_count}")
    print(f"  Output: {resolved_path}")
else:
    print(f"\n✗ No brands resolved")

# Write still unresolved brands
unresolved_path = os.path.join(OUTPUT_DIR, "still_unresolved_brands.csv")
if unresolved_rows:
    with open(unresolved_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unresolved_rows)
    print(f"✗ Still unresolved: {unresolved_count}")
    print(f"  Output: {unresolved_path}")
else:
    print(f"✓ All brands resolved!")

print(f"\nTotal processed: {resolved_count + unresolved_count}")
