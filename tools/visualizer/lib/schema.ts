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
    description: z.string().nullish(),
    constraints: z.string().nullish(),
})

const dataPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullish(),
    characteristics: z.array(characteristicSchema),
    domain: z.array(z.string()),
    range: dataTypeSchema,
})

const objectPropertySchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullish(),
    characteristics: z.array(characteristicSchema),
    domain: z.array(z.string()),
    range: z.array(z.string()),
})

const classSchema = z.object({
    name: z.string(),
    description: descriptionSchema.nullish(),
    own_properties: z.array(z.string()),
    superclass: z.string().nullable(),
})

const classExportSchema = z.object({
    data: classSchema,
    parents: z.array(z.string()),
    children: z.array(z.string()),
})

const dataPropertyExportSchema = z.object({
    type: z.literal('data'),
    data: dataPropertySchema,
})

const objectPropertyExportSchema = z.object({
    type: z.literal('object'),
    data: objectPropertySchema,
})

export const ontologyExportSchema = z.object({
    classes: z.array(classExportSchema),
    properties: z.array(
        z.discriminatedUnion('type', [dataPropertyExportSchema, objectPropertyExportSchema]),
    ),
})

export type ClassExport = z.infer<typeof classExportSchema>

export type OntologyExport = z.infer<typeof ontologyExportSchema>
