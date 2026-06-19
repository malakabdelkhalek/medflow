"""
Blueprint-based prescription validator.

Loads clinical knowledge blueprint once, validates all prescriptions
against in-memory graph. No database queries per validation.
"""

import json
import os
import psycopg2
from pathlib import Path


class BlueprintValidator:
    """Clinical decision support agent using in-memory knowledge graph."""

    def __init__(self, blueprint_path="blueprint.json"):
        """
        Initialize validator with blueprint.

        Args:
            blueprint_path: Path to blueprint.json file
        """
        self.blueprint_path = blueprint_path
        self.blueprint = self._load_blueprint()
        self.db_conn = None
        self._connect_db()

    def _load_blueprint(self):
        """Load blueprint from JSON file."""
        if not os.path.exists(self.blueprint_path):
            raise FileNotFoundError(f"Blueprint not found: {self.blueprint_path}")

        print(f"Loading blueprint from {self.blueprint_path}...")
        with open(self.blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)
        print(f"✓ Blueprint loaded ({len(blueprint['drugs'])} drugs)")
        return blueprint

    def _connect_db(self):
        """Connect to PostgreSQL for patient data only."""
        self.db_conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "medflow"),
            user=os.getenv("POSTGRES_USER", "medflow"),
            password=os.getenv("POSTGRES_PASSWORD", "medflow"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
        )

    def validate_prescription(self, patient_id: int, prescribed_inn: str) -> dict:
        """
        Validate prescription using blueprint graph.

        Args:
            patient_id: Patient ID in database
            prescribed_inn: Drug INN to validate

        Returns:
            {
                "patient_id": int,
                "prescribed_drug": str,
                "alerts": [...],
                "safe_to_prescribe": bool,
                "reasoning": str
            }
        """

        alerts = []

        # 1. Get patient data from database (only patient-specific queries)
        patient_data = self._get_patient_data(patient_id)
        if not patient_data:
            return {
                "patient_id": patient_id,
                "prescribed_drug": prescribed_inn,
                "alerts": [{"alert_type": "error", "message": "Patient not found"}],
                "safe_to_prescribe": False,
            }

        # 2. Check prescribed drug exists in blueprint
        if prescribed_inn not in self.blueprint["drugs"]:
            return {
                "patient_id": patient_id,
                "prescribed_drug": prescribed_inn,
                "alerts": [
                    {
                        "alert_type": "error",
                        "message": f"Drug '{prescribed_inn}' not in knowledge base",
                    }
                ],
                "safe_to_prescribe": False,
            }

        # 3. All validations run against blueprint (in-memory)
        alerts.extend(
            self._check_interactions(prescribed_inn, patient_data["active_drugs"])
        )
        alerts.extend(
            self._check_allergies(prescribed_inn, patient_data["allergies"])
        )
        alerts.extend(
            self._check_therapeutic_duplication(prescribed_inn, patient_data["active_drugs"])
        )
        alerts.extend(self._check_cyp_competition(prescribed_inn, patient_data["active_drugs"]))
        alerts.extend(
            self._check_dosing(prescribed_inn, patient_data["labs"])
        )

        # 4. Decision
        safe_to_prescribe = not any(
            alert["severity"] == "deconseillee" for alert in alerts if "severity" in alert
        )

        # 5. Build reasoning
        reasoning = self._build_reasoning(prescribed_inn, patient_data, alerts, safe_to_prescribe)

        return {
            "patient_id": patient_id,
            "prescribed_drug": prescribed_inn,
            "alerts": alerts,
            "safe_to_prescribe": safe_to_prescribe,
            "reasoning": reasoning,
        }

    # ─────────────────────────────────────────────────────────────────────────

    def _get_patient_data(self, patient_id: int) -> dict:
        """Get patient-specific data from database (only query per validation)."""
        cur = self.db_conn.cursor()

        # Get active medications
        cur.execute(
            """
            SELECT m.inn FROM active_medications am
            JOIN drugs d ON d.id = am.drug_id
            JOIN molecules m ON m.id = d.molecule_id
            WHERE am.patient_id = %s
        """,
            (patient_id,),
        )
        active_drugs = [row[0] for row in cur.fetchall()]

        # Get allergies
        cur.execute(
            """
            SELECT ag.name FROM allergies a
            JOIN allergy_groups ag ON ag.id = a.allergy_group_id
            WHERE a.patient_id = %s
        """,
            (patient_id,),
        )
        allergies = [row[0] for row in cur.fetchall()]

        # Get labs (creatinine)
        cur.execute(
            """
            SELECT value FROM lab_results
            WHERE patient_id = %s AND test_name ILIKE %s
            ORDER BY collected_at DESC LIMIT 1
        """,
            (patient_id, "%creatinine%"),
        )
        creatinine_row = cur.fetchone()
        creatinine = creatinine_row[0] if creatinine_row else None

        cur.close()

        return {
            "patient_id": patient_id,
            "active_drugs": active_drugs,
            "allergies": allergies,
            "labs": {"creatinine": creatinine},
        }

    def _check_interactions(self, prescribed_inn: str, active_drugs: list) -> list:
        """Check drug-drug interactions using blueprint."""
        alerts = []

        # Traverse blueprint interactions
        for interaction in self.blueprint["interactions"]:
            drug_a = interaction["drug_a"]
            drug_b = interaction["drug_b"]

            # Check if prescribed drug interacts with any active med
            if prescribed_inn == drug_a and drug_b in active_drugs:
                alerts.append({
                    "alert_type": "drug_interaction",
                    "severity": interaction["severity"],
                    "interacting_drug": drug_b,
                    "clinical_effect": interaction["clinical_effect"],
                    "management": interaction["management"],
                    "level": "molecule",
                })
            elif prescribed_inn == drug_b and drug_a in active_drugs:
                alerts.append({
                    "alert_type": "drug_interaction",
                    "severity": interaction["severity"],
                    "interacting_drug": drug_a,
                    "clinical_effect": interaction["clinical_effect"],
                    "management": interaction["management"],
                    "level": "molecule",
                })

        return alerts

    def _check_allergies(self, prescribed_inn: str, patient_allergies: list) -> list:
        """Check allergy contraindications using blueprint."""
        alerts = []

        if not patient_allergies:
            return alerts

        prescribed_drug = self.blueprint["drugs"].get(prescribed_inn)
        if not prescribed_drug:
            return alerts

        # Check direct match
        for allergy in prescribed_drug["allergies"]:
            if allergy in patient_allergies:
                alerts.append({
                    "alert_type": "allergy",
                    "severity": "deconseillee",
                    "interacting_drug": prescribed_inn,
                    "clinical_effect": f"Patient has documented {allergy} allergy",
                    "management": "CONTRAINDICATED. Use alternative.",
                    "level": "allergy",
                })

        # Check cross-reactivities
        for patient_allergy in patient_allergies:
            allergy_data = self.blueprint["allergies"].get(patient_allergy, {})
            cross_reactivities = allergy_data.get("cross_reactivities", [])

            for cross in cross_reactivities:
                if cross in prescribed_drug["allergies"]:
                    alerts.append({
                        "alert_type": "allergy",
                        "severity": "precaution_emploi",
                        "interacting_drug": prescribed_inn,
                        "clinical_effect": f"Cross-reactivity risk: {patient_allergy} → {cross}",
                        "management": "Use with caution. Consider desensitization if essential.",
                        "level": "allergy",
                    })

        return alerts

    def _check_therapeutic_duplication(self, prescribed_inn: str, active_drugs: list) -> list:
        """Check for therapeutic duplication (same family)."""
        alerts = []

        prescribed_drug = self.blueprint["drugs"].get(prescribed_inn)
        if not prescribed_drug:
            return alerts

        prescribed_families = prescribed_drug["families"]

        # Get families of active drugs
        for active_inn in active_drugs:
            active_drug = self.blueprint["drugs"].get(active_inn)
            if not active_drug:
                continue

            active_families = active_drug["families"]

            # Check for overlap
            overlap = set(prescribed_families) & set(active_families)
            for family in overlap:
                alerts.append({
                    "alert_type": "therapeutic_duplication",
                    "severity": "deconseillee",
                    "interacting_drug": active_inn,
                    "clinical_effect": f"Both drugs in {family} family",
                    "management": f"Choose ONE drug from {family}. Discontinue {active_inn} or {prescribed_inn}.",
                    "level": "family",
                })

        return alerts

    def _check_cyp_competition(self, prescribed_inn: str, active_drugs: list) -> list:
        """Check CYP enzyme competition."""
        alerts = []

        prescribed_drug = self.blueprint["drugs"].get(prescribed_inn)
        if not prescribed_drug:
            return alerts

        prescribed_cyp = prescribed_drug["cyp"]  # ["CYP3A4_inhibitor", "CYP2C9_substrate"]

        for active_inn in active_drugs:
            active_drug = self.blueprint["drugs"].get(active_inn)
            if not active_drug:
                continue

            active_cyp = active_drug["cyp"]

            # Check for enzyme competition
            for p_cyp in prescribed_cyp:
                for a_cyp in active_cyp:
                    # Parse format: CYP2C9_inhibited_by or CYP2C9_metabolized_by
                    p_parts = p_cyp.rsplit("_", 1)
                    a_parts = a_cyp.rsplit("_", 1)
                    
                    if len(p_parts) < 2 or len(a_parts) < 2:
                        continue
                    
                    p_enzyme, p_role = p_parts
                    a_enzyme, a_role = a_parts

                    if p_enzyme == a_enzyme:
                        # metabolized_by = substrate
                        # inhibited_by = inhibitor
                        # induced_by = inducer
                        
                        if ("inhibited_by" in p_role or "inhibitor" in p_role) and ("metabolized_by" in a_role or "substrate" in a_role):
                            alerts.append({
                                "alert_type": "cyp_competition",
                                "severity": "precaution_emploi",
                                "interacting_drug": active_inn,
                                "clinical_effect": f"{prescribed_inn} inhibits {p_enzyme}, increasing {active_inn} levels",
                                "management": f"Monitor {active_inn} levels. Consider dose reduction.",
                                "level": "family",
                            })
                        elif ("induced_by" in p_role or "inducer" in p_role) and ("metabolized_by" in a_role or "substrate" in a_role):
                            alerts.append({
                                "alert_type": "cyp_competition",
                                "severity": "precaution_emploi",
                                "interacting_drug": active_inn,
                                "clinical_effect": f"{prescribed_inn} induces {p_enzyme}, reducing {active_inn} effectiveness",
                                "management": f"Monitor {active_inn} efficacy. Consider dose increase.",
                                "level": "family",
                            })

        return alerts

    def _check_dosing(self, prescribed_inn: str, labs: dict) -> list:
        """Check dosing based on patient labs."""
        alerts = []

        creatinine = labs.get("creatinine")
        if not creatinine:
            return alerts

        prescribed_drug = self.blueprint["drugs"].get(prescribed_inn)
        if not prescribed_drug:
            return alerts

        # Check renal dosing
        if creatinine > 150:  # CKD stage 4+
            renal_dose = prescribed_drug["doses"].get("renal_impairment", "")
            if renal_dose:
                alerts.append({
                    "alert_type": "dosing",
                    "severity": "precaution_emploi",
                    "interacting_drug": prescribed_inn,
                    "clinical_effect": f"Creatinine {creatinine} μmol/L indicates renal impairment",
                    "management": f"Use renal-adjusted dose: {renal_dose}",
                    "level": "patient_specific",
                })

        return alerts

    def _build_reasoning(self, prescribed_inn: str, patient_data: dict, alerts: list, safe_to_prescribe: bool) -> str:
        """Build human-readable reasoning."""
        lines = []
        lines.append(f"Patient {patient_data['patient_id']}: Prescription '{prescribed_inn}'")
        lines.append("")
        lines.append(f"Active medications: {', '.join(patient_data['active_drugs']) or 'None'}")
        lines.append(f"Known allergies: {', '.join(patient_data['allergies']) or 'None'}")
        if patient_data["labs"]["creatinine"]:
            lines.append(f"Creatinine: {patient_data['labs']['creatinine']} μmol/L")

        lines.append("")

        if not alerts:
            lines.append("✓ No interactions detected.")
        else:
            lines.append(f"Found {len(alerts)} alert(s):")
            for alert in alerts:
                severity = alert.get("severity", "")
                alert_type = alert.get("alert_type", "")
                lines.append(f"  • [{alert_type.upper()}] {severity}")
                if "clinical_effect" in alert:
                    lines.append(f"    {alert['clinical_effect']}")
                if "management" in alert:
                    lines.append(f"    → {alert['management']}")

        lines.append("")
        if safe_to_prescribe:
            lines.append("✓ RECOMMENDATION: Safe to prescribe with noted precautions.")
        else:
            lines.append("✗ RECOMMENDATION: CONTRAINDICATED or requires specialist review.")

        return "\n".join(lines)

    def close(self):
        """Close database connection."""
        if self.db_conn:
            self.db_conn.close()


if __name__ == "__main__":
    # Example usage
    validator = BlueprintValidator()

    # Test: Warfarin patient + aspirin
    result = validator.validate_prescription(patient_id=1, prescribed_inn="aspirin")
    print(result["reasoning"])
    print(f"\nSafe to prescribe: {result['safe_to_prescribe']}")

    validator.close()
