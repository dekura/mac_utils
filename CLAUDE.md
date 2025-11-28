# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal `~/bin` directory containing utility scripts for workflow automation. The scripts are written in different languages (Bash, Ruby, Python) and focus on two main domains:

1. **Tmuxinator workflow management** - Enhanced tmuxinator commands for project lifecycle management with deadline tracking
2. **PDF utilities** - Tools for PDF manipulation and annotation extraction

## Architecture

### Tmuxinator Utilities

The tmuxinator utilities form a cohesive system for managing project-based tmux sessions with deadline tracking:

- `mux` - Main entry point (zsh wrapper) that routes commands to specialized subcommands
  - Routes `ddl`, `new`, `archive`, and `summary` to custom commands
  - By default, `mux ddl` launches the Textual dashboard; use `--linear` for classic view
  - Passes all other commands directly to tmuxinator
- **`tmuxinator-ls-ddl.py` (Python + Textual)** - **NEW**: Interactive Eisenhower matrix dashboard
  - Full-screen TUI application with 6-quadrant layout
  - Classifies projects by urgency (≤7d deadline) and importance (priority field)
  - Real-time refresh (`r` key), keyboard navigation, visual notifications
  - CSS-styled quadrants: red (Q1: urgent+important), green (Q2: important), yellow (Q3: urgent), etc.
  - Reads YAML configs from `~/.config/tmuxinator`
  - Shows project counts per quadrant and overdue warnings in header
- `tmuxinator-ls-ddl` (Ruby) - **LEGACY**: Classic linear list view (use `--linear` flag)
  - Lists projects sorted by deadline with color-coded urgency indicators
  - Parses `ddl`, `description`, and `priority` fields from project configs
  - Color codes: red (overdue/urgent), yellow (soon), green (normal), gray (no deadline)
- `tmuxinator-new` (Ruby) - Creates new projects from template with auto-calculated 7-day deadline
  - Uses `~/.config/tmuxinator/template.yml` as base
  - Automatically sets ddl to 7 days from creation
  - Opens new config in $EDITOR after creation
- `tmuxinator-archive` (Ruby) - Archives projects to `~/.config/tmuxinator-backups`
  - Moves inactive projects out of main config directory
  - Adds timestamps to prevent overwriting existing backups
- `tmuxinator-summary` (Ruby) - Displays comprehensive progress summary for all projects
  - Reads projects in same order as deadline-sorted view
  - For each project, looks for `prgs.md` in the project's root directory
  - Displays project metadata (name, ddl, priority, description) alongside progress content
  - Color-codes deadline urgency and highlights projects without progress reports

**Design Philosophy**: These scripts extend tmuxinator rather than replace it. They read/write standard tmuxinator YAML configs with custom fields (`ddl`, `priority`) that tmuxinator ignores but the scripts use for organization. Projects are expected to maintain a `prgs.md` file in their root directory for progress tracking.

### PDF Utilities

- `pdfutils` - Main dispatcher script (Bash) with two subcommands:
  - `crop` - Extracts page ranges using pdfjam
    - Filters out harmless macOS sed warnings
    - Output format: `{basename}_{range}.pdf`
  - `extractnotes` - Extracts PDF annotations in multiple formats
    - Delegates to Python script at `~/bin/pdfutils_scripts/extract_annotations.py`
    - Supports markdown (default), json, and txt output formats
    - Output format: `{basename}_annotations.{ext}`

- `pdfutils_scripts/extract_annotations.py` - PDF annotation extraction using PyMuPDF
  - Extracts all annotation types (highlights, comments, etc.)
  - For highlights/underlines, attempts to extract the highlighted text region
  - Formats output as structured data (JSON) or readable text (markdown/txt)
  - Requires PyMuPDF (imported as `pymupdf`)

**Python Environment**: The `pdfutils` script prefers the conda base environment Python at `/opt/homebrew/Caskroom/miniconda/base/bin/python` if available, otherwise falls back to `python3`.

## Common Commands

### Tmuxinator Workflow

```bash
# Show interactive Eisenhower matrix dashboard (default, NEW!)
mux ddl

# Show classic linear list view (old behavior)
mux ddl --linear

# Create new project (opens in editor with 7-day deadline)
mux new <project_name>

# Archive completed/inactive project
mux archive <project_name>

# Show progress summary for all projects (reads prgs.md from each project root)
mux summary

# Standard tmuxinator commands work through mux
mux start <project_name>
mux stop <project_name>
```

**Interactive Dashboard Controls** (when using `mux ddl`):
- `q` - Quit dashboard
- `r` - Refresh (reload all projects)
- `?` - Show help
- `Tab` / `Shift+Tab` - Navigate between quadrants

### PDF Operations

```bash
# Extract pages from PDF (inclusive range)
pdfutils crop input.pdf 5-10        # Creates input_5-10.pdf

# Extract annotations to markdown (default)
pdfutils extractnotes input.pdf

# Extract annotations to JSON
pdfutils extractnotes input.pdf json

# Extract annotations to plain text
pdfutils extractnotes input.pdf txt
```

## Dependencies

### Tmuxinator Scripts
- **Python 3.9+** (for Textual dashboard)
  - `textual>=6.0` - TUI framework
  - `pyyaml` - YAML parsing
  - Install: `/opt/homebrew/Caskroom/miniconda/base/bin/pip install textual pyyaml`
- Ruby (system default, for legacy scripts)
- tmuxinator (expected to be installed and in PATH)
- Standard Ruby libraries: yaml, date, fileutils

### PDF Scripts
- Bash
- pdfjam (for PDF cropping, part of TeX Live)
- Python 3 with PyMuPDF (pymupdf package)

## Project Configuration Format

Tmuxinator projects support custom fields that the deadline scripts recognize:

```yaml
name: project_name
root: ~/path/to/project
ddl: "2025-12-31"           # ISO date format for deadline tracking
priority: high              # high/urgent, normal, or low
description: "Short desc"   # Shown in ddl listing

# Standard tmuxinator configuration follows...
windows:
  - editor: vim
  - server: npm start
```

## Testing

When modifying these scripts:
- Test tmuxinator scripts with various date scenarios (overdue, today, soon, future, no ddl)
- Test PDF operations with various PDF types (annotated, multi-page, edge cases)
- Verify that invalid inputs produce helpful error messages
- Test that file naming conventions are preserved (underscores, paths, extensions)
