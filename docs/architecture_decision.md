# Architecture Decision — Single PostgreSQL Database

## Decision
Everything lives in PostgreSQL.

## What this covers
- Drug knowledge (molecules, drugs, brand names)
- Interaction records (pairwise drug-drug interactions with severity)
- CYP pathways (enzyme inhibition/induction relationships)
- Allergy groups and cross-reactivities
- Patient data (demographics, conditions, active medications)
- Lab results
- Prescription history

## Why
One database means the engine is pure SQL joins — no syncing between systems, no data consistency issues, no extra infrastructure for a team of 3 interns to manage.

## What this rules out
- No separate NoSQL store for drug knowledge
- No CSV/JSON files as the source of truth at runtime
- No Redis or separate cache layer
- Raw downloaded source files (DrugBank XML, ANSM Excel) live in `knowledge_base/sources/` and are only used by loaders to populate the DB — they are not read at runtime
