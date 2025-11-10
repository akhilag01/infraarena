import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'voicearena'))

from main import app

handler = app
