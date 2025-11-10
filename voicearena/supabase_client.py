import os
from supabase import create_client, Client
from typing import Optional

_supabase_client = None

def get_supabase() -> Client:
    """Lazy initialization of Supabase client"""
    global _supabase_client
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be set in environment variables")
        
        _supabase_client = create_client(supabase_url, supabase_key)
    return _supabase_client

def get_user_from_token(token: str) -> Optional[dict]:
    """Get user data from JWT token"""
    try:
        supabase = get_supabase()
        user = supabase.auth.get_user(token)
        return user.user if user else None
    except Exception as e:
        print(f"Error getting user from token: {e}")
        return None
