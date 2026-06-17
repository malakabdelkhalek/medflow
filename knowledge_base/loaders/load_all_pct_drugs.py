import csv, os, re, psycopg2

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "medflow"),
    user=os.getenv("POSTGRES_USER", "medflow"),
    password=os.getenv("POSTGRES_PASSWORD", "medflow"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
)
cur = conn.cursor()

csv_path = os.path.join(os.path.dirname(__file__), "../sources/pct_all_medicines.csv")
loaded, skipped = 0, 0

with open(csv_path, newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        brand = row["brand_name"].strip()
        inn_raw = row["inn_raw"].strip().lower()
        full_text = row["full_text"].strip()

        if not brand:
            skipped += 1
            continue

        # derive INN: use inn_raw if present, else brand name lowercased
        inn = inn_raw if inn_raw else brand.lower()
        inn = re.sub(r'\s+', ' ', inn).strip()

        try:
            cur.execute("SAVEPOINT sp")

            # get or create molecule
            cur.execute("SELECT id FROM molecules WHERE inn = %s", (inn,))
            mol = cur.fetchone()
            if not mol:
                cur.execute("INSERT INTO molecules (inn) VALUES (%s) RETURNING id", (inn,))
                mol = cur.fetchone()

            # insert drug
            cur.execute("""
                INSERT INTO drugs (molecule_id, brand_name, brand_name_tn)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (mol[0], brand, brand))

            cur.execute("RELEASE SAVEPOINT sp")
            loaded += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp")
            skipped += 1

conn.commit()
print(f"Loaded: {loaded}, Skipped: {skipped}")
cur.close()
conn.close()
