from typing import Generic, TypeVar, Protocol, Callable
from enum import Enum
from arena.elo import calculate_team_elo_from_vote

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class VoteOutcome(Enum):
    A = "A"
    B = "B"
    TIE = "tie"
    BOTH_BAD = "both_bad"


class TTSModelName(str, Enum):
    """Enum for all available TTS model names with their providers."""

    # OpenAI models
    TTS_1 = "tts-1"

    # ElevenLabs models
    ELEVEN_V3 = "eleven_v3"
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"

    # Deepgram models
    AURA_2_THALIA_EN = "aura-2-thalia-en"

    # Cartesia models
    SONIC_3 = "sonic-3"


class Model(Protocol[TInput, TOutput]):
    """
    Model protocol that standardizes the interface for models in the arena.

    Purpose:
    - Standardizes model usage interface across different model types
    - Holds metadata about each model (name, function)
    - Provides a uniform way to call models regardless of their underlying implementation
    - Uses name as unique identifier for tracking ELO ratings and statistics

    Attributes:
        name: Human-readable name/identifier for the model (acts as unique hash key)
        function: The callable that performs the model's inference

    Usage:
        Models can be hashed and compared by name, making them suitable for use
        as dictionary keys or in sets for tracking ELO ratings and statistics.
    """

    def __init__(self, name: str, function: Callable[[TInput], TOutput]) -> None:
        self.function = function
        self.name = name

    def __call__(self, input_data: TInput) -> TOutput: ...

    def __repr__(self) -> str:
        return f"Model(name={self.name})"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if isinstance(other, Model):
            return self.name == other.name
        return False


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

    def __hash__(self) -> int:
        """Hash based on concatenated model names with '|' separator."""
        chain_key = "|".join(model.name for model in self.model_chain)
        return hash(chain_key)

    def __eq__(self, other) -> bool:
        """Two model chains are equal if they contain the same models in the same order."""
        if isinstance(other, ModelChain):
            return self.model_chain == other.model_chain
        return False


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
        initial_elo: float = 1500.0,
    ):
        """
        Initialize the arena.

        Args:
            model_chains: List of model chains to include in the arena
            initial_elo: Initial ELO rating for all models (default: 1500.0)
        """
        self.model_chains = model_chains
        # Track ELO ratings for each model (using model as key via __hash__)
        self.model_elos: dict[Model, float] = {}
        # Initialize ELO ratings for all models in all chains
        for chain in model_chains:
            for model in chain.model_chain:
                if model not in self.model_elos:
                    self.model_elos[model] = initial_elo

    # === Voting and ELO Management ===
    def record_vote(
        self,
        chain_a: ModelChain[TInput, TOutput],
        chain_b: ModelChain[TInput, TOutput],
        vote: VoteOutcome,
    ) -> None:
        """
        Record a vote between two model chains and update their ELO ratings.

        This method treats each model chain as a team and calculates team-based
        ELO ratings. Each model in the chain gets the same rating adjustment.

        Args:
            chain_a: First model chain (team A)
            chain_b: Second model chain (team B)
            vote: The outcome of the vote (A wins, B wins, tie, or both bad)
        """
        # Get current ELO ratings for all models in each chain
        team_a_ratings = [self.model_elos[model] for model in chain_a.model_chain]
        team_b_ratings = [self.model_elos[model] for model in chain_b.model_chain]

        # Calculate new ELO ratings using team-based algorithm
        new_team_a_ratings, new_team_b_ratings = calculate_team_elo_from_vote(
            vote, team_a_ratings, team_b_ratings
        )

        # Update ELO ratings for all models
        for i, model in enumerate(chain_a.model_chain):
            self.model_elos[model] = new_team_a_ratings[i]

        for i, model in enumerate(chain_b.model_chain):
            self.model_elos[model] = new_team_b_ratings[i]

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

    def get_leaderboard(self) -> list[tuple[Model, float]]:
        """
        Get models sorted by ELO rating (highest first).

        Returns:
            List of tuples containing (model, elo_rating) sorted by rating
        """
        return sorted(self.model_elos.items(), key=lambda x: x[1], reverse=True)

    def get_model_elo(self, model: Model | str) -> float:
        """
        Get the current ELO rating for a specific model.

        Args:
            model: Model object or model name string to look up

        Returns:
            Current ELO rating for the model

        Raises:
            KeyError: If model is not found in the arena
        """
        if isinstance(model, str):
            # Search by name if string provided
            for m, elo in self.model_elos.items():
                if m.name == model:
                    return elo
            raise KeyError(f"Model with name '{model}' not found in arena")
        return self.model_elos[model]
