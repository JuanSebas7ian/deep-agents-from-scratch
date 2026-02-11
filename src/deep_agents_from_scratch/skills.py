"""Skills system for deep agents.

Skills are filesystem-based directories containing a SKILL.md file
with YAML frontmatter (name, description) and markdown instructions.
The agent discovers skills via progressive disclosure — it sees only
the name and description initially, then reads the full content when needed.

This module implements the skills concept from-scratch, adapted from
the official Deep Agents documentation.
"""

import yaml
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from deep_agents_from_scratch.state import DeepAgentState


def parse_skill_md(content: str) -> dict:
    """Parse a SKILL.md file into its frontmatter and body.

    Args:
        content: Raw content of a SKILL.md file

    Returns:
        Dict with 'name', 'description', and 'instructions' keys
    """
    # Split frontmatter from body
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_str = parts[1].strip()
            body = parts[2].strip()
            try:
                frontmatter = yaml.safe_load(frontmatter_str)
            except yaml.YAMLError:
                frontmatter = {}
            return {
                "name": frontmatter.get("name", "unknown"),
                "description": frontmatter.get("description", "No description"),
                "instructions": body,
            }

    # No frontmatter found
    return {
        "name": "unknown",
        "description": "No description",
        "instructions": content,
    }


def discover_skills(files: dict[str, str]) -> list[dict]:
    """Discover available skills from the virtual filesystem.

    Looks for files matching the pattern */SKILL.md and parses
    only their frontmatter (name + description) for progressive disclosure.

    Args:
        files: The virtual filesystem dict

    Returns:
        List of dicts with 'name', 'description', and 'path' keys
    """
    skills = []
    for path, content in files.items():
        if path.endswith("SKILL.md") or path.endswith("skill.md"):
            parsed = parse_skill_md(content)
            skills.append({
                "name": parsed["name"],
                "description": parsed["description"],
                "path": path,
            })
    return skills


def get_skills_system_prompt(files: dict[str, str]) -> str:
    """Generate a system prompt section listing available skills.

    This implements progressive disclosure — only shows names and
    descriptions, not the full instructions.

    Args:
        files: The virtual filesystem dict

    Returns:
        Formatted system prompt string for skills
    """
    skills = discover_skills(files)
    if not skills:
        return ""

    lines = [
        "## Available Skills",
        "",
        "You have access to specialized skills that provide detailed instructions for specific tasks.",
        "Use `load_skill(skill_name)` to read the full instructions when you need them.",
        "",
    ]
    for s in skills:
        lines.append(f"- **{s['name']}**: {s['description']}")

    lines.append("")
    lines.append("Only load a skill when you determine it's relevant to the current task.")
    return "\n".join(lines)


LOAD_SKILL_DESCRIPTION = """Load the full instructions of a skill by name.

Skills provide specialized step-by-step guidance for particular tasks.
You can see available skills and their descriptions in your system prompt.
Use this tool when you decide a skill is relevant to the user's request.

Parameters:
- skill_name (required): Name of the skill to load (as shown in available skills list)

Returns the full SKILL.md content with detailed instructions."""


@tool(description=LOAD_SKILL_DESCRIPTION, parse_docstring=True)
def load_skill(
    skill_name: str,
    state: Annotated[DeepAgentState, InjectedState],
) -> str:
    """Load full instructions for a specific skill.

    Args:
        skill_name: Name of the skill to load
        state: Agent state containing virtual filesystem with skill files

    Returns:
        Full skill instructions or error message
    """
    files = state.get("files", {})
    skills = discover_skills(files)

    for skill in skills:
        if skill["name"].lower() == skill_name.lower():
            content = files.get(skill["path"], "")
            parsed = parse_skill_md(content)
            return f"""# Skill: {parsed['name']}

{parsed['instructions']}"""

    available = [s["name"] for s in skills]
    if available:
        return f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(available)}"
    return "Error: No skills are currently loaded. Skills are SKILL.md files in the virtual filesystem."


# ─── Example Skills ─── #

RESEARCH_SKILL_MD = """---
name: web-research
description: Use this skill for research tasks that require searching the web for information, synthesizing findings, and creating comprehensive reports.
---

# web-research

## Overview
This skill provides a structured approach to conducting web research using the tavily_search tool.

## Instructions

### 1. Plan Your Research
Before searching, identify:
- The main question or topic
- 2-3 specific sub-questions to investigate
- What type of sources would be most valuable (news, academic, general)

### 2. Execute Searches
Use `tavily_search` with targeted queries:
- Start with broad queries to understand the landscape
- Follow with specific queries to fill knowledge gaps
- Use the `topic` parameter (general/news/finance) to target results

### 3. Reflect After Each Search
Use `think_tool` after each search to:
- Assess what you learned
- Identify remaining gaps
- Decide if more searching is needed

### 4. Synthesize Findings
After gathering enough information:
- Read collected files with `read_file`
- Identify common themes and key insights
- Note any conflicting information

### 5. Deliver Results
Present findings in a clear, structured format:
- Executive summary (2-3 sentences)
- Key findings organized by theme
- Sources cited with URLs
"""

CODE_REVIEW_SKILL_MD = """---
name: code-review
description: Use this skill when reviewing code for quality, bugs, security issues, or best practices.
---

# code-review

## Overview
Structured approach to reviewing code files for quality and correctness.

## Instructions

### 1. Understand Context
- Read the file(s) to review using `read_file`
- Understand the purpose and architecture
- Check for related files using `glob_files` and `grep_files`

### 2. Review Checklist
Check each file for:
- **Correctness**: Logic errors, edge cases, off-by-one errors
- **Security**: Input validation, injection risks, secrets exposure
- **Performance**: Unnecessary loops, missing caching opportunities
- **Readability**: Clear naming, adequate comments, consistent style
- **Error handling**: Missing try/catch, unhandled edge cases

### 3. Report Findings
For each issue found:
- File and line reference
- Severity (critical/warning/info)
- Description of the issue
- Suggested fix
"""
