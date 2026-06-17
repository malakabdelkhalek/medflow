import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
import time

BASE_URL = "http://www.phct.com.tn/index.php/catalogue/medicament-humain/form/25/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def scrape_all():
    print(f"Connecting to {BASE_URL}...")
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Connection failed: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    options = soup.find_all("option")
    print(f"Found {len(options)} entries")

    records = []
    for option in options:
        text_line = option.text.strip()
        if not text_line or "choisir" in text_line.lower():
            continue

        words = text_line.split()
        brand_name = words[0] if words else ""

        strength_match = re.search(r'\d+\s?(mg|g|ui|µg|ml|ui|mcg)', text_line, re.IGNORECASE)
        strength = strength_match.group(0) if strength_match else "N/A"

        # extract INN — look for parenthetical or second capitalized word
        inn_match = re.search(r'\(([^)]+)\)', text_line)
        inn = inn_match.group(1).strip() if inn_match else ""

        records.append({
            "brand_name": brand_name,
            "inn_raw": inn,
            "full_text": text_line,
            "strength": strength,
        })

    return records

data = scrape_all()
if data:
    df = pd.DataFrame(data)
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../sources/pct_all_medicines.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(data)} entries to pct_all_medicines.csv")
else:
    print("No data retrieved")
