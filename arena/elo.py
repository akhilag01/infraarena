from arena.arena_base import VoteOutcome


# ELO calculation functions
def calculate_elo(winner_rating: float, loser_rating: float, k_factor: int = 32):
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
    new_winner_rating = winner_rating + k_factor * (1 - expected_winner)
    new_loser_rating = loser_rating + k_factor * (0 - expected_loser)
    return new_winner_rating, new_loser_rating


def calculate_elo_tie(rating_a: float, rating_b: float, k_factor: int = 32):
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    new_rating_a = rating_a + k_factor * (0.5 - expected_a)
    new_rating_b = rating_b + k_factor * (0.5 - expected_b)
    return new_rating_a, new_rating_b


def calculate_elo_both_bad(rating_a: float, rating_b: float, k_factor: int = 32):
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    new_rating_a = rating_a + k_factor * (0 - expected_a)
    new_rating_b = rating_b + k_factor * (0 - expected_b)
    return new_rating_a, new_rating_b


def calculate_elo_from_vote(
    vote_outcome: VoteOutcome, rating_a: float, rating_b: float, k_factor: int = 32
) -> tuple[float, float]:
    """
    Calculate new ELO ratings based on the vote outcome.

    Args:
        vote_outcome: The outcome of the vote (A wins, B wins, tie, or both bad)
        rating_a: Current ELO rating for model A
        rating_b: Current ELO rating for model B
        k_factor: ELO k-factor (default 32)

    Returns:
        Tuple of (new_rating_a, new_rating_b)
    """
    if vote_outcome == VoteOutcome.A:
        return calculate_elo(
            winner_rating=rating_a,
            loser_rating=rating_b,
            k_factor=k_factor,
        )
    elif vote_outcome == VoteOutcome.B:
        new_rating_b, new_rating_a = calculate_elo(
            winner_rating=rating_b,
            loser_rating=rating_a,
            k_factor=k_factor,
        )
        return new_rating_a, new_rating_b
    elif vote_outcome == VoteOutcome.TIE:
        return calculate_elo_tie(rating_a, rating_b, k_factor)
    elif vote_outcome == VoteOutcome.BOTH_BAD:
        return calculate_elo_both_bad(rating_a, rating_b, k_factor)
    else:
        raise ValueError(f"Invalid vote outcome: {vote_outcome}")
