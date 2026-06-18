import os
import subprocess
import sys
import time

LOADERS_DIR = os.path.dirname(os.path.abspath(__file__))

scripts = [
    # Data Generation Phase
    ("generate_ansm_interactions.py", "Generating ANSM drug interactions CSV..."),
    ("step1_rxnorm.py", "Fetching RxNorm mappings..."),
    ("ChEMBL.py", "Fetching ChEMBL CYP pathways..."),
    ("OpenFDA.py", "Fetching OpenFDA drug labels..."),
    
    # DB Load Phase
    ("load_rxnorm_chembl.py", "Loading RxNorm & ChEMBL molecules..."),
    ("load_ansm_interactions.py", "Loading ANSM drug interactions..."),
    ("load_drugs_contraindications.py", "Loading drugs and contraindications..."),
    ("load_cyp.py", "Loading CYP relationships..."),
    ("load_pct_brands.py", "Loading PCT brand mappings..."),
]

def run_script(name, desc):
    print(f"\n==========================================")
    print(f"[RUNNING] {desc}")
    print(f"==========================================")
    script_path = os.path.join(LOADERS_DIR, name)
    
    start_time = time.time()
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    duration = time.time() - start_time
    
    if result.returncode == 0:
        print(result.stdout)
        print(f"[SUCCESS] {name} completed in {duration:.2f} seconds")
    else:
        print(result.stderr)
        print(f"[FAILURE] {name} failed with exit code {result.returncode}")
        sys.exit(1)

def main():
    print("Starting MedFlow Knowledge Base Load Orchestrator...")
    for script, desc in scripts:
        run_script(script, desc)
    print("\n==========================================")
    print("MedFlow Knowledge Base fully loaded successfully!")
    print("==========================================")

if __name__ == "__main__":
    main()
