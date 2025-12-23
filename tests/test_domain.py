import pytest
from src.domain import geo_changes

def test_compute_changes_not_implemented():
    with pytest.raises(NotImplementedError):
        geo_changes.compute_changes("{}", "{}")
