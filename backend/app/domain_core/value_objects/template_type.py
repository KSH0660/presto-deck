"""
Template type value object.
"""

from enum import Enum


class TemplateType(Enum):
    MINIMAL = "minimal"
    PROFESSIONAL = "professional"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    CORPORATE = "corporate"
    STARTUP = "startup"
