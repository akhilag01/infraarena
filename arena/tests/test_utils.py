"""
Test utilities and fixtures for arena testing.

This module provides common test helpers, mock implementations,
and factory functions for creating test data.
"""

from typing import Callable
from arena.arena_base import ModelChain, ArenaBase
from arena.elo import VoteOutcome


# Global counter to ensure unique model names
_model_counter = 0


def _get_unique_model_id() -> int:
    """Get a unique ID for model naming."""
    global _model_counter
    _model_counter += 1
    return _model_counter


def reset_model_counter() -> None:
    """
    Reset the global model counter.

    Useful for test isolation to ensure predictable model names.
    Call this at the beginning of tests if you need consistent naming.
    """
    global _model_counter
    _model_counter = 0


class SimpleModel:
    """
    Simple model implementation for testing.

    This provides a simple, predictable model for testing without external dependencies.
    """

    def __init__(self, name: str, function: Callable[[str], str]) -> None:
        self.name = name
        self.function = function

    def __call__(self, input_data: str) -> str:
        return self.function(input_data)

    def __repr__(self) -> str:
        return f"Model(name={self.name})"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if isinstance(other, SimpleModel):
            return self.name == other.name
        return False


# Common model transformation functions
def upper_transform(x: str) -> str:
    """Transform text to uppercase."""
    return x.upper()


def lower_transform(x: str) -> str:
    """Transform text to lowercase."""
    return x.lower()


def exclaim_transform(x: str) -> str:
    """Add exclamation mark to text."""
    return x + "!"


def reverse_transform(x: str) -> str:
    """Reverse the text."""
    return x[::-1]


def repeat_transform(x: str) -> str:
    """Repeat the text twice."""
    return x + x


# Factory functions for creating test data
def create_mock_model(name: str = None, transform: Callable[[str], str] = None) -> SimpleModel:
    """
    Create a mock model with the given name and optional transform function.

    Each model gets a unique name by appending an auto-incremented ID.

    Args:
        name: Base name for the model (will have unique ID appended). If None, uses "model"
        transform: Optional transformation function (default: identity function)

    Returns:
        SimpleModel instance with unique name like "name_1", "name_2", etc.
    """
    if name is None:
        name = "model"
    if transform is None:
        transform = lambda x: x
    unique_name = f"{name}_{_get_unique_model_id()}"
    model = SimpleModel(unique_name, transform)
    model._base_name = name  # Store original name for lookups
    return model


def create_basic_models() -> list[SimpleModel]:
    """
    Create a standard set of basic models for testing.

    Returns:
        List of 5 models with different transformations
    """
    return [
        create_mock_model("upper", upper_transform),
        create_mock_model("lower", lower_transform),
        create_mock_model("exclaim", exclaim_transform),
        create_mock_model("reverse", reverse_transform),
        create_mock_model("repeat", repeat_transform),
    ]


def create_mock_model_chain(models: list[SimpleModel]) -> ModelChain[str, str]:
    """
    Create a model chain from a list of models.

    Args:
        models: List of models to chain together

    Returns:
        ModelChain instance
    """
    return ModelChain(models)


def create_test_arena(
    num_models: int = 3,
    initial_elo: float = 1500.0,
    temperature: float = 400.0,
    recency_penalty: float = 0.3,
) -> tuple[ArenaBase[str, str], list[SimpleModel], list[ModelChain[str, str]]]:
    """
    Create a complete test arena with models and chains.

    Args:
        num_models: Number of models to create
        initial_elo: Initial ELO rating for all competitors
        temperature: Matchup temperature parameter
        recency_penalty: Recency penalty parameter

    Returns:
        Tuple of (arena, models, chains)
    """
    models = create_basic_models()[:num_models]
    # Create single-model chains for each model
    chains = [create_mock_model_chain([model]) for model in models]

    arena = ArenaBase(
        chains,
        initial_elo=initial_elo,
        matchup_temperature=temperature,
        recency_penalty=recency_penalty,
    )

    return arena, models, chains


def set_model_elos(
    arena: ArenaBase, model_elos: dict[str, float]
) -> None:
    """
    Set specific ELO ratings for models by base name (without the unique ID suffix).

    Args:
        arena: Arena instance to modify
        model_elos: Dictionary mapping base model names to desired ELO ratings
                   (e.g., {"upper": 1800.0} will match "upper_1", "upper_2", etc.)
    """
    for model in arena.model_elos.keys():
        # Check if model has _base_name attribute (MockModel)
        if hasattr(model, '_base_name'):
            base_name = model._base_name
            if base_name in model_elos:
                arena.model_elos[model] = model_elos[base_name]
        else:
            # Fallback to exact name match for non-MockModel instances
            if model.name in model_elos:
                arena.model_elos[model] = model_elos[model.name]


def set_chain_elos(
    arena: ArenaBase, chain_elos: dict[str, float]
) -> None:
    """
    Set specific ELO ratings for chains by their string representation.

    Args:
        arena: Arena instance to modify
        chain_elos: Dictionary mapping chain keys to desired ELO ratings
                   Keys should be pipe-separated model names (e.g., "model_a|model_b")
    """
    for chain, elo in arena.chain_elos.items():
        chain_key = "|".join(model.name for model in chain.model_chain)
        if chain_key in chain_elos:
            arena.chain_elos[chain] = chain_elos[chain_key]


def simulate_votes(
    arena: ArenaBase,
    chain_pairs: list[tuple[int, int]],
    outcomes: list[str],
) -> None:
    """
    Simulate a series of votes in the arena.

    Args:
        arena: Arena instance
        chain_pairs: List of tuples (chain_a_index, chain_b_index)
        outcomes: List of outcome strings ("A", "B", "TIE", "BOTH_BAD")
    """
    outcome_map = {
        "A": VoteOutcome.A,
        "B": VoteOutcome.B,
        "TIE": VoteOutcome.TIE,
        "BOTH_BAD": VoteOutcome.BOTH_BAD,
    }

    chains = arena.model_chains

    for (a_idx, b_idx), outcome_str in zip(chain_pairs, outcomes):
        outcome = outcome_map[outcome_str]
        arena.record_vote(chains[a_idx], chains[b_idx], outcome)


def get_model_by_name(arena: ArenaBase, name: str) -> SimpleModel:
    """
    Find a model by name in the arena.

    Searches by both exact name and base name (for SimpleModel instances).

    Args:
        arena: Arena instance
        name: Model name or base name to search for

    Returns:
        Model with matching name

    Raises:
        ValueError: If model not found
    """
    for model in arena.model_elos.keys():
        # Try exact match first
        if model.name == name:
            return model
        # Try base name match for MockModel
        if hasattr(model, '_base_name') and model._base_name == name:
            return model
    raise ValueError(f"Model '{name}' not found in arena")


def get_chain_by_models(
    arena: ArenaBase, model_names: list[str]
) -> ModelChain:
    """
    Find a chain by its model names in the arena.

    Args:
        arena: Arena instance
        model_names: List of model names in order

    Returns:
        ModelChain matching the model names

    Raises:
        ValueError: If chain not found
    """
    target_key = "|".join(model_names)

    for chain in arena.chain_elos.keys():
        chain_key = "|".join(model.name for model in chain.model_chain)
        if chain_key == target_key:
            return chain

    raise ValueError(f"Chain with models {model_names} not found in arena")


def assert_elo_increased(initial: float, final: float, min_change: float = 0.1):
    """
    Assert that ELO increased by at least min_change.

    Args:
        initial: Initial ELO rating
        final: Final ELO rating
        min_change: Minimum expected change
    """
    change = final - initial
    assert change >= min_change, f"ELO change {change} is less than {min_change}"


def assert_elo_decreased(initial: float, final: float, min_change: float = 0.1):
    """
    Assert that ELO decreased by at least min_change.

    Args:
        initial: Initial ELO rating
        final: Final ELO rating
        min_change: Minimum expected change (positive value)
    """
    change = initial - final
    assert change >= min_change, f"ELO change {change} is less than {min_change}"


def assert_elo_in_range(elo: float, min_elo: float, max_elo: float):
    """
    Assert that ELO is within specified range.

    Args:
        elo: ELO rating to check
        min_elo: Minimum expected ELO
        max_elo: Maximum expected ELO
    """
    assert min_elo <= elo <= max_elo, f"ELO {elo} not in range [{min_elo}, {max_elo}]"


def count_matchup_appearances(
    arena: ArenaBase, num_matchups: int
) -> dict[ModelChain, int]:
    """
    Generate matchups and count how many times each chain appears.

    Args:
        arena: Arena instance
        num_matchups: Number of matchups to generate

    Returns:
        Dictionary mapping chains to appearance counts
    """
    appearances = {chain: 0 for chain in arena.model_chains}

    for _ in range(num_matchups):
        chain_a, chain_b = arena.generate_matchup()
        appearances[chain_a] += 1
        appearances[chain_b] += 1

    return appearances
