"""
Pytest configuration and fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add the backend directory to Python path so imports work
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import after path setup
try:
    from app.domain_core.value_objects.deck_status import DeckStatus
    from app.domain_core.value_objects.template_type import TemplateType
except ImportError as e:
    # This will help debug import issues
    print(f"Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Backend dir: {backend_dir}")
    raise


@pytest.fixture
def sample_deck_data():
    """Sample deck data for testing."""
    return {
        "prompt": "Create a presentation about machine learning basics",
        "style_preferences": {"theme": "professional", "color_scheme": "blue"},
        "status": DeckStatus.PENDING,
    }


@pytest.fixture
def sample_slide_data():
    """Sample slide data for testing."""
    return {
        "title": "Introduction to Machine Learning",
        "content_outline": "Overview of ML concepts, types of learning, and basic algorithms",
        "presenter_notes": "Welcome the audience and provide agenda",
        "template_type": TemplateType.PROFESSIONAL,
        "order": 1,
    }


@pytest.fixture
def sample_deck_plan():
    """Sample LLM-generated deck plan for testing."""
    return {
        "title": "Machine Learning Fundamentals",
        "theme": "professional",
        "slides": [
            {
                "title": "Introduction",
                "content": "Overview of machine learning and its applications",
                "notes": "Welcome and set expectations",
            },
            {
                "title": "Types of Learning",
                "content": "Supervised, unsupervised, and reinforcement learning",
                "notes": "Explain each type with examples",
            },
            {
                "title": "Common Algorithms",
                "content": "Linear regression, decision trees, neural networks",
                "notes": "Focus on practical applications",
            },
        ],
    }


# Integration test fixtures would go here
# These would set up test database, Redis, etc.


@pytest.fixture(scope="session")
def test_database():
    """Set up test database for integration tests."""
    # This would create a test database
    # For now, just return None to avoid errors
    return None


@pytest.fixture
def test_redis():
    """Set up test Redis for integration tests."""
    # This would set up Redis connection for testing
    return None
