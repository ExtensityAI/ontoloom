"""Public API for pattern matching.

Deliberate exception to the project rule that `__init__.py` files are empty
and never re-export. `_generated.py` is regenerated from the axiom hierarchy
by `gen_patterns.py`, and consumers should not depend on its internal layout
-> this module is the single stable import surface that hides regeneration
churn. The PLC0414 `as`-aliases are explicit re-export markers required by
ruff for this case.
"""

from ontoloom.patterns._generated import (
    AnnotationAssertionPattern as AnnotationAssertionPattern,
)
from ontoloom.patterns._generated import (
    AnnotationPropertyDomainPattern as AnnotationPropertyDomainPattern,
)
from ontoloom.patterns._generated import (
    AnnotationPropertyRangePattern as AnnotationPropertyRangePattern,
)
from ontoloom.patterns._generated import (
    AxiomPattern as AxiomPattern,
)
from ontoloom.patterns._generated import (
    ClassAssertionPattern as ClassAssertionPattern,
)
from ontoloom.patterns._generated import (
    ContainsExpr as ContainsExpr,
)
from ontoloom.patterns._generated import (
    ContainsSlot as ContainsSlot,
)
from ontoloom.patterns._generated import (
    DataHasValuePattern as DataHasValuePattern,
)
from ontoloom.patterns._generated import (
    DataPropertyAssertionPattern as DataPropertyAssertionPattern,
)
from ontoloom.patterns._generated import (
    DataPropertyDomainPattern as DataPropertyDomainPattern,
)
from ontoloom.patterns._generated import (
    DataPropertyRangePattern as DataPropertyRangePattern,
)
from ontoloom.patterns._generated import (
    DataSomeValuesFromPattern as DataSomeValuesFromPattern,
)
from ontoloom.patterns._generated import (
    DatatypeDefinitionPattern as DatatypeDefinitionPattern,
)
from ontoloom.patterns._generated import (
    DeclarationPattern as DeclarationPattern,
)
from ontoloom.patterns._generated import (
    DifferentIndividualsPattern as DifferentIndividualsPattern,
)
from ontoloom.patterns._generated import (
    DisjointClassesPattern as DisjointClassesPattern,
)
from ontoloom.patterns._generated import (
    EquivalentClassesPattern as EquivalentClassesPattern,
)
from ontoloom.patterns._generated import (
    EquivalentDataPropertiesPattern as EquivalentDataPropertiesPattern,
)
from ontoloom.patterns._generated import (
    EquivalentObjectPropertiesPattern as EquivalentObjectPropertiesPattern,
)
from ontoloom.patterns._generated import (
    ExpressionPattern as ExpressionPattern,
)
from ontoloom.patterns._generated import (
    ExprSlot as ExprSlot,
)
from ontoloom.patterns._generated import (
    FunctionalDataPropertyPattern as FunctionalDataPropertyPattern,
)
from ontoloom.patterns._generated import (
    HasKeyPattern as HasKeyPattern,
)
from ontoloom.patterns._generated import (
    NamedClassPattern as NamedClassPattern,
)
from ontoloom.patterns._generated import (
    NegativeDataPropertyAssertionPattern as NegativeDataPropertyAssertionPattern,
)
from ontoloom.patterns._generated import (
    NegativeObjectPropertyAssertionPattern as NegativeObjectPropertyAssertionPattern,
)
from ontoloom.patterns._generated import (
    ObjectHasSelfPattern as ObjectHasSelfPattern,
)
from ontoloom.patterns._generated import (
    ObjectHasValuePattern as ObjectHasValuePattern,
)
from ontoloom.patterns._generated import (
    ObjectIntersectionOfPattern as ObjectIntersectionOfPattern,
)
from ontoloom.patterns._generated import (
    ObjectOneOfPattern as ObjectOneOfPattern,
)
from ontoloom.patterns._generated import (
    ObjectPropertyAssertionPattern as ObjectPropertyAssertionPattern,
)
from ontoloom.patterns._generated import (
    ObjectPropertyDomainPattern as ObjectPropertyDomainPattern,
)
from ontoloom.patterns._generated import (
    ObjectPropertyRangePattern as ObjectPropertyRangePattern,
)
from ontoloom.patterns._generated import (
    ObjectSomeValuesFromPattern as ObjectSomeValuesFromPattern,
)
from ontoloom.patterns._generated import (
    Pattern as Pattern,
)
from ontoloom.patterns._generated import (
    ReflexiveObjectPropertyPattern as ReflexiveObjectPropertyPattern,
)
from ontoloom.patterns._generated import (
    SameIndividualPattern as SameIndividualPattern,
)
from ontoloom.patterns._generated import (
    SubAnnotationPropertyOfPattern as SubAnnotationPropertyOfPattern,
)
from ontoloom.patterns._generated import (
    SubClassOfPattern as SubClassOfPattern,
)
from ontoloom.patterns._generated import (
    SubDataPropertyOfPattern as SubDataPropertyOfPattern,
)
from ontoloom.patterns._generated import (
    SubObjectPropertyOfChainPattern as SubObjectPropertyOfChainPattern,
)
from ontoloom.patterns._generated import (
    SubObjectPropertyOfPattern as SubObjectPropertyOfPattern,
)
from ontoloom.patterns._generated import (
    TransitiveObjectPropertyPattern as TransitiveObjectPropertyPattern,
)
