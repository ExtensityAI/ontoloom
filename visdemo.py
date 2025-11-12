import json
from pathlib import Path

from pyvis.network import Network

from ontology_hydra.ontology.models import Ontology

ontology = Path("temp/biography/output-gpt5/cache/ontology.json")
output_path = Path("temp/biography/output-gpt5/ontology.html")

ontology = Ontology.model_validate_json(ontology.read_text(encoding="utf-8"))
kg = json.loads(Path("temp/biography/output-gpt5/cache/kg.partial.json").read_text(encoding="utf-8"))


def visualize_ontology(ontology: Ontology, output_path: Path):
    net = Network(height="100vh", width="100%", directed=True, bgcolor="#ffffff", font_color="#222")

    # Add class nodes
    for cls_name, cls in ontology.classes.items():
        title_parts = []
        if cls.description:
            if cls.description.description:
                title_parts.append(f"<b>Description:</b> {cls.description.description}")
            if cls.description.constraints:
                title_parts.append(f"<b>Constraints:</b> {cls.description.constraints}")
        title_html = "<br/>".join(title_parts) if title_parts else cls_name
        color = "#ffcc66" if cls.superclass is None else "#d0e6ff"
        net.add_node(
            cls_name,
            label=cls_name,
            title=title_html,
            shape="box",
            color=color,
            font={"multi": True},
        )

    # Subclass edges
    for cls in ontology.classes.values():
        if cls.superclass and cls.superclass in ontology.classes:
            net.add_edge(
                cls.superclass,
                cls.name,
                label="is_a",
                color="#999999",
                arrows="to",
                dashes=True,
                physics=True,
            )

    # Object property edges
    for prop in ontology.object_properties.values():
        if not prop.domain or not prop.range:
            continue
        for d in prop.domain:
            if d not in ontology.classes:
                continue
            for r in prop.range:
                if r not in ontology.classes:
                    continue
                net.add_edge(
                    d,
                    r,
                    label=prop.name,
                    color="#2b7ce9",
                    arrows="to",
                    physics=True,
                )

    # Interaction / style options
    net.set_options(
        """
{
  "layout": { "randomSeed": 42, "improvedLayout": true },
  "interaction": {
    "hover": true,
    "hoverConnectedEdges": true,
    "navigationButtons": true,
    "keyboard": true,
    "zoomView": true,
    "multiselect": true,
    "tooltipDelay": 100
  },
  "nodes": {
    "shape": "box",
    "shapeProperties": { "borderRadius": 8 },
    "borderWidth": 1,
    "borderWidthSelected": 2,
    "shadow": true,
    "font": { "face": "Inter, Arial, sans-serif", "size": 15, "color": "#222222" },
    "color": {
      "border": "#A0AEC0",
      "background": "#F7FAFC",
      "highlight": { "border": "#2B6CB0", "background": "#EBF8FF" },
      "hover": { "border": "#2B6CB0", "background": "#EDF2F7" }
    },
    "margin": 10
  },
  "edges": {
    "smooth": { "enabled": true, "type": "cubicBezier", "roundness": 0.15 },
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.9 } },
    "color": { "color": "#A0AEC0", "highlight": "#2B6CB0", "hover": "#2B6CB0" },
    "width": 1.2,
    "selectionWidth": 2,
    "font": { "align": "top", "size": 12, "color": "#374151", "strokeWidth": 0 },
    "length": 240
  },
  "physics": {
    "enabled": true,
    "solver": "repulsion",
    "stabilization": { "enabled": true, "iterations": 1500, "fit": true },
    "minVelocity": 0.5,
    "timestep": 0.45,
    "repulsion": {
      "nodeDistance": 500,
      "centralGravity": 0.08,
      "springLength": 300,
      "springConstant": 0.025,
      "damping": 0.4
    },
    "maxVelocity": 25
  }
}
        """
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(output_path), notebook=False)

    # Increase initial zoom (post-process HTML to add a moveTo call)
    html = output_path.read_text(encoding="utf-8")
    html = html.replace(
        "var network = new vis.Network(container, data, options);",
        "var network = new vis.Network(container, data, options);\n"
        "network.once('stabilizationIterationsDone', function () { "
        "network.moveTo({ scale: 1.4 }); "
        "network.setOptions({ physics: { enabled: false } }); "
        "});\n"
        "network.stabilize();",
    )
    output_path.write_text(html, encoding="utf-8")


def visualize_kg(ontology: Ontology, kg, output_path: Path):
    """
    Visualize a knowledge graph (generated via src/ontopipe/kg/kg.py) together with the ontology.
    """
    from pyvis.network import Network

    net = Network(height="100vh", width="100%", directed=True, bgcolor="#ffffff", font_color="#222")

    # 1) Class nodes (same style as visualize_ontology)
    for cls_name, cls in ontology.classes.items():
        title_parts = []
        if cls.description:
            if cls.description.description:
                title_parts.append(f"<b>Description:</b> {cls.description.description}")
            if cls.description.constraints:
                title_parts.append(f"<b>Constraints:</b> {cls.description.constraints}")
        title_html = "<br/>".join(title_parts) if title_parts else cls_name
        color = "#ffcc66" if cls.superclass is None else "#d0e6ff"
        net.add_node(
            cls_name,
            label=cls_name,
            title=title_html,
            shape="box",
            color=color,
            font={"multi": True},
        )

    # Subclass edges
    for cls in ontology.classes.values():
        if cls.superclass and cls.superclass in ontology.classes:
            net.add_edge(
                cls.superclass,
                cls.name,
                label="is_a",
                color="#999999",
                arrows="to",
                dashes=True,
                physics=True,
            )

    # 2) Collect entities from the KG (schema-agnostic extraction)
    def _to_dict(x):
        if hasattr(x, "model_dump"):
            return x.model_dump(exclude_none=True)
        if hasattr(x, "dict"):
            return x.dict(exclude_none=True)
        return dict(x)

    def _get_name(d: dict) -> str | None:
        for k in ("name", "id", "entity", "label", "key"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v
        return None

    def _get_classes(d: dict) -> list[str]:
        classes = []
        # include 'cls' (the discriminator in DynamicPartialEntity)
        for k in ("cls", "class", "classes", "type", "types", "is_a", "isa"):
            v = d.get(k)
            if isinstance(v, str):
                classes.append(v)
            elif isinstance(v, list):
                classes += [x for x in v if isinstance(x, str)]
        return [c for c in classes if c in ontology.classes]

    # Safe access to KG data (supports both Pydantic model instance and dict)
    kg_items = []
    if hasattr(kg, "data"):
        data = getattr(kg, "data")
        if isinstance(data, list):
            kg_items = data
    elif isinstance(kg, dict) and "data" in kg:
        kg_items = kg["data"]

    # Build entity map
    entities: list[tuple[str, dict]] = []
    for item in kg_items:
        try:
            d = _to_dict(item)
        except Exception:
            continue
        name = _get_name(d)
        if not name:
            continue
        entities.append((name, d))

    ent_id = lambda n: f"inst:{n}"
    entity_ids: dict[str, str] = {name: ent_id(name) for name, _ in entities}

    # 3) Add entity nodes (ellipses)
    for name, d in entities:
        classes = _get_classes(d)
        title_parts = []
        if classes:
            title_parts.append(f"<b>Classes:</b> {', '.join(classes)}")

        # Add data properties (if schema aligns with ontology)
        if hasattr(ontology, "data_properties") and isinstance(ontology.data_properties, dict):
            for dp_name in ontology.data_properties.keys():
                if dp_name in d and d[dp_name] is not None:
                    val = d[dp_name]
                    if isinstance(val, list):
                        vstr = ", ".join(str(x) for x in val)
                    else:
                        vstr = str(val)
                    title_parts.append(f"<b>{dp_name}:</b> {vstr}")

        title_html = "<br/>".join(title_parts) if title_parts else name
        color = "#C6F6D5" if classes else "#FEE2E2"  # green if typed, light red if untyped

        net.add_node(
            entity_ids[name],
            label=name,
            title=title_html,
            shape="ellipse",
            color=color,
            font={"multi": True},
        )

    # 4) Add is_a edges (entity -> class)
    for name, d in entities:
        classes = _get_classes(d)
        for c in classes:
            if c in ontology.classes:
                net.add_edge(
                    entity_ids[name],
                    c,
                    label="is_a",
                    color="#999999",
                    arrows="to",
                    dashes=True,
                    physics=True,
                )

    # 5) Add object property edges (entity -> entity)
    obj_props = getattr(ontology, "object_properties", {}) if hasattr(ontology, "object_properties") else {}
    for name, d in entities:
        for prop_name in obj_props.keys():
            if prop_name not in d or d[prop_name] is None:
                continue
            targets = d[prop_name]
            if not isinstance(targets, list):
                targets = [targets]
            for t in targets:
                if isinstance(t, dict):
                    tname = _get_name(t) or str(t)
                else:
                    tname = str(t)
                if not tname:
                    continue
                # ensure target node exists (placeholder if unseen)
                if tname not in entity_ids:
                    entity_ids[tname] = ent_id(tname)
                    net.add_node(
                        entity_ids[tname],
                        label=tname,
                        title=tname,
                        shape="ellipse",
                        color="#FFF5F5",
                        font={"multi": True},
                    )
                net.add_edge(
                    entity_ids[name],
                    entity_ids[tname],
                    label=prop_name,
                    color="#2b7ce9",
                    arrows="to",
                    physics=True,
                )

    # 6) Interaction / style options (same as visualize_ontology)
    net.set_options(
        """
{
  "layout": { "randomSeed": 42, "improvedLayout": true },
  "interaction": {
    "hover": true,
    "hoverConnectedEdges": true,
    "navigationButtons": true,
    "keyboard": true,
    "zoomView": true,
    "multiselect": true,
    "tooltipDelay": 100
  },
  "nodes": {
    "shape": "box",
    "shapeProperties": { "borderRadius": 8 },
    "borderWidth": 1,
    "borderWidthSelected": 2,
    "shadow": true,
    "font": { "face": "Inter, Arial, sans-serif", "size": 15, "color": "#222222" },
    "color": {
      "border": "#A0AEC0",
      "background": "#F7FAFC",
      "highlight": { "border": "#2B6CB0", "background": "#EBF8FF" },
      "hover": { "border": "#2B6CB0", "background": "#EDF2F7" }
    },
    "margin": 10
  },
  "edges": {
    "smooth": { "enabled": true, "type": "cubicBezier", "roundness": 0.15 },
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.9 } },
    "color": { "color": "#A0AEC0", "highlight": "#2B6CB0", "hover": "#2B6CB0" },
    "width": 1.2,
    "selectionWidth": 2,
    "font": { "align": "top", "size": 12, "color": "#374151", "strokeWidth": 0 },
    "length": 240
  },
  "physics": {
    "enabled": true,
    "solver": "repulsion",
    "stabilization": { "enabled": true, "iterations": 1500, "fit": true },
    "minVelocity": 0.5,
    "timestep": 0.45,
    "repulsion": {
      "nodeDistance": 500,
      "centralGravity": 0.08,
      "springLength": 300,
      "springConstant": 0.025,
      "damping": 0.4
    },
    "maxVelocity": 25
  }
}
        """
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(output_path), notebook=False)

    # Increase initial zoom and disable physics after stabilize
    html = output_path.read_text(encoding="utf-8")
    html = html.replace(
        "var network = new vis.Network(container, data, options);",
        "var network = new vis.Network(container, data, options);\n"
        "network.once('stabilizationIterationsDone', function () { "
        "network.moveTo({ scale: 1.4 }); "
        "network.setOptions({ physics: { enabled: false } }); "
        "});\n"
        "network.stabilize();",
    )
    output_path.write_text(html, encoding="utf-8")


visualize_ontology(ontology, output_path)
visualize_kg(ontology, kg, output_path.with_name("kg_visualization.html"))
