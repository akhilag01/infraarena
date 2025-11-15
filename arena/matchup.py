"""
Matchup generation strategies for arena competitions.

This module provides algorithms for generating matchups between competitors
that balance exploration (trying all combinations) with exploitation (matching
top performers more frequently).
"""

import random
from typing import TypeVar, Generic
from collections import defaultdict

T = TypeVar("T")


class MatchupGenerator(Generic[T]):
    """
    Generates matchups between competitors with ELO-weighted sampling.

    Strategy:
    - Uses softmax probability distribution based on combined ELO ratings
    - Tracks matchup history to encourage diverse pairings
    - Applies recency penalty to prevent repeated matchups
    - Balances exploration (all matchups) with exploitation (high-ELO matchups)
    """

    def __init__(
        self,
        temperature: float = 400.0,
        recency_penalty: float = 0.3,
        history_size: int = 50,
    ):
        """
        Initialize the matchup generator.

        Args:
            temperature: Controls randomness (higher = more random, lower = more deterministic)
                        Default 400 matches ELO rating scale
            recency_penalty: Penalty factor for recent matchups (0-1, higher = stronger penalty)
            history_size: Number of recent matchups to track for recency penalty
        """
        self.temperature = temperature
        self.recency_penalty = recency_penalty
        self.matchup_history: list[tuple[T, T]] = []
        self.matchup_counts: dict[tuple[T, T], int] = defaultdict(int)
        self.history_size = history_size

    def generate_matchup(
        self, competitors: list[T], elo_ratings: dict[T, float]
    ) -> tuple[T, T]:
        """
        Generate a matchup between two competitors using ELO-weighted sampling.

        Args:
            competitors: List of all available competitors
            elo_ratings: Dictionary mapping competitors to their ELO ratings

        Returns:
            Tuple of (competitor_a, competitor_b)

        Raises:
            ValueError: If fewer than 2 competitors available
        """
        if len(competitors) < 2:
            raise ValueError("Need at least 2 competitors to generate a matchup")

        # Sample first competitor using ELO-weighted probabilities
        first = self._sample_competitor(competitors, elo_ratings)

        # Sample second competitor (excluding first) with combined ELO weighting
        remaining = [c for c in competitors if c != first]
        second = self._sample_competitor_with_recency(
            remaining, elo_ratings, first
        )

        matchup = self._normalize_matchup(first, second)
        self._record_matchup(matchup)

        return first, second

    def _sample_competitor(
        self, competitors: list[T], elo_ratings: dict[T, float]
    ) -> T:
        """Sample a single competitor using softmax probabilities based on ELO."""
        # Calculate softmax probabilities
        scores = [elo_ratings[c] / self.temperature for c in competitors]
        max_score = max(scores)
        exp_scores = [2 ** (s - max_score) for s in scores]  # Numerical stability
        total = sum(exp_scores)
        probabilities = [exp / total for exp in exp_scores]

        # Weighted random selection
        return random.choices(competitors, weights=probabilities, k=1)[0]

    def _sample_competitor_with_recency(
        self, competitors: list[T], elo_ratings: dict[T, float], first: T
    ) -> T:
        """
        Sample second competitor with recency penalty for recent matchups.

        This encourages exploration by reducing probability of recently seen matchups.
        """
        # Calculate base probabilities from ELO
        scores = [elo_ratings[c] / self.temperature for c in competitors]
        max_score = max(scores)
        exp_scores = [2 ** (s - max_score) for s in scores]
        total = sum(exp_scores)
        base_probs = [exp / total for exp in exp_scores]

        # Apply recency penalty
        adjusted_probs = []
        for i, competitor in enumerate(competitors):
            matchup = self._normalize_matchup(first, competitor)
            recency_factor = self._get_recency_factor(matchup)
            adjusted_probs.append(base_probs[i] * recency_factor)

        # Renormalize
        total_adjusted = sum(adjusted_probs)
        final_probs = [p / total_adjusted for p in adjusted_probs]

        return random.choices(competitors, weights=final_probs, k=1)[0]

    def _get_recency_factor(self, matchup: tuple[T, T]) -> float:
        """
        Calculate penalty factor based on how recently a matchup occurred.

        Recent matchups get penalized more heavily, older matchups less so.
        """
        # Count recent occurrences
        recent_count = sum(
            1 for m in self.matchup_history[-self.history_size :] if m == matchup
        )

        # Apply exponential penalty
        penalty = (1 - self.recency_penalty) ** recent_count
        return penalty

    def _normalize_matchup(self, a: T, b: T) -> tuple[T, T]:
        """Normalize matchup order for consistent tracking (order-independent)."""
        return (a, b) if hash(a) <= hash(b) else (b, a)

    def _record_matchup(self, matchup: tuple[T, T]) -> None:
        """Record matchup in history and counts."""
        self.matchup_history.append(matchup)
        self.matchup_counts[matchup] += 1

        # Trim history if too large
        if len(self.matchup_history) > self.history_size * 2:
            self.matchup_history = self.matchup_history[-self.history_size :]

    def get_matchup_stats(self) -> dict[tuple[T, T], int]:
        """Get statistics on how many times each matchup has occurred."""
        return dict(self.matchup_counts)

    def reset_history(self) -> None:
        """Reset matchup history and counts."""
        self.matchup_history.clear()
        self.matchup_counts.clear()


def simple_random_matchup(competitors: list[T]) -> tuple[T, T]:
    """
    Generate a completely random matchup (no ELO weighting).

    Useful for baseline comparison or when equal exploration is desired.

    Args:
        competitors: List of all available competitors

    Returns:
        Tuple of (competitor_a, competitor_b)
    """
    if len(competitors) < 2:
        raise ValueError("Need at least 2 competitors to generate a matchup")

    return tuple(random.sample(competitors, 2))


def top_k_matchup(
    competitors: list[T], elo_ratings: dict[T, float], k: int = 5
) -> tuple[T, T]:
    """
    Generate matchup by randomly selecting from top-k competitors.

    This is a simpler alternative that focuses on high-ELO matchups.

    Args:
        competitors: List of all available competitors
        elo_ratings: Dictionary mapping competitors to their ELO ratings
        k: Number of top competitors to sample from

    Returns:
        Tuple of (competitor_a, competitor_b)
    """
    if len(competitors) < 2:
        raise ValueError("Need at least 2 competitors to generate a matchup")

    # Sort by ELO and take top-k
    sorted_competitors = sorted(
        competitors, key=lambda c: elo_ratings[c], reverse=True
    )
    top_competitors = sorted_competitors[: min(k, len(competitors))]

    return tuple(random.sample(top_competitors, 2))
