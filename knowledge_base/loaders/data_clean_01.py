import pandas as pd
import re
from collections import defaultdict
from pathlib import Path
import os

# ============================================================
# CONFIG
# ============================================================
BASE = Path(__file__).resolve().parents[2]
INPUT_CSV = BASE / "knowledge_base" / "sources" / "dataset" / "interactions_grouped_by_class.csv"
OUTPUT_DIR = BASE / "knowledge_base" / "graph"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 1 — LOAD
# ============================================================
df = pd.read_csv(INPUT_CSV)
print(f" Loaded: {len(df)} rows")

# ============================================================
# STEP 2 — CLEAN CLASSES
# ============================================================
def clean_class(name):
    if pd.isna(name):
        return None
    name = str(name).strip()
    if name.lower() in ["inconnue", "unknown", "nan", "", "none"]:
        return None
    name = re.sub(r"\s*\[(EPC|VA|MoA|PE|CS)\]\s*", "", name).strip()
    name = name.title()
    return name if len(name) > 2 else None

df["Classe_Clean"] = df["Classe_Finale"].apply(clean_class)
df_clean = df[df["Classe_Clean"].notna()].copy()
print(f" Valid classes after cleaning: {len(df_clean)}")
print(f"  Dropped: {len(df) - len(df_clean)} rows (Inconnue/unknown)")

# ============================================================
# STEP 3 — PARSE DRUG LISTS
# ============================================================
def parse_drugs(cell):
    if pd.isna(cell):
        return []
    return [d.strip().lower() for d in str(cell).split(",") if d.strip()]

df_clean["drug_list"] = df_clean["Medicaments"].apply(parse_drugs)

# ============================================================
# STEP 4 — SEVERITY
# ============================================================
SEVERITY_PATTERNS = {
    "CONTRAINDICATED": r"contraindicated|do not use|must not",
    "MAJOR":           r"major|serious|severe|life.threatening",
    "MODERATE":        r"moderate|caution|monitor closely",
    "MINOR":           r"minor|minimal|unlikely",
}

def extract_severity(text):
    if pd.isna(text):
        return "UNKNOWN"
    t = str(text).lower()
    for level, pat in SEVERITY_PATTERNS.items():
        if re.search(pat, t):
            return level
    return "UNKNOWN"

df_clean["severity"] = df_clean["Interactions"].apply(extract_severity)

# ============================================================
# STEP 5 — BUILD CLASS→CLASS EDGES
# ============================================================
drug_to_class = {}
for _, row in df_clean.iterrows():
    for drug in row["drug_list"]:
        drug_to_class[drug] = row["Classe_Clean"]

class_pairs = defaultdict(lambda: {"count": 0, "severity": set(), "drugs": set()})
SEVERITY_ORDER = ["CONTRAINDICATED", "MAJOR", "MODERATE", "MINOR", "UNKNOWN"]

for _, row in df_clean.iterrows():
    class_a  = row["Classe_Clean"]
    text     = str(row.get("Interactions", "")).lower()
    severity = row["severity"]
    for drug, class_b in drug_to_class.items():
        if class_b != class_a and drug in text:
            key = tuple(sorted([class_a, class_b]))
            class_pairs[key]["count"]    += 1
            class_pairs[key]["severity"].add(severity)
            class_pairs[key]["drugs"].add(drug)

edges = []
for (class_a, class_b), data in class_pairs.items():
    top = next((s for s in SEVERITY_ORDER if s in data["severity"]), "UNKNOWN")
    edges.append({
        "source":       class_a,
        "target":       class_b,
        "weight":       data["count"],
        "severity":     top,
        "shared_drugs": ", ".join(list(data["drugs"])[:5]),
    })

edges_df = pd.DataFrame(edges).sort_values("weight", ascending=False)

# ============================================================
# STEP 6 — SAVE nodes.csv + edges.csv
# ============================================================
nodes_df = df_clean[["Classe_Clean", "Nombre_Medicaments", "severity"]].rename(
    columns={"Classe_Clean": "id", "Nombre_Medicaments": "drug_count"}
).drop_duplicates("id")

nodes_path = rf"{OUTPUT_DIR}\nodes.csv"
edges_path = rf"{OUTPUT_DIR}\edges.csv"

nodes_df.to_csv(nodes_path, index=False)
edges_df.to_csv(edges_path, index=False)

# ============================================================
# SUMMARY
# ============================================================
print(f"\n Saved:")
print(f"   → {nodes_path} ({len(nodes_df)} nodes)")
print(f"   → {edges_path} ({len(edges_df)} edges)")
print(f"\n Severity breakdown:")
print(edges_df["severity"].value_counts().to_string())
print(f"\n Top 5 strongest interactions:")
print(edges_df[["source","target","weight","severity"]].head(5).to_string(index=False))
print(f"\n Cleaning done — run 02_load_to_age.py when ready to load into PostgreSQL")