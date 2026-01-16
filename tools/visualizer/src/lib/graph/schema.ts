import { z } from 'zod'

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
    definition: z.string(),
    constraints: z.string().nullish(),
})

const dataPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema,
    domain: z.array(z.string()),
    range: dataTypeSchema,
})

const objectPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema,
    domain: z.array(z.string()),
    range: z.array(z.string()),
})

const classSchema = z.object({
    name: z.string(),
    description: descriptionSchema,
    sub_class_of: z.array(z.string()),
})

export const ontologySchema = z.object({
    classes: z.record(z.string(), classSchema),
    object_properties: z.record(z.string(), objectPropertySchema),
    data_properties: z.record(z.string(), dataPropertySchema),
})

export type Class = z.infer<typeof classSchema>
export type DataProperty = z.infer<typeof dataPropertySchema>
export type ObjectProperty = z.infer<typeof objectPropertySchema>
export type Ontology = z.infer<typeof ontologySchema>