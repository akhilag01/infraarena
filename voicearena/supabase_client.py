import os
from supabase import create_client, Client
from typing import Optional

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL and Key must be set in environment variables")

supabase: Client = create_client(supabase_url, supabase_key)

def get_user_from_token(token: str) -> Optional[dict]:
    """Get user data from JWT token"""
    try:
        user = supabase.auth.get_user(token)
        return user.user if user else None
    except Exception as e:
        print(f"Error getting user from token: {e}")
        return None
