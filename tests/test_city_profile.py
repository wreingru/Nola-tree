import pytest

from tree_counter.city_profile import get_profile


def test_nola_profile():
    p = get_profile("nola")
    assert p.name == "New Orleans"
    assert p.default_zip == "70115"


def test_unknown_city():
    with pytest.raises(ValueError):
        get_profile("atlantis")
