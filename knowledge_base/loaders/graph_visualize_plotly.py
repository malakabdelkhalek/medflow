import argparse
from pathlib import Path
import math

try:
    import pandas as pd
    import networkx as nx
    import plotly.graph_objects as go
except ImportError as exc:
    missing = exc.name
    raise ImportError(
        f"Missing package '{missing}'. Install dependencies with:\n"
        "    python -m pip install -r requirements-visualization.txt"
    ) from exc

BASE = Path(__file__).resolve().parents[2]
GRAPH_DIR = BASE / "knowledge_base" / "graph"
DEFAULT_NODES = GRAPH_DIR / "nodes.csv"
DEFAULT_EDGES = GRAPH_DIR / "edges.csv"
DEFAULT_OUTPUT = GRAPH_DIR / "graph_plotly.html"

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
            drug_count=int(row.get("drug_count", 1)),
            severity=str(row.get("severity", "UNKNOWN")) if not pd.isna(row.get("severity")) else "UNKNOWN",
            title=f"{node_id}<br>Drug count: {row.get('drug_count', '')}<br>Severity: {row.get('severity', '')}",
        )

    for _, row in edges.iterrows():
        src = str(row["source"])
        tgt = str(row["target"])
        G.add_edge(
            src,
            tgt,
            weight=float(row.get("weight", 1)),
            severity=str(row.get("severity", "UNKNOWN")) if not pd.isna(row.get("severity")) else "UNKNOWN",
            title=f"Weight: {row.get('weight', '')}<br>Severity: {row.get('severity', '')}<br>Shared drugs: {row.get('shared_drugs', '')}",
        )

    return G


def make_plot(G: nx.Graph, title: str):
    if G.number_of_nodes() == 0:
        raise ValueError("Graph has no nodes. Check your nodes.csv file.")

    pos = nx.spring_layout(G, seed=42, k=0.8)

    edge_x = []
    edge_y = []
    edge_text = []
    edge_colors = []
    edge_widths = []

    for source, target, data in G.edges(data=True):
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        edge_text.append(data.get("title", ""))
        edge_colors.append(SEVERITY_COLORS.get(data.get("severity", "UNKNOWN"), SEVERITY_COLORS["UNKNOWN"]))
        edge_widths.append(max(1, float(data.get("weight", 1)) * 0.35))

    # single edge trace (lighter default) — detailed hover per-edge handled below
    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="rgba(120,120,120,0.25)"),
        hoverinfo="text",
        text=edge_text,
        mode="lines",
    )

    node_x = []
    node_y = []
    node_color = []
    node_size = []
    node_text = []

    # node sizes: use sqrt scaling to avoid huge circles
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_color.append(SEVERITY_COLORS.get(data.get("severity", "UNKNOWN"), SEVERITY_COLORS["UNKNOWN"]))
        drug_count = max(1, int(data.get("drug_count", 1)))
        size = 8 + math.sqrt(drug_count) * 6
        size = min(size, 60)  # clamp max
        node_size.append(size)
        node_text.append(data.get("title", node))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        text=node_text,
        marker=dict(
            showscale=False,
            color=node_color,
            size=node_size,
            opacity=0.85,
            line_width=1,
            line_color="#333333",
        ),
    )

    fig = go.Figure(data=[edge_trace, node_trace])

    # add a simple legend using invisible scatter traces per severity
    for sev, color in SEVERITY_COLORS.items():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=12, color=color),
                name=sev,
                hoverinfo="none",
            )
        )

    fig.update_layout(
        title=title,
        title_x=0.5,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hovermode="closest",
    )
    return fig


def save_html(fig: go.Figure, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    print(f"Saved interactive HTML to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an interactive Plotly graph from nodes.csv and edges.csv.")
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
    figure = make_plot(graph, args.title)
    save_html(figure, args.output)
