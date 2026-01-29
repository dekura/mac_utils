#!/opt/homebrew/Caskroom/miniconda/base/bin/python
"""
Tmuxinator Project Dashboard - Eisenhower Matrix View
Beautiful TUI application using Textual framework
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional, Literal
import yaml

from textual.app import App, ComposeResult
from textual.containers import Grid, Container, Vertical
from textual.widgets import Static, Header, Footer, DataTable
from textual.binding import Binding
from rich.text import Text


# ============================================================================
# Data Models & Classification
# ============================================================================

Urgency = Literal["urgent", "not_urgent", "no_deadline"]
Importance = Literal["important", "routine", "low"]


class Project:
    """Represents a tmuxinator project with deadline and priority"""

    def __init__(self, name: str, ddl: Optional[date], priority: str, description: str, file_path: str):
        self.name = name
        self.ddl = ddl
        self.priority = priority.lower() if priority else "normal"
        self.description = description or ""
        self.file_path = file_path

    @property
    def urgency(self) -> Urgency:
        """Classify urgency based on deadline"""
        if not self.ddl:
            return "no_deadline"
        days_left = (self.ddl - date.today()).days
        return "urgent" if days_left <= 7 else "not_urgent"

    @property
    def importance(self) -> Importance:
        """Classify importance based on priority field"""
        if self.priority in ["high", "urgent"]:
            return "important"
        elif self.priority == "low":
            return "low"
        else:
            return "routine"

    @property
    def quadrant(self) -> str:
        """Determine which quadrant this project belongs to"""
        urg = self.urgency
        imp = self.importance

        # Urgency + Importance matrix
        mapping = {
            ("urgent", "important"): "q1",
            ("not_urgent", "important"): "q2",
            ("urgent", "routine"): "q3",
            ("not_urgent", "routine"): "q4",
            ("urgent", "low"): "q5",
            ("not_urgent", "low"): "q6",
            # No deadline: distribute by importance
            ("no_deadline", "important"): "q1",  # Important habits -> Q1
            ("no_deadline", "routine"): "q4",    # Long-term maintenance -> Q4
            ("no_deadline", "low"): "q6",        # Candidates for cleanup -> Q6
        }

        return mapping.get((urg, imp), "q4")

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
    def priority_symbol(self) -> str:
        """Get symbol for priority level"""
        symbols = {"important": "▲", "routine": "●", "low": "▼"}
        return symbols.get(self.importance, "●")

    @property
    def display_deadline(self) -> str:
        """Format deadline for display"""
        if not self.ddl:
            return "No ddl"
        days = self.days_left
        if days < 0:
            return f"{abs(days)}d ago"
        elif days == 0:
            return "Today"
        else:
            return f"{days}d"


def load_projects(config_dir: Path) -> List[Project]:
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

            # Parse deadline
            ddl = None
            if ddl_str:
                try:
                    ddl = datetime.strptime(str(ddl_str), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass

            projects.append(Project(name, ddl, priority, description, str(yaml_file)))

        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file}: {e}", file=sys.stderr)

    return projects


def group_by_quadrant(projects: List[Project]) -> Dict[str, List[Project]]:
    """Group projects into 6 quadrants"""
    quadrants = {f"q{i}": [] for i in range(1, 7)}

    for project in projects:
        quadrants[project.quadrant].append(project)

    # Sort within each quadrant
    for q in quadrants.values():
        q.sort(key=lambda p: (
            0 if p.is_overdue else 1,  # Overdue first
            p.days_left if p.days_left is not None else 9999,  # Then by deadline
            p.name  # Then alphabetically
        ))

    return quadrants


# ============================================================================
# Textual Widgets
# ============================================================================

class QuadrantPanel(Static):
    """A panel displaying projects in one quadrant"""

    def __init__(self, title: str, projects: List[Project], quadrant_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title_base = title
        self.projects = projects
        self.quadrant_id = quadrant_id
        # Update border title with count
        count = len(projects)
        self.border_title = f"{title} ({count})"

    def compose(self) -> ComposeResult:
        """Create the widget content"""
        if not self.projects:
            yield Static("[dim italic]Empty - Good! 👍[/dim italic]", classes="empty")
        else:
            for project in self.projects:
                yield ProjectLine(project)


class ProjectLine(Static):
    """A single project line with formatting"""

    def __init__(self, project: Project, *args, **kwargs):
        self.project = project

        # Build the display text
        parts = []

        # Overdue warning
        if project.is_overdue:
            parts.append("[red bold]⚠[/red bold]")

        # Priority symbol with color
        symbol_colors = {
            "important": "red bold",
            "routine": "white",
            "low": "dim"
        }
        color = symbol_colors.get(project.importance, "white")
        parts.append(f"[{color}]{project.priority_symbol}[/{color}]")

        # Project name
        parts.append(f"[bold]{project.name:12}[/bold]")

        # Deadline
        ddl_color = "red" if project.is_overdue else ("yellow" if project.urgency == "urgent" else "green")
        parts.append(f"[{ddl_color}]{project.display_deadline:>8}[/{ddl_color}]")

        # Description (truncated)
        if project.description:
            desc = project.description[:30] + "..." if len(project.description) > 30 else project.description
            parts.append(f"[dim]{desc}[/dim]")

        content = " ".join(parts)
        super().__init__(content, *args, **kwargs)


# ============================================================================
# Main Application
# ============================================================================

class MuxDashboard(App):
    """Tmuxinator Project Dashboard - Eisenhower Matrix"""

    CSS = """
    Screen {
        background: $surface;
    }

    Grid {
        grid-size: 2 3;
        grid-gutter: 1;
        padding: 1;
        height: 100%;
    }

    QuadrantPanel {
        border: round $primary;
        padding: 1;
        height: 100%;
        overflow-y: auto;
    }

    #q1 {
        border: heavy red;
        background: $error 10%;
    }

    #q2 {
        border: heavy green;
        background: $success 10%;
    }

    #q3 {
        border: round yellow;
        background: $warning 10%;
    }

    #q4 {
        border: round $primary;
    }

    #q5 {
        border: dashed orange;
        background: $warning 5%;
    }

    #q6 {
        border: dashed gray;
        background: $surface-darken-1;
    }

    ProjectLine {
        padding: 0 1;
    }

    .empty {
        text-align: center;
        padding: 2;
    }

    Footer {
        background: $primary-background;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("1", "focus_q1", "Focus Q1", show=False),
        Binding("2", "focus_q2", "Focus Q2", show=False),
        Binding("?", "help", "Help", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Tmuxinator Dashboard"
        self.sub_title = "Eisenhower Matrix View"

        # Store config directory
        self.config_dir = Path.home() / ".config" / "tmuxinator"
        if not self.config_dir.exists():
            self.config_dir = Path.home() / ".tmuxinator"

        # Load projects
        self.projects = load_projects(self.config_dir)
        self.quadrants = group_by_quadrant(self.projects)

    def compose(self) -> ComposeResult:
        """Create the application layout"""
        yield Header()

        with Grid():
            # Row 1: Q1 (urgent+important) | Q2 (not urgent+important)
            yield QuadrantPanel(
                "🔴 DO FIRST (Urgent & Important)",
                self.quadrants["q1"],
                "q1",
                id="q1"
            )
            yield QuadrantPanel(
                "🟢 SCHEDULE (Not Urgent & Important)",
                self.quadrants["q2"],
                "q2",
                id="q2"
            )

            # Row 2: Q3 (urgent+routine) | Q4 (not urgent+routine)
            yield QuadrantPanel(
                "🟡 QUICK WINS (Urgent & Routine)",
                self.quadrants["q3"],
                "q3",
                id="q3"
            )
            yield QuadrantPanel(
                "⚪ ORGANIZE (Not Urgent & Routine)",
                self.quadrants["q4"],
                "q4",
                id="q4"
            )

            # Row 3: Q5 (urgent+low) | Q6 (not urgent+low)
            yield QuadrantPanel(
                "🟠 REVIEW (Urgent & Low Priority)",
                self.quadrants["q5"],
                "q5",
                id="q5"
            )
            yield QuadrantPanel(
                "⚫ DROP? (Not Urgent & Low Priority)",
                self.quadrants["q6"],
                "q6",
                id="q6"
            )

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted - update footer with stats"""
        total = len(self.projects)
        overdue = sum(1 for p in self.projects if p.is_overdue)

        # Build status message
        stats = f"Total: {total} projects"
        if overdue > 0:
            stats += f" | ⚠ {overdue} overdue"

        # Update subtitle with stats
        self.sub_title = f"Eisenhower Matrix | {stats}"

    def action_refresh(self) -> None:
        """Refresh the dashboard by reloading projects"""
        # Reload projects from config
        self.projects = load_projects(self.config_dir)
        self.quadrants = group_by_quadrant(self.projects)

        # Remove old grid and recreate
        grid = self.query_one(Grid)
        grid.remove()

        # Recreate grid with updated data
        new_grid = Grid()
        self.mount(new_grid, before=self.query_one(Footer))

        # Populate new grid with updated quadrants
        new_grid.mount(QuadrantPanel(
            "🔴 DO FIRST (Urgent & Important)",
            self.quadrants["q1"],
            "q1",
            id="q1"
        ))
        new_grid.mount(QuadrantPanel(
            "🟢 SCHEDULE (Not Urgent & Important)",
            self.quadrants["q2"],
            "q2",
            id="q2"
        ))
        new_grid.mount(QuadrantPanel(
            "🟡 QUICK WINS (Urgent & Routine)",
            self.quadrants["q3"],
            "q3",
            id="q3"
        ))
        new_grid.mount(QuadrantPanel(
            "⚪ ORGANIZE (Not Urgent & Routine)",
            self.quadrants["q4"],
            "q4",
            id="q4"
        ))
        new_grid.mount(QuadrantPanel(
            "🟠 REVIEW (Urgent & Low Priority)",
            self.quadrants["q5"],
            "q5",
            id="q5"
        ))
        new_grid.mount(QuadrantPanel(
            "⚫ DROP? (Not Urgent & Low Priority)",
            self.quadrants["q6"],
            "q6",
            id="q6"
        ))

        # Update statistics
        total = len(self.projects)
        overdue = sum(1 for p in self.projects if p.is_overdue)
        stats = f"Total: {total} projects"
        if overdue > 0:
            stats += f" | ⚠ {overdue} overdue"
        self.sub_title = f"Eisenhower Matrix | {stats}"

        self.notify("Dashboard refreshed!", severity="information")

    def action_help(self) -> None:
        """Show help message"""
        self.notify("Navigation: Tab/Shift+Tab | Quit: q | Refresh: r", severity="information")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    app = MuxDashboard()
    app.run()


if __name__ == "__main__":
    main()
