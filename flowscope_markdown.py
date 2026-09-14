"""FlowScope Phase 4 - Markdown Export.

Converts the structured blocks.json produced by Phase 3 (Heuristics)
into a faithful, human-readable Markdown transcript.

This module is intentionally deterministic and contains no AI logic.

Pipeline:

    Recorder
        ↓
    Parser
        ↓
    Heuristics
        ↓
    blocks.json
        ↓
    Markdown Export
        ↓
    transcript.md

The AI Curator is a separate Phase 5:

    blocks.json
        ↓
    AI Curator
        ↓
    curated.md

The raw session data and blocks.json remain unchanged by this module.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _safe_fence(content: str) -> str:
    """Return a Markdown code fence longer than any backtick run in content.

    This prevents terminal output containing ``` from accidentally closing
    the generated code block.
    """

    longest = max(
        (
            len(run)
            for run in re.findall(r"`+", content)
        ),
        default=0,
    )

    return "`" * max(3, longest + 1)


def _render_block(block: dict) -> str:
    """Render one command block as Markdown.

    A command block contains:

        command
        output
        started_at
        ended_at

    The prompt is intentionally not rendered because the command itself is
    the useful part of the transcript.
    """

    command = str(block.get("command", ""))

    content = f"$ {command}"

    output = block.get("output", [])

    if output:
        content += "\n" + "\n".join(
            str(line)
            for line in output
        )

    fence = _safe_fence(content)

    return "\n".join(
        [
            f"{fence}console",
            content,
            fence,
        ]
    )


# ---------------------------------------------------------------------------
# blocks.json loading
# ---------------------------------------------------------------------------

def _load_blocks(blocks_path: Path) -> dict:
    """Load and validate a FlowScope blocks.json file."""

    if not blocks_path.exists():
        raise FileNotFoundError(
            f"Blocks file not found: {blocks_path}"
        )

    try:
        payload = json.loads(
            blocks_path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {blocks_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "blocks.json must contain a JSON object."
        )

    blocks = payload.get("blocks")

    if not isinstance(blocks, list):
        raise ValueError(
            "blocks.json does not contain a valid 'blocks' list."
        )

    return payload


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(blocks_path: Path) -> str:
    """Render blocks.json as a faithful Markdown transcript."""

    payload = _load_blocks(blocks_path)

    parts = [
        "# FlowScope Session Transcript",
        "",
        f"- **Session ID:** {payload.get('session_id', '')}",
        f"- **Shell:** {payload.get('shell', '')}",
        f"- **Started:** {payload.get('started_at', '')}",
        f"- **Ended:** {payload.get('ended_at', '')}",
        f"- **Duration:** {payload.get('duration', '')}s",
        "",
        "---",
        "",
    ]

    for block in payload.get("blocks", []):
        parts.append(
            _render_block(block)
        )
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line entry point."""

    if len(sys.argv) < 2:
        sys.exit(
            f"Usage: {sys.argv[0]} "
            "<blocks.json> [--out transcript.md]"
        )

    blocks_path = Path(sys.argv[1])

    out_path: Path | None = None

    if "--out" in sys.argv:
        out_index = sys.argv.index("--out")

        if out_index + 1 >= len(sys.argv):
            sys.exit(
                "Error: --out requires an output path."
            )

        out_path = Path(
            sys.argv[out_index + 1]
        )

    try:
        markdown = render_markdown(
            blocks_path
        )

        if out_path:
            out_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            out_path.write_text(
                markdown,
                encoding="utf-8",
            )

            print(
                f"Markdown written to {out_path}"
            )
        else:
            print(markdown)

    except Exception as exc:
        sys.exit(
            f"Error generating Markdown: {exc}"
        )


if __name__ == "__main__":
    main()