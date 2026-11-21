import os

import pytest

from bench.scenario import load_scenarios

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIO_DIR = os.path.join(ROOT, "scenarios")


@pytest.fixture(scope="session")
def scenarios():
    return load_scenarios(SCENARIO_DIR)


@pytest.fixture()
def by_id(scenarios):
    return {s.id: s for s in scenarios}
