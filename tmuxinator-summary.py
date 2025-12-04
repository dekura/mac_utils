#!/opt/homebrew/Caskroom/miniconda/base/bin/python
"""
Tmuxinator Project Summary - AI-Powered Analysis
Full-screen TUI application using Textual framework with OpenAI integration
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
import yaml

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, Header, Footer, LoadingIndicator
from textual.binding import Binding
from textual import work
from rich.text import Text
from rich.markdown import Markdown

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed", file=sys.stderr)
    print("Install with: /opt/homebrew/Caskroom/miniconda/base/bin/pip install openai", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Data Models
# ============================================================================

class ProjectWithProgress:
    """Represents a tmuxinator project with progress tracking"""

    def __init__(self, name: str, ddl: Optional[date], priority: str,
                 description: str, root: Optional[str], file_path: str):
        self.name = name
        self.ddl = ddl
        self.priority = priority.lower() if priority else "normal"
        self.description = description or ""
        self.root = root
        self.file_path = file_path
        self.progress_content = None

    def load_progress(self):
        """Load prgs.md content from project root"""
        if self.root and Path(self.root).exists():
            prgs_file = Path(self.root) / "prgs.md"
            if prgs_file.exists():
                try:
                    self.progress_content = prgs_file.read_text()
                except Exception as e:
                    self.progress_content = f"[Error reading prgs.md: {e}]"

    @property
    def days_left(self) -> Optional[int]:
        """Calculate days until deadline"""
        if not self.ddl:
            return None
        return (self.ddl - date.today()).days

    @property
    def is_overdue(self) -> bool:
        """Check if project is overdue"""
        return self.days_left is not None and self.days_left < 0

    @property
    def display_deadline(self) -> str:
        """Format deadline for display"""
        if not self.ddl:
            return "No deadline"
        days = self.days_left
        if days < 0:
            return f"OVERDUE by {abs(days)}d"
        elif days == 0:
            return "DUE TODAY"
        elif days <= 3:
            return f"URGENT ({days}d left)"
        elif days <= 7:
            return f"SOON ({days}d left)"
        else:
            return f"{days}d left"

    @property
    def deadline_color(self) -> str:
        """Get color for deadline display"""
        if not self.ddl:
            return "dim"
        days = self.days_left
        if days < 0 or days <= 3:
            return "red"
        elif days <= 7:
            return "yellow"
        else:
            return "green"

    @property
    def priority_display(self) -> str:
        """Get priority display text"""
        if self.priority in ["high", "urgent"]:
            return "[red bold][HIGH][/red bold]"
        elif self.priority == "low":
            return "[dim][LOW][/dim]"
        return ""


def load_projects(config_dir: Path) -> List[ProjectWithProgress]:
    """Load all tmuxinator projects from config directory"""
    projects = []

    if not config_dir.exists():
        return projects

    for yaml_file in config_dir.glob("*.yml"):
        # Skip template
        if yaml_file.name == "template.yml":
            continue

        try:
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                continue

            name = config.get('name', yaml_file.stem)
            ddl_str = config.get('ddl')
            priority = config.get('priority', 'normal')
            description = config.get('description', '')
            root = config.get('root')

            # Expand tilde in root path
            if root:
                root = os.path.expanduser(root)

            # Parse deadline
            ddl = None
            if ddl_str:
                try:
                    ddl = datetime.strptime(str(ddl_str), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass

            project = ProjectWithProgress(name, ddl, priority, description, root, str(yaml_file))
            project.load_progress()
            projects.append(project)

        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file}: {e}", file=sys.stderr)

    # Sort: projects with ddl first (by date), then without ddl (by name)
    projects_with_ddl = [p for p in projects if p.ddl]
    projects_with_ddl.sort(key=lambda p: (p.ddl, p.name))

    projects_without_ddl = [p for p in projects if not p.ddl]
    projects_without_ddl.sort(key=lambda p: p.name)

    return projects_with_ddl + projects_without_ddl


# ============================================================================
# AI Analysis Engine
# ============================================================================

class AIAnalyzer:
    """Handles OpenAI API calls for project analysis"""

    def __init__(self):
        self.base_url = "https://api.chatanywhere.org/v1"
        self.api_key = os.environ.get("chat_any_where_key")
        self.model = "gpt-5.1"

    def analyze_projects(self, projects: List[ProjectWithProgress]) -> dict:
        """Call OpenAI API to analyze projects and return recommendations"""
        if not self.api_key:
            return {
                "error": "API key not found. Set $chat_any_where_key environment variable.",
                "content": ""
            }

        if not projects:
            return {
                "error": "No projects to analyze",
                "content": ""
            }

        prompt = self._build_prompt(projects)

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a productivity advisor analyzing project portfolios. Provide concise, actionable advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            return {
                "error": None,
                "content": content
            }

        except Exception as e:
            return {
                "error": f"API call failed: {str(e)}",
                "content": ""
            }

    def _build_prompt(self, projects: List[ProjectWithProgress]) -> str:
        """Build the analysis prompt"""
        today = date.today()

        # Format project data
        project_summaries = []
        for p in projects:
            days_left = (p.ddl - today).days if p.ddl else None
            deadline_str = f"{days_left} days" if days_left is not None else "No deadline"

            progress = p.progress_content or "[No progress file]"
            # Truncate very long progress files
            if len(progress) > 500:
                progress = progress[:500] + "\n... [truncated]"

            project_summaries.append(f"""
Project: {p.name}
Deadline: {deadline_str}
Priority: {p.priority}
Description: {p.description}
Recent Progress:
{progress}
---
""")

        prompt = f"""You are a productivity advisor analyzing my project portfolio.

Today is {today.strftime('%Y-%m-%d')}.

Here are my active projects:

{''.join(project_summaries)}

Please analyze and provide:

1. **PRIORITY ORDER** (top 3-5 projects I should focus on):
   - Rank projects by what I should work on first
   - For each, explain WHY (consider: deadline urgency, current progress, priority level, momentum)

2. **STRATEGIC INSIGHTS**:
   - Which projects are at risk of missing deadlines?
   - Which projects seem stalled despite importance?
   - Any workload balance issues (too scattered vs too focused)?
   - Recommendations for time allocation this week

Format your response as markdown with ## headers.
"""
        return prompt


# ============================================================================
# Textual Widgets
# ============================================================================

class AIRecommendationPanel(Static):
    """Panel displaying AI analysis results"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "🤖 AI RECOMMENDATIONS"

    def show_empty(self):
        """Show initial empty state"""
        self.update("[dim italic]Press 'a' to analyze projects with AI[/dim italic]")

    def show_analyzing(self):
        """Show analyzing state"""
        self.update("🔄 [yellow]Analyzing projects...[/yellow]\n\nThis may take a few seconds.")

    def show_results(self, content: str):
        """Show AI analysis results"""
        self.update(Markdown(content))

    def show_error(self, error: str):
        """Show error message"""
        self.update(f"[red bold]Error:[/red bold] {error}\n\n[dim]Press 'a' to retry[/dim]")


class ProjectListPanel(Static):
    """Panel displaying project details"""

    def __init__(self, projects: List[ProjectWithProgress], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.projects = projects
        self.border_title = f"📋 PROJECT DETAILS ({len(projects)} projects)"

    def compose(self) -> ComposeResult:
        """Create the widget content"""
        if not self.projects:
            yield Static("[dim italic]No projects found[/dim italic]")
            return

        content_parts = []

        for i, project in enumerate(self.projects):
            if i > 0:
                content_parts.append("\n")

            content_parts.append("─" * 80 + "\n")

            # Project name with priority
            name_line = f"[bold]{project.name}[/bold]"
            if project.priority_display:
                name_line += f" {project.priority_display}"
            content_parts.append(name_line + "\n")

            # Deadline
            ddl_text = project.display_deadline
            content_parts.append(f"DDL: [{project.deadline_color}]{ddl_text}[/{project.deadline_color}]\n")

            # Description
            if project.description:
                content_parts.append(f"Description: {project.description}\n")

            # Root path
            if project.root:
                content_parts.append(f"Path: [dim]{project.root}[/dim]\n")

            content_parts.append("\n")

            # Progress
            if project.progress_content:
                content_parts.append("[bold]Progress:[/bold]\n")
                # Indent progress content
                for line in project.progress_content.split('\n'):
                    content_parts.append(f"  {line}\n")
            else:
                content_parts.append("[dim][No prgs.md found][/dim]\n")

        yield Static("".join(content_parts))

    def refresh_projects(self, projects: List[ProjectWithProgress]):
        """Update with new project list"""
        self.projects = projects
        self.border_title = f"📋 PROJECT DETAILS ({len(projects)} projects)"
        # Remove all children and recreate
        self.remove_children()
        self.mount(*self.compose())


# ============================================================================
# Main Application
# ============================================================================

class SummaryApp(App):
    """Tmuxinator Project Summary - AI-Powered Analysis"""

    CSS = """
    Screen {
        background: $surface;
    }

    #ai-panel {
        height: 40%;
        border: heavy green;
        padding: 1;
        overflow-y: auto;
        background: $success 5%;
    }

    #project-panel {
        height: 60%;
        border: round $primary;
        padding: 1;
        overflow-y: auto;
    }

    Footer {
        background: $primary-background;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("a", "analyze", "Analyze with AI", show=True),
        Binding("?", "help", "Help", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Tmuxinator Summary - AI-Powered Analysis"
        self.sub_title = f"{date.today().strftime('%Y-%m-%d')}"

        # Find config directory
        self.config_dir = Path.home() / ".config" / "tmuxinator"
        if not self.config_dir.exists():
            self.config_dir = Path.home() / ".tmuxinator"

        # Load projects
        self.projects = load_projects(self.config_dir)

        # AI analyzer
        self.ai_analyzer = AIAnalyzer()

        # Track if we've analyzed
        self.has_analyzed = False

    def compose(self) -> ComposeResult:
        """Create the application layout"""
        yield Header()

        # AI recommendations panel
        ai_panel = AIRecommendationPanel(id="ai-panel")
        ai_panel.show_empty()
        yield ai_panel

        # Project list panel
        yield ProjectListPanel(self.projects, id="project-panel")

        yield Footer()

    def action_refresh(self) -> None:
        """Refresh projects from disk"""
        self.projects = load_projects(self.config_dir)

        # Update project panel
        project_panel = self.query_one("#project-panel", ProjectListPanel)
        project_panel.refresh_projects(self.projects)

        # Update subtitle
        self.sub_title = f"{date.today().strftime('%Y-%m-%d')} | {len(self.projects)} projects"

        self.notify("Projects refreshed!", severity="information")

    def action_analyze(self) -> None:
        """Analyze projects with AI (triggers async worker)"""
        ai_panel = self.query_one("#ai-panel", AIRecommendationPanel)

        # Show analyzing state
        ai_panel.show_analyzing()
        self.notify("Analyzing projects with AI...", severity="information")

        # Start async worker
        self.analyze_with_worker()

    @work(exclusive=True, thread=True)
    async def analyze_with_worker(self) -> None:
        """Worker thread to call AI API without blocking UI"""
        # This runs in a separate thread
        result = self.ai_analyzer.analyze_projects(self.projects)

        # Call method to update UI from main thread
        self.call_from_thread(self.on_analysis_complete, result)

    def on_analysis_complete(self, result: dict) -> None:
        """Handle AI analysis results (called from main thread)"""
        ai_panel = self.query_one("#ai-panel", AIRecommendationPanel)

        if result["error"]:
            ai_panel.show_error(result["error"])
            self.notify(f"Analysis failed: {result['error']}", severity="error")
        else:
            ai_panel.show_results(result["content"])
            self.notify("Analysis complete!", severity="success")
            self.has_analyzed = True

    def action_help(self) -> None:
        """Show help message"""
        help_text = """
Commands:
  a - Analyze projects with AI
  r - Refresh project list from disk
  q - Quit application
  ↑↓ - Scroll panels
  ? - Show this help
"""
        self.notify(help_text, severity="information", timeout=10)


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    app = SummaryApp()
    app.run()


if __name__ == "__main__":
    main()
