import pandas as pd
import os

# Chemins des fichiers
source_path = r"C:\Users\arijk\Desktop\medflow\knowledge_base\sources\dataset\toutes_les_interactions_fda.csv"
output_path = r"C:\Users\arijk\Desktop\medflow\knowledge_base\sources\dataset\interactions_fda_clean.csv"

def clean_local_csv(input_file, output_file):
    print(" Chargement du fichier CSV en mémoire...")
    
    try:
        # Lecture du fichier CSV d'origine
        df = pd.read_csv(input_file, encoding='utf-8')
        
        initial_rows = len(df)
        print(f" Fichier chargé avec succès ({initial_rows} lignes au total).")
        
        # 1. Suppression de la colonne 'FDA_Set_ID' si elle existe
        if 'FDA_Set_ID' in df.columns:
            df = df.drop(columns=['FDA_Set_ID'])
            print("  Colonne 'FDA_Set_ID' supprimée.")
        elif 'id' in df.columns: # Au cas où la colonne s'appellerait 'id'
            df = df.drop(columns=['id'])
            print(" Colonne 'id' supprimée.")
            
        # 2. Suppression des lignes où Nom_Marque est nul, vide ou vaut "Inconnu"
        # On passe tout en minuscules temporairement pour attraper "Inconnu", "inconnu", "INCONNU"
        df['Nom_Marque_Lower'] = df['Nom_Marque'].astype(str).str.strip().str.lower()
        
        # Filtrage
        condition_valide = (df['Nom_Marque'].notna()) & (df['Nom_Marque_Lower'] != 'inconnu') & (df['Nom_Marque_Lower'] != '')
        df_clean = df[condition_valide].copy()
        
        # On supprime la colonne temporaire de calcul
        df_clean = df_clean.drop(columns=['Nom_Marque_Lower'])
        
        final_rows = len(df_clean)
        rows_deleted = initial_rows - final_rows
        
        # 3. Sauvegarde du nouveau fichier nettoyé
        print(f" Sauvegarde du fichier nettoyé vers : {output_file}")
        df_clean.to_csv(output_file, index=False, encoding='utf-8')
        
        print("\n Nettoyage terminé avec succès !")
        print(f"   -> Lignes d'origine : {initial_rows}")
        print(f"   -> Lignes 'Inconnu' supprimées (60% environ) : {rows_deleted}")
        print(f"   -> Lignes valides conservées : {final_rows}")
        
    except FileNotFoundError:
        print(f" Erreur : Le fichier est introuvable au chemin spécifié.\nVeuillez vérifier que le dossier et le fichier existent bien.")
    except Exception as e:
        print(f" Une erreur est survenue lors du traitement : {e}")

if __name__ == "__main__":
    clean_local_csv(source_path, output_path)