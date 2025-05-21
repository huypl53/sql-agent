import pytest
from shared.db import get_db as mdb


@pytest.fixture
def db():
    return mdb


def test_dialect(db):
    assert len(db.get_usable_table_names())
