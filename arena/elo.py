from arena.types import VoteOutcome


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


# Team Elo calculation functions
def calculate_team_elo(
    winner_ratings: list[float], loser_ratings: list[float], k_factor: int = 32
) -> tuple[list[float], list[float]]:
    """
    Calculate new ELO ratings for teams where one team wins.

    Args:
        winner_ratings: List of ELO ratings for members of the winning team
        loser_ratings: List of ELO ratings for members of the losing team
        k_factor: ELO k-factor (default 32)

    Returns:
        Tuple of (new_winner_ratings, new_loser_ratings)
    """
    # Calculate average team ratings
    avg_winner_rating = sum(winner_ratings) / len(winner_ratings)
    avg_loser_rating = sum(loser_ratings) / len(loser_ratings)

    # Calculate expected scores
    expected_winner = 1 / (1 + 10 ** ((avg_loser_rating - avg_winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((avg_winner_rating - avg_loser_rating) / 400))

    # Calculate rating changes
    winner_change = k_factor * (1 - expected_winner)
    loser_change = k_factor * (0 - expected_loser)

    # Apply changes to all team members
    new_winner_ratings = [rating + winner_change for rating in winner_ratings]
    new_loser_ratings = [rating + loser_change for rating in loser_ratings]

    return new_winner_ratings, new_loser_ratings


def calculate_team_elo_tie(
    team_a_ratings: list[float], team_b_ratings: list[float], k_factor: int = 32
) -> tuple[list[float], list[float]]:
    """
    Calculate new ELO ratings for teams when the match is a tie.

    Args:
        team_a_ratings: List of ELO ratings for members of team A
        team_b_ratings: List of ELO ratings for members of team B
        k_factor: ELO k-factor (default 32)

    Returns:
        Tuple of (new_team_a_ratings, new_team_b_ratings)
    """
    # Calculate average team ratings
    avg_rating_a = sum(team_a_ratings) / len(team_a_ratings)
    avg_rating_b = sum(team_b_ratings) / len(team_b_ratings)

    # Calculate expected scores
    expected_a = 1 / (1 + 10 ** ((avg_rating_b - avg_rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((avg_rating_a - avg_rating_b) / 400))

    # Calculate rating changes (0.5 for tie)
    change_a = k_factor * (0.5 - expected_a)
    change_b = k_factor * (0.5 - expected_b)

    # Apply changes to all team members
    new_ratings_a = [rating + change_a for rating in team_a_ratings]
    new_ratings_b = [rating + change_b for rating in team_b_ratings]

    return new_ratings_a, new_ratings_b


def calculate_team_elo_both_bad(
    team_a_ratings: list[float], team_b_ratings: list[float], k_factor: int = 32
) -> tuple[list[float], list[float]]:
    """
    Calculate new ELO ratings for teams when both teams performed badly.

    Args:
        team_a_ratings: List of ELO ratings for members of team A
        team_b_ratings: List of ELO ratings for members of team B
        k_factor: ELO k-factor (default 32)

    Returns:
        Tuple of (new_team_a_ratings, new_team_b_ratings)
    """
    # Calculate average team ratings
    avg_rating_a = sum(team_a_ratings) / len(team_a_ratings)
    avg_rating_b = sum(team_b_ratings) / len(team_b_ratings)

    # Calculate expected scores
    expected_a = 1 / (1 + 10 ** ((avg_rating_b - avg_rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((avg_rating_a - avg_rating_b) / 400))

    # Calculate rating changes (0 for both bad - both "lose")
    change_a = k_factor * (0 - expected_a)
    change_b = k_factor * (0 - expected_b)

    # Apply changes to all team members
    new_ratings_a = [rating + change_a for rating in team_a_ratings]
    new_ratings_b = [rating + change_b for rating in team_b_ratings]

    return new_ratings_a, new_ratings_b


def calculate_team_elo_from_vote(
    vote_outcome: VoteOutcome,
    team_a_ratings: list[float],
    team_b_ratings: list[float],
    k_factor: int = 32,
) -> tuple[list[float], list[float]]:
    """
    Calculate new ELO ratings for teams based on the vote outcome.

    Args:
        vote_outcome: The outcome of the vote (A wins, B wins, tie, or both bad)
        team_a_ratings: List of ELO ratings for members of team A
        team_b_ratings: List of ELO ratings for members of team B
        k_factor: ELO k-factor (default 32)

    Returns:
        Tuple of (new_team_a_ratings, new_team_b_ratings)
    """
    if vote_outcome == VoteOutcome.A:
        return calculate_team_elo(
            winner_ratings=team_a_ratings,
            loser_ratings=team_b_ratings,
            k_factor=k_factor,
        )
    elif vote_outcome == VoteOutcome.B:
        new_ratings_b, new_ratings_a = calculate_team_elo(
            winner_ratings=team_b_ratings,
            loser_ratings=team_a_ratings,
            k_factor=k_factor,
        )
        return new_ratings_a, new_ratings_b
    elif vote_outcome == VoteOutcome.TIE:
        return calculate_team_elo_tie(team_a_ratings, team_b_ratings, k_factor)
    elif vote_outcome == VoteOutcome.BOTH_BAD:
        return calculate_team_elo_both_bad(team_a_ratings, team_b_ratings, k_factor)
    else:
        raise ValueError(f"Invalid vote outcome: {vote_outcome}")
