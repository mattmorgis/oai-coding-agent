# Daily Updates Feature Proposal

## Background and Previous Implementation

### Meeting Context

- **Source:** AI Launchpad discussion on July 15, 2025
- **Project:** OGAI daily stand-up summary feature revival
- **Jira Ticket:** OGAI-397

### Previous Implementation Review

A search through the current codebase did not reveal any existing implementation for the daily updates feature. It appears to have been removed or refactored out in earlier iterations. As a result, this proposal outlines a fresh architecture and implementation plan.

## Proposed Architecture

The daily updates feature will provide a stand-up summary of work items, grouped and formatted for easy consumption.

### 1. Data Model

Define a canonical `UpdateItem` data class in `src/oai_coding_agent/updates.py`:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class UpdateItem:
    author: str
    project: str  # project name or identifier
    content: str  # description of the update
    timestamp: datetime  # timestamp when the update was recorded
```

### 2. Collection Mechanism

- Introduce a plugin hook or invocation point where agents register updates throughout the day.
- Each task execution can emit one or more `UpdateItem` entries to a centralized store (e.g., file-based or in-memory registry).

### 3. Grouping Strategies

Support two grouping modes, configurable via a CLI flag (`--group-by`):

| Strategy   | Description                                          |
|------------|------------------------------------------------------|
| project    | Group all updates by project name (default)          |
| individual | Group all updates by author name                     |

#### Miscellaneous Items

Any `UpdateItem` with an empty or unknown `project` field will be placed in a `Miscellaneous` section under either grouping.

### 4. CLI Command

Add a new top-level CLI command:

```bash
# Default grouping (by project)
oai daily-updates

# Grouping by individual contributors
oai daily-updates --group-by individual
```

This command will:
1. Load collected `UpdateItem` entries for the current date.
2. Group them per the selected strategy.
3. Print or write a Markdown-formatted summary to stdout or a file.

### 5. Output Format

Generate output in Markdown with headings and bullet lists:

```markdown
# Daily Stand-up Summary — 2025-07-16

## Project Alpha
- **Alice:** Completed integration tests for the billing API.
- **Bob:** Reviewed PR #124 and updated documentation.

## Project Beta
- **Eve:** Started prototype for the new client dashboard.

## Miscellaneous
- **Dan:** Attended team retro and captured action items.
```

## Implementation Plan

1. **Data Models**: Create `src/oai_coding_agent/updates.py` with `UpdateItem` and registry interface.
2. **Grouping Logic**: Implement grouping functions (`group_by_project`, `group_by_individual`) in the same module.
3. **Persistence Layer**: Define a simple storage adapter (e.g., JSON file per day) to collect and read updates.
4. **CLI Integration**: Hook new `daily-updates` command into `src/oai_coding_agent/cli.py` using the existing click/argparse patterns.
5. **Formatting**: Add markdown renderer for summaries in `updates.py` or a dedicated formatter module.
6. **Testing**: Write unit tests for model, grouping logic, and markdown output in `tests/test_updates.py`.
7. **Documentation**: Update `README.md` and add usage examples; refer users to the new command.

## Assumptions

- No residual code for this feature remains; a full reimplementation is acceptable.
- Project names will be available for each update item; untagged items will default to `Miscellaneous`.
- The CLI framework supports extension, and JSON file storage is sufficient for initial persistence.

## Alternatives Considered

- **Only Individual Grouping**: Discarded in favor of project grouping, since teams often think in project context.
- **Database-backed Storage**: Deferred in favor of a lightweight file-based registry to minimize dependencies.

## Next Steps

- Gather feedback on the grouping strategy preference.
- Align on storage format and retention policy.
- Prioritize and schedule implementation milestones.
