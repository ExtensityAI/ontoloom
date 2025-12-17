import { z } from 'zod'

const characteristicSchema = z.enum([
    'functional',
    'inverseFunctional',
    'transitive',
    'symmetric',
    'asymmetric',
    'reflexive',
    'irreflexive',
])

const dataTypeSchema = z.enum([
    'string',
    'int',
    'float',
    'boolean',
    'datetime',
    'date',
    'time',
])

const descriptionSchema = z.object({
    description: z.string().nullable(),
    constraints: z.string().nullable(),
})

const dataPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullable(),
    characteristics: z.array(characteristicSchema),
    domain: z.array(z.string()),
    range: dataTypeSchema,
})

const objectPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullable(),
    characteristics: z.array(characteristicSchema),
    domain: z.array(z.string()),
    range: z.array(z.string()),
})

const classSchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullable(),
    own_properties: z.array(z.string()),
    superclass: z.string().nullable(),
})

export const ontologySchema = z.object({
    classes: z.record(z.string(), classSchema),
    objectProperties: z.record(z.string(), objectPropertySchema),
    dataProperties: z.record(z.string(), dataPropertySchema),
})

export type Class = z.infer<typeof classSchema>
export type DataProperty = z.infer<typeof dataPropertySchema>
export type ObjectProperty = z.infer<typeof objectPropertySchema>
export type Ontology = z.infer<typeof ontologySchema>