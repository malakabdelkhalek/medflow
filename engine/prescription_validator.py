"""
MedFlow Prescription Validation Agent.

Validates incoming prescriptions against:
1. Drug-drug interactions
2. Allergy contraindications
3. Renal/hepatic dosing rules
"""

import os
import psycopg2


class PrescriptionValidator:
    """Clinical decision support agent for prescription validation."""

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
        Validate a prescription for a patient.

        Returns:
        {
            "patient_id": int,
            "prescribed_drug": str,
            "alerts": [
                {
                    "alert_type": "drug_interaction" | "allergy" | "dosing",
                    "severity": "deconseillee" | "precaution_emploi" | "a_prendre_en_compte",
                    "interacting_drug": str,
                    "clinical_effect": str,
                    "management": str
                }
            ],
            "safe_to_prescribe": bool
        }
        """

        alerts = []

        # 1. Check drug-drug interactions
        interaction_alerts = self._check_interactions(patient_id, prescribed_inn)
        alerts.extend(interaction_alerts)

        # 2. Check allergy contraindications
        allergy_alerts = self._check_allergies(patient_id, prescribed_inn)
        alerts.extend(allergy_alerts)

        # 3. Check renal/hepatic dosing
        dosing_alerts = self._check_dosing(patient_id, prescribed_inn)
        alerts.extend(dosing_alerts)

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
            WHERE am.patient_id = %s AND am.id IN (
                SELECT id FROM active_medications WHERE patient_id = %s
                ORDER BY start_date DESC LIMIT 10
            )
        """,
            (patient_id, patient_id),
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
                            "clinical_effect": f"Cross-reactivity risk: patient allergic to {patient_allergy}, prescribed drug in {cross} group",
                            "management": "Use with caution. Consider skin testing or desensitization if essential.",
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
            WHERE patient_id = %s AND test_name ILIKE '%creatinine%'
            ORDER BY collected_at DESC LIMIT 1
        """,
            (patient_id,),
        )
        creatinine_row = self.cur.fetchone()

        if creatinine_row:
            creatinine = creatinine_row[0]
            # CKD stage 4: 15-29 mL/min/1.73m²
            if creatinine > 150:
                alerts.append(
                    {
                        "alert_type": "dosing",
                        "severity": "precaution_emploi",
                        "interacting_drug": prescribed_inn,
                        "clinical_effect": f"Patient has elevated creatinine ({creatinine} μmol/L), suggesting renal impairment",
                        "management": "Consider dose adjustment or extended dosing interval per drug-specific guidance.",
                    }
                )

        return alerts

    def close(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()


if __name__ == "__main__":
    # Example: validate aspirin for warfarin patient
    validator = PrescriptionValidator()
    result = validator.validate_prescription(patient_id=1, prescribed_inn="aspirin")
    print(f"Safe to prescribe: {result['safe_to_prescribe']}")
    for alert in result["alerts"]:
        print(f"\n[{alert['alert_type'].upper()}] {alert['severity']}")
        print(f"  Drug: {alert['interacting_drug']}")
        print(f"  Effect: {alert['clinical_effect']}")
        print(f"  Management: {alert['management']}")
    validator.close()
