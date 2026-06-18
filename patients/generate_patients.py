import psycopg2
import os
from datetime import date, datetime, timedelta

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "medflow"),
        user=os.getenv("POSTGRES_USER", "medflow"),
        password=os.getenv("POSTGRES_PASSWORD", "medflow"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Clear existing patient data (clean slate)
    print("Clearing old patient data...")
    cur.execute("TRUNCATE refill_records, prescription_history, allergies, active_medications, lab_results, conditions, patients CASCADE;")
    conn.commit()

    # Helper to get drug_id and rxnorm_cui from INN
    def get_drug_info(inn):
        cur.execute("""
            SELECT d.id, m.rxnorm_cui FROM drugs d
            JOIN molecules m ON m.id = d.molecule_id
            WHERE m.inn = %s LIMIT 1
        """, (inn,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Drug for INN '{inn}' not found in database. Make sure loaders are run first!")
        return row[0], row[1]

    # Helper to get allergy group id by name
    def get_allergy_group_id(name):
        cur.execute("SELECT id FROM allergy_groups WHERE name = %s", (name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Allergy group '{name}' not found.")
        return row[0]

    # ─────────────────────────────────────────────────────────────────────────
    # Load 8 Trap Patients
    # ─────────────────────────────────────────────────────────────────────────
    
    # TRAP 1: Warfarin + Aspirin
    print("Inserting Trap Patient 1...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Mohamed Ben Ali', '1960-05-15', 'M', 75.0, TRUE, 'warfarin_aspirin')
        RETURNING id
    """)
    p1_id = cur.fetchone()[0]
    
    d_warf_id, c_warf = get_drug_info("warfarin")
    cur.execute("""
        INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
        VALUES (%s, %s, %s, 5, 'once daily', %s, 101)
    """, (p1_id, d_warf_id, c_warf, date.today() - timedelta(days=90)))
    
    # Lab result: INR = 2.5 (therapeutic)
    cur.execute("""
        INSERT INTO lab_results (patient_id, loinc_code, test_name, value, unit, collected_at)
        VALUES (%s, '34714-6', 'INR', 2.5, 'INR', %s)
    """, (p1_id, datetime.now() - timedelta(days=2)))

    # TRAP 2: Metformin + CKD (eGFR < 30 / High creatinine)
    print("Inserting Trap Patient 2...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Fatma Oueslati', '1955-10-22', 'F', 62.0, TRUE, 'metformin_ckd')
        RETURNING id
    """)
    p2_id = cur.fetchone()[0]
    
    cur.execute("""
        INSERT INTO conditions (patient_id, icd11_code, condition_name, onset_date)
        VALUES (%s, '5A11', 'Type 2 Diabetes Mellitus', %s)
    """, (p2_id, date.today() - timedelta(days=365)))
    
    # Lab result: Creatinine = 180 umol/L (high, normal is <100)
    cur.execute("""
        INSERT INTO lab_results (patient_id, loinc_code, test_name, value, unit, collected_at)
        VALUES (%s, '2160-0', 'Serum Creatinine', 180.0, 'umol/L', %s)
    """, (p2_id, datetime.now() - timedelta(days=3)))

    # TRAP 3: Simvastatin + Clarithromycin (CYP3A4 inhibitor)
    print("Inserting Trap Patient 3...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Yassine Trabelsi', '1968-03-08', 'M', 80.0, TRUE, 'simvastatin_clarithromycin')
        RETURNING id
    """)
    p3_id = cur.fetchone()[0]
    
    d_simv_id, c_simv = get_drug_info("simvastatin")
    cur.execute("""
        INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
        VALUES (%s, %s, %s, 40, 'once daily at night', %s, 102)
    """, (p3_id, d_simv_id, c_simv, date.today() - timedelta(days=60)))

    # TRAP 4: Penicillin Allergy + Amoxicillin
    print("Inserting Trap Patient 4...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Amira Gharbi', '1992-07-14', 'F', 58.0, TRUE, 'penicillin_allergy_amoxicillin')
        RETURNING id
    """)
    p4_id = cur.fetchone()[0]
    
    ag_pen_id = get_allergy_group_id("Penicillins")
    cur.execute("""
        INSERT INTO allergies (patient_id, allergy_group_id, reaction_type, documented_at)
        VALUES (%s, %s, 'Anaphylaxis', %s)
    """, (p4_id, ag_pen_id, date.today() - timedelta(days=2000)))

    # TRAP 5: Serotonin Syndrome (Fluoxetine + Tramadol)
    print("Inserting Trap Patient 5...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Hedi Dridi', '1980-11-30', 'M', 70.0, TRUE, 'serotonin_syndrome')
        RETURNING id
    """)
    p5_id = cur.fetchone()[0]
    
    d_fluox_id, c_fluox = get_drug_info("fluoxetine")
    cur.execute("""
        INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
        VALUES (%s, %s, %s, 20, 'once daily in the morning', %s, 103)
    """, (p5_id, d_fluox_id, c_fluox, date.today() - timedelta(days=45)))

    # TRAP 6: Elderly Dose Adjustment (borderline renal function + standard antibiotic dose)
    print("Inserting Trap Patient 6...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Beji Caid', '1948-02-12', 'M', 52.0, TRUE, 'elderly_dose')
        RETURNING id
    """)
    p6_id = cur.fetchone()[0]
    
    # Lab result: Creatinine = 135 umol/L (decreased clearance given age 78 and weight 52kg)
    cur.execute("""
        INSERT INTO lab_results (patient_id, loinc_code, test_name, value, unit, collected_at)
        VALUES (%s, '2160-0', 'Serum Creatinine', 135.0, 'umol/L', %s)
    """, (p6_id, datetime.now() - timedelta(days=1)))

    # TRAP 7: CYP2C9 Overload (Warfarin + Fluconazole + Diclofenac)
    print("Inserting Trap Patient 7...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Monia Selmi', '1963-09-05', 'F', 68.0, TRUE, 'cyp2c9_overload')
        RETURNING id
    """)
    p7_id = cur.fetchone()[0]
    
    d_warf_id, c_warf = get_drug_info("warfarin")
    d_fluc_id, c_fluc = get_drug_info("fluconazole")
    
    # Active on Warfarin + Fluconazole
    cur.execute("""
        INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
        VALUES 
            (%s, %s, %s, 4, 'once daily', %s, 101),
            (%s, %s, %s, 150, 'once daily', %s, 104)
    """, (p7_id, d_warf_id, c_warf, date.today() - timedelta(days=30),
          p7_id, d_fluc_id, c_fluc, date.today() - timedelta(days=5)))

    # TRAP 8: Therapeutic Duplication (Tahor + Atorvastatin)
    print("Inserting Trap Patient 8...")
    cur.execute("""
        INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario)
        VALUES ('Kamel Mansour', '1972-12-01', 'M', 85.0, TRUE, 'therapeutic_duplication')
        RETURNING id
    """)
    p8_id = cur.fetchone()[0]
    
    d_ator_id, c_ator = get_drug_info("atorvastatin")
    
    # Active on Tahor (atorvastatin)
    cur.execute("""
        INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
        VALUES (%s, %s, %s, 20, 'once daily at night', %s, 105)
    """, (p8_id, d_ator_id, c_ator, date.today() - timedelta(days=120)))

    # ─────────────────────────────────────────────────────────────────────────
    # Load 22 Control / Complex Patients
    # ─────────────────────────────────────────────────────────────────────────
    # At least 8 of these must have 3 or more active medications
    
    names_pool = [
        ("Salma Toumi", "F", 65, "1988-06-12"),
        ("Anis Ben Amor", "M", 78, "1974-04-18"),
        ("Rim Rezgui", "F", 55, "1995-10-05"),
        ("Khaled Bessa", "M", 92, "1964-08-30"),
        ("Sonia Jamil", "F", 71, "1979-01-25"),
        ("Tarek Zouari", "M", 84, "1950-12-14"),
        ("Yasmine Said", "F", 60, "1990-09-09"),
        ("Habib Ben Salem", "M", 73, "1958-03-21"),
        ("Meriam Ferchiou", "F", 52, "1985-05-18"),
        ("Nabil Lahmar", "M", 88, "1970-11-12"),
        ("Olfa Ghorbel", "F", 67, "1976-02-28"),
        ("Firas Chaabane", "M", 80, "1993-07-07"),
        ("Houda Kallel", "F", 59, "1961-04-01"),
        ("Walid Mami", "M", 75, "1982-10-10"),
        ("Jihene Gharbi", "F", 63, "1989-12-25"),
        ("Slim Bouaziz", "M", 82, "1971-08-08"),
        ("Ines Ayadi", "F", 70, "1966-03-15"),
        ("Ridha Hammami", "M", 90, "1953-06-22"),
        ("Dora Chebbi", "F", 54, "1998-05-05"),
        ("Adel Mejri", "M", 77, "1969-02-17"),
        ("Leila Rekik", "F", 61, "1978-09-19"),
        ("Moncef Guedwar", "M", 86, "1957-04-30")
    ]

    # Pre-select medications to use for populating
    med_inns = ["metformin", "amlodipine", "omeprazole", "ramipril", "sertraline", "amoxicillin", "furosemide", "prednisolone"]
    
    for i, (name, sex, weight, dob_str) in enumerate(names_pool, start=9):
        print(f"Inserting Patient {i} ({name})...")
        cur.execute("""
            INSERT INTO patients (name, dob, sex, weight_kg, is_trap)
            VALUES (%s, %s, %s, %s, FALSE)
            RETURNING id
        """, (name, dob_str, sex, weight))
        pat_id = cur.fetchone()[0]
        
        # Decide if this patient has 3+ medications (at least 8 patients must)
        # We'll give patients 9 to 16 (8 patients) 3 active medications each
        num_meds = 3 if (9 <= i <= 16) else 1
        
        # Add active medications
        for m_idx in range(num_meds):
            inn = med_inns[(i + m_idx) % len(med_inns)]
            drug_id, cui = get_drug_info(inn)
            cur.execute("""
                INSERT INTO active_medications (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date, prescriber_id)
                VALUES (%s, %s, %s, 10, 'once daily', %s, 201)
            """, (pat_id, drug_id, cui, date.today() - timedelta(days=30)))
            
        # Add basic lab results (e.g. Potassium = 4.1 mmol/L)
        cur.execute("""
            INSERT INTO lab_results (patient_id, loinc_code, test_name, value, unit, collected_at)
            VALUES (%s, '2823-3', 'Serum Potassium', 4.1, 'mmol/L', %s)
        """, (pat_id, datetime.now() - timedelta(days=10)))

    conn.commit()
    
    # Assert counts
    cur.execute("SELECT count(*) FROM patients")
    patients_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM active_medications")
    meds_count = cur.fetchone()[0]
    
    print(f"\nDone. Successfully generated:")
    print(f"  - Patients: {patients_count} (Expected: 30)")
    print(f"  - Active medications: {meds_count}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
