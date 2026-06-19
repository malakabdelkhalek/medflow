# Drug Family Architecture & Detection

## Problem: Trap 8 (Therapeutic Duplication)

Patient is on **Tahor (atorvastatin)** and is prescribed **atorvastatin** 20mg.

**Old validator:** Only matches exact molecule pairs → MISSES the duplicate
**Family validator:** Groups by therapeutic family → DETECTS the duplicate

---

## Data Flow: Therapeutic Duplication Detection

```
PATIENT STATUS:
  Active medications: Tahor (atorvastatin)
    → drug_id: 42
    → molecule_id: 15 (atorvastatin)
    → drug_family_members links it to family_id: 3 (Statins)

NEW PRESCRIPTION:
  prescribed_inn: "atorvastatin"
    → molecule_id: 15
    → drug_family_members links it to family_id: 3 (Statins)

DETECTION QUERY:
  SELECT DISTINCT df.id, df.name
  FROM drug_family_members dfm
  JOIN drug_families df ON df.id = dfm.family_id
  JOIN drugs d ON d.id = dfm.drug_id
  JOIN molecules m ON m.id = d.molecule_id
  WHERE m.inn = 'atorvastatin'
  
  → Returns: (3, "Statins")

CONFLICT CHECK:
  SELECT DISTINCT m.inn, df.id, df.name
  FROM active_medications am
  WHERE patient_id = 1
  JOIN drug_family_members dfm ON dfm.drug_id = am.drug_id
  
  → Active meds also have family_id = 3
  → ALERT: "Therapeutic duplication in Statins family"
  → Severity: "deconseillee"
```

---

## Data Model: 4 New Tables

### 1. `drug_families`
```
id | name      | description              | atc_prefix | clinical_note
3  | Statins   | HMG-CoA reductase...     | C10A       | cholesterol reduction
5  | NSAIDs    | Anti-inflammatory drugs  | M01A       | pain/inflammation
```

### 2. `drug_family_members` (bridges drugs to families)
```
id | drug_id | family_id | indication
10 | 42      | 3         | cholesterol reduction    (Tahor → Statins)
11 | 43      | 3         | cholesterol reduction    (Atorvastatin generic → Statins)
```

### 3. `family_interactions` (family-level rules)
```
family_a_id | family_b_id | interaction_type | severity      | clinical_effect
3           | 5           | bleeding_risk    | deconseillee  | Statins + NSAIDs = myopathy + GI bleed
```

### 4. `family_cyp_relationships` (enzyme competition)
```
family_id | enzyme   | relationship | strength
3         | CYP3A4   | substrate     | moderate   (Statins are metabolized by CYP3A4)
7         | CYP3A4   | inhibitor     | strong     (Antibiotics inhibit CYP3A4)
→ Result: Statin + strong CYP inhibitor = toxicity risk
```

---

## Detection Scenarios

### Scenario 1: Therapeutic Duplication
```
Patient on: atorvastatin
Prescription: simvastatin
Both in family: Statins
Alert: "Duplicate therapy - choose ONE statin"
```

### Scenario 2: CYP Enzyme Competition
```
Patient on: atorvastatin (substrate of CYP3A4)
Prescription: clarithromycin (inhibitor of CYP3A4)
Detection:
  1. Find atorvastatin's family (Statins)
  2. Find Statins' CYP relationships (CYP3A4 substrate)
  3. Find clarithromycin's family (Antibiotics)
  4. Find Antibiotics' CYP relationships (CYP3A4 inhibitor)
  5. Match: Both affect CYP3A4 → statin levels ↑↑
Alert: "Monitor statin levels. Reduce dose."
```

### Scenario 3: Family-Level Interaction
```
Patient on: warfarin (Anticoagulants family)
Prescription: ibuprofen (NSAIDs family)
Lookup: family_interactions where (Anticoagulants, NSAIDs)
Result: severity="deconseillee", clinical_effect="GI bleeding"
Alert: "CONTRAINDICATED - use acetaminophen instead"
```

---

## Validator Levels

```python
validator = FamilyPrescriptionValidator()
result = validator.validate_prescription(patient_id=1, prescribed_inn="aspirin")

alerts have "level" field:
  ├─ "molecule"          # drug_interactions table (warfarin + aspirin exact pair)
  ├─ "family"            # family_interactions table (NSAIDs + anticoagulants)
  ├─ "allergy"           # allergy_groups table
  ├─ "cyp_competition"   # family_cyp_relationships table
  └─ "patient_specific"  # lab_results (creatinine, etc.)
```

---

## Integration Steps

### 1. Create Tables
```bash
psql medflow < db/migrations/002_drug_families.sql
```

### 2. Load Families
```bash
python knowledge_base/loaders/load_drug_families.py
```

### 3. Test Validator
```bash
python engine/family_validator.py
# Should detect therapeutic duplication, CYP competition, family interactions
```

### 4. Use in API
```python
from engine.family_validator import FamilyPrescriptionValidator

validator = FamilyPrescriptionValidator()
result = validator.validate_prescription(patient_id=1, prescribed_inn="aspirin")
print(result)
# {
#   "safe_to_prescribe": False,
#   "alerts": [
#     {"alert_type": "drug_interaction", "severity": "deconseillee", ...},
#     {"alert_type": "therapeutic_duplication", "severity": "deconseillee", ...},
#     {"alert_type": "cyp_competition", "severity": "precaution_emploi", ...}
#   ]
# }
```

---

## What Gets Detected Now?

| Trap | Old Validator | Family Validator |
|------|---|---|
| 1: warfarin + aspirin | ✓ (exact pair) | ✓ (exact pair) |
| 2: metformin + renal impairment | ✓ (dosing check) | ✓ (dosing check) |
| 3: simvastatin + clarithromycin | ✗ (no CYP) | ✓ (CYP competition) |
| 4: penicillin allergy → amoxicillin | ✓ (allergy group) | ✓ (allergy group) |
| 5: fluoxetine + tramadol | ✓ (exact pair) | ✓ (exact pair) |
| 6: elderly + ciprofloxacin | ✓ (dosing check) | ✓ (dosing check) |
| 7: warfarin + fluconazole (CYP2C9) | ✗ (no CYP) | ✓ (CYP competition) |
| **8: Tahor + atorvastatin** | **✗ (different brands)** | **✓ (same family)** |

---

## Why This Works

1. **Families group clinically equivalent drugs** (all statins act similarly)
2. **Family interactions capture therapeutic rules** (no two drugs from same family)
3. **CYP relationships model metabolism** (enzyme competition at family level)
4. **Alerts have context** (alert type says whether it's molecule-level, family-level, etc.)
