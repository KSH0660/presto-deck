import os
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from presto.app.core.config import settings

class TemplateService:
    def __init__(self):
        self.template_env = Environment(loader=FileSystemLoader(settings.TEMPLATE_DIR))
        self.prompt_env = Environment(loader=FileSystemLoader(settings.PROMPT_DIR))

    def get_available_layouts(self, theme: str) -> list[str]:
        """Scans the file system to get available layout names for a given theme."""
        try:
            theme_dir = os.path.join(settings.TEMPLATE_DIR, theme)
            if not os.path.isdir(theme_dir):
                return []
            return [f.replace(".html", "") for f in os.listdir(theme_dir) if f.endswith(".html")]
        except Exception:
            return []

    def get_prompt_template(self, template_name: str):
        """Loads a prompt template by name."""
        return self.prompt_env.get_template(template_name)

    def render_slide_html(self, theme: str, layout: str, data: dict) -> str:
        """Renders the HTML for a slide using the specified theme and layout."""
        template_name = f"{theme}/{layout}.html"
        try:
            template = self.template_env.get_template(template_name)
            return template.render(**data)
        except TemplateNotFound:
            return f"<div><h2>Error</h2><p>Layout '{layout}' not found.</p></div>"
