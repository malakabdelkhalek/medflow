#!/usr/bin/env python3
import csv
import html
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path


SEVERITY_ORDER = ["CONTRAINDICATED", "MAJOR", "MODERATE", "MINOR", "UNKNOWN"]
SEVERITY_COLORS = {
    "CONTRAINDICATED": "#dc2626",
    "MAJOR": "#ea580c",
    "MODERATE": "#ca8a04",
    "MINOR": "#16a34a",
    "UNKNOWN": "#64748b",
}


def clean_class(value):
    if value is None:
        return None
    name = str(value).strip()
    if name.lower() in {"inconnue", "unknown", "nan", "", "none"}:
        return None
    name = re.sub(r"\s*\[(EPC|VA|MoA|PE|CS)\]\s*", "", name).strip()
    return name.title() if len(name) > 2 else None


def parse_drugs(value):
    if not value:
        return []
    return [drug.strip().lower() for drug in str(value).split(",") if drug.strip()]


def extract_severity(value):
    text = "" if value is None else str(value).lower()
    if re.search(r"contraindicated|do not use|must not", text):
        return "CONTRAINDICATED"
    if re.search(r"major|serious|severe|life.threatening", text):
        return "MAJOR"
    if re.search(r"moderate|caution|monitor closely", text):
        return "MODERATE"
    if re.search(r"minor|minimal|unlikely", text):
        return "MINOR"
    return "UNKNOWN"


def read_rows(path):
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def build_graph(rows):
    clean_rows = []
    drug_to_class = {}

    for row in rows:
        class_name = clean_class(row.get("Classe_Finale"))
        if not class_name:
            continue
        drugs = parse_drugs(row.get("Medicaments"))
        severity = extract_severity(row.get("Interactions"))
        drug_count = int(float(row.get("Nombre_Medicaments") or len(drugs) or 1))
        clean_rows.append(
            {
                "class_name": class_name,
                "drugs": drugs,
                "drug_count": drug_count,
                "severity": severity,
                "interactions": str(row.get("Interactions") or "").lower(),
            }
        )
        for drug in drugs:
            drug_to_class[drug] = class_name

    nodes_by_id = {}
    for row in clean_rows:
        current = nodes_by_id.get(row["class_name"])
        if current is None or row["drug_count"] > current["drug_count"]:
            nodes_by_id[row["class_name"]] = {
                "id": row["class_name"],
                "drug_count": row["drug_count"],
                "severity": row["severity"],
            }

    pairs = defaultdict(lambda: {"weight": 0, "severity": set(), "drugs": set()})
    for row in clean_rows:
        class_a = row["class_name"]
        text = row["interactions"]
        for drug, class_b in drug_to_class.items():
            if class_b != class_a and drug in text:
                source, target = sorted([class_a, class_b])
                pair = pairs[(source, target)]
                pair["weight"] += 1
                pair["severity"].add(row["severity"])
                pair["drugs"].add(drug)

    nodes = sorted(nodes_by_id.values(), key=lambda item: item["drug_count"], reverse=True)
    edges = []
    for (source, target), data in pairs.items():
        top_severity = next((level for level in SEVERITY_ORDER if level in data["severity"]), "UNKNOWN")
        edges.append(
            {
                "source": source,
                "target": target,
                "weight": data["weight"],
                "severity": top_severity,
                "shared_drugs": ", ".join(sorted(data["drugs"])[:8]),
            }
        )
    edges.sort(key=lambda item: item["weight"], reverse=True)
    return nodes, edges


def write_csvs(out_dir, nodes, edges):
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "nodes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "drug_count", "severity"])
        writer.writeheader()
        writer.writerows(nodes)
    with (out_dir / "edges.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "weight", "severity", "shared_drugs"])
        writer.writeheader()
        writer.writerows(edges)


def graph_payload(nodes, edges, max_edges):
    selected_edges = edges[:max_edges]
    connected = {edge["source"] for edge in selected_edges} | {edge["target"] for edge in selected_edges}
    selected_nodes = [node for node in nodes if node["id"] in connected]
    if not selected_nodes:
        selected_nodes = nodes[:80]

    radius = 360
    count = max(1, len(selected_nodes))
    positions = {}
    for index, node in enumerate(selected_nodes):
        angle = (2 * math.pi * index) / count
        positions[node["id"]] = {
            "x": 500 + radius * math.cos(angle),
            "y": 440 + radius * math.sin(angle),
        }

    return {
        "summary": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "shownEdges": len(selected_edges),
        },
        "nodes": [
            {
                **node,
                **positions[node["id"]],
                "size": max(8, min(34, 7 + math.sqrt(max(1, node["drug_count"])))),
                "color": SEVERITY_COLORS.get(node["severity"], SEVERITY_COLORS["UNKNOWN"]),
            }
            for node in selected_nodes
        ],
        "edges": [
            {
                **edge,
                "width": max(1, min(8, 1 + math.log1p(edge["weight"]))),
                "color": SEVERITY_COLORS.get(edge["severity"], SEVERITY_COLORS["UNKNOWN"]),
            }
            for edge in selected_edges
            if edge["source"] in positions and edge["target"] in positions
        ],
    }


def write_html(out_dir, nodes, edges, max_edges):
    payload = graph_payload(nodes, edges, max_edges)
    data = json.dumps(payload, ensure_ascii=False)
    top_rows = "\n".join(
        f"""<tr>
          <td>{index}</td>
          <td>{html.escape(edge["source"])}</td>
          <td>{html.escape(edge["target"])}</td>
          <td><span class="badge {edge["severity"].lower()}">{edge["severity"]}</span></td>
          <td>{edge["weight"]}</td>
          <td>{html.escape(edge["shared_drugs"] or "n/a")}</td>
        </tr>"""
        for index, edge in enumerate(edges[:40], start=1)
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MedFlow Interaction Graph</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f8fafc; color: #111827; font-family: Arial, sans-serif; }}
    header {{ padding: 16px 24px; border-bottom: 1px solid #d1d5db; background: white; }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    p {{ margin: 0; color: #475569; }}
    main {{ display: grid; grid-template-columns: minmax(620px, 1fr) 420px; min-height: calc(100vh - 78px); }}
    .canvas-panel {{ padding: 16px; }}
    .side-panel {{ border-left: 1px solid #d1d5db; background: white; padding: 16px; overflow: auto; max-height: calc(100vh - 78px); }}
    .toolbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; }}
    .legend span, .badge {{ display: inline-flex; align-items: center; border-radius: 4px; padding: 3px 7px; color: white; font-size: 11px; font-weight: 700; }}
    .contraindicated {{ background: #dc2626; }}
    .major {{ background: #ea580c; }}
    .moderate {{ background: #ca8a04; }}
    .minor {{ background: #16a34a; }}
    .unknown {{ background: #64748b; }}
    label {{ color: #334155; font-size: 13px; }}
    select {{ margin-left: 6px; padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: white; }}
    svg {{ display: block; width: 100%; height: 680px; border: 1px solid #d1d5db; background: #ffffff; }}
    .edge {{ opacity: 0.35; }}
    .edge.active {{ opacity: 0.9; }}
    .node {{ stroke: #111827; stroke-width: 1; cursor: pointer; }}
    .node.dim, .edge.dim, .label.dim {{ opacity: 0.12; }}
    .label {{ fill: #111827; font-size: 10px; font-weight: 700; pointer-events: none; text-anchor: middle; }}
    h2 {{ margin: 0 0 10px; font-size: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 6px; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: white; color: #334155; }}
    tr:hover {{ background: #f1f5f9; }}
    .tip {{ position: fixed; display: none; max-width: 420px; padding: 10px 12px; background: #020617; border: 1px solid #475569; border-radius: 6px; color: #e5e7eb; font-size: 13px; }}
    @media (max-width: 1050px) {{
      main {{ grid-template-columns: 1fr; }}
      .side-panel {{ border-left: 0; border-top: 1px solid #d1d5db; max-height: none; }}
      svg {{ height: 560px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>MedFlow Drug Class Interaction Graph</h1>
    <p>{len(nodes)} pharmacological classes, {len(edges)} inferred class-to-class links. The page starts with the strongest {min(max_edges, len(edges))} links to keep the view readable.</p>
  </header>
  <main>
    <section class="canvas-panel">
      <div class="toolbar">
        <label>Show strongest links
          <select id="limit">
            <option value="25">25</option>
            <option value="50" selected>50</option>
            <option value="100">100</option>
            <option value="150">150</option>
          </select>
        </label>
        <div class="legend">
          <span class="contraindicated">Contraindicated</span>
          <span class="major">Major</span>
          <span class="moderate">Moderate</span>
          <span class="minor">Minor</span>
          <span class="unknown">Unknown</span>
        </div>
      </div>
      <svg viewBox="0 0 1000 820" role="img" aria-label="Drug class interaction graph"></svg>
    </section>
    <aside class="side-panel">
      <h2>Top Inferred Interactions</h2>
      <table>
        <thead>
          <tr><th>#</th><th>Class A</th><th>Class B</th><th>Severity</th><th>Weight</th><th>Evidence Drugs</th></tr>
        </thead>
        <tbody>
          {top_rows}
        </tbody>
      </table>
    </aside>
  </main>
  <div class="tip"></div>
  <script>
    const graph = {data};
    const svg = document.querySelector("svg");
    const tip = document.querySelector(".tip");
    const limitSelect = document.querySelector("#limit");

    function render(limit) {{
      svg.innerHTML = "";
      const edges = graph.edges.slice(0, limit);
      const visible = new Set();
      for (const edge of edges) {{
        visible.add(edge.source);
        visible.add(edge.target);
      }}
      const nodes = graph.nodes.filter(node => visible.has(node.id));
      const byId = new Map(nodes.map(n => [n.id, n]));

      for (const e of edges) {{
      const a = byId.get(e.source);
      const b = byId.get(e.target);
      if (!a || !b) continue;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", a.x);
      line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x);
      line.setAttribute("y2", b.y);
      line.setAttribute("stroke", e.color);
      line.setAttribute("stroke-width", e.width);
      line.classList.add("edge");
      line.addEventListener("mousemove", event => showTip(event, `<b>${{escapeHtml(e.source)}} ↔ ${{escapeHtml(e.target)}}</b><br>Severity: ${{e.severity}}<br>Weight: ${{e.weight}}<br>Shared drugs: ${{escapeHtml(e.shared_drugs || "n/a")}}`));
      line.addEventListener("mouseleave", hideTip);
      line.dataset.source = e.source;
      line.dataset.target = e.target;
      svg.appendChild(line);
    }}

      for (const n of nodes) {{
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", n.x);
      circle.setAttribute("cy", n.y);
      circle.setAttribute("r", n.size);
      circle.setAttribute("fill", n.color);
      circle.classList.add("node");
      circle.addEventListener("mousemove", event => showTip(event, `<b>${{escapeHtml(n.id)}}</b><br>Drugs: ${{n.drug_count}}<br>Severity: ${{n.severity}}`));
      circle.addEventListener("mouseleave", hideTip);
      circle.addEventListener("mouseenter", () => highlight(n.id));
      circle.addEventListener("mouseleave", () => clearHighlight());
      circle.dataset.id = n.id;
      svg.appendChild(circle);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", n.x);
      label.setAttribute("y", n.y + n.size + 13);
      label.classList.add("label");
      label.dataset.id = n.id;
      label.textContent = n.id.length > 22 ? n.id.slice(0, 20) + "..." : n.id;
      svg.appendChild(label);
    }}
    }}

    limitSelect.addEventListener("change", () => render(Number(limitSelect.value)));
    render(Number(limitSelect.value));

    function highlight(id) {{
      const linked = new Set([id]);
      for (const edge of svg.querySelectorAll(".edge")) {{
        const active = edge.dataset.source === id || edge.dataset.target === id;
        edge.classList.toggle("active", active);
        edge.classList.toggle("dim", !active);
        if (active) {{
          linked.add(edge.dataset.source);
          linked.add(edge.dataset.target);
        }}
      }}
      for (const node of svg.querySelectorAll(".node, .label")) {{
        node.classList.toggle("dim", !linked.has(node.dataset.id));
      }}
    }}

    function clearHighlight() {{
      for (const item of svg.querySelectorAll(".dim, .active")) {{
        item.classList.remove("dim", "active");
      }}
    }}

    function showTip(event, content) {{
      tip.innerHTML = content;
      tip.style.display = "block";
      tip.style.left = `${{event.clientX + 14}}px`;
      tip.style.top = `${{event.clientY + 14}}px`;
    }}

    function hideTip() {{
      tip.style.display = "none";
    }}

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, ch => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[ch]));
    }}
  </script>
</body>
</html>
"""
    (out_dir / "interactions_graph.html").write_text(html_text, encoding="utf-8")


def main():
    base = Path(__file__).resolve().parents[1]
    input_csv = base / "knowledge_base/sources/dataset/interactions_grouped_by_class.csv"
    out_dir = base / "knowledge_base/graph"
    max_edges = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    if not input_csv.exists():
        raise SystemExit(f"Missing input CSV: {input_csv}")

    nodes, edges = build_graph(read_rows(input_csv))
    write_csvs(out_dir, nodes, edges)
    write_html(out_dir, nodes, edges, max_edges)

    print(f"nodes: {len(nodes)} -> {out_dir / 'nodes.csv'}")
    print(f"edges: {len(edges)} -> {out_dir / 'edges.csv'}")
    print(f"html : {out_dir / 'interactions_graph.html'}")


if __name__ == "__main__":
    main()
