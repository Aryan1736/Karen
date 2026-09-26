"""
Karen's Ear — Scenario Registry Package.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md, architecture/simulation.md
Status: Phase 2 — Golden Disaster Scenarios
"""

from typing import Callable, Dict, List

from simulator.models import ScenarioEvent
from simulator.scenarios.flood_rasulgarh import (
    SCENARIO_DESCRIPTION as FLOOD_DESC,
    SCENARIO_ID as FLOOD_ID,
    SCENARIO_NAME as FLOOD_NAME,
    get_flood_rasulgarh_events,
)
from simulator.scenarios.mixed_hard_negatives import (
    SCENARIO_DESCRIPTION as HARD_NEG_DESC,
    SCENARIO_ID as HARD_NEG_ID,
    SCENARIO_NAME as HARD_NEG_NAME,
    get_mixed_hard_negatives_events,
)

SCENARIO_REGISTRY: Dict[str, Dict[str, object]] = {
    FLOOD_ID: {
        "id": FLOOD_ID,
        "name": FLOOD_NAME,
        "description": FLOOD_DESC,
        "loader": get_flood_rasulgarh_events,
    },
    HARD_NEG_ID: {
        "id": HARD_NEG_ID,
        "name": HARD_NEG_NAME,
        "description": HARD_NEG_DESC,
        "loader": get_mixed_hard_negatives_events,
    },
}


def register_scenario(
    scenario_id: str,
    name: str,
    description: str,
    loader: Callable[[], List[ScenarioEvent]],
) -> None:
    """Dynamically registers a custom scenario in the registry."""
    SCENARIO_REGISTRY[scenario_id] = {
        "id": scenario_id,
        "name": name,
        "description": description,
        "loader": loader,
    }


def list_scenarios() -> List[str]:
    """Returns list of registered scenario identifiers."""
    return list(SCENARIO_REGISTRY.keys())


def get_scenario(scenario_id: str) -> List[ScenarioEvent]:
    """
    Loads and returns the deterministic events for a registered scenario.

    Raises:
        KeyError: If scenario_id is not registered.
    """
    if scenario_id not in SCENARIO_REGISTRY:
        raise KeyError(
            f"Scenario '{scenario_id}' not found. Available scenarios: {list_scenarios()}"
        )
    loader = SCENARIO_REGISTRY[scenario_id]["loader"]
    return loader()  # type: ignore[operator]


__all__ = [
    "FLOOD_ID",
    "HARD_NEG_ID",
    "SCENARIO_REGISTRY",
    "get_flood_rasulgarh_events",
    "get_mixed_hard_negatives_events",
    "get_scenario",
    "list_scenarios",
    "register_scenario",
]
