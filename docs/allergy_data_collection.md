# Allergy Data Collection

The 30 priority drugs are only a smoke-test slice for Week 1. They are not the
boundary of the allergy knowledge base.

The allergy dataset should be built in layers:

1. Clinical rule layer
   - Source: CDC, NICE, AAAAI, DailyMed/OpenFDA.
   - Purpose: define allergy groups, cross-reactivity, and when a rule is an
     absolute contraindication versus a review/caution.

2. Drug membership layer
   - Source: RxNorm/RxClass plus DailyMed/OpenFDA label validation.
   - Purpose: map every known drug ingredient/brand to one or more allergy
     groups.
   - Rule: do not blindly trust automated class extraction. Validate obvious
     nonsense before loading.

3. Local brand layer
   - Source: Tunisian PCT/PHCT mappings.
   - Purpose: connect local brand names to canonical INNs/RxCUIs, then inherit
     allergy group membership from the canonical molecule.

Current files:

- `knowledge_base/sources/allergy_groups_clean.csv`
- `knowledge_base/sources/drug_allergy_groups_clean.csv`
- `knowledge_base/sources/allergy_cross_reactivities_clean.csv`
- `knowledge_base/sources/allergy_source_evidence.csv`
- `knowledge_base/sources/allergy_collection_targets.csv`

The `drug_allergy_groups_clean.csv` file currently includes full coverage for
the Week 1 priority-drug smoke test, but the collection targets file defines the
broader data collection scope.

Important validation notes:

- Penicillin to cephalosporin cross-reactivity is not an automatic universal
  block. It depends on reaction history, timing, severity, cephalosporin
  generation, and side-chain similarity.
- Sulfonamide antibiotic allergy should not automatically block non-antibiotic
  sulfonamides such as sulfonylureas or loop diuretics.
- NSAID allergy should distinguish non-selective NSAIDs, aspirin/salicylates,
  and COX-2 selective agents.
- ACE-inhibitor angioedema should be treated as a same-class high-risk review,
  not as a simple side effect.
