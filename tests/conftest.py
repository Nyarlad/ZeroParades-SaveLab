import pytest

from zero_parades_savelab.demo import synthetic_save
from zero_parades_savelab.service import SaveService


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source" / "synthetic.sav"
    path.parent.mkdir()
    path.write_bytes(synthetic_save())
    return path


@pytest.fixture
def service(tmp_path):
    return SaveService(tmp_path / "recovery", process_check=lambda: None)
