"""
MedFlow Family-Aware Prescription Validator.

Extends basic validation with:
1. Therapeutic duplication detection (same drug family)
2. CYP enzyme competition warnings
3. Family-level interaction rules
"""

import os
import psycopg2


class FamilyPrescriptionValidator:
    """Clinical decision support agent with drug family awareness."""

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "medflow"),
            user=os.getenv("POSTGRES_USER", "medflow"),
            password=os.getenv("POSTGRES_PASSWORD", "medflow"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
        )
        self.cur = self.conn.cursor()

    def validate_prescription(self, patient_id: int, prescribed_inn: str) -> dict:
        """
        Comprehensive validation including family-level interactions.
        """

        alerts = []

        # 1. Drug-drug interactions (molecule level)
        alerts.extend(self._check_interactions(patient_id, prescribed_inn))

        # 2. Allergy contraindications
        alerts.extend(self._check_allergies(patient_id, prescribed_inn))

        # 3. Therapeutic duplication (family level)
        alerts.extend(self._check_therapeutic_duplication(patient_id, prescribed_inn))

        # 4. CYP enzyme competition (family level)
        alerts.extend(self._check_cyp_competition(patient_id, prescribed_inn))

        # 5. Family-level interactions
        alerts.extend(self._check_family_interactions(patient_id, prescribed_inn))

        # 6. Renal/hepatic dosing
        alerts.extend(self._check_dosing(patient_id, prescribed_inn))

        # Safe if no "deconseillee" (contraindicated) alerts
        safe_to_prescribe = not any(
            alert["severity"] == "deconseillee" for alert in alerts
        )

        return {
            "patient_id": patient_id,
            "prescribed_drug": prescribed_inn,
            "alerts": alerts,
            "safe_to_prescribe": safe_to_prescribe,
        }

    def _check_interactions(self, patient_id: int, prescribed_inn: str) -> list:
        """Check for drug-drug interactions with active medications."""
        alerts = []

        # Get active medications
        self.cur.execute(
            """
            SELECT m.inn, m.id FROM active_medications am
            JOIN drugs d ON d.id = am.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE am.patient_id = %s
        """,
            (patient_id,),
        )
        active_meds = self.cur.fetchall()

        # Get prescribed drug molecule ID
        self.cur.execute("SELECT id FROM molecules WHERE inn = %s", (prescribed_inn,))
        prescribed_row = self.cur.fetchone()
        if not prescribed_row:
            return alerts

        prescribed_mol_id = prescribed_row[0]

        # Check interactions with each active med
        for active_inn, active_mol_id in active_meds:
            id_a, id_b = min(active_mol_id, prescribed_mol_id), max(
                active_mol_id, prescribed_mol_id
            )
            self.cur.execute(
                """
                SELECT severity_ansm, severity_openfda, clinical_effect, management
                FROM drug_interactions
                WHERE molecule_a_id = %s AND molecule_b_id = %s
            """,
                (id_a, id_b),
            )
            row = self.cur.fetchone()

            if row:
                severity_ansm, severity_openfda, clinical_effect, management = row
                alerts.append(
                    {
                        "alert_type": "drug_interaction",
                        "severity": severity_ansm or severity_openfda,
                        "interacting_drug": active_inn,
                        "clinical_effect": clinical_effect,
                        "management": management,
                        "level": "molecule",
                    }
                )

        return alerts

    def _check_allergies(self, patient_id: int, prescribed_inn: str) -> list:
        """Check for allergy contraindications."""
        alerts = []

        # Get patient allergies
        self.cur.execute(
            """
            SELECT ag.name FROM allergies a
            JOIN allergy_groups ag ON ag.id = a.allergy_group_id
            WHERE a.patient_id = %s
        """,
            (patient_id,),
        )
        patient_allergies = [row[0] for row in self.cur.fetchall()]

        if not patient_allergies:
            return alerts

        # Get drug's allergy group memberships
        self.cur.execute(
            """
            SELECT ag.name FROM drug_allergy_groups dag
            JOIN allergy_groups ag ON ag.id = dag.allergy_group_id
            JOIN drugs d ON d.id = dag.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE m.inn = %s
        """,
            (prescribed_inn,),
        )
        drug_allergies = [row[0] for row in self.cur.fetchall()]

        # Check direct match
        for allergy in drug_allergies:
            if allergy in patient_allergies:
                alerts.append(
                    {
                        "alert_type": "allergy",
                        "severity": "deconseillee",
                        "interacting_drug": prescribed_inn,
                        "clinical_effect": f"Patient has documented {allergy} allergy",
                        "management": "CONTRAINDICATED. Use alternative drug.",
                        "level": "allergy",
                    }
                )

        # Check cross-reactivities
        for patient_allergy in patient_allergies:
            self.cur.execute(
                """
                SELECT ag2.name FROM allergy_cross_reactivities acr
                JOIN allergy_groups ag1 ON ag1.id = acr.group_a_id
                JOIN allergy_groups ag2 ON ag2.id = acr.group_b_id
                WHERE ag1.name = %s
                UNION
                SELECT ag1.name FROM allergy_cross_reactivities acr
                JOIN allergy_groups ag1 ON ag1.id = acr.group_a_id
                JOIN allergy_groups ag2 ON ag2.id = acr.group_b_id
                WHERE ag2.name = %s
            """,
                (patient_allergy, patient_allergy),
            )
            cross_reactivities = [row[0] for row in self.cur.fetchall()]

            for cross in cross_reactivities:
                if cross in drug_allergies:
                    alerts.append(
                        {
                            "alert_type": "allergy",
                            "severity": "precaution_emploi",
                            "interacting_drug": prescribed_inn,
                            "clinical_effect": f"Cross-reactivity: patient allergic to {patient_allergy}, prescribed drug in {cross}",
                            "management": "Use with caution. Consider desensitization if essential.",
                            "level": "allergy",
                        }
                    )

        return alerts

    def _check_therapeutic_duplication(self, patient_id: int, prescribed_inn: str) -> list:
        """Check for therapeutic duplication (same drug family)."""
        alerts = []

        # Get families of prescribed drug
        self.cur.execute(
            """
            SELECT DISTINCT df.id, df.name, dfm.indication
            FROM drug_family_members dfm
            JOIN drug_families df ON df.id = dfm.family_id
            JOIN drugs d ON d.id = dfm.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE m.inn = %s
        """,
            (prescribed_inn,),
        )
        prescribed_families = self.cur.fetchall()

        if not prescribed_families:
            return alerts

        # Get active meds and their families
        self.cur.execute(
            """
            SELECT DISTINCT m.inn, df.id, df.name
            FROM active_medications am
            JOIN drugs d ON d.id = am.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            JOIN drug_family_members dfm ON dfm.drug_id = d.id
            JOIN drug_families df ON df.id = dfm.family_id
            WHERE am.patient_id = %s
        """,
            (patient_id,),
        )
        active_families = self.cur.fetchall()

        # Check for overlap
        prescribed_family_ids = {f[0] for f in prescribed_families}
        for active_inn, active_family_id, active_family_name in active_families:
            if active_family_id in prescribed_family_ids:
                alerts.append(
                    {
                        "alert_type": "therapeutic_duplication",
                        "severity": "deconseillee",
                        "interacting_drug": active_inn,
                        "clinical_effect": f"Patient already taking {active_inn} from {active_family_name} family",
                        "management": f"Duplicate therapy detected. Use only one drug from {active_family_name}.",
                        "level": "family",
                    }
                )

        return alerts

    def _check_cyp_competition(self, patient_id: int, prescribed_inn: str) -> list:
        """Check for CYP enzyme competition (multiple inhibitors/inducers)."""
        alerts = []

        # Get CYP relationships of prescribed drug's family
        self.cur.execute(
            """
            SELECT DISTINCT fcr.enzyme, fcr.relationship, fcr.strength
            FROM drug_family_members dfm
            JOIN drug_families df ON df.id = dfm.family_id
            JOIN family_cyp_relationships fcr ON fcr.family_id = df.id
            JOIN drugs d ON d.id = dfm.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE m.inn = %s
        """,
            (prescribed_inn,),
        )
        prescribed_cyp = self.cur.fetchall()

        if not prescribed_cyp:
            return alerts

        # Get CYP relationships of active meds
        self.cur.execute(
            """
            SELECT DISTINCT m.inn, fcr.enzyme, fcr.relationship, fcr.strength
            FROM active_medications am
            JOIN drugs d ON d.id = am.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            JOIN drug_family_members dfm ON dfm.drug_id = d.id
            JOIN drug_families df ON df.id = dfm.family_id
            JOIN family_cyp_relationships fcr ON fcr.family_id = df.id
            WHERE am.patient_id = %s
        """,
            (patient_id,),
        )
        active_cyp = self.cur.fetchall()

        # Check for enzyme competition
        for prescribed_enzyme, prescribed_rel, prescribed_strength in prescribed_cyp:
            for active_inn, active_enzyme, active_rel, active_strength in active_cyp:
                if prescribed_enzyme == active_enzyme:
                    # Both affect same enzyme
                    if prescribed_rel == "inhibitor" and active_rel == "substrate":
                        alerts.append(
                            {
                                "alert_type": "cyp_competition",
                                "severity": "precaution_emploi",
                                "interacting_drug": active_inn,
                                "clinical_effect": f"Both {active_inn} (substrate) and {prescribed_inn} ({prescribed_rel}) affect {prescribed_enzyme}, increasing active drug levels",
                                "management": f"Monitor {active_inn} levels. Consider dose reduction or therapeutic drug monitoring.",
                                "level": "family",
                            }
                        )
                    elif prescribed_rel == "inducer" and active_rel == "substrate":
                        alerts.append(
                            {
                                "alert_type": "cyp_competition",
                                "severity": "precaution_emploi",
                                "interacting_drug": active_inn,
                                "clinical_effect": f"{prescribed_inn} induces {prescribed_enzyme}, reducing effectiveness of {active_inn}",
                                "management": f"Monitor {active_inn} efficacy. Consider dose increase.",
                                "level": "family",
                            }
                        )

        return alerts

    def _check_family_interactions(self, patient_id: int, prescribed_inn: str) -> list:
        """Check family-level interactions."""
        alerts = []

        # Get families of prescribed drug
        self.cur.execute(
            """
            SELECT df.id FROM drug_family_members dfm
            JOIN drug_families df ON df.id = dfm.family_id
            JOIN drugs d ON d.id = dfm.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE m.inn = %s
        """,
            (prescribed_inn,),
        )
        prescribed_family_ids = [row[0] for row in self.cur.fetchall()]

        if not prescribed_family_ids:
            return alerts

        # Get families of active meds
        self.cur.execute(
            """
            SELECT DISTINCT m.inn, dfm.family_id
            FROM active_medications am
            JOIN drugs d ON d.id = am.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            JOIN drug_family_members dfm ON dfm.drug_id = d.id
            WHERE am.patient_id = %s
        """,
            (patient_id,),
        )
        active_families = self.cur.fetchall()

        # Check for family interactions
        for active_inn, active_family_id in active_families:
            for prescribed_family_id in prescribed_family_ids:
                self.cur.execute(
                    """
                    SELECT interaction_type, severity, mechanism, clinical_effect, management
                    FROM family_interactions
                    WHERE (family_a_id = %s AND family_b_id = %s)
                       OR (family_a_id = %s AND family_b_id = %s)
                """,
                    (
                        active_family_id,
                        prescribed_family_id,
                        prescribed_family_id,
                        active_family_id,
                    ),
                )
                row = self.cur.fetchone()

                if row:
                    interaction_type, severity, mechanism, clinical_effect, management = row
                    alerts.append(
                        {
                            "alert_type": interaction_type,
                            "severity": severity,
                            "interacting_drug": active_inn,
                            "clinical_effect": clinical_effect,
                            "management": management,
                            "level": "family",
                        }
                    )

        return alerts

    def _check_dosing(self, patient_id: int, prescribed_inn: str) -> list:
        """Check for renal/hepatic dosing adjustments needed."""
        alerts = []

        # Get patient's most recent creatinine
        self.cur.execute(
            """
            SELECT value FROM lab_results
            WHERE patient_id = %s AND test_name ILIKE '%%creatinine%%'
            ORDER BY collected_at DESC LIMIT 1
        """,
            (patient_id,),
        )
        creatinine_row = self.cur.fetchone()

        if creatinine_row:
            creatinine = creatinine_row[0]
            if creatinine > 150:
                alerts.append(
                    {
                        "alert_type": "dosing",
                        "severity": "precaution_emploi",
                        "interacting_drug": prescribed_inn,
                        "clinical_effect": f"Elevated creatinine ({creatinine} μmol/L) suggests renal impairment",
                        "management": "Consider dose adjustment or extended dosing interval.",
                        "level": "patient_specific",
                    }
                )

        return alerts

    def close(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()


if __name__ == "__main__":
    # Example: validate aspirin for warfarin patient
    validator = FamilyPrescriptionValidator()
    result = validator.validate_prescription(patient_id=1, prescribed_inn="aspirin")
    print(f"\n{'='*60}")
    print(f"Prescription Validation: {result['prescribed_drug']}")
    print(f"Safe to prescribe: {result['safe_to_prescribe']}")
    print(f"{'='*60}\n")
    for alert in result["alerts"]:
        print(f"[{alert['level'].upper()}] {alert['alert_type']}")
        print(f"  Severity: {alert['severity']}")
        print(f"  Drug: {alert['interacting_drug']}")
        print(f"  Effect: {alert['clinical_effect']}")
        print(f"  Management: {alert['management']}\n")
    validator.close()
