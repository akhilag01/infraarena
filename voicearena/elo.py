def calculate_elo(winner_rating: float, loser_rating: float, k_factor: int = 32) -> tuple[float, float]:
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
    
    new_winner_rating = winner_rating + k_factor * (1 - expected_winner)
    new_loser_rating = loser_rating + k_factor * (0 - expected_loser)
    
    return new_winner_rating, new_loser_rating

def calculate_elo_tie(rating_a: float, rating_b: float, k_factor: int = 32) -> tuple[float, float]:
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    
    new_rating_a = rating_a + k_factor * (0.5 - expected_a)
    new_rating_b = rating_b + k_factor * (0.5 - expected_b)
    
    return new_rating_a, new_rating_b

def calculate_elo_both_bad(rating_a: float, rating_b: float, k_factor: int = 32) -> tuple[float, float]:
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    
    new_rating_a = rating_a + k_factor * (0 - expected_a)
    new_rating_b = rating_b + k_factor * (0 - expected_b)
    
    return new_rating_a, new_rating_b
