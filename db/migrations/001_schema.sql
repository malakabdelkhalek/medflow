-- ============================================================
-- MedFlow — 001_schema.sql
-- Full PostgreSQL schema for pharmaceutical knowledge base
-- and patient dataset.
-- ============================================================

-- -------------------------
-- PHARMACEUTICAL KNOWLEDGE BASE
-- -------------------------

CREATE TABLE molecules (
    id SERIAL PRIMARY KEY,
    inn VARCHAR(255) UNIQUE NOT NULL,
    rxnorm_cui VARCHAR(20),
    drugbank_id VARCHAR(20),
    chembl_id VARCHAR(20),
    molecular_class VARCHAR(100),
    half_life_hours NUMERIC,
    elimination_route VARCHAR(50)   -- renal | hepatic | mixed
);

CREATE TABLE drugs (
    id SERIAL PRIMARY KEY,
    molecule_id INT REFERENCES molecules(id),
    brand_name VARCHAR(255),
    brand_name_tn VARCHAR(255),     -- Tunisian brand name
    brand_name_fr VARCHAR(255),
    atc_code VARCHAR(10),
    therapeutic_category VARCHAR(100),
    dosage_form VARCHAR(50),
    dose_adult VARCHAR(100),
    dose_elderly VARCHAR(100),
    dose_renal_impairment VARCHAR(100),
    dose_hepatic_impairment VARCHAR(100)
);

CREATE TABLE drug_interactions (
    id SERIAL PRIMARY KEY,
    molecule_a_id INT REFERENCES molecules(id),
    molecule_b_id INT REFERENCES molecules(id),
    severity_drugbank VARCHAR(20),  -- major | moderate | minor
    severity_ansm VARCHAR(40),      -- contre-indiqué | déconseillée | précaution | à prendre en compte
    severity_active VARCHAR(40),    -- most conservative of the two
    mechanism_type VARCHAR(50),     -- pharmacokinetic | pharmacodynamic
    mechanism_description TEXT,
    clinical_effect TEXT,
    management TEXT,
    dose_dependent BOOLEAN DEFAULT FALSE,
    onset VARCHAR(20),              -- rapid | delayed
    documentation_level VARCHAR(20),
    condition_modifiers TEXT,
    source_confidence VARCHAR(20),
    UNIQUE(molecule_a_id, molecule_b_id)
);

CREATE TABLE cyp_relationships (
    id SERIAL PRIMARY KEY,
    molecule_id INT REFERENCES molecules(id),
    enzyme VARCHAR(20),             -- CYP3A4 | CYP2C9 | CYP2D6 ...
    relationship VARCHAR(20),       -- metabolized_by | inhibits | induces
    strength VARCHAR(10)            -- strong | moderate | weak
);

CREATE TABLE contraindications (
    id SERIAL PRIMARY KEY,
    drug_id INT REFERENCES drugs(id),
    condition_icd11 VARCHAR(20),
    condition_name VARCHAR(255),
    reason TEXT,
    source VARCHAR(50)
);

CREATE TABLE allergy_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE allergy_cross_reactivities (
    group_a_id INT REFERENCES allergy_groups(id),
    group_b_id INT REFERENCES allergy_groups(id),
    PRIMARY KEY (group_a_id, group_b_id)
);

CREATE TABLE drug_allergy_groups (
    drug_id INT REFERENCES drugs(id),
    allergy_group_id INT REFERENCES allergy_groups(id),
    PRIMARY KEY (drug_id, allergy_group_id)
);

-- -------------------------
-- PATIENT DATASET
-- -------------------------

CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    dob DATE,
    sex CHAR(1),
    weight_kg NUMERIC,
    is_trap BOOLEAN DEFAULT FALSE,
    trap_scenario VARCHAR(100)
);

CREATE TABLE conditions (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    icd11_code VARCHAR(20),
    condition_name VARCHAR(255),
    onset_date DATE
);

CREATE TABLE active_medications (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    drug_id INT REFERENCES drugs(id),
    rxnorm_cui VARCHAR(20),
    dose_mg NUMERIC,
    frequency VARCHAR(50),
    start_date DATE,
    prescriber_id INT
);

CREATE TABLE lab_results (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    loinc_code VARCHAR(20),
    test_name VARCHAR(100),
    value NUMERIC,
    unit VARCHAR(20),
    collected_at TIMESTAMP
);

CREATE TABLE allergies (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    allergy_group_id INT REFERENCES allergy_groups(id),
    reaction_type VARCHAR(50),
    documented_at DATE
);

CREATE TABLE prescription_history (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    drug_id INT REFERENCES drugs(id),
    prescribed_at DATE,
    prescriber_id INT,
    dose_mg NUMERIC,
    frequency VARCHAR(50)
);

CREATE TABLE refill_records (
    id SERIAL PRIMARY KEY,
    patient_id INT REFERENCES patients(id),
    drug_id INT REFERENCES drugs(id),
    expected_refill_date DATE,
    actual_refill_date DATE
);

-- -------------------------
-- INDEXES
-- -------------------------

CREATE INDEX idx_interactions_mol_a ON drug_interactions(molecule_a_id);
CREATE INDEX idx_interactions_mol_b ON drug_interactions(molecule_b_id);
CREATE INDEX idx_active_meds_patient ON active_medications(patient_id);
CREATE INDEX idx_active_meds_rxnorm  ON active_medications(rxnorm_cui);
CREATE INDEX idx_cyp_molecule        ON cyp_relationships(molecule_id);
CREATE INDEX idx_cyp_enzyme          ON cyp_relationships(enzyme);
CREATE INDEX idx_lab_patient         ON lab_results(patient_id);
CREATE INDEX idx_allergies_patient   ON allergies(patient_id);
