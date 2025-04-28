import pytest
from db import db as mdb


@pytest.fixture
def db():
    return mdb



def test_dialect(db):
    assert db.dialect == "sqlite"
    assert db.get_usable_table_names() == [
        "Album",
        "Artist",
        "Customer",
        "Employee",
        "Genre",
        "Invoice",
        "InvoiceLine",
        "MediaType",
        "Playlist",
        "PlaylistTrack",
        "Track"
    ]