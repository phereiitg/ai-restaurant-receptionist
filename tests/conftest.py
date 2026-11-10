import pytest
from app.storage import Storage

@pytest.fixture
def store(tmp_path):
    return Storage(str(tmp_path/'data.sqlite3'))
