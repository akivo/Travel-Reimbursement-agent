"""
conftest.py -- Pytest configuration

Adds the project root to sys.path so src.* imports work
when running pytest tests/ from the tr-agent/ directory.
"""
import sys
from pathlib import Path

# Ensure the project root (tr-agent/) is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))
