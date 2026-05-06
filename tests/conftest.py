"""
pytest configuration for the opencode-nvidia test suite.
Adds the backend package to sys.path so that `import main` resolves correctly.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
