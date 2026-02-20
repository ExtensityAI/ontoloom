# Ontology Summarization for the Strategic Agent

The main agent sees an abstract summary of the ontology, not the full JSON. This document defines the summary format, compression strategies, and design rationale.

## Three-Section Format

### Section A: Headline Stats

Fixed cost (~80 tokens). Quick pulse check.

```
=== Ontology Overview ===
Classes: 47 | Data properties: 38 | Object properties: 21
Root classes (direct children of Thing): 5
Leaf classes: 28 (60%)
Max depth: 5 | Avg depth: 2.8
Classes with no properties: 3 (ElectricalSystem, PassiveSensor, MountPoint)
```

**Why these numbers:**
- Class/property counts: overall size
- Root count: top-level breadth (too many = disorganized, too few = overly abstract)
- Leaf ratio: high = bushy (lots of specialization), low = all internal nodes
- Max/avg depth: shape signal (max 5, avg 2.8 = mostly shallow with one deep branch)
- No-property classes: named explicitly so the agent knows what's underdeveloped

### Section B: Class Hierarchy Tree

Indented tree with inline annotations. This is the core of the summary.

```
=== Class Hierarchy ===
Thing
  Vehicle [dp:3, op:4]
    GroundVehicle [dp:1, op:0]
      Car [dp:2, op:1, +4 inherited]
      Truck [dp:3, op:2, +4 inherited]
        HeavyTruck [dp:1, op:0, +7 inherited]
      Motorcycle [dp:1, op:0, +4 inherited]
    AerialVehicle [dp:2, op:1]
      Drone [dp:3, op:2, +5 inherited]
      Helicopter [dp:1, op:1, +5 inherited]
  Person [dp:4, op:2]
    Driver [dp:2, op:1, +4 inherited]
    Passenger [dp:1, op:0, +4 inherited]
  Sensor [dp:1, op:2]
    ActiveSensor [dp:2, op:1, +1 inherited]
    PassiveSensor [dp:0, op:0, +1 inherited] <!>
  ElectricalSystem [dp:0, op:0] <!>
```

**Annotations:**
- `[dp:N, op:N]` — direct data property count, direct object property count (where this class is in the domain)
- `[+N inherited]` — total inherited property count (from all ancestors). Only shown when > 0 and class is a leaf or near-leaf. Prevents the agent from underestimating leaf class complexity.
- `<!>` — flag for structural anomaly (no properties, extreme depth, extreme property concentration)
- `... N more leaf classes` — collapsed homogeneous siblings
- `... N more (depth D)` — collapsed subtree with depth info
- `ClassName [dp:N, op:N] (K subtypes)` — summary-only node

### Section C: Connectivity Map

Object properties as directed edges. Shows how classes relate beyond hierarchy.

```
=== Connectivity ===
Vehicle --[hasPart]--> Component
Vehicle --[hasDriver]--> Driver
Sensor --[monitors]--> PhysicalQuantity
Sensor --[mountedOn]--> Component
Trip --[hasOrigin]--> Location
Trip --[hasDestination]--> Location
Component --[madeOf]--> Material
```

**Format:** Arrow format (`A --[rel]--> B`) for semantic clarity. Group by source class. Cap at ~25 lines for large ontologies with `... N more object properties`.

---

## Design Decisions

### Property counts, not property names
The strategic agent needs to know a class has 3 data properties, not which ones. Property names add 5-10 tokens each and are detail for exploration/modification subagents.

### Direct properties primary, inherited as annotation
Direct counts (`dp:N, op:N`) show where properties are *declared*, which is the actionable signal for whether a class "earns its place." The `+N inherited` annotation on leaf/near-leaf classes shows total inherited property load, preventing the agent from underestimating effective class complexity. Without this, a leaf class showing `[dp:0, op:0]` might look empty when it actually inherits 12 properties from its ancestors.

### Indented tree format
LLMs are well-trained on indented structures from Python, YAML, and Markdown. Research confirms indented trees are most effective for hierarchical understanding (Fu, Noy & Storey, ISWC 2013). Arrow-format connectivity adds the graph dimension.

### `<!>` flag conditions
- Class with 0 direct properties (both data and object)
- Class with unusually high property count (>2x mean)
- Subtree with depth >2x average depth

---

## Compression Strategy

Target: keep full summary under **~2000 tokens**.

**Token budget breakdown:**
- Section A (stats): ~80 tokens (fixed)
- Section C (connectivity): ~375 tokens (cap at 25 lines, ~15 tokens each)
- Section B (tree): ~1545 tokens remaining → ~77 lines at ~20 tokens per line

### Compression thresholds

| Ontology size | Strategy |
|---|---|
| <80 classes | Full tree, all classes shown |
| 80-200 classes | Full tree, collapse leaf-only sibling groups with >5 members |
| 200-500 classes | Top 3 levels fully, collapse deeper subtrees with counts |
| 500+ classes | Top 2 levels, only show "interesting" deeper branches |

### Collapse priority (least informative first)

1. **Homogeneous leaf siblings:** 6+ leaf classes sharing the same parent with similar property counts → `... N more leaf classes`
2. **Deep narrow chains:** Branch deeper than avg_depth + 2 with branching factor 1 → `... via N intermediate classes --> LeafName`
3. **Balanced subtrees:** Internally consistent subtree (similar depth, similar property counts) → `ClassName [dp:N, op:N] (K subtypes, depth D)`
4. **Property-poor subtrees:** Every class has 0 properties → `ElectricalSystem <!> (4 subtypes, all without properties)`

### Never collapse

- Root-level classes (direct children of Thing)
- Any class flagged with `<!>`
- Hub classes in connectivity (appear in 3+ object property domains)
- First 2 levels of every subtree

---

## Concrete Examples

### ~50 Class Ontology (Full Detail)

```
=== Ontology Overview ===
Classes: 47 | Data properties: 38 | Object properties: 21
Root classes (direct children of Thing): 5
Leaf classes: 28 (60%)
Max depth: 5 | Avg depth: 2.6
Classes with no properties: 3 (ElectricalSystem, PassiveSensor, MountPoint)

=== Class Hierarchy ===
Thing
  Vehicle [dp:3, op:4]
    GroundVehicle [dp:1, op:0]
      Car [dp:2, op:1]
      Truck [dp:3, op:2]
        HeavyTruck [dp:1, op:0]
      Motorcycle [dp:1, op:0]
    AerialVehicle [dp:2, op:1]
      Drone [dp:3, op:2]
      Helicopter [dp:1, op:1]
  Person [dp:4, op:2]
    Driver [dp:2, op:1]
    Passenger [dp:1, op:0]
    Mechanic [dp:1, op:1]
  Location [dp:2, op:1]
    GeoPoint [dp:3, op:0]
    Zone [dp:1, op:2]
      ParkingZone [dp:2, op:1]
      RestrictedZone [dp:1, op:0]
    Road [dp:3, op:1]
      Highway [dp:2, op:0]
      UrbanRoad [dp:1, op:0]
  Event [dp:2, op:3]
    Trip [dp:4, op:3]
    MaintenanceEvent [dp:3, op:2]
    Incident [dp:2, op:2]
  PhysicalQuantity [dp:1, op:0]
    Temperature [dp:1, op:0]
    Speed [dp:1, op:0]
    FuelLevel [dp:1, op:0]
  Component [dp:1, op:1]
    Engine [dp:4, op:1]
    Chassis [dp:2, op:0]
    Sensor [dp:1, op:2]
      ActiveSensor [dp:2, op:1]
        Radar [dp:3, op:0]
        Lidar [dp:2, op:0]
      PassiveSensor [dp:0, op:0] <!>
        Camera [dp:3, op:1]
        Thermometer [dp:1, op:0]
    ElectricalSystem [dp:0, op:0] <!>
    MountPoint [dp:0, op:0] <!>
  Material [dp:2, op:0]
    Metal [dp:1, op:0]
    Composite [dp:1, op:0]

=== Connectivity ===
Vehicle --[hasPart]--> Component
Vehicle --[hasDriver]--> Driver
Vehicle --[locatedAt]--> Location
Vehicle --[onTrip]--> Trip
Sensor --[monitors]--> PhysicalQuantity
Sensor --[mountedOn]--> Component
Trip --[hasOrigin]--> Location
Trip --[hasDestination]--> Location
Trip --[involves]--> Vehicle
MaintenanceEvent --[targets]--> Component
MaintenanceEvent --[performedBy]--> Mechanic
Incident --[occurredAt]--> Location
Incident --[involves]--> Vehicle
Component --[madeOf]--> Material
Zone --[contains]--> Vehicle
Zone --[adjacentTo]--> Zone
Engine --[consumes]--> FuelLevel
Road --[connectsTo]--> Location
Drone --[operatedBy]--> Person
Driver --[certified]--> Vehicle
Mechanic --[specializes]--> Component
```

~800-1000 tokens.

### ~200 Class Ontology (Compressed)

```
=== Ontology Overview ===
Classes: 203 | Data properties: 156 | Object properties: 89
Root classes (direct children of Thing): 8
Leaf classes: 134 (66%)
Max depth: 7 | Avg depth: 3.4
Classes with no properties: 11 (listed below tree)

=== Class Hierarchy ===
Thing
  Vehicle [dp:3, op:5]
    GroundVehicle [dp:1, op:0]
      Car [dp:2, op:1]
        Sedan [dp:1, op:0]
        SUV [dp:2, op:1]
        ... 4 more leaf classes
      Truck [dp:3, op:2]
        HeavyTruck [dp:2, op:1]
        LightTruck [dp:1, op:0]
        ... 3 more leaf classes
      Bus [dp:2, op:1]
        CityBus [dp:1, op:0]
        CoachBus [dp:1, op:0]
      Motorcycle [dp:2, op:0]
      EmergencyVehicle [dp:3, op:2]
        Ambulance [dp:2, op:1]
        FireTruck [dp:3, op:1]
        PoliceCar [dp:2, op:1]
    AerialVehicle [dp:2, op:1]
      Drone [dp:4, op:3]
        SurveillanceDrone [dp:2, op:1]
        DeliveryDrone [dp:3, op:2]
        ... 3 more leaf classes
      Helicopter [dp:2, op:1]
      FixedWingAircraft [dp:2, op:1]
    WaterVehicle [dp:2, op:1]
      ... 6 leaf classes
  Person [dp:5, op:3]
    Driver [dp:3, op:2]
      ProfessionalDriver [dp:2, op:1]
      ... 3 more leaf classes
    Passenger [dp:1, op:0]
    Mechanic [dp:2, op:2]
      ... 4 specializations
    FleetManager [dp:2, op:2]
    Inspector [dp:1, op:1]
  Location [dp:3, op:2]
    GeoPoint [dp:4, op:0]
    Zone [dp:2, op:3]
      ... 8 zone types
    Road [dp:4, op:2]
      ... 6 road types
    Facility [dp:3, op:3]
      Warehouse [dp:3, op:2]
      MaintenanceDepot [dp:2, op:2]
      ... 5 more leaf classes
  Event [dp:3, op:4]
    Trip [dp:5, op:4]
      ScheduledTrip [dp:2, op:1]
      AdHocTrip [dp:1, op:0]
    MaintenanceEvent [dp:4, op:3]
      ScheduledMaintenance [dp:2, op:1]
      BreakdownRepair [dp:3, op:2]
      ... 4 more leaf classes
    Incident [dp:3, op:3]
      Accident [dp:4, op:2]
      TrafficViolation [dp:2, op:1]
      ... 5 more leaf classes
    InspectionEvent [dp:3, op:2]
      ... 4 types
  PhysicalQuantity [dp:2, op:0]
    ... 12 leaf classes
  Component [dp:2, op:2]
    Engine [dp:5, op:2]
      InternalCombustion [dp:3, op:1]
      ElectricMotor [dp:2, op:1]
      HybridPowertrain [dp:2, op:1]
    Chassis [dp:3, op:1]
    Sensor [dp:2, op:3]
      ActiveSensor [dp:2, op:1]
        ... 6 types
      PassiveSensor [dp:0, op:0] <!>
        ... 5 types
    ElectricalSystem [dp:0, op:0] <!>
      ... 4 subtypes, all without properties
    BrakeSystem [dp:3, op:1]
    Transmission [dp:3, op:1]
      ... 3 types
    Tire [dp:4, op:0]
  Material [dp:2, op:0]
    ... 8 leaf classes
  Organization [dp:3, op:3]
    FleetOperator [dp:3, op:3]
    MaintenanceProvider [dp:2, op:2]
    RegulatoryBody [dp:2, op:1]
    ... 4 more leaf classes

Classes with no properties:
  PassiveSensor, ElectricalSystem, MountPoint, Axle, Mirror,
  FuelFilter, Washer, BoltGrade, CableType, SignalRelay, TrafficCone

=== Connectivity (top 25) ===
Vehicle --[hasPart]--> Component
Vehicle --[hasDriver]--> Driver
Vehicle --[locatedAt]--> Location
Vehicle --[assignedTo]--> Organization
Vehicle --[onTrip]--> Trip
Sensor --[monitors]--> PhysicalQuantity
Sensor --[mountedOn]--> Component
Trip --[hasOrigin]--> Location
Trip --[hasDestination]--> Location
Trip --[involves]--> Vehicle
Trip --[scheduledBy]--> FleetManager
MaintenanceEvent --[targets]--> Component
MaintenanceEvent --[performedBy]--> Mechanic
MaintenanceEvent --[authorizedBy]--> FleetManager
Incident --[occurredAt]--> Location
Incident --[involves]--> Vehicle
Incident --[reportedTo]--> RegulatoryBody
Component --[madeOf]--> Material
Zone --[contains]--> Vehicle
Organization --[operates]--> Vehicle
Organization --[employs]--> Person
FleetOperator --[manages]--> Trip
Inspector --[conducts]--> InspectionEvent
InspectionEvent --[evaluates]--> Component
Driver --[certified]--> Vehicle
... 64 more object properties
```

~1500-2000 tokens.

---

## Implementation Notes

Existing code that can be reused:

- `compute_class_value_maps()` in `metrics/ontology.py` — returns depths, subclass counts, property counts per class
- `_children_by_parent()` helper — builds the tree structure
- `format_metrics_summary()` in `draft_plan.py` — produces a one-line stats string (Section A replaces this)

A `summarize_ontology(ontology: Ontology, token_budget: int = 2000) -> str` function would:
1. Call `compute_class_value_maps()` for per-class data
2. Build tree using `_children_by_parent()`
3. Render Section A from counts
4. Render Section B by depth-first tree walk, applying compression based on remaining budget
5. Render Section C by iterating `object_properties` and formatting arrows

---

## Sources

- [Talk like a Graph (Fatemi et al., ICLR 2024)](https://arxiv.org/abs/2310.04560)
- [ABSTAT: Ontology-Driven Linked Data Summaries](https://link.springer.com/chapter/10.1007/978-3-319-47602-5_51)
- [Indented Tree or Graph? Usability Study (Fu, Noy & Storey, ISWC 2013)](https://link.springer.com/chapter/10.1007/978-3-642-41335-3_8)
- [Visualizing Ontologies with VOWL](https://www.semantic-web-journal.net/system/files/swj1114.pdf)
- [Measuring Ontology Complexity (PLOS ONE)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0075993)
- [Ontology Modularization Review (IEEE Access 2022)](https://ieeexplore.ieee.org/document/9721157/)
- [MemTree: Dynamic Tree Memory for LLMs](https://openreview.net/forum?id=moXtEmCleY)
