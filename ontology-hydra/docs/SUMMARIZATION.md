# Ontology Summarization

The main agent sees an abstract summary of the ontology, not the full JSON. This document defines the summary format, compression strategies, and design rationale.

For how the summary fits into the overall architecture, see [ARCHITECTURE.md](ARCHITECTURE.md). The exploration subagent uses summary data when reviewing subtrees — see [EXPLORATION.md](EXPLORATION.md).

---

## Format: Stats Header + Turtle

The summary has two parts:

1. **Stats header** — 2–3 lines of aggregate metrics for quick orientation
2. **Turtle body** — the ontology rendered as Turtle, progressively compressed for larger ontologies

No separate connectivity section (Turtle already shows connections via domain/range). No flagging (the diagnostics system handles quality signals — see [CATALOG.md](CATALOG.md)).

### Stats Header

```
# 47 classes, 38 data properties, 21 object properties
# Max depth: 5 | 5 root classes | 28 leaf classes (60%)
```

Two lines, ~30 tokens. Just enough for the agent to gauge overall size and shape without scanning the full Turtle. Rendered as Turtle comments so the summary is one valid Turtle document.

### Turtle Body

The ontology rendered as standard Turtle. Classes grouped by hierarchy (depth-first traversal), followed by object properties, then data properties.

```turtle
@prefix : <urn:ontology:> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# --- Classes ---

:Vehicle a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A motorized transport vehicle for moving people or goods" .

:GroundVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle that operates on land surfaces" .

:Car a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A four-wheeled passenger vehicle for personal transport" .

:Truck a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A large vehicle designed for transporting goods" .

:Sensor a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "A device that detects physical phenomena and produces signals" .

:PassiveSensor a owl:Class ;
    rdfs:subClassOf :Sensor ;
    rdfs:comment "A sensor that detects naturally emitted energy" .

# --- Object Properties ---

:hasPart a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Component ;
    rdfs:comment "A physical component installed in this vehicle" .

:hasDriver a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Driver ;
    rdfs:comment "The person currently operating this vehicle" .

:monitors a owl:ObjectProperty ;
    rdfs:domain :Sensor ;
    rdfs:range :PhysicalQuantity ;
    rdfs:comment "The physical quantity this sensor measures" .

# --- Data Properties ---

:vehicleWeight a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:float ;
    rdfs:comment "Total weight in kilograms" .

:sensorAccuracy a owl:DatatypeProperty ;
    rdfs:domain :Sensor ;
    rdfs:range xsd:float ;
    rdfs:comment "Measurement accuracy as a percentage" .
```

---

## Why Turtle

**LLMs are heavily trained on it.** Turtle is the standard ontology serialization format. LLMs have seen vast quantities of it in training data and reason naturally about ontology structure in this format.

**It keeps related things together.** A class's hierarchy position (subClassOf), its description (comment), and its properties (domain/range declarations) are all visible as one coherent representation. The old three-section format artificially separated hierarchy, property counts, and connectivity.

**No information loss from abstraction.** The old format showed `[dp:3, op:2]` — the agent knew a class had 3 data properties but not which ones. Turtle shows the actual properties with their names, domains, ranges, and descriptions. This is strictly more information for the same or similar token cost.

**Read-only display, not data model.** The earlier decision to avoid Turtle was about the *data model* (can't programmatically update/delete strings). As a *read-only display format* in the summary prompt, that objection doesn't apply. The internal data model remains the Pydantic `Ontology` structure.

---

## Compression Strategy

No fixed token budget. The summary scales naturally with the ontology — small ontologies get full detail, large ones get progressively compressed. The actual budget is whatever context remains after the other prompt components (scope doc, diagnostics, instructions).

### Compression Levels

| Ontology size | Strategy | Approx. tokens |
|---|---|---|
| <80 classes | **Full Turtle.** Every class, property, and description rendered. | ~2000–4000 |
| 80–200 classes | **Descriptions trimmed.** Top 3 levels keep full descriptions. Deeper classes keep only name + subClassOf. Leaf sibling groups with >5 members collapsed into comments. | ~3000–5000 |
| 200–500 classes | **Subtrees collapsed.** Top 2 levels in full. Deeper subtrees summarized as Turtle comments with class counts. All properties keep signatures (domain/range) but drop descriptions. | ~3000–5000 |
| 500+ classes | **Selective rendering.** Only root classes + branches with active findings rendered in full. Everything else summarized. Properties listed as signatures only. | ~3000–5000 |

### What Gets Compressed First (least informative → most)

1. **Descriptions on deep leaf classes.** A leaf 5 levels deep is rarely the focus of strategic decisions. Drop `rdfs:comment`, keep `rdfs:subClassOf`.
2. **Homogeneous leaf siblings.** 8 leaf subclasses of Car that all look similar → collapse to `# 8 subclasses: Sedan, SUV, Hatchback, Coupe, Wagon, Convertible, Minivan, Pickup`
3. **Property descriptions.** Keep signatures (`domain`, `range`) but drop `rdfs:comment` on properties. The property name + domain + range usually tells you enough.
4. **Balanced deep subtrees.** A subtree that's internally consistent → `# Component: 24 subclasses, max depth 3` as a Turtle comment.

### What Never Gets Compressed

- **Root-level classes** (direct children of Thing) — always in full with descriptions
- **Classes referenced in current diagnostic findings** — the agent needs to see these in context
- **Hub classes** (appear in 3+ property domains) — structurally important
- **Property signatures** (domain + range) — always shown, even when descriptions are dropped

---

## Concrete Examples

### ~50 Class Ontology (Full)

```turtle
# 47 classes, 38 data properties, 21 object properties
# Max depth: 5 | 5 root classes | 28 leaf classes (60%)

@prefix : <urn:ontology:> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# --- Classes ---

:Vehicle a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A motorized transport vehicle for moving people or goods" .

:GroundVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle that operates on land surfaces" .

:Car a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A four-wheeled passenger vehicle for personal transport" .

:Truck a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A large vehicle designed for transporting goods" .

:HeavyTruck a owl:Class ;
    rdfs:subClassOf :Truck ;
    rdfs:comment "A truck exceeding 26,000 lbs GVWR requiring a CDL" .

:Motorcycle a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A two-wheeled motorized vehicle" .

:AerialVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle capable of atmospheric flight" .

:Drone a owl:Class ;
    rdfs:subClassOf :AerialVehicle ;
    rdfs:comment "An unmanned aerial vehicle operated remotely or autonomously" .

:Helicopter a owl:Class ;
    rdfs:subClassOf :AerialVehicle ;
    rdfs:comment "A rotary-wing aircraft with vertical takeoff capability" .

:Person a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A human individual involved in the transportation domain" .

:Driver a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person qualified and authorized to operate a vehicle" .

:Passenger a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person being transported in a vehicle" .

:Mechanic a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person who inspects, maintains, and repairs vehicles" .

:Location a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical place or geographic area" .

:GeoPoint a owl:Class ;
    rdfs:subClassOf :Location ;
    rdfs:comment "A precise geographic coordinate (latitude, longitude)" .

:Zone a owl:Class ;
    rdfs:subClassOf :Location ;
    rdfs:comment "A bounded geographic area with defined boundaries" .

:ParkingZone a owl:Class ;
    rdfs:subClassOf :Zone ;
    rdfs:comment "A designated area for vehicle parking" .

:RestrictedZone a owl:Class ;
    rdfs:subClassOf :Zone ;
    rdfs:comment "An area with access restrictions for certain vehicle types" .

:Road a owl:Class ;
    rdfs:subClassOf :Location ;
    rdfs:comment "A route or path for vehicle travel" .

:Highway a owl:Class ;
    rdfs:subClassOf :Road ;
    rdfs:comment "A major high-speed road connecting regions" .

:UrbanRoad a owl:Class ;
    rdfs:subClassOf :Road ;
    rdfs:comment "A road within city or town limits" .

:Event a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A discrete occurrence relevant to fleet operations" .

:Trip a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "A journey from origin to destination involving a vehicle" .

:MaintenanceEvent a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "A scheduled or unscheduled vehicle maintenance activity" .

:Incident a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "An unplanned event such as an accident or breakdown" .

:Component a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical part or subsystem of a vehicle" .

:Engine a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "The primary power source of a vehicle" .

:Chassis a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "The structural frame of a vehicle" .

:Sensor a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "A device that detects physical phenomena and produces signals" .

:ActiveSensor a owl:Class ;
    rdfs:subClassOf :Sensor ;
    rdfs:comment "A sensor that emits energy and measures reflections" .

:Radar a owl:Class ;
    rdfs:subClassOf :ActiveSensor ;
    rdfs:comment "A sensor using radio waves for distance and speed detection" .

:Lidar a owl:Class ;
    rdfs:subClassOf :ActiveSensor ;
    rdfs:comment "A sensor using laser pulses for 3D spatial mapping" .

:PassiveSensor a owl:Class ;
    rdfs:subClassOf :Sensor ;
    rdfs:comment "A sensor that detects naturally emitted energy" .

:Camera a owl:Class ;
    rdfs:subClassOf :PassiveSensor ;
    rdfs:comment "An optical sensor capturing visible light images" .

:Thermometer a owl:Class ;
    rdfs:subClassOf :PassiveSensor ;
    rdfs:comment "A sensor measuring temperature" .

:ElectricalSystem a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "The electrical wiring and control systems of a vehicle" .

:MountPoint a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "A physical location where a sensor or device is attached" .

:PhysicalQuantity a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A measurable physical property" .

:Temperature a owl:Class ;
    rdfs:subClassOf :PhysicalQuantity ;
    rdfs:comment "A measure of thermal energy" .

:Speed a owl:Class ;
    rdfs:subClassOf :PhysicalQuantity ;
    rdfs:comment "A measure of distance traveled per unit time" .

:FuelLevel a owl:Class ;
    rdfs:subClassOf :PhysicalQuantity ;
    rdfs:comment "The amount of fuel remaining in a tank" .

:Material a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical substance used in vehicle construction" .

:Metal a owl:Class ;
    rdfs:subClassOf :Material ;
    rdfs:comment "A metallic material such as steel or aluminum" .

:Composite a owl:Class ;
    rdfs:subClassOf :Material ;
    rdfs:comment "An engineered material combining multiple substances" .

# --- Object Properties ---

:hasPart a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Component ;
    rdfs:comment "A physical component installed in this vehicle" .

:hasDriver a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Driver ;
    rdfs:comment "The person currently operating this vehicle" .

:locatedAt a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Location ;
    rdfs:comment "The current physical location of this vehicle" .

:onTrip a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Trip ;
    rdfs:comment "The trip this vehicle is currently performing" .

:monitors a owl:ObjectProperty ;
    rdfs:domain :Sensor ;
    rdfs:range :PhysicalQuantity ;
    rdfs:comment "The physical quantity this sensor measures" .

:mountedOn a owl:ObjectProperty ;
    rdfs:domain :Sensor ;
    rdfs:range :Component ;
    rdfs:comment "The component this sensor is physically attached to" .

:hasOrigin a owl:ObjectProperty ;
    rdfs:domain :Trip ;
    rdfs:range :Location ;
    rdfs:comment "The starting location of this trip" .

:hasDestination a owl:ObjectProperty ;
    rdfs:domain :Trip ;
    rdfs:range :Location ;
    rdfs:comment "The ending location of this trip" .

:involves a owl:ObjectProperty ;
    rdfs:domain :Event ;
    rdfs:range :Vehicle ;
    rdfs:comment "A vehicle involved in this event" .

:targets a owl:ObjectProperty ;
    rdfs:domain :MaintenanceEvent ;
    rdfs:range :Component ;
    rdfs:comment "The component being maintained or repaired" .

:performedBy a owl:ObjectProperty ;
    rdfs:domain :MaintenanceEvent ;
    rdfs:range :Mechanic ;
    rdfs:comment "The mechanic performing this maintenance" .

:occurredAt a owl:ObjectProperty ;
    rdfs:domain :Incident ;
    rdfs:range :Location ;
    rdfs:comment "Where this incident took place" .

:madeOf a owl:ObjectProperty ;
    rdfs:domain :Component ;
    rdfs:range :Material ;
    rdfs:comment "The primary material this component is constructed from" .

:contains a owl:ObjectProperty ;
    rdfs:domain :Zone ;
    rdfs:range :Vehicle ;
    rdfs:comment "A vehicle currently within this zone" .

:adjacentTo a owl:ObjectProperty ;
    rdfs:domain :Zone ;
    rdfs:range :Zone ;
    rdfs:comment "A zone sharing a boundary with this zone" .

:consumes a owl:ObjectProperty ;
    rdfs:domain :Engine ;
    rdfs:range :FuelLevel ;
    rdfs:comment "The fuel consumption of this engine" .

:connectsTo a owl:ObjectProperty ;
    rdfs:domain :Road ;
    rdfs:range :Location ;
    rdfs:comment "A location this road connects to" .

:operatedBy a owl:ObjectProperty ;
    rdfs:domain :Drone ;
    rdfs:range :Person ;
    rdfs:comment "The person remotely controlling this drone" .

:certifiedFor a owl:ObjectProperty ;
    rdfs:domain :Driver ;
    rdfs:range :Vehicle ;
    rdfs:comment "A vehicle type this driver is certified to operate" .

:specializesIn a owl:ObjectProperty ;
    rdfs:domain :Mechanic ;
    rdfs:range :Component ;
    rdfs:comment "The component type this mechanic specializes in" .

# --- Data Properties ---

:vehicleWeight a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:float ;
    rdfs:comment "Total weight in kilograms" .

:maxSpeed a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:float ;
    rdfs:comment "Maximum rated speed in km/h" .

:licensePlate a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:string ;
    rdfs:comment "The vehicle registration plate number" .

:firstName a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string ;
    rdfs:comment "The person's given name" .

:lastName a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string ;
    rdfs:comment "The person's family name" .

:dateOfBirth a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:date ;
    rdfs:comment "The person's date of birth" .

:licenseNumber a owl:DatatypeProperty ;
    rdfs:domain :Driver ;
    rdfs:range xsd:string ;
    rdfs:comment "The driver's license identification number" .

:latitude a owl:DatatypeProperty ;
    rdfs:domain :GeoPoint ;
    rdfs:range xsd:float ;
    rdfs:comment "Geographic latitude in decimal degrees" .

:longitude a owl:DatatypeProperty ;
    rdfs:domain :GeoPoint ;
    rdfs:range xsd:float ;
    rdfs:comment "Geographic longitude in decimal degrees" .

:zoneName a owl:DatatypeProperty ;
    rdfs:domain :Zone ;
    rdfs:range xsd:string ;
    rdfs:comment "The human-readable name of this zone" .

:startTime a owl:DatatypeProperty ;
    rdfs:domain :Event ;
    rdfs:range xsd:dateTime ;
    rdfs:comment "When this event began" .

:endTime a owl:DatatypeProperty ;
    rdfs:domain :Event ;
    rdfs:range xsd:dateTime ;
    rdfs:comment "When this event ended" .

:tripDistance a owl:DatatypeProperty ;
    rdfs:domain :Trip ;
    rdfs:range xsd:float ;
    rdfs:comment "Total distance traveled in kilometers" .

:sensorAccuracy a owl:DatatypeProperty ;
    rdfs:domain :Sensor ;
    rdfs:range xsd:float ;
    rdfs:comment "Measurement accuracy as a percentage" .

:horsepower a owl:DatatypeProperty ;
    rdfs:domain :Engine ;
    rdfs:range xsd:integer ;
    rdfs:comment "Engine power output in horsepower" .
```

~3000 tokens. More than the old format (~1000), but the agent sees actual property names, descriptions, and domain/range — strictly more useful information.

### ~200 Class Ontology (Compressed)

```turtle
# 203 classes, 156 data properties, 89 object properties
# Max depth: 7 | 8 root classes | 134 leaf classes (66%)

@prefix : <urn:ontology:> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# --- Classes ---

:Vehicle a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A motorized transport vehicle for moving people or goods" .

:GroundVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle that operates on land surfaces" .

:Car a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A four-wheeled passenger vehicle" .

# 6 subclasses of Car: Sedan, SUV, Hatchback, Coupe, Wagon, Convertible

:Truck a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A large vehicle for transporting goods" .

# 5 subclasses of Truck: HeavyTruck, LightTruck, TankerTruck, FlatbedTruck, RefrigeratedTruck

:Bus a owl:Class ;
    rdfs:subClassOf :GroundVehicle .

# 2 subclasses of Bus: CityBus, CoachBus

:Motorcycle a owl:Class ;
    rdfs:subClassOf :GroundVehicle .

:EmergencyVehicle a owl:Class ;
    rdfs:subClassOf :GroundVehicle ;
    rdfs:comment "A vehicle equipped for emergency response" .

:Ambulance a owl:Class ;
    rdfs:subClassOf :EmergencyVehicle .

:FireTruck a owl:Class ;
    rdfs:subClassOf :EmergencyVehicle .

:PoliceCar a owl:Class ;
    rdfs:subClassOf :EmergencyVehicle .

:AerialVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle capable of atmospheric flight" .

:Drone a owl:Class ;
    rdfs:subClassOf :AerialVehicle ;
    rdfs:comment "An unmanned aerial vehicle" .

# 5 subclasses of Drone: SurveillanceDrone, DeliveryDrone, MappingDrone, InspectionDrone, AgriculturalDrone

:Helicopter a owl:Class ;
    rdfs:subClassOf :AerialVehicle .

:FixedWingAircraft a owl:Class ;
    rdfs:subClassOf :AerialVehicle .

:WaterVehicle a owl:Class ;
    rdfs:subClassOf :Vehicle ;
    rdfs:comment "A vehicle that operates on water" .

# 6 subclasses of WaterVehicle: Boat, Ship, Barge, Ferry, Hovercraft, Submarine

:Person a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A human individual involved in the transportation domain" .

:Driver a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person qualified to operate a vehicle" .

# 4 subclasses of Driver: ProfessionalDriver, TraineeDriver, HazmatDriver, CDLDriver

:Passenger a owl:Class ;
    rdfs:subClassOf :Person .

:Mechanic a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person who maintains and repairs vehicles" .

# 4 specializations of Mechanic

:FleetManager a owl:Class ;
    rdfs:subClassOf :Person ;
    rdfs:comment "A person responsible for managing a fleet of vehicles" .

:Inspector a owl:Class ;
    rdfs:subClassOf :Person .

:Location a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical place or geographic area" .

:GeoPoint a owl:Class ;
    rdfs:subClassOf :Location .

:Zone a owl:Class ;
    rdfs:subClassOf :Location ;
    rdfs:comment "A bounded geographic area" .

# 8 zone types

:Road a owl:Class ;
    rdfs:subClassOf :Location .

# 6 road types

:Facility a owl:Class ;
    rdfs:subClassOf :Location ;
    rdfs:comment "A built structure serving transportation operations" .

:Warehouse a owl:Class ;
    rdfs:subClassOf :Facility .

:MaintenanceDepot a owl:Class ;
    rdfs:subClassOf :Facility .

# 5 more subclasses of Facility

:Event a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A discrete occurrence relevant to fleet operations" .

:Trip a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "A journey from origin to destination" .

:ScheduledTrip a owl:Class ;
    rdfs:subClassOf :Trip .

:AdHocTrip a owl:Class ;
    rdfs:subClassOf :Trip .

:MaintenanceEvent a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "A vehicle maintenance activity" .

# 6 subclasses of MaintenanceEvent

:Incident a owl:Class ;
    rdfs:subClassOf :Event ;
    rdfs:comment "An unplanned event" .

# 7 subclasses of Incident

:InspectionEvent a owl:Class ;
    rdfs:subClassOf :Event .

# 4 subclasses of InspectionEvent

:Component a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical part or subsystem of a vehicle" .

:Engine a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "The primary power source of a vehicle" .

:InternalCombustion a owl:Class ;
    rdfs:subClassOf :Engine .

:ElectricMotor a owl:Class ;
    rdfs:subClassOf :Engine .

:HybridPowertrain a owl:Class ;
    rdfs:subClassOf :Engine .

:Chassis a owl:Class ;
    rdfs:subClassOf :Component .

:Sensor a owl:Class ;
    rdfs:subClassOf :Component ;
    rdfs:comment "A device that detects physical phenomena" .

:ActiveSensor a owl:Class ;
    rdfs:subClassOf :Sensor .

# 6 subclasses of ActiveSensor

:PassiveSensor a owl:Class ;
    rdfs:subClassOf :Sensor .

# 5 subclasses of PassiveSensor

:ElectricalSystem a owl:Class ;
    rdfs:subClassOf :Component .

# 4 subclasses of ElectricalSystem

:BrakeSystem a owl:Class ;
    rdfs:subClassOf :Component .

:Transmission a owl:Class ;
    rdfs:subClassOf :Component .

# 3 subclasses of Transmission

:Tire a owl:Class ;
    rdfs:subClassOf :Component .

# PhysicalQuantity: 12 leaf subclasses (Temperature, Speed, FuelLevel, Pressure, ...)

:PhysicalQuantity a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A measurable physical property" .

# Material: 8 leaf subclasses (Metal, Composite, Rubber, Glass, ...)

:Material a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A physical substance used in vehicle construction" .

:Organization a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:comment "A company or institution in the transportation domain" .

:FleetOperator a owl:Class ;
    rdfs:subClassOf :Organization .

:MaintenanceProvider a owl:Class ;
    rdfs:subClassOf :Organization .

:RegulatoryBody a owl:Class ;
    rdfs:subClassOf :Organization .

# 4 more subclasses of Organization

# --- Object Properties (signatures only) ---

:hasPart a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Component .

:hasDriver a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Driver .

:locatedAt a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Location .

:assignedTo a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Organization .

:onTrip a owl:ObjectProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range :Trip .

:monitors a owl:ObjectProperty ;
    rdfs:domain :Sensor ;
    rdfs:range :PhysicalQuantity .

:mountedOn a owl:ObjectProperty ;
    rdfs:domain :Sensor ;
    rdfs:range :Component .

:hasOrigin a owl:ObjectProperty ;
    rdfs:domain :Trip ;
    rdfs:range :Location .

:hasDestination a owl:ObjectProperty ;
    rdfs:domain :Trip ;
    rdfs:range :Location .

:involves a owl:ObjectProperty ;
    rdfs:domain :Event ;
    rdfs:range :Vehicle .

:scheduledBy a owl:ObjectProperty ;
    rdfs:domain :Trip ;
    rdfs:range :FleetManager .

:targets a owl:ObjectProperty ;
    rdfs:domain :MaintenanceEvent ;
    rdfs:range :Component .

:performedBy a owl:ObjectProperty ;
    rdfs:domain :MaintenanceEvent ;
    rdfs:range :Mechanic .

:authorizedBy a owl:ObjectProperty ;
    rdfs:domain :MaintenanceEvent ;
    rdfs:range :FleetManager .

:occurredAt a owl:ObjectProperty ;
    rdfs:domain :Incident ;
    rdfs:range :Location .

:reportedTo a owl:ObjectProperty ;
    rdfs:domain :Incident ;
    rdfs:range :RegulatoryBody .

:madeOf a owl:ObjectProperty ;
    rdfs:domain :Component ;
    rdfs:range :Material .

:contains a owl:ObjectProperty ;
    rdfs:domain :Zone ;
    rdfs:range :Vehicle .

:operates a owl:ObjectProperty ;
    rdfs:domain :Organization ;
    rdfs:range :Vehicle .

:employs a owl:ObjectProperty ;
    rdfs:domain :Organization ;
    rdfs:range :Person .

:manages a owl:ObjectProperty ;
    rdfs:domain :FleetOperator ;
    rdfs:range :Trip .

:conducts a owl:ObjectProperty ;
    rdfs:domain :Inspector ;
    rdfs:range :InspectionEvent .

:evaluates a owl:ObjectProperty ;
    rdfs:domain :InspectionEvent ;
    rdfs:range :Component .

:certifiedFor a owl:ObjectProperty ;
    rdfs:domain :Driver ;
    rdfs:range :Vehicle .

# ... 64 more object properties

# --- Data Properties (89 total, showing first 15) ---

:vehicleWeight a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:float .

:maxSpeed a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:float .

:licensePlate a owl:DatatypeProperty ;
    rdfs:domain :Vehicle ;
    rdfs:range xsd:string .

:firstName a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string .

:lastName a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string .

:dateOfBirth a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:date .

:startTime a owl:DatatypeProperty ;
    rdfs:domain :Event ;
    rdfs:range xsd:dateTime .

:endTime a owl:DatatypeProperty ;
    rdfs:domain :Event ;
    rdfs:range xsd:dateTime .

:tripDistance a owl:DatatypeProperty ;
    rdfs:domain :Trip ;
    rdfs:range xsd:float .

:sensorAccuracy a owl:DatatypeProperty ;
    rdfs:domain :Sensor ;
    rdfs:range xsd:float .

:horsepower a owl:DatatypeProperty ;
    rdfs:domain :Engine ;
    rdfs:range xsd:integer .

:latitude a owl:DatatypeProperty ;
    rdfs:domain :GeoPoint ;
    rdfs:range xsd:float .

:longitude a owl:DatatypeProperty ;
    rdfs:domain :GeoPoint ;
    rdfs:range xsd:float .

:zoneName a owl:DatatypeProperty ;
    rdfs:domain :Zone ;
    rdfs:range xsd:string .

:roadLength a owl:DatatypeProperty ;
    rdfs:domain :Road ;
    rdfs:range xsd:float .

# ... 141 more data properties
```

~4000 tokens. Compression applied:
- Deep leaf classes collapsed to comments with names listed
- Property descriptions dropped (signatures only)
- Homogeneous subtrees (PhysicalQuantity, Material) summarized in one line
- Data properties truncated with count

---

## Implementation Notes

A `summarize_ontology(ontology: Ontology) -> str` function:
1. Compute per-class data: depths, subclass counts, property counts
2. Determine compression level from class count
3. Render stats header as Turtle comments
4. Render classes by depth-first traversal of the hierarchy, applying compression
5. Render object properties, then data properties, applying compression

The summary must serialize **deterministically** — same ontology produces the same summary string. Use alphabetical ordering within each hierarchy level. This is critical for KV-cache prefix matching across rounds (see [ARCHITECTURE.md](ARCHITECTURE.md) § Persistence & Serialization).

---

## Sources

- [Talk like a Graph (Fatemi et al., ICLR 2024)](https://arxiv.org/abs/2310.04560)
- [Indented Tree or Graph? Usability Study (Fu, Noy & Storey, ISWC 2013)](https://link.springer.com/chapter/10.1007/978-3-642-41335-3_8)
- [Visualizing Ontologies with VOWL](https://www.semantic-web-journal.net/system/files/swj1114.pdf)
