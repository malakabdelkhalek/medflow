import argparse
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import networkx as nx
    import pandas as pd
except ImportError as exc:
    missing = exc.name
    raise ImportError(
        f"Missing package '{missing}'. Install dependencies with:\n"
        "    python -m pip install pandas matplotlib networkx"
    ) from exc

BASE = Path(__file__).resolve().parents[2]
GRAPH_DIR = BASE / "knowledge_base" / "graph"
DEFAULT_NODES = GRAPH_DIR / "nodes.csv"
DEFAULT_EDGES = GRAPH_DIR / "edges.csv"

SEVERITY_COLORS = {
    "CONTRAINDICATED": "red",
    "MAJOR": "orange",
    "MODERATE": "gold",
    "MINOR": "green",
    "UNKNOWN": "gray",
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
            severity=str(row.get("severity", "UNKNOWN")) if not pd.isna(row.get("severity")) else "UNKNOWN",
            shared_drugs=str(row.get("shared_drugs", "")),
        )

    return G


def draw_graph(G, output_path: Path, title: str):
    if G.number_of_nodes() == 0:
        raise ValueError("Graph has no nodes. Check your nodes.csv file.")

    plt.figure(figsize=(14, 10))
    pos = nx.spring_layout(G, seed=42, k=0.8)

    node_sizes = [max(100, G.nodes[n].get("drug_count", 1) * 15) for n in G.nodes]
    node_colors = [SEVERITY_COLORS.get(G.nodes[n].get("severity", "UNKNOWN"), "gray") for n in G.nodes]
    edge_widths = [max(1.0, G.edges[e].get("weight", 1) * 0.35) for e in G.edges]
    edge_colors = [SEVERITY_COLORS.get(G.edges[e].get("severity", "UNKNOWN"), "gray") for e in G.edges]

    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.85)
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_colors, alpha=0.7)
    nx.draw_networkx_labels(G, pos, font_size=8, font_family="sans-serif")

    legend_handles = []
    for severity, color in SEVERITY_COLORS.items():
        legend_handles.append(plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=10, label=severity))
    plt.legend(handles=legend_handles, title="Severity", loc="upper right")

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    print(f"Saved graph image to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize drug class graph from nodes.csv and edges.csv.")
    parser.add_argument(
        "--nodes",
        type=Path,
        default=DEFAULT_NODES,
        help="Path to nodes.csv (default: knowledge_base/graph/nodes.csv)",
    )
    parser.add_argument(
        "--edges",
        type=Path,
        default=DEFAULT_EDGES,
        help="Path to edges.csv (default: knowledge_base/graph/edges.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GRAPH_DIR / "graph_plot.png",
        help="Output image file path (default: knowledge_base/graph/graph_plot.png)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Drug Class Interaction Graph",
        help="Title for the generated graph image.",
    )
    args = parser.parse_args()

    if not args.nodes.exists():
        raise FileNotFoundError(f"Nodes CSV not found: {args.nodes}")
    if not args.edges.exists():
        raise FileNotFoundError(f"Edges CSV not found: {args.edges}")

    nodes_df, edges_df = load_data(args.nodes, args.edges)
    graph = build_graph(nodes_df, edges_df)
    draw_graph(graph, args.output, args.title)
