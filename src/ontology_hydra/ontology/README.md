## Growing Ontologies

Instead of using our CQ approach, **grow ontologies**. Always start with a pre-defined `Thing` class. Generate a number of proposals for changes (may be additions, removals, or large-scale updates). Let a LLM rank them and pick one. Apply it and continue. In the beginning, proposal generation is pretty much open. Later iterations become more and more focused, essentially generating a fine-grained structure.

**Why?** Using proposals and modifications, we get a change history. Also, in early iterations, we do not have a lot of data, so it makes sense to make more coarse-grained operations. With later iterations, we assume that the model has already zeroed in on a specific structure, and we can focus on finer details.

We could e.g. calculate a cost of update (e.g. cost of removal of a class can vary depending on if it has subclasses, etc., same for changes, and maybe adding new higher-level classes is more costly later)

Alternatively, we could infer stage (early, late, etc.) depending on what the best change proposal is.

--> would also allow us to not generate a lot of the baggage we have (like meta properties that the current ontology generator creates ala "DeduplicationCluster" in biography ontology)

## Problem: Training Data

How do I make sure it is diverse enough?

1. in the early stages, grow multiple ontologies at the same time and then merge them at a later time point, ensuring that we have diverse ones
2. embed our data, use sth like KMeans and then sample from each cluster for training data
