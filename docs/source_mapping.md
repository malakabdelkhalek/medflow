# MedFlow — Source Mapping

Every field in the database schema is traced to a real data source here before any row is inserted.

## Sources

| ID | Source | Access | Owner |
|----|--------|--------|-------|
| S1 | DrugBank | Academic download (requires registration) | Arij |
| S2 | ANSM Thesaurus des Interactions Médicamenteuses | Free download — ansm.sante.fr | Malak |
| S3 | ChEMBL REST API | Free, no key | Baha |
| S4 | OpenFDA Drug API | Free, no key | Baha |
| S5 | RxNorm API | Free, no key | Baha |
| S6 | Tunisian Formulary (manual research) | Manual — pharmacies + DPMPE | Malak |

## Field → Source Mapping

### molecules

| Field | Source | Confidence | Notes |
|-------|--------|------------|-------|
| inn | S1, S5 | High | INN from DrugBank, verified via RxNorm |
| rxnorm_cui | S5 | High | RxNorm /rxcui endpoint |
| drugbank_id | S1 | High | DrugBank accession number |
| chembl_id | S3 | High | ChEMBL molecule search |
| molecular_class | S1 | Medium | DrugBank drug_class field |
| half_life_hours | S1, S4 | Medium | DrugBank pharmacokinetics; cross-check OpenFDA label |
| elimination_route | S1, S3 | High | DrugBank + ChEMBL metabolism data |

### drug_interactions

| Field | Source | Confidence | Notes |
|-------|--------|------------|-------|
| severity_drugbank | S1 | High | DrugBank interaction severity field |
| severity_ansm | S2 | High | ANSM thesaurus level column |
| severity_active | S1+S2 | High | Most conservative of the two — always |
| mechanism_type | S1, S3 | High | Pharmacokinetic vs pharmacodynamic |
| mechanism_description | S1, S2 | High | DrugBank description + ANSM mechanism |
| clinical_effect | S1, S2 | High | Plain-language summary for pharmacist |
| management | S2, S4 | High | ANSM recommendation; OpenFDA label warnings |

### cyp_relationships

| Field | Source | Confidence | Notes |
|-------|--------|------------|-------|
| enzyme | S3 | High | ChEMBL target classification |
| relationship | S3 | High | metabolized_by / inhibits / induces |
| strength | S3, S1 | High | ChEMBL activity data; DrugBank CYP section |

### drugs (Tunisian mapping)

| Field | Source | Confidence | Notes |
|-------|--------|------------|-------|
| brand_name_tn | S6 | Medium | Manual research — document each entry's source |
| brand_name_fr | S1, S2 | High | DrugBank synonyms |
| atc_code | S1 | High | DrugBank ATC field |

---

## Discrepancy Log

When DrugBank and ANSM disagree on severity, log it here.

| Drug A | Drug B | DrugBank severity | ANSM severity | Active severity | Notes |
|--------|--------|-------------------|---------------|-----------------|-------|
| _to be filled during loading_ | | | | | |

---

## Tunisian Formulary — 30 Priority Drugs

| INN | Tunisian Brand | French Brand | RxNorm CUI | DrugBank ID | Source |
|-----|---------------|--------------|------------|-------------|--------|
| warfarin | | Coumadine | | DB00682 | |
| heparin | | Héparine | | DB01109 | |
| aspirin | Aspégic | Aspégic | | DB00945 | |
| clopidogrel | Plavix | Plavix | | DB00758 | |
| metformin | Glucophage | Glucophage | | DB00331 | |
| glibenclamide | Daonil | Daonil | | DB01016 | |
| insulin glargine | Lantus | Lantus | | DB00047 | |
| enalapril | | Renitec | | DB00584 | |
| ramipril | Triatec | Triatec | | DB00178 | |
| amlodipine | Amlor | Amlor | | DB00381 | |
| furosemide | Lasilix | Lasilix | | DB00695 | |
| spironolactone | Aldactone | Aldactone | | DB00421 | |
| digoxin | Digoxine | Digoxine | | DB00390 | |
| atorvastatin | Tahor | Tahor | | DB01076 | |
| simvastatin | Zocor | Zocor | | DB00641 | |
| ibuprofen | Brufen | Brufen | | DB01050 | |
| diclofenac | Voltarène | Voltarène | | DB00586 | |
| naproxen | Naprosyne | Naprosyne | | DB00788 | |
| prednisolone | Solupred | Solupred | | DB00860 | |
| amoxicillin | Clamoxyl | Clamoxyl | | DB01060 | |
| ciprofloxacin | Ciflox | Ciflox | | DB00537 | |
| metronidazole | Flagyl | Flagyl | | DB00916 | |
| clarithromycin | Zeclar | Zeclar | | DB01211 | |
| fluconazole | Triflucan | Triflucan | | DB00196 | |
| carbamazepine | Tégrétol | Tégrétol | | DB00564 | |
| valproate | Dépakine | Dépakine | | DB00313 | |
| fluoxetine | Prozac | Prozac | | DB00472 | |
| sertraline | Zoloft | Zoloft | | DB01104 | |
| omeprazole | Mopral | Mopral | | DB00338 | |
| tramadol | Topalgic | Topalgic | | DB00193 | |

_Fill RxNorm CUI and Tunisian brand columns during Milestone 2 research — document the source for each entry._
