import pandas as pd
import psycopg2

# ============================================================
# CONFIG
# ============================================================
BASE       = r"C:\Users\arijk\Desktop\medflow"
GRAPH_DIR  = rf"{BASE}\knowledge_base\graph"
NODES_CSV  = rf"{GRAPH_DIR}\nodes.csv"
EDGES_CSV  = rf"{GRAPH_DIR}\edges.csv"

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "medflow",
    "user":     "medflow",
    "password": "medflow",
}

GRAPH_NAME = "drug_interactions"

# ============================================================
# LOAD CSVs
# ============================================================
nodes_df = pd.read_csv(NODES_CSV)
edges_df = pd.read_csv(EDGES_CSV)
print(f"📥 nodes.csv: {len(nodes_df)} rows")
print(f"📥 edges.csv: {len(edges_df)} rows")

# ============================================================
# CONNECT
# ============================================================
print("\n🔌 Connecting to PostgreSQL...")
conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
cur = conn.cursor()

cur.execute("LOAD '$libdir/plugins/age';")
cur.execute("SET search_path = ag_catalog, \"$user\", public;")
print("✅ Connected")

# ============================================================
# CREATE GRAPH (if not exists)
# ============================================================
cur.execute(f"SELECT count(*) FROM ag_graph WHERE name = '{GRAPH_NAME}';")
if cur.fetchone()[0] == 0:
    cur.execute(f"SELECT create_graph('{GRAPH_NAME}');")
    print(f"✅ Graph '{GRAPH_NAME}' created")
else:
    print(f"ℹ️  Graph '{GRAPH_NAME}' already exists — appending data")

# ============================================================
# INSERT NODES
# ============================================================
print(f"\n📌 Inserting {len(nodes_df)} nodes...")
ok = 0
for _, row in nodes_df.iterrows():
    name  = str(row["id"]).replace("'", "\\'")
    count = int(row["drug_count"])
    sev   = str(row["severity"])
    try:
        cur.execute(f"""
            SELECT * FROM cypher('{GRAPH_NAME}', $$
                MERGE (c:DrugClass {{name: '{name}'}})
                SET c.drug_count = {count},
                    c.severity   = '{sev}'
                RETURN c
            $$) AS (c agtype);
        """)
        ok += 1
    except Exception as e:
        print(f"  ⚠️  Node skipped ({name}): {e}")

print(f"✅ {ok}/{len(nodes_df)} nodes inserted")

# ============================================================
# INSERT EDGES
# ============================================================
print(f"\n🔗 Inserting {len(edges_df)} edges...")
ok = 0
for _, row in edges_df.iterrows():
    src   = str(row["source"]).replace("'", "\\'")
    tgt   = str(row["target"]).replace("'", "\\'")
    w     = int(row["weight"])
    sev   = str(row["severity"])
    drugs = str(row["shared_drugs"]).replace("'", "\\'")
    try:
        cur.execute(f"""
            SELECT * FROM cypher('{GRAPH_NAME}', $$
                MATCH (a:DrugClass {{name: '{src}'}})
                MATCH (b:DrugClass {{name: '{tgt}'}})
                MERGE (a)-[r:INTERACTS_WITH]->(b)
                SET r.weight       = {w},
                    r.severity     = '{sev}',
                    r.shared_drugs = '{drugs}'
                RETURN r
            $$) AS (r agtype);
        """)
        ok += 1
    except Exception as e:
        print(f"  ⚠️  Edge skipped ({src} → {tgt}): {e}")

print(f"✅ {ok}/{len(edges_df)} edges inserted")

# ============================================================
# VERIFY
# ============================================================
print("\n📊 Graph summary:")
cur.execute(f"""
    SELECT * FROM cypher('{GRAPH_NAME}', $$
        MATCH (c:DrugClass) RETURN count(c)
    $$) AS (total agtype);
""")
print(f"   Nodes : {cur.fetchone()[0]}")

cur.execute(f"""
    SELECT * FROM cypher('{GRAPH_NAME}', $$
        MATCH ()-[r:INTERACTS_WITH]->() RETURN count(r)
    $$) AS (total agtype);
""")
print(f"   Edges : {cur.fetchone()[0]}")

cur.close()
conn.close()
print("\n✅ Done — graph loaded into PostgreSQL/AGE")