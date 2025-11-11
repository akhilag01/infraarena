from typing import Generic, TypeVar, Protocol, Callable
from enum import Enum

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class VoteOutcome(Enum):
    LEFT = "left"
    RIGHT = "right"
    TIE = "tie"
    BOTH_BAD = "both_bad"


class Model(Protocol[TInput, TOutput]):
    def __init__(self, name: str, function: Callable[[TInput], TOutput]) -> None:
        self.function = function
        self.name = name

    def __call__(self, input_data: TInput) -> TOutput: ...

    def __repr__(self) -> str:
        return f"Model(name={self.name})"


class ModelChain(Generic[TInput, TOutput]):
    def __init__(self, model_chain: list[Model] | Model):
        if isinstance(model_chain, Callable):
            model_chain = [model_chain]
        self.model_chain = model_chain

    def __repr__(self) -> str:
        return f"ModelChain({self.model_chain})"

    def __call__(self, input_data: TInput) -> TOutput:
        for model in self.model_chain:
            input_data = model(input_data)
        return input_data


class ArenaBase(Generic[TInput, TOutput]):
    """
    Base arena class for comparing models with any input/output types.

    This class provides a reusable framework for:
    - Managing models with ELO ratings
    - Generating outputs from multiple models
    - Recording votes and updating ELO ratings
    - Generating matchups between models
    - Tracking model statistics

    Type Parameters:
        TInput: The input type for model generation (e.g., str, dict, bytes)
        TOutput: The output type from models (e.g., str, bytes, dict)
    """

    def __init__(
        self,
        model_chains: list[ModelChain[TInput, TOutput]],
    ):
        """
        Initialize the arena.

        Args:
            models: List of models to include in the arena
        """
        self.model_chains = model_chains

    # === Voting and ELO Management ===
    def record_vote(
        self,
        winner: ModelChain[TInput, TOutput],
        loser: ModelChain[TInput, TOutput],
        vote: VoteOutcome,
    ) -> None:
        """Record a vote between two models and update their ELO ratings."""
        raise NotImplementedError

    # === Matchup Generation ===
    def generate_matchup(
        self,
    ) -> tuple[ModelChain[TInput, TOutput], ModelChain[TInput, TOutput]]:
        """Generate a matchup between two models."""
        raise NotImplementedError

    def generate_output(
        self,
        input_data: TInput,
    ) -> TOutput:
        """Generate outputs to compare from model chains given input data."""
        model_chain_a, model_chain_b = self.generate_matchup()

        # TODO make this work with async + streaming
        output_a = model_chain_a(input_data)
        output_b = model_chain_b(input_data)

        return output_a, output_b

    # === Model Access ===

    def list_models(self) -> list[ModelChain[TInput, TOutput]]:
        """List all models in the arena."""
        return self.model_chains

    def get_leaderboard(self) -> list[ModelChain[TInput, TOutput]]:
        """Get models sorted by ELO rating (highest first)."""
        raise NotImplementedError
