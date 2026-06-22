import argparse
from pathlib import Path

try:
    import networkx as nx
    import pandas as pd
    from pyvis.network import Network
except ImportError as exc:
    missing = exc.name
    raise ImportError(
        f"Missing package '{missing}'. Install dependencies with:\n"
        "    python -m pip install pandas networkx pyvis"
    ) from exc

BASE = Path(__file__).resolve().parents[2]
GRAPH_DIR = BASE / "knowledge_base" / "graph"
DEFAULT_NODES = GRAPH_DIR / "nodes.csv"
DEFAULT_EDGES = GRAPH_DIR / "edges.csv"
DEFAULT_OUTPUT = GRAPH_DIR / "graph_interactive.html"

SEVERITY_COLORS = {
    "CONTRAINDICATED": "#d62728",
    "MAJOR": "#ff7f0e",
    "MODERATE": "#bcbd22",
    "MINOR": "#2ca02c",
    "UNKNOWN": "#7f7f7f",
}


def load_data(nodes_path: Path, edges_path: Path):
    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)
    return nodes, edges


def build_graph(nodes, edges):
    G = nx.Graph()
    for _, row in nodes.iterrows():
        node_id = str(row["id"])
        G.add_node(
            node_id,
            title=f"{node_id}\nDrug count: {row.get('drug_count', '')}\nSeverity: {row.get('severity', '')}",
            drug_count=int(row.get("drug_count", 1)),
            severity=str(row.get("severity", "UNKNOWN")) if not pd.isna(row.get("severity")) else "UNKNOWN",
        )

    for _, row in edges.iterrows():
        src = str(row["source"])
        tgt = str(row["target"])
        G.add_edge(
            src,
            tgt,
            weight=float(row.get("weight", 1)),
            title=f"Weight: {row.get('weight', '')}\nSeverity: {row.get('severity', '')}\nShared drugs: {row.get('shared_drugs', '')}",
            severity=str(row.get("severity", "UNKNOWN")) if not pd.isna(row.get("severity")) else "UNKNOWN",
        )

    return G


def export_interactive(G: nx.Graph, output_path: Path, title: str):
    if G.number_of_nodes() == 0:
        raise ValueError("Graph has no nodes. Check your nodes.csv file.")

    net = Network(height="1000px", width="100%", bgcolor="#ffffff", font_color="#222222")
    net.force_atlas_2based()
    net.show_buttons(filter_=["physics"])
    net.set_options("""
var options = {
  "nodes": {
    "shape": "dot",
    "scaling": {
      "min": 10,
      "max": 40
    }
  },
  "edges": {
    "color": {
      "inherit": true
    },
    "smooth": false
  },
  "physics": {
    "forceAtlas2Based": {
      "gravitationalConstant": -50,
      "centralGravity": 0.01,
      "springLength": 100,
      "springConstant": 0.08
    },
    "maxVelocity": 50,
    "solver": "forceAtlas2Based"
  }
}
""")

    for node, data in G.nodes(data=True):
        color = SEVERITY_COLORS.get(data.get("severity", "UNKNOWN"), SEVERITY_COLORS["UNKNOWN"])
        net.add_node(
            node,
            label=node,
            title=data.get("title", node),
            value=max(1, data.get("drug_count", 1)),
            color=color,
        )

    for source, target, data in G.edges(data=True):
        edge_color = SEVERITY_COLORS.get(data.get("severity", "UNKNOWN"), SEVERITY_COLORS["UNKNOWN"])
        net.add_edge(
            source,
            target,
            value=max(1, data.get("weight", 1)),
            title=data.get("title", ""),
            color=edge_color,
        )

    net.heading = title
    net.show(str(output_path))
    print(f"Saved interactive graph to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an interactive HTML graph from nodes.csv and edges.csv.")
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES, help="Path to nodes.csv")
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES, help="Path to edges.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output HTML file path")
    parser.add_argument("--title", type=str, default="Drug Class Interaction Graph", help="Graph title")
    args = parser.parse_args()

    if not args.nodes.exists():
        raise FileNotFoundError(f"Nodes CSV not found: {args.nodes}")
    if not args.edges.exists():
        raise FileNotFoundError(f"Edges CSV not found: {args.edges}")

    nodes_df, edges_df = load_data(args.nodes, args.edges)
    graph = build_graph(nodes_df, edges_df)
    export_interactive(graph, args.output, args.title)
