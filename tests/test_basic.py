# pyright: strict, reportUnusedExpression=false

import pytest
from great_project import compute, entrypoint
from great_project.__about__ import __version__


def test_version():
    assert "dev" in __version__


def test_compute():
    assert compute(1, 2) == 3
    with pytest.raises(TypeError):
        compute(1.0, 2)  # pyright: ignore [reportGeneralTypeIssues]
    assert entrypoint() is None
