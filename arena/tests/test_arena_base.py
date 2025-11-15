"""
Tests for the ArenaBase class and core arena functionality.
"""

import pytest
from arena.arena_base import ModelChain
from arena.elo import VoteOutcome
from arena.tests.test_utils import (
    create_mock_model,
    create_test_arena,
    set_model_elos,
    count_matchup_appearances,
    upper_transform,
    lower_transform,
    exclaim_transform,
)


class TestModel:
    """Test the Model protocol implementation."""

    def test_model_hash_by_name(self):
        """Test that models are hashed by their unique name."""
        model1 = create_mock_model("test", lambda x: x)
        model2 = create_mock_model("other", lambda x: x)

        # Each model gets a unique name with counter, so hashes differ
        assert hash(model1) != hash(model2)

        # Same model instance should have consistent hash
        assert hash(model1) == hash(model1)

    def test_model_equality_by_name(self):
        """Test that models are equal if they have the same unique name."""
        model1 = create_mock_model("test", lambda x: x)
        model2 = create_mock_model("other", lambda x: x)

        # Different models have different unique names
        assert model1 != model2

        # Same model instance is equal to itself
        assert model1 == model1

    def test_model_callable(self):
        """Test that models can be called."""
        model = create_mock_model("upper", upper_transform)
        assert model("hello") == "HELLO"


class TestModelChain:
    """Test the ModelChain class."""

    def test_model_chain_single_model(self):
        """Test model chain with a single model."""
        model = create_mock_model("upper", upper_transform)
        chain = ModelChain([model])

        result = chain("hello")
        assert result == "HELLO"

    def test_model_chain_multiple_models(self):
        """Test model chain with multiple models in sequence."""
        upper = create_mock_model("upper", upper_transform)
        exclaim = create_mock_model("exclaim", exclaim_transform)
        chain = ModelChain([upper, exclaim])

        result = chain("hello")
        assert result == "HELLO!"

    def test_model_chain_hash_by_names(self):
        """Test that model chains are hashed by pipe-separated model names."""
        model1 = create_mock_model("a", lambda x: x)
        model2 = create_mock_model("b", lambda x: x)
        model3 = create_mock_model("c", lambda x: x)

        chain1 = ModelChain([model1, model2])
        chain2 = ModelChain([model1, model2])
        chain3 = ModelChain([model2, model1])  # Different order
        chain4 = ModelChain([model1, model3])  # Different second model

        assert hash(chain1) == hash(chain2)  # Same models, same order
        assert hash(chain1) != hash(chain3)  # Different order
        assert hash(chain1) != hash(chain4)  # Different models

    def test_model_chain_equality(self):
        """Test that model chains are equal if they have the same models in order."""
        model1 = create_mock_model("a", lambda x: x)
        model2 = create_mock_model("b", lambda x: x)

        chain1 = ModelChain([model1, model2])
        chain2 = ModelChain([model1, model2])
        chain3 = ModelChain([model2, model1])

        assert chain1 == chain2  # Same models, same order
        assert chain1 != chain3  # Different order


class TestArenaBase:
    """Test the ArenaBase class."""

    @pytest.fixture
    def arena_setup(self):
        """Create an arena instance with models and chains for testing."""
        return create_test_arena(num_models=3)

    def test_arena_initialization(self, arena_setup):
        """Test that arena initializes with correct ELO ratings."""
        arena, models, chains = arena_setup

        # All models should have initial ELO
        for model in models:
            assert arena.model_elos[model] == 1500.0

        # All chains should have initial ELO
        for chain in chains:
            assert arena.chain_elos[chain] == 1500.0

    def test_arena_custom_initial_elo(self):
        """Test arena with custom initial ELO."""
        arena, models, chains = create_test_arena(num_models=3, initial_elo=1200.0)

        for chain in chains:
            assert arena.chain_elos[chain] == 1200.0

    def test_record_vote_updates_model_elos(self, arena_setup):
        """Test that recording a vote updates model ELOs."""
        arena, models, chains = arena_setup
        chain_a, chain_b = chains[0], chains[1]

        initial_a = arena.model_elos[models[0]]
        initial_b = arena.model_elos[models[1]]

        # Record a win for chain A
        arena.record_vote(chain_a, chain_b, VoteOutcome.A)

        # Winner should gain ELO, loser should lose ELO
        assert arena.model_elos[models[0]] > initial_a
        assert arena.model_elos[models[1]] < initial_b

    def test_record_vote_updates_chain_elos(self, arena_setup):
        """Test that recording a vote updates chain ELOs."""
        arena, _, chains = arena_setup
        chain_a, chain_b = chains[0], chains[1]

        initial_a = arena.chain_elos[chain_a]
        initial_b = arena.chain_elos[chain_b]

        # Record a win for chain A
        arena.record_vote(chain_a, chain_b, VoteOutcome.A)

        # Winner should gain ELO, loser should lose ELO
        assert arena.chain_elos[chain_a] > initial_a
        assert arena.chain_elos[chain_b] < initial_b

    def test_record_vote_tie(self, arena_setup):
        """Test that tie votes update ELOs appropriately."""
        arena, _, chains = arena_setup
        chain_a, chain_b = chains[0], chains[1]

        # Give chain_a a higher ELO so tie affects both
        arena.chain_elos[chain_a] = 1600.0

        initial_a = arena.chain_elos[chain_a]
        initial_b = arena.chain_elos[chain_b]

        arena.record_vote(chain_a, chain_b, VoteOutcome.TIE)

        # With unequal ratings, a tie should lower higher rated and raise lower rated
        assert arena.chain_elos[chain_a] < initial_a
        assert arena.chain_elos[chain_b] > initial_b

    def test_record_vote_both_bad(self, arena_setup):
        """Test that both_bad votes penalize both competitors."""
        arena, _, chains = arena_setup
        chain_a, chain_b = chains[0], chains[1]

        initial_a = arena.chain_elos[chain_a]
        initial_b = arena.chain_elos[chain_b]

        arena.record_vote(chain_a, chain_b, VoteOutcome.BOTH_BAD)

        # The sum should decrease
        assert (arena.chain_elos[chain_a] + arena.chain_elos[chain_b]) < (initial_a + initial_b)

    def test_generate_matchup(self, arena_setup):
        """Test that generate_matchup returns valid matchups."""
        arena, _, chains = arena_setup

        for _ in range(10):
            chain_a, chain_b = arena.generate_matchup()
            assert chain_a in chains
            assert chain_b in chains
            assert chain_a != chain_b

    def test_generate_matchup_favors_high_elo(self, arena_setup):
        """Test that matchup generation favors higher ELO chains."""
        arena, _, chains = arena_setup

        # Boost one chain's ELO
        arena.chain_elos[chains[0]] = 2000.0

        # Count appearances
        appearances = count_matchup_appearances(arena, 100)

        # High ELO chain should appear more often
        assert appearances[chains[0]] > appearances[chains[1]]

    def test_get_leaderboard(self, arena_setup):
        """Test leaderboard returns models sorted by ELO."""
        arena, models, _ = arena_setup

        # Set different ELOs
        set_model_elos(arena, {"upper": 1800.0, "lower": 1500.0, "exclaim": 1600.0})

        leaderboard = arena.get_leaderboard()

        # Should be sorted high to low
        assert leaderboard[0][1] == 1800.0
        assert leaderboard[1][1] == 1600.0
        assert leaderboard[2][1] == 1500.0

    def test_get_chain_leaderboard(self, arena_setup):
        """Test chain leaderboard returns chains sorted by ELO."""
        arena, _, chains = arena_setup

        # Set different ELOs
        arena.chain_elos[chains[0]] = 1700.0
        arena.chain_elos[chains[1]] = 1600.0
        arena.chain_elos[chains[2]] = 1800.0

        leaderboard = arena.get_chain_leaderboard()

        # Should be sorted high to low
        assert leaderboard[0] == (chains[2], 1800.0)
        assert leaderboard[1] == (chains[0], 1700.0)
        assert leaderboard[2] == (chains[1], 1600.0)

    def test_get_model_elo_by_name(self, arena_setup):
        """Test getting model ELO by model name string."""
        arena, models, _ = arena_setup
        # Get the actual unique name of the first model
        first_model = models[0]
        assert arena.get_model_elo(first_model.name) == 1500.0

    def test_get_model_elo_not_found(self, arena_setup):
        """Test that KeyError is raised for non-existent model."""
        arena, _, _ = arena_setup
        with pytest.raises(KeyError):
            arena.get_model_elo("nonexistent")

    def test_get_chain_elo(self, arena_setup):
        """Test getting chain ELO."""
        arena, _, chains = arena_setup
        assert arena.get_chain_elo(chains[0]) == 1500.0

    def test_get_matchup_stats(self, arena_setup):
        """Test that matchup statistics are tracked."""
        arena, _, _ = arena_setup

        # Generate some matchups
        for _ in range(10):
            arena.generate_matchup()

        stats = arena.get_matchup_stats()

        # Should have recorded matchups
        assert len(stats) > 0
        # Total should equal number generated
        assert sum(stats.values()) == 10

    def test_list_models(self, arena_setup):
        """Test that list_models returns all model chains."""
        arena, _, chains = arena_setup
        models_list = arena.list_models()
        assert models_list == chains

    def test_elo_conservation_in_matchup(self, arena_setup):
        """Test that total ELO is roughly conserved in standard matchups."""
        arena, _, chains = arena_setup
        initial_total = sum(arena.chain_elos.values())

        # Perform many matchups with various outcomes
        for i in range(20):
            chain_a, chain_b = chains[i % 2], chains[(i + 1) % 2]
            outcome = [VoteOutcome.A, VoteOutcome.B][i % 2]
            arena.record_vote(chain_a, chain_b, outcome)

        final_total = sum(arena.chain_elos.values())

        # Total should be roughly conserved (within rounding errors)
        assert abs(initial_total - final_total) < 1.0

    def test_both_bad_reduces_total_elo(self, arena_setup):
        """Test that both_bad outcomes reduce total ELO in the system."""
        arena, _, chains = arena_setup
        initial_total = sum(arena.chain_elos.values())

        # Multiple both_bad outcomes
        for _ in range(5):
            arena.record_vote(chains[0], chains[1], VoteOutcome.BOTH_BAD)

        final_total = sum(arena.chain_elos.values())

        # Total should decrease with both_bad
        assert final_total < initial_total
