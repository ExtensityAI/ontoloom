from ontoloom.owl.expressions import ObjectHasSelf, is_class_expression
from ontoloom.owl.iri import IRI


class TestIsClassExpression:
    """Tests for is_class_expression predicate."""

    def test_iri_instance_returns_true(self):
        """IRI instance should return True."""
        iri = IRI(":Dog")
        assert is_class_expression(iri) is True

    def test_base_class_expression_instance_returns_true(self):
        """BaseClassExpression instance (ObjectHasSelf) should return True."""
        expr = ObjectHasSelf(property=IRI(":likes"))
        assert is_class_expression(expr) is True

    def test_plain_int_returns_false(self):
        """Plain int should return False."""
        assert is_class_expression(42) is False

    def test_plain_dict_returns_false(self):
        """Plain dict should return False."""
        assert is_class_expression({"key": "value"}) is False

    def test_plain_none_returns_false(self):
        """None should return False."""
        assert is_class_expression(None) is False

    def test_plain_str_returns_false(self):
        """Plain str (not IRI) should return False."""
        assert is_class_expression("plain string") is False
