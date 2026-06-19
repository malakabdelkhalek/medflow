import requests
import csv
import time
import sys

BASE_URL = "https://api.fda.gov/drug/label.json"
INITIAL_QUERY = "search=_exists_:drug_interactions&limit=1000&sort=set_id:asc"


API_KEY = ""  

def download_all_interactions(output_filename="toutes_les_interactions_fda.csv"):
    headers_csv = ["FDA_Set_ID", "Nom_Marque", "Nom_Generique", "Classe_Pharmacologique", "Texte_Interaction"]
    
    # Initialize the URL with or without the API key
    next_url = f"{BASE_URL}?{INITIAL_QUERY}"
    if API_KEY:
        next_url += f"&api_key={API_KEY}"
        
    page_count = 1
    total_rows_saved = 0
    
    print(f"🔄 Initialisation du téléchargement global vers '{output_filename}'...")
    
    try:
        with open(output_filename, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers_csv)
            
            while next_url:
                print(f" Récupération de la page {page_count}...")
                response = requests.get(next_url, timeout=30)
                
                if response.status_code != 200:
                    print(f" Erreur lors de la récupération (Status {response.status_code})")
                    print(response.text[:500])
                    break
                    
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    print(" Fin des données détectée (Aucun résultat sur cette page).")
                    break
                
                # Écriture des données de la page courante dans le CSV
                for label in results:
                    set_id = label.get("id", "Inconnu")
                    openfda = label.get("openfda", {})
                    brand_name = openfda.get("brand_name", ["Inconnu"])[0]
                    generic_name = openfda.get("generic_name", ["Inconnu"])[0]
                    pharm_class = openfda.get("pharm_class_epc", ["Inconnue"])[0] if openfda.get("pharm_class_epc") else "Inconnue"
                    
                    interactions = label.get("drug_interactions", [])
                    for paragraph in interactions:
                        clean_paragraph = paragraph.replace("\n", " ").strip()
                        writer.writerow([set_id, brand_name, generic_name, pharm_class, clean_paragraph])
                        total_rows_saved += 1
                
                print(f"   -> {len(results)} notices traitées. Total sauvegardé : {total_rows_saved} lignes.")
                
                
                link_header = response.headers.get("Link")
                next_url = None
                
                if link_header:
                   
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link or 'rel="Next"' in link:
                           
                            next_url = link.substring(link.find("<")+1, link.find(">")) if hasattr(link, 'substring') else link.split("<")[1].split(">")[0]
                           
                            if API_KEY and "api_key=" not in next_url:
                                next_url += f"&api_key={API_KEY}"
                
                page_count += 1
                
                # Respecter les limites de l'API (un léger délai pour éviter d'être bloqué)
                time.sleep(0.25)
                
        print(f" Terminé avec succès ! {total_rows_saved} interactions au total ont été sauvegardées dans '{output_filename}'.")
        
    except KeyboardInterrupt:
        print("\n Processus interrompu par l'utilisateur. Le fichier CSV contient les données récoltées jusqu'ici.")
    except Exception as e:
        print(f" Une erreur inattendue est survenue : {e}")

if __name__ == "__main__":
    download_all_interactions()