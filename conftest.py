"""
Pytest configuration to ensure arena can be imported during tests.
"""
import sys
from pathlib import Path

# Add repo root to Python path so 'arena' can be imported
repo_root = Path(__file__).parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
