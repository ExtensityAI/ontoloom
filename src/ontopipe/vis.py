from pathlib import Path

from pyvis.network import Network

from ontopipe.ontology.models import Ontology

COLORS = [
    "#dc2626",  # red-600
    "#ea580c",  # orange-600
    "#d97706",  # amber-600
    "#ca8a04",  # yellow-600
    "#65a30d",  # lime-600
    "#16a34a",  # green-600
    "#059669",  # emerald-600
    "#0d9488",  # teal-600
    "#0891b2",  # cyan-600
    "#0284c7",  # sky-600
    "#2563eb",  # blue-600
    "#4f46e5",  # indigo-600
    "#7c3aed",  # violet-600
    "#9333ea",  # purple-600
    "#c026d3",  # fuchsia-600
    "#db2777",  # pink-600
    "#e11d48",  # rose-600
]


def visualize_knowledge_graph(ontology: Ontology, kg: dict, output_path: Path):
    net = Network(height="100vh", width="100vw", directed=True)

    for entity in kg["data"]:
        name, cls = entity["name"], entity["cls"]
        cid = hash(cls) % len(COLORS)

        props = [(k, v) for k, v in entity.items() if k not in ("name", "cls")]

        n_edges = sum(len(v) if isinstance(v, list) else 1 for _, v in props)

        if n_edges > 2:
            net.add_node(name, label=name, title=cls, color=COLORS[cid], shape="circle", size=30 + n_edges * 5)

    for entity in kg["data"]:
        name = entity["name"]
        for prop, values in entity.items():
            if prop not in ("name", "cls") and prop in ontology.object_properties:
                for value in values:
                    if value in net.node_ids and name in net.node_ids:
                        # TODO validate that linked node exists!
                        net.add_edge(name, value, label=prop)

    # Enable interactive controls
    net.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 300},
        "barnesHut": {
          "gravitationalConstant": -12000,
          "centralGravity": 0.05,
          "springLength": 400,
          "springConstant": 0.005,
          "damping": 0.2,
          "avoidOverlap": 1
        }
      },
      "interaction": {
        "dragNodes": true,
        "dragView": true,
        "zoomView": true,
        "zoomSpeed": 1,
        "selectConnectedEdges": true,
        "hover": true,
        "hoverConnectedEdges": true,
        "keyboard": {
          "enabled": false
        },
        "navigationButtons": true,
        "tooltipDelay": 300
      },
      "manipulation": {
        "enabled": false
      },
      "nodes": {
        "font": {
          "size": 18,
          "color": "#000000"
        },
        "borderWidth": 2
      },
      "edges": {
        "font": {
          "size": 14,
          "color": "#000000"
        },
        "arrows": {
          "to": {"enabled": true, "scaleFactor": 1.2}
        },
        "width": 2
      },
      "configure": {
        "enabled": false
      }
    }
    """)

    net.save_graph(str(output_path))
