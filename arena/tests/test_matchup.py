"""
Tests for the matchup generation system.
"""

import pytest
from collections import Counter
from arena.matchup import MatchupGenerator, simple_random_matchup, top_k_matchup


class TestMatchupGenerator:
    """Test the ELO-weighted matchup generator."""

    @pytest.fixture
    def competitors(self):
        """Sample competitors for testing."""
        return ["Alice", "Bob", "Charlie", "David", "Eve"]

    @pytest.fixture
    def elo_ratings(self):
        """Sample ELO ratings with varied skill levels."""
        return {
            "Alice": 1800,  # High ELO
            "Bob": 1750,  # High ELO
            "Charlie": 1600,  # Medium ELO
            "David": 1450,  # Low ELO
            "Eve": 1400,  # Low ELO
        }

    @pytest.fixture
    def generator(self):
        """Create a matchup generator instance."""
        return MatchupGenerator[str](temperature=400.0, recency_penalty=0.3)

    def test_generate_matchup_returns_two_different_competitors(
        self, generator, competitors, elo_ratings
    ):
        """Test that matchups always return two different competitors."""
        for _ in range(20):
            a, b = generator.generate_matchup(competitors, elo_ratings)
            assert a != b
            assert a in competitors
            assert b in competitors

    def test_high_elo_competitors_appear_more_frequently(
        self, generator, competitors, elo_ratings
    ):
        """Test that higher ELO competitors appear in matchups more often."""
        appearances = Counter()
        for _ in range(100):
            a, b = generator.generate_matchup(competitors, elo_ratings)
            appearances[a] += 1
            appearances[b] += 1

        # Alice and Bob (high ELO) should appear more than David and Eve (low ELO)
        assert appearances["Alice"] > appearances["Eve"]
        assert appearances["Bob"] > appearances["David"]

    def test_all_competitors_get_matchups(self, generator, competitors, elo_ratings):
        """Test that exploration ensures all competitors get some matchups."""
        appearances = Counter()
        for _ in range(50):
            a, b = generator.generate_matchup(competitors, elo_ratings)
            appearances[a] += 1
            appearances[b] += 1

        # All competitors should appear at least once
        for competitor in competitors:
            assert appearances[competitor] > 0

    def test_recency_penalty_reduces_repeated_matchups(self, competitors, elo_ratings):
        """Test that recency penalty discourages immediate rematches."""
        # Generator with strong recency penalty
        generator = MatchupGenerator[str](temperature=400.0, recency_penalty=0.8)

        matchups = []
        for _ in range(20):
            matchup = generator.generate_matchup(competitors, elo_ratings)
            matchups.append(tuple(sorted(matchup)))

        # Count consecutive duplicates
        consecutive_duplicates = sum(
            1 for i in range(len(matchups) - 1) if matchups[i] == matchups[i + 1]
        )

        # Should have very few consecutive duplicates with strong penalty
        assert consecutive_duplicates <= 2

    def test_matchup_stats_tracking(self, generator, competitors, elo_ratings):
        """Test that matchup statistics are correctly tracked."""
        # Generate some matchups
        for _ in range(10):
            generator.generate_matchup(competitors, elo_ratings)

        stats = generator.get_matchup_stats()

        # Should have recorded matchups
        assert len(stats) > 0

        # Total matchups should equal number generated
        assert sum(stats.values()) == 10

    def test_reset_history(self, generator, competitors, elo_ratings):
        """Test that history reset clears all tracking."""
        # Generate some matchups
        for _ in range(5):
            generator.generate_matchup(competitors, elo_ratings)

        # Reset
        generator.reset_history()

        # Stats should be empty
        assert len(generator.get_matchup_stats()) == 0
        assert len(generator.matchup_history) == 0

    def test_insufficient_competitors_raises_error(self, generator, elo_ratings):
        """Test that error is raised with fewer than 2 competitors."""
        with pytest.raises(ValueError):
            generator.generate_matchup(["Alice"], {"Alice": 1500})

        with pytest.raises(ValueError):
            generator.generate_matchup([], {})


class TestSimpleRandomMatchup:
    """Test the simple random matchup function."""

    def test_returns_two_different_competitors(self):
        """Test that random matchup returns two different competitors."""
        competitors = ["A", "B", "C", "D"]
        for _ in range(20):
            a, b = simple_random_matchup(competitors)
            assert a != b
            assert a in competitors
            assert b in competitors

    def test_uniform_distribution(self):
        """Test that random matchups are roughly uniformly distributed."""
        competitors = ["A", "B", "C"]
        matchups = Counter()

        for _ in range(300):
            matchup = tuple(sorted(simple_random_matchup(competitors)))
            matchups[matchup] += 1

        # All possible matchups should occur
        assert len(matchups) == 3  # C(3,2) = 3

        # Should be roughly equal (within reason for randomness)
        counts = list(matchups.values())
        assert max(counts) - min(counts) < 50  # Tolerance for randomness

    def test_insufficient_competitors_raises_error(self):
        """Test error handling with insufficient competitors."""
        with pytest.raises(ValueError):
            simple_random_matchup(["A"])


class TestTopKMatchup:
    """Test the top-k matchup function."""

    def test_only_selects_from_top_k(self):
        """Test that only top-k competitors are selected."""
        competitors = ["A", "B", "C", "D", "E"]
        elo_ratings = {"A": 1800, "B": 1700, "C": 1600, "D": 1500, "E": 1400}

        # Test with k=3
        top_3 = {"A", "B", "C"}
        for _ in range(20):
            a, b = top_k_matchup(competitors, elo_ratings, k=3)
            assert a in top_3
            assert b in top_3

    def test_k_larger_than_competitors(self):
        """Test that k larger than competitor count works correctly."""
        competitors = ["A", "B"]
        elo_ratings = {"A": 1600, "B": 1500}

        # k=10 but only 2 competitors
        a, b = top_k_matchup(competitors, elo_ratings, k=10)
        assert a != b
        assert {a, b} == {"A", "B"}

    def test_insufficient_competitors_raises_error(self):
        """Test error handling with insufficient competitors."""
        with pytest.raises(ValueError):
            top_k_matchup(["A"], {"A": 1500}, k=3)
