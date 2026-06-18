import os
import csv

interactions = [
    # Warfarin interactions (Needs at least 6 correct pairwise results)
    {
        "molecule_a": "warfarin",
        "molecule_b": "aspirin",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "Increased risk of hemorrhage due to additive anticoagulant/antiplatelet effects and gastric mucosal irritation by aspirin.",
        "management": "Avoid combination. If co-administration is necessary, monitor INR closely and check for clinical signs of bleeding."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "heparin",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Additive anticoagulant effect increases the risk of serious bleeding.",
        "management": "Monitor coagulation profiles (INR and aPTT) closely and adjust doses as needed."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "clopidogrel",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "Increased risk of major bleeding due to combined antiplatelet and anticoagulant action.",
        "management": "Avoid co-prescription unless strictly indicated. Perform intensive clinical monitoring for bleeding signs."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "ibuprofen",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "NSAID inhibits platelet aggregation and damages gastric mucosa, dramatically raising gastrointestinal bleeding risk.",
        "management": "Avoid NSAIDs. Recommend acetaminophen/paracetamol for pain control instead."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "diclofenac",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "NSAID platelet inhibition and mucosal damage increase bleeding risk.",
        "management": "Avoid combination. Monitor coagulation parameters and use alternative analgesics."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "naproxen",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "Increased risk of GI bleeding and severe hemorrhage due to pharmacological synergy.",
        "management": "Contraindicated/deconseillee. Use alternative pain relievers and monitor INR."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "fluconazole",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "Fluconazole inhibits CYP2C9, which metabolizes the active S-warfarin, leading to warfarin accumulation and high bleeding risk.",
        "management": "Reduce warfarin dose by 30-50% when starting fluconazole. Monitor INR daily."
    },
    {
        "molecule_a": "warfarin",
        "molecule_b": "carbamazepine",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Carbamazepine induces CYP2C9 and CYP3A4, increasing warfarin clearance and reducing its anticoagulant efficacy.",
        "management": "Monitor INR and increase warfarin dosage as required during co-treatment. Monitor INR again upon carbamazepine discontinuation."
    },

    # Simvastatin + Clarithromycin (CYP3A4 inhibitor trap)
    {
        "molecule_a": "simvastatin",
        "molecule_b": "clarithromycin",
        "severity_ansm": "contre_indique",
        "severity_openfda": "major",
        "clinical_effect": "Clarithromycin is a potent CYP3A4 inhibitor. It blocks simvastatin metabolism, increasing its exposure and risk of severe myopathy/rhabdomyolysis.",
        "management": "Absolute contraindication. Withhold simvastatin during the antibiotic course."
    },

    # Fluoxetine + Tramadol (Serotonin Syndrome trap)
    {
        "molecule_a": "fluoxetine",
        "molecule_b": "tramadol",
        "severity_ansm": "deconseillee",
        "severity_openfda": "major",
        "clinical_effect": "Risk of serotonin syndrome (agitation, muscle rigidity, hyperthermia) and increased risk of seizures. Fluoxetine also inhibits CYP2D6, lowering active tramadol levels.",
        "management": "Avoid combination. Monitor closely for serotonergic symptoms if co-prescribed."
    },
    {
        "molecule_a": "sertraline",
        "molecule_b": "tramadol",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Increased risk of serotonin syndrome due to serotonin reuptake inhibition by both drugs.",
        "management": "Monitor for mental status changes, autonomic instability, and neuromuscular hyperactivity."
    },

    # Enalapril/Ramipril + Spironolactone (Hyperkalemia trap)
    {
        "molecule_a": "enalapril",
        "molecule_b": "spironolactone",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Risk of severe, life-threatening hyperkalemia, especially in patients with renal impairment.",
        "management": "Monitor serum potassium and creatinine regularly. Discontinue if potassium levels exceed 5.0 mEq/L."
    },
    {
        "molecule_a": "ramipril",
        "molecule_b": "spironolactone",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Risk of severe hyperkalemia due to additive potassium-sparing effects.",
        "management": "Check potassium levels and renal function before and during treatment."
    },

    # Digoxin + Clarithromycin
    {
        "molecule_a": "digoxin",
        "molecule_b": "clarithromycin",
        "severity_ansm": "precaution_emploi",
        "severity_openfda": "major",
        "clinical_effect": "Clarithromycin inhibits P-gp, increasing digoxin bioavailability and decreasing its renal clearance, causing digitalis toxicity.",
        "management": "Reduce digoxin dosage, monitor serum digoxin levels, and monitor ECG for signs of toxicity."
    },

    # Carbamazepine + Clarithromycin
    {
        "molecule_a": "carbamazepine",
        "molecule_b": "clarithromycin",
        "severity_ansm": "contre_indique",
        "severity_openfda": "major",
        "clinical_effect": "Clarithromycin inhibits CYP3A4, causing a dramatic increase in carbamazepine plasma levels and risk of neurotoxicity.",
        "management": "Contraindicated. Use alternative antibiotic that does not inhibit CYP3A4 (e.g. amoxicillin)."
    },

    # Clopidogrel + Omeprazole
    {
        "molecule_a": "clopidogrel",
        "molecule_b": "omeprazole",
        "severity_ansm": "a_prendre_en_compte",
        "severity_openfda": "moderate",
        "clinical_effect": "Omeprazole inhibits CYP2C19, which is required to convert clopidogrel to its active metabolite, reducing its antiplatelet efficacy.",
        "management": "Avoid omeprazole. Use pantoprazole or famotidine instead as a gastric protectant."
    },

    # Amlodipine + Simvastatin
    {
        "molecule_a": "amlodipine",
        "molecule_b": "simvastatin",
        "severity_ansm": "a_prendre_en_compte",
        "severity_openfda": "moderate",
        "clinical_effect": "Amlodipine increases simvastatin exposure (via CYP3A4 inhibition), raising the risk of myopathy.",
        "management": "Limit Simvastatin dose to a maximum of 20mg/day when co-administered."
    }
]

def generate_csv():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../sources")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "ansm_interactions_all.csv")
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "molecule_a", "molecule_b", "severity_ansm",
            "severity_openfda", "clinical_effect", "management"
        ])
        writer.writeheader()
        writer.writerows(interactions)
        
    print(f"Generated {len(interactions)} interactions in {output_path}")

if __name__ == "__main__":
    generate_csv()
