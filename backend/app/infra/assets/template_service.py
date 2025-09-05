"""
Template Service implementation for managing slide templates.

This service provides template operations including loading, validation,
and rendering of slide templates.
"""

from typing import List, Dict, Any, Optional
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from app.application.ports import TemplateServicePort
from app.infra.config.logging_config import get_logger


class TemplateService(TemplateServicePort):
    """
    Infrastructure implementation of template service using Jinja2.

    This service manages slide templates stored as HTML files with Jinja2 syntax,
    and provides rendering capabilities for slide content.
    """

    def __init__(self, template_directory: str):
        """
        Initialize template service.

        Args:
            template_directory: Path to directory containing template files
        """
        self.template_directory = Path(template_directory)
        self._log = get_logger("infra.template_service")

        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_directory)),
            autoescape=True,  # For security when rendering HTML
        )

        # Cache for template metadata
        self._template_metadata_cache: Optional[Dict[str, Any]] = None

    async def get_available_templates(
        self, template_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available slide templates, optionally filtered by type.

        Args:
            template_type: Optional template type filter

        Returns:
            List[Dict[str, Any]]: Available templates with metadata
        """
        try:
            # Load template metadata if not cached
            if self._template_metadata_cache is None:
                await self._load_template_metadata()

            templates = self._template_metadata_cache.get("templates", [])

            # Filter by template type if specified
            if template_type:
                templates = [
                    template
                    for template in templates
                    if template.get("template_type", "").lower()
                    == template_type.lower()
                ]

            self._log.debug(
                f"Found {len(templates)} templates for type: {template_type}"
            )
            return templates

        except Exception as e:
            self._log.exception(f"Error loading templates: {str(e)}")
            return []

    async def render_slide(
        self, template_filename: str, content_data: Dict[str, Any]
    ) -> str:
        """
        Render slide content using a template.

        Args:
            template_filename: Name of the template file to use
            content_data: Data to render into the template

        Returns:
            str: Rendered HTML content

        Raises:
            ValueError: If template not found or rendering fails
        """
        try:
            # Load template
            template = self.jinja_env.get_template(template_filename)

            # Add default variables for all templates
            render_context = {
                **content_data,
                "template_filename": template_filename,
                "has_content": bool(content_data.get("html_content")),
                "slide_number": content_data.get("order", 1),
            }

            # Render template with content data
            rendered_content = template.render(**render_context)

            self._log.debug(f"Successfully rendered template: {template_filename}")
            return rendered_content

        except Exception as e:
            self._log.error(f"Error rendering template {template_filename}: {str(e)}")
            raise ValueError(f"Failed to render template {template_filename}: {str(e)}")

    async def _load_template_metadata(self) -> None:
        """Load template metadata from templates.json or scan directory."""
        metadata_file = self.template_directory / "templates.json"

        if metadata_file.exists():
            # Load from metadata file
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    self._template_metadata_cache = json.load(f)
                self._log.info("Loaded template metadata from templates.json")
                return
            except Exception as e:
                self._log.warning(
                    f"Error loading templates.json: {str(e)}, falling back to directory scan"
                )

        # Fallback: scan directory for HTML files
        await self._scan_template_directory()

    async def _scan_template_directory(self) -> None:
        """Scan template directory and generate metadata."""
        try:
            templates = []

            if not self.template_directory.exists():
                self._log.warning(
                    f"Template directory not found: {self.template_directory}"
                )
                self._template_metadata_cache = {"templates": []}
                return

            # Scan for HTML files
            for template_file in self.template_directory.glob("*.html"):
                template_info = await self._analyze_template_file(template_file)
                if template_info:
                    templates.append(template_info)

            self._template_metadata_cache = {"templates": templates}
            self._log.info(
                f"Scanned template directory and found {len(templates)} templates"
            )

        except Exception as e:
            self._log.exception(f"Error scanning template directory: {str(e)}")
            self._template_metadata_cache = {"templates": []}

    async def _analyze_template_file(
        self, template_file: Path
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a template file and extract metadata.

        Args:
            template_file: Path to the template file

        Returns:
            Optional[Dict[str, Any]]: Template metadata or None if invalid
        """
        try:
            # Extract template type and display name from filename
            filename = template_file.name
            name_parts = filename.replace(".html", "").split("_")

            # Determine template type from filename convention
            template_type = "professional"  # Default
            display_name = filename.replace(".html", "").replace("_", " ").title()

            if len(name_parts) >= 2:
                template_type = name_parts[0].lower()
                display_name = " ".join(name_parts[1:]).title()

            # Basic template info
            template_info = {
                "filename": filename,
                "display_name": display_name,
                "template_type": template_type,
                "file_size": template_file.stat().st_size,
                "last_modified": template_file.stat().st_mtime,
            }

            # Try to extract additional metadata from template comments
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    content = f.read(1000)  # Read first 1000 chars for metadata

                    # Look for metadata comments
                    if "<!-- TEMPLATE_TYPE:" in content:
                        type_start = content.find("<!-- TEMPLATE_TYPE:") + len(
                            "<!-- TEMPLATE_TYPE:"
                        )
                        type_end = content.find("-->", type_start)
                        if type_end > type_start:
                            template_info["template_type"] = (
                                content[type_start:type_end].strip().lower()
                            )

                    if "<!-- DISPLAY_NAME:" in content:
                        name_start = content.find("<!-- DISPLAY_NAME:") + len(
                            "<!-- DISPLAY_NAME:"
                        )
                        name_end = content.find("-->", name_start)
                        if name_end > name_start:
                            template_info["display_name"] = content[
                                name_start:name_end
                            ].strip()

            except Exception:
                # Ignore errors in metadata extraction
                pass

            return template_info

        except Exception as e:
            self._log.warning(
                f"Error analyzing template file {template_file}: {str(e)}"
            )
            return None

    def get_template_path(self, template_filename: str) -> Path:
        """
        Get the full path to a template file.

        Args:
            template_filename: Name of the template file

        Returns:
            Path: Full path to the template file
        """
        return self.template_directory / template_filename

    async def template_exists(self, template_filename: str) -> bool:
        """
        Check if a template file exists.

        Args:
            template_filename: Name of the template file to check

        Returns:
            bool: True if template exists
        """
        return self.get_template_path(template_filename).exists()

    async def validate_template(self, template_filename: str) -> bool:
        """
        Validate that a template can be loaded and rendered.

        Args:
            template_filename: Name of the template file to validate

        Returns:
            bool: True if template is valid
        """
        try:
            # Try to load the template
            template = self.jinja_env.get_template(template_filename)

            # Try a basic render with minimal data
            test_data = {"title": "Test Title", "content": "Test Content", "order": 1}
            template.render(**test_data)

            return True

        except Exception as e:
            self._log.warning(
                f"Template validation failed for {template_filename}: {str(e)}"
            )
            return False
