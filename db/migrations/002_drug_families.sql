-- MedFlow Extended Schema: Drug Families & Family-Level Interactions

-- Drug families (therapeutic classes)
CREATE TABLE drug_families (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    atc_prefix VARCHAR(10),  -- e.g., "C10" for statins
    clinical_note TEXT
);

-- Links individual drugs to families
CREATE TABLE drug_family_members (
    id SERIAL PRIMARY KEY,
    drug_id INT REFERENCES drugs(id),
    family_id INT REFERENCES drug_families(id),
    indication VARCHAR(255),  -- e.g., "cholesterol reduction"
    UNIQUE(drug_id, family_id)
);

-- Family-level interactions (e.g., statins + CYP3A4 inhibitors)
CREATE TABLE family_interactions (
    id SERIAL PRIMARY KEY,
    family_a_id INT REFERENCES drug_families(id),
    family_b_id INT REFERENCES drug_families(id),
    interaction_type VARCHAR(50),  -- "therapeutic_duplication", "cyp_competition", "additive_effect"
    severity VARCHAR(40),
    mechanism TEXT,
    clinical_effect TEXT,
    management TEXT,
    UNIQUE(family_a_id, family_b_id)
);

-- CYP enzyme interactions (family level)
CREATE TABLE family_cyp_relationships (
    id SERIAL PRIMARY KEY,
    family_id INT REFERENCES drug_families(id),
    enzyme VARCHAR(20),  -- CYP2C9, CYP3A4, etc.
    relationship VARCHAR(20),  -- "substrate", "inhibitor", "inducer"
    strength VARCHAR(10),  -- "strong", "moderate", "weak"
    UNIQUE(family_id, enzyme, relationship)
);

CREATE INDEX idx_family_members_drug ON drug_family_members(drug_id);
CREATE INDEX idx_family_members_family ON drug_family_members(family_id);
CREATE INDEX idx_family_interactions_a ON family_interactions(family_a_id);
CREATE INDEX idx_family_interactions_b ON family_interactions(family_b_id);
