"""
Template catalog service for managing HTML template assets.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TemplateInfo:
    """Information about a template file."""

    filename: str
    description: str
    file_path: Path


class TemplateCatalog:
    """Service for managing and querying template assets."""

    def __init__(self, asset_dir_path: str):
        self.asset_dir = Path(asset_dir_path)
        self.catalog_path = self.asset_dir / "catalog.json"
        self._templates: Dict[str, TemplateInfo] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Load template catalog from catalog.json."""
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.catalog_path}")

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)

        for filename, description in catalog_data.items():
            template_path = self.asset_dir / filename
            if template_path.exists():
                self._templates[filename] = TemplateInfo(
                    filename=filename, description=description, file_path=template_path
                )

    def get_all_templates(self) -> List[TemplateInfo]:
        """Get all available templates."""
        return list(self._templates.values())

    def get_template_info(self, filename: str) -> Optional[TemplateInfo]:
        """Get information about a specific template."""
        return self._templates.get(filename)

    def get_template_content(self, filename: str) -> Optional[str]:
        """Get the HTML content of a template."""
        template_info = self.get_template_info(filename)
        if not template_info:
            return None

        try:
            with open(template_info.file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def get_templates_by_keywords(self, keywords: List[str]) -> List[TemplateInfo]:
        """Find templates that match any of the given keywords."""
        matching_templates = []
        keywords_lower = [kw.lower() for kw in keywords]

        for template in self._templates.values():
            description_lower = template.description.lower()
            if any(keyword in description_lower for keyword in keywords_lower):
                matching_templates.append(template)

        return matching_templates

    def get_catalog_for_llm(self) -> Dict[str, str]:
        """Get catalog data formatted for LLM consumption."""
        return {
            filename: template.description
            for filename, template in self._templates.items()
        }

    def get_template_filenames(self) -> List[str]:
        """Get list of all template filenames."""
        return list(self._templates.keys())
