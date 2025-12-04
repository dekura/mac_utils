# AI-Powered Tmuxinator Summary - Design Document

**Date:** 2025-12-04
**Status:** Approved for implementation

## Overview

Rewrite `tmuxinator-summary` from Ruby to Python with OpenAI-powered task prioritization recommendations. The new tool will analyze project metadata and progress files to provide actionable insights on what to work on next.

## Architecture

### 1. Data Layer

Reuses data loading logic from `tmuxinator-ls-ddl.py`:
- Load tmuxinator YAML configs from `~/.config/tmuxinator`
- Parse `ddl`, `priority`, `description`, and `root` fields
- For each project, read `prgs.md` from the project root directory
- Build unified data structure with both metadata and progress content

**Data Model:**

```python
class ProjectWithProgress:
    name: str
    ddl: Optional[date]           # Deadline
    priority: str                 # 'high', 'normal', 'low'
    description: str
    root: str                     # Project root directory
    file_path: str               # Path to .yml config
    progress_content: Optional[str]  # Content from prgs.md
```

### 2. AI Analysis Engine

**Configuration:**
- Base URL: `https://api.chatanywhere.org/v1` (hardcoded)
- API Key: Read from `$chat_any_where_key` environment variable
- Model: `gpt-5.1`

**Prompt Design:**

The AI receives:
- Today's date for context
- For each project: name, deadline (days left), priority, description, progress content
- Instructions to provide:
  1. **Prioritized work order** (1-5 ranked projects with reasoning)
  2. **Strategic insights** (high-level portfolio observations)

**Analysis Dimensions:**
- Urgency vs progress mismatch
- Momentum detection (projects with good velocity)
- Stalled projects (no progress despite deadlines)
- Workload balance assessment
- Priority conflicts

**Error Handling:**
- Missing API key → Show error message, still display projects
- Network failure → Show error with retry option (press 'a' again)
- API error (rate limit, etc.) → Display error message with details

### 3. UI Layer - Full-Screen TUI

**Layout:**

```
┌─────────────────────────────────────────────────┐
│ Header: Title + Date                            │
├─────────────────────────────────────────────────┤
│ AI RECOMMENDATIONS (30-40% of screen)           │
│ - Initially empty: "Press 'a' to analyze"      │
│ - Analyzing: Loading spinner                    │
│ - Results: Markdown-formatted recommendations   │
├─────────────────────────────────────────────────┤
│ PROJECT DETAILS (60-70% of screen)              │
│ - Same format as current Ruby script            │
│ - Color-coded deadlines and priorities          │
│ - Scrollable list                               │
└─────────────────────────────────────────────────┘
 Footer: Key bindings
```

**Key Bindings:**
- `a` - Analyze with AI (trigger OpenAI API call)
- `r` - Refresh projects (reload YAML configs and prgs.md files)
- `q` - Quit
- `↑↓` or scroll - Navigate project list
- `?` - Show help

**Visual Design:**
- AI section uses rich markdown rendering
- Project section matches current Ruby output:
  - Bold project names
  - Color-coded deadlines (red=overdue, yellow=urgent, green=normal)
  - Priority indicators [HIGH], [LOW]
  - Indented progress content

## Technology Stack

- **Textual** - TUI framework (already used in tmuxinator-ls-ddl.py)
- **PyYAML** - Parse tmuxinator configs
- **openai** - OpenAI API client with custom base_url support
- **rich** - Text formatting (comes with Textual)

## File Structure

```
~/bin/
├── tmuxinator-summary          # Updated to call Python script
├── tmuxinator-summary.py       # New main Python TUI application
└── docs/plans/
    └── 2025-12-04-ai-summary-design.md
```

## Implementation Components

### Main Classes

1. **ProjectWithProgress** - Data model for project + progress content
2. **AIAnalyzer** - Handles OpenAI API calls and prompt construction
3. **AIRecommendationPanel** - Top panel widget (Textual Static)
4. **ProjectListPanel** - Bottom panel widget (Textual Static)
5. **SummaryApp** - Main Textual App with key bindings

### Wrapper Script

Replace existing Ruby script with shell wrapper:

```bash
#!/bin/bash
exec /opt/homebrew/Caskroom/miniconda/base/bin/python \
    ~/bin/tmuxinator-summary.py "$@"
```

## Dependencies

Install via conda base environment:

```bash
/opt/homebrew/Caskroom/miniconda/base/bin/pip install \
    textual pyyaml openai
```

## Success Criteria

1. Load all tmuxinator projects and progress files
2. Call OpenAI API on 'a' key press
3. Display prioritized recommendations with reasoning
4. Display strategic insights about project portfolio
5. Show project list in familiar format
6. Handle errors gracefully (missing API key, network failures)
7. Maintain same UX as current Ruby script for project viewing
