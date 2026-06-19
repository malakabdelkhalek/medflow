import pandas as pd
import requests
import time
from tqdm import tqdm

# ============================================================
# 1. LOAD YOUR FILES
# ============================================================
BASE = r"C:\Users\arijk\Desktop\medflow"  

interactions = pd.read_csv(rf"{BASE}\knowledge_base\sources\dataset\interactions_fda_clean.csv")
rxnorm_ref   = pd.read_csv(rf"{BASE}\knowledge_base\sources\dataset\rxnorm_mapping.csv") 

# Normalize names to lowercase for matching
interactions["Nom_Generique_clean"] = interactions["Nom_Generique"].str.lower().str.strip()
rxnorm_ref["inn_name_clean"]        = rxnorm_ref["inn_name"].str.lower().str.strip()

# ============================================================
# 2. JOIN — fill what we can from the reference file
# ============================================================
merged = interactions.merge(
    rxnorm_ref[["inn_name_clean", "rxnorm_cui"]],
    left_on="Nom_Generique_clean",
    right_on="inn_name_clean",
    how="left"
)

print(f"✅ Matched from reference file: {merged['rxnorm_cui'].notna().sum()} / {len(merged)}")

# ============================================================
# 3. FOR UNMATCHED ROWS — fetch CUI from RxNorm API
# ============================================================
def get_rxnorm_cui(drug_name):
    """Search RxNorm API for a drug CUI by name."""
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}&search=2"
        r = requests.get(url, timeout=10)
        data = r.json()
        cuis = data.get("idGroup", {}).get("rxnormId", [])
        return cuis[0] if cuis else None
    except:
        return None

def get_pharma_class(cui):
    """Fetch pharmacological class from RxNorm using CUI."""
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={cui}&relaSource=EPC"
        r = requests.get(url, timeout=10)
        data = r.json()
        classes = data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        if classes:
            return classes[0]["rxclassMinConceptItem"]["className"]
        return "Inconnue"
    except:
        return "Inconnue"

# ============================================================
# 4. ONLY CALL API FOR UNIQUE UNMATCHED DRUG NAMES
#    (avoids 31,250 API calls — deduplicate first!)
# ============================================================
unmatched_drugs = merged[merged["rxnorm_cui"].isna()]["Nom_Generique_clean"].unique()
print(f"🔍 Unique drugs to look up via API: {len(unmatched_drugs)}")

drug_class_map = {}

for drug in tqdm(unmatched_drugs, desc="Fetching from RxNorm API"):
    cui = get_rxnorm_cui(drug)
    if cui:
        pharma_class = get_pharma_class(cui)
        drug_class_map[drug] = {"rxnorm_cui": cui, "Classe_API": pharma_class}
    else:
        drug_class_map[drug] = {"rxnorm_cui": None, "Classe_API": "Inconnue"}
    time.sleep(0.2)  # ← be polite to the API (rate limit)

# ============================================================
# 5. MERGE API RESULTS BACK
# ============================================================
api_df = pd.DataFrame.from_dict(drug_class_map, orient="index").reset_index()
api_df.columns = ["Nom_Generique_clean", "rxnorm_cui_api", "Classe_API"]

merged = merged.merge(api_df, on="Nom_Generique_clean", how="left")

# Fill CUI: prefer reference file, fallback to API
merged["rxnorm_cui_final"] = merged["rxnorm_cui"].combine_first(merged["rxnorm_cui_api"])

# ============================================================
# 6. FETCH CLASS FOR REFERENCE-MATCHED ROWS (that had no class)
# ============================================================
needs_class = (
    merged["Classe_Pharmacologique"].isna() |
    (merged["Classe_Pharmacologique"].str.lower().str.strip() == "inconnue")
) & merged["Classe_API"].isna()

print(f"⚙️  Fetching class for reference-matched rows: {needs_class.sum()}")

for idx, row in tqdm(merged[needs_class].iterrows(), total=needs_class.sum()):
    if pd.notna(row["rxnorm_cui_final"]):
        cls = get_pharma_class(str(int(row["rxnorm_cui_final"])))
        merged.at[idx, "Classe_API"] = cls
    time.sleep(0.2)

# ============================================================
# 7. FINAL CLASS COLUMN
#    Priority: original (if not Inconnue) → API result
# ============================================================
def pick_class(row):
    original = str(row.get("Classe_Pharmacologique", "")).strip().lower()
    if original and original != "inconnue" and original != "nan":
        return row["Classe_Pharmacologique"]
    return row.get("Classe_API", "Inconnue")

merged["Classe_Finale"] = merged.apply(pick_class, axis=1)

# ============================================================
# 8. GROUP BY FINAL CLASS
# ============================================================
grouped = merged.groupby("Classe_Finale").agg(
    Nombre_Medicaments=("Nom_Marque", "count"),
    Medicaments=("Nom_Marque", lambda x: ", ".join(x.dropna().unique())),
    Noms_Generiques=("Nom_Generique", lambda x: ", ".join(x.dropna().unique())),
    Interactions=("Texte_Interaction", lambda x: " | ".join(x.dropna()))
).reset_index().sort_values("Nombre_Medicaments", ascending=False)

# ============================================================
# 9. SAVE RESULTS
# ============================================================
merged.to_csv(rf"{BASE}\\knowledge_base\\sources\\dataset\\interactions_enriched.csv", index=False)
grouped.to_csv(rf"{BASE}\\knowledge_base\\sources\\dataset\\interactions_grouped_by_class.csv", index=False)

print("\n Done!")
print(f"   interactions_enriched.csv     → full dataset with filled classes")
print(f"   interactions_grouped_by_class.csv → grouped by pharmacological class")
print(f"\n Class coverage:")
print(merged["Classe_Finale"].value_counts().head(20))