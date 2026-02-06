export interface RunMetadata {
  id: string
  title: string
  intent: string
  input_files: string[]
  created_at: string
  n_iterations: number
}

export interface RunSummary {
  metadata: RunMetadata
}

export interface Metric {
  min: number
  max: number
  mean: number
  median: number
  stdev: number
  raw: number[]
}

export interface OntologyMetricCounts {
  n_classes: number
  n_properties: number
  n_object_properties: number
  n_data_properties: number
  n_root_classes: number
  n_leaf_classes: number
  classes_with_no_properties: number
}

export interface OntologyMetricDistributions {
  class_depth: Metric
  subclasses_per_class: Metric
  superclasses_per_class: Metric
  data_props_per_class: Metric
  object_props_out_per_class: Metric
  object_props_in_per_class: Metric
  data_prop_domain_arity: Metric
  object_prop_domain_arity: Metric
  object_prop_range_arity: Metric
  intersection_arity: Metric
}

export interface OntologyMetrics {
  counts: OntologyMetricCounts
  distributions: OntologyMetricDistributions
}

export interface IterationSummary {
  index: number
  ontology_metrics: OntologyMetrics | null
}

export interface RunDetail {
  metadata: RunMetadata
  iterations: IterationSummary[]
}

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

export interface IterationDetail {
  index: number
  ontology: Ontology | null
  ops: Operation[]
  plan: string | null
  review: string | null
  ontology_metrics: OntologyMetrics | null
}
