# Supported Features

HyDRA supports the following features of OWL:

- `owl:Class`
- `rdfs:subClassOf` (including multi-inheritance)

- `owl:ObjectProperty` and `owl:DatatypeProperty`
- `rdfs:subPropertyOf`
- `rdfs:domain` and `rdfs:range` with named classes and `owl:intersectionOf`

- `owl:intersectionOf`
- `owl:inverseOf`
- `owl:equivalentClass`

# Choices

We use a custom JSON structure for prompting the LLMs instead of JSON-LD, as JSON-LD is token-heavy.
