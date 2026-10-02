"""Suite-wide guard: running the tests must not create /content.

The package mirrors to /content on Colab. Off Colab that path is at the
filesystem root (C:\\content on Windows), outside the repository. An unguarded
mirror in train() once created it on every machine that ran training, and it
was found only by accident. This fails the run instead.
"""
from pathlib import Path

import pytest

_ROOT = Path("/content")


@pytest.fixture(scope="session", autouse=True)
def _suite_creates_nothing_under_content():
    existed = _ROOT.exists()
    yield
    assert existed or not _ROOT.exists(), (
        f"the test run created {_ROOT.resolve()} -- something writes to the Colab "
        "mirror without going through graphsentinel.utils.scratch.local_scratch"
    )
