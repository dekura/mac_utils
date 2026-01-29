#!/opt/homebrew/Caskroom/miniconda/base/bin/python
"""
Tmuxinator Project Summary - AI-Powered Analysis
Full-screen TUI application using Textual framework with OpenAI integration
"""

import os
import sys
import json
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
        # Use gpt-4o to avoid reasoning tokens (gpt-5.1 uses reasoning by default)
        self.model = "gpt-4o"

        # Cache directory
        self.cache_dir = Path.home() / ".cache" / "tmuxinator-summary"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "ai_analysis.json"

    def load_cached_analysis(self) -> Optional[dict]:
        """Load cached AI analysis if exists"""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                # Check if cache is from today
                cache_date = cache_data.get('date')
                if cache_date == date.today().isoformat():
                    return {
                        "error": None,
                        "content": cache_data.get('content', '')
                    }
        except Exception:
            pass

        return None

    def save_analysis_to_cache(self, content: str):
        """Save AI analysis to cache"""
        try:
            cache_data = {
                'date': date.today().isoformat(),
                'content': content
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # Silently fail if cache write fails

    def analyze_projects(self, projects: List[ProjectWithProgress], force: bool = False) -> dict:
        """Call OpenAI API to analyze projects and return recommendations"""
        # Try to load from cache if not forcing refresh
        if not force:
            cached = self.load_cached_analysis()
            if cached:
                return cached

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
                        "content": "你是一个生产力顾问，专门分析项目组合。请提供简洁、可操作的建议。用中文回复。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1500  # Increased for more comprehensive analysis
            )

            content = response.choices[0].message.content

            # Debug logging to file
            with open("/tmp/ai-debug.log", "a") as f:
                f.write(f"\n=== API Response ===\n")
                f.write(f"Response message: {response.choices[0].message}\n")
                f.write(f"Content type: {type(content)}\n")
                f.write(f"Content: {content}\n")

            # Save to cache
            if content:
                self.save_analysis_to_cache(content)

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

        prompt = f"""你是一个生产力顾问，正在分析我的项目组合。

今天是 {today.strftime('%Y年%m月%d日')}。

以下是我的活跃项目：

{''.join(project_summaries)}

请分析并提供：

1. **优先级排序**（我应该专注的前3-5个项目）：
   - 按照我应该优先处理的顺序排列项目
   - 对每个项目解释为什么（考虑：截止日期紧迫性、当前进度、优先级级别、动力）

2. **战略洞察**：
   - 哪些项目有错过截止日期的风险？
   - 哪些重要项目似乎停滞不前？
   - 工作负载平衡是否存在问题（过于分散 vs 过于集中）？
   - 本周时间分配建议

请用中文回复，使用 markdown 格式，用 ## 标题。
"""
        return prompt


# ============================================================================
# Textual Widgets
# ============================================================================

class AIRecommendationPanel(Static):
    """Panel displaying AI analysis results"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def show_empty(self):
        """Show initial empty state"""
        self.update("[dim italic]按 'a' 键使用 AI 分析项目[/dim italic]")

    def show_analyzing(self):
        """Show analyzing state"""
        self.update("🔄 [yellow]正在分析项目...[/yellow]\n\n这可能需要几秒钟。")

    def show_results(self, content: str):
        """Show AI analysis results"""
        # Debug logging to file
        with open("/tmp/ai-debug.log", "a") as f:
            f.write(f"\n=== show_results ===\n")
            f.write(f"Content length: {len(content)}\n")
            f.write(f"Content: {content[:500]}\n")

        if not content:
            self.update("[red]Empty content received[/red]")
        else:
            # Try rendering as markdown
            try:
                self.update(Markdown(content))
                with open("/tmp/ai-debug.log", "a") as f:
                    f.write("Markdown render succeeded\n")
            except Exception as e:
                with open("/tmp/ai-debug.log", "a") as f:
                    f.write(f"Markdown render failed: {e}\n")
                # Fallback to plain text
                self.update(content)

    def show_error(self, error: str):
        """Show error message"""
        self.update(f"[red bold]错误：[/red bold] {error}\n\n[dim]按 'a' 键重试[/dim]")


class ProjectListPanel(Static):
    """Panel displaying project details"""

    def __init__(self, projects: List[ProjectWithProgress], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.projects = projects

    def compose(self) -> ComposeResult:
        """Create the widget content"""
        if not self.projects:
            yield Static("[dim italic]未找到项目[/dim italic]")
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
            content_parts.append(f"截止日期: [{project.deadline_color}]{ddl_text}[/{project.deadline_color}]\n")

            # Description
            if project.description:
                content_parts.append(f"描述: {project.description}\n")

            # Root path
            if project.root:
                content_parts.append(f"路径: [dim]{project.root}[/dim]\n")

            content_parts.append("\n")

            # Progress
            if project.progress_content:
                content_parts.append("[bold]进度:[/bold]\n")
                # Indent progress content
                for line in project.progress_content.split('\n'):
                    content_parts.append(f"  {line}\n")
            else:
                content_parts.append("[dim][未找到 prgs.md][/dim]\n")

        yield Static("".join(content_parts))

    def refresh_projects(self, projects: List[ProjectWithProgress]):
        """Update with new project list"""
        self.projects = projects
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

    #ai-scroll {
        height: 40%;
        border: heavy green;
        background: $success 5%;
    }

    #ai-panel {
        padding: 1;
    }

    #project-scroll {
        height: 60%;
        border: round $primary;
    }

    #project-panel {
        padding: 1;
    }

    Footer {
        background: $primary-background;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
        Binding("r", "refresh", "刷新", show=True),
        Binding("a", "analyze", "AI分析", show=True),
        Binding("?", "help", "帮助", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Tmuxinator 项目总结 - AI 分析"
        self.sub_title = f"{date.today().strftime('%Y年%m月%d日')}"

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

    def on_mount(self) -> None:
        """Called when app is mounted - load cached analysis"""
        # Try to load cached analysis
        cached = self.ai_analyzer.load_cached_analysis()
        if cached and cached.get("content"):
            ai_panel = self.query_one("#ai-panel", AIRecommendationPanel)
            ai_panel.show_results(cached["content"])
            self.has_analyzed = True

    def compose(self) -> ComposeResult:
        """Create the application layout"""
        yield Header()

        # AI recommendations panel (scrollable)
        with VerticalScroll(id="ai-scroll") as ai_scroll:
            ai_scroll.border_title = "🤖 AI 分析建议"
            ai_panel = AIRecommendationPanel(id="ai-panel")
            ai_panel.show_empty()
            yield ai_panel

        # Project list panel (scrollable)
        with VerticalScroll(id="project-scroll") as project_scroll:
            project_scroll.border_title = f"📋 项目详情 ({len(self.projects)} 个项目)"
            yield ProjectListPanel(self.projects, id="project-panel")

        yield Footer()

    def action_refresh(self) -> None:
        """Refresh projects from disk"""
        self.projects = load_projects(self.config_dir)

        # Update project panel
        project_panel = self.query_one("#project-panel", ProjectListPanel)
        project_panel.refresh_projects(self.projects)

        # Update project scroll container border title
        project_scroll = self.query_one("#project-scroll", VerticalScroll)
        project_scroll.border_title = f"📋 项目详情 ({len(self.projects)} 个项目)"

        # Update subtitle
        self.sub_title = f"{date.today().strftime('%Y-%m-%d')} | {len(self.projects)} 个项目"

        self.notify("项目列表已刷新！", severity="information")

    def action_analyze(self) -> None:
        """Analyze projects with AI"""
        ai_panel = self.query_one("#ai-panel", AIRecommendationPanel)

        # Show analyzing state
        ai_panel.show_analyzing()
        self.notify("正在使用 AI 分析项目...", severity="information")

        # Run analysis in background worker to avoid blocking UI
        self.run_worker_analyze()

    @work(exclusive=True, thread=True)
    def run_worker_analyze(self) -> None:
        """Background worker for AI analysis"""
        # Call AI analyzer in worker thread with force=True to bypass cache
        result = self.ai_analyzer.analyze_projects(self.projects, force=True)

        # Update UI with results (safe to call from worker)
        self.call_from_thread(self.on_analysis_complete, result)

    def on_analysis_complete(self, result: dict) -> None:
        """Handle AI analysis results (called from main thread)"""
        ai_panel = self.query_one("#ai-panel", AIRecommendationPanel)

        # Debug logging to file
        with open("/tmp/ai-debug.log", "a") as f:
            f.write(f"\n=== on_analysis_complete ===\n")
            f.write(f"Result keys: {result.keys()}\n")
            f.write(f"Error: {result.get('error')}\n")
            f.write(f"Content length: {len(result.get('content', ''))}\n")
            f.write(f"Content preview: {result.get('content', '')[:500]}\n")

        if result["error"]:
            ai_panel.show_error(result["error"])
            self.notify(f"分析失败：{result['error']}", severity="error")
        else:
            content = result["content"]
            if not content or content.strip() == "":
                ai_panel.show_error("AI 返回了空响应")
                self.notify("AI 返回了空响应", severity="warning")
            else:
                ai_panel.show_results(content)
                self.notify("分析完成！", severity="success")
                self.has_analyzed = True

    def action_help(self) -> None:
        """Show help message"""
        help_text = """
快捷键：
  a - 使用 AI 分析项目
  r - 从磁盘刷新项目列表
  q - 退出应用
  ↑↓ - 滚动面板
  ? - 显示此帮助
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
