// Run metadata from run.json
export interface RunMetadata {
  id: string
  title: string
  intent: string
  input_files: string[]
  created_at: string // ISO datetime string
  n_iterations: number
}

// Run summary returned from list endpoint
export interface RunSummary {
  metadata: RunMetadata
}

// Structural metrics for an ontology
export interface StructuralMetrics {
  // Basic counts
  class_count: number
  data_property_count: number
  object_property_count: number

  // Hierarchy metrics
  root_class_count: number
  leaf_class_count: number
  max_depth: number
  avg_depth: number
  avg_branching_factor: number

  // Connectivity metrics
  orphan_class_count: number
  classes_with_data_properties: number
  property_coverage: number
  relationship_density: number

  // Quality indicators
  classes_with_empty_definition: number
  classes_with_constraints: number
  properties_with_thing_domain: number
}

// Iteration summary (used in run detail)
export interface IterationSummary {
  index: number
  has_ontology: boolean
  has_ops: boolean
  has_plan: boolean
  has_review: boolean
  metrics: StructuralMetrics | null
}

// Run detail with iterations list
export interface RunDetail {
  metadata: RunMetadata
  iterations: IterationSummary[]
}

// Ontology types
export interface ClassDescription {
  definition: string
  constraints: string | null
}

export interface OntologyClass {
  name: string
  description: ClassDescription
  sub_class_of: string[]
}

export interface ClassExpression {
  intersectionOf?: string[]
  // Single class name can just be a string
}

export interface DataProperty {
  name: string
  description: string
  domain: (string | ClassExpression)[]
  range: string
}

export interface ObjectProperty {
  name: string
  description: string
  domain: (string | ClassExpression)[]
  range: (string | ClassExpression)[]
}

export interface Ontology {
  classes: Record<string, OntologyClass>
  data_properties: Record<string, DataProperty>
  object_properties: Record<string, ObjectProperty>
}

// Operation types - discriminated by 'op' field
export interface AddClassOp {
  op: "add_class"
  name: string
  description: ClassDescription
  sub_class_of: string[]
}

export interface UpdateClassOp {
  op: "update_class"
  name: string
  new_name?: string
  description?: ClassDescription
  sub_class_of?: string[]
}

export interface DeleteClassOp {
  op: "del_class"
  name: string
}

export interface MergeClassesOp {
  op: "merge_classes"
  source_classes: string[]
  target_name: string
  description: ClassDescription
}

export interface AddDataPropertyOp {
  op: "add_data_prop"
  name: string
  description: string
  domain: (string | ClassExpression)[]
  range: string
}

export interface UpdateDataPropertyOp {
  op: "update_data_prop"
  name: string
  new_name?: string
  description?: string
  domain?: (string | ClassExpression)[]
  range?: string
}

export interface DeleteDataPropertyOp {
  op: "del_data_prop"
  name: string
}

export interface AddObjectPropertyOp {
  op: "add_object_prop"
  name: string
  description: string
  domain: (string | ClassExpression)[]
  range: (string | ClassExpression)[]
}

export interface UpdateObjectPropertyOp {
  op: "update_object_prop"
  name: string
  new_name?: string
  description?: string
  domain?: (string | ClassExpression)[]
  range?: (string | ClassExpression)[]
}

export interface DeleteObjectPropertyOp {
  op: "del_object_prop"
  name: string
}

export type Operation =
  | AddClassOp
  | UpdateClassOp
  | DeleteClassOp
  | MergeClassesOp
  | AddDataPropertyOp
  | UpdateDataPropertyOp
  | DeleteDataPropertyOp
  | AddObjectPropertyOp
  | UpdateObjectPropertyOp
  | DeleteObjectPropertyOp

// Full iteration detail
export interface IterationDetail {
  index: number
  ontology: Ontology | null
  ops: Operation[]
  plan: string | null
  review: string | null
  metrics: StructuralMetrics | null
}

// Metrics time series
export interface MetricsTimeSeriesPoint {
  iteration: number
  metrics: StructuralMetrics
}

export interface MetricsTimeSeries {
  name: string
  points: MetricsTimeSeriesPoint[]
}
