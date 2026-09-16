"""FlowScope Phase 5 - AI Guide Curator.

Takes the structured blocks.json produced by Phase 3 (Heuristics) and
uses the Gemini API to convert the recorded terminal session into a
clean, minimal, step-by-step technical guide.

The AI Curator:
    - identifies the main goal of the session
    - removes irrelevant, redundant, accidental, or failed commands
    - keeps only commands necessary for the core task
    - classifies the retained steps
    - explains what each step does
    - produces a clean Markdown guide

Input:
    blocks.json

Output:
    curated Markdown guide

The original session.json and blocks.json are never modified by AI.
The curated guide is a separate artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Optional .env support
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# AI System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are FlowScope's AI Guide Curator.

You receive a structured JSON representation of a recorded terminal
session. The JSON contains session metadata and command blocks reconstructed
by FlowScope's deterministic parsing and heuristic stages.

Your job is to transform the recorded session into a clean, step-by-step
technical guide that documents every command that was executed.

IMPORTANT PRINCIPLES:

1. IDENTIFY THE CORE GOAL

   Determine what the user was actually trying to accomplish in the
   terminal session. The guide should be framed around that goal.

2. PRESERVE EVERY COMMAND

   Include ALL commands from the session without exception.

   Do not omit any command regardless of how simple, obvious, or
   redundant it may appear. Every command the user ran is intentional
   and must appear in the guide.

   This includes but is not limited to:
   - ls, pwd, whoami, clear
   - directory navigation
   - inspection commands
   - repeated commands
   - failed attempts (document them as troubleshooting steps)

3. HANDLE FAILED ATTEMPTS

   Do not omit failed attempts. Document them as-is.

   If a command failed, include it and note the failure and its outcome.

4. CLASSIFY STEPS

   Assign each step one of these categories:

   - SETUP
   - DEPENDENCY
   - CONFIG
   - BUILD
   - EXECUTION
   - VERIFICATION
   - CLEANUP

5. EXPLAIN EACH STEP

   For every command, provide a concise explanation of:

   - what the command does
   - why the step was performed

   Do not write long explanations for simple commands.

6. EXPECTED OUTPUT

   Include the actual output from the session where available.

   Do not reproduce excessively long output — truncate with "..." if
   needed, but always show the beginning and the key result lines.

7. DO NOT MODIFY THE SOURCE DATA

   The input JSON is historical session data. Treat it as read-only.

   Do not invent or substitute commands that were not in the session.

8. OUTPUT FORMAT

   Return ONLY Markdown.

   Use this structure:

   # <Clear Guide Title>

   ## Overview

   <Brief explanation of what the guide accomplishes.>

   ## Prerequisites

   <Only include prerequisites that are relevant and supported by the
   recorded session. Omit this section if there are no meaningful
   prerequisites.>

   ## Step 1: <Step Title> [CATEGORY]

   <Concise explanation of what the step does and why it was performed.>

```bash
   <command>
```

   <Actual output if available and useful.>

   ## Step 2: <Step Title> [CATEGORY]

   ...

   ## Result

   <Brief description of the final outcome of the session.>

Do not include analysis, commentary, JSON, or explanations outside the
Markdown guide.
"""

# ---------------------------------------------------------------------------
# Custom prompt behavior
# ---------------------------------------------------------------------------

CUSTOM_PROMPT_RULE = """
When a USER-CUSTOM-PROMPT is supplied, treat it as the user's specific
instruction for this curation run.

Follow the custom prompt while still treating the recorded session data
as the source of truth. Never invent commands, output, errors, or results.
If the custom prompt conflicts with the recorded session data, the recorded
session data takes precedence.
"""

# ---------------------------------------------------------------------------

# Gemini API

# ---------------------------------------------------------------------------


def _call_gemini_api(
    prompt: str,
    api_key: str | None = None,
    model: str = "gemini-2.5-flash",
) -> str:
    """Send a prompt to Gemini and return the generated Markdown."""

    key = api_key or os.environ.get("GEMINI_API_KEY")

    if not key:
        raise ValueError(
            "Gemini API key is required. "
            "Set GEMINI_API_KEY environment variable or pass --api-key."
        )

    # -----------------------------------------------------------------------
    # Attempt 1: Official Google GenAI SDK
    # -----------------------------------------------------------------------

    try:
        from google import genai

        client = genai.Client(api_key=key)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        if response and response.text:
            return response.text.strip()

    except Exception:
        # Fall back to direct REST API below.
        pass

    # -----------------------------------------------------------------------
    # Attempt 2: Direct REST API
    # -----------------------------------------------------------------------

    import urllib.error
    import urllib.request

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent?key={key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_bytes = response.read()

        response_json = json.loads(
            response_bytes.decode("utf-8")
        )

        candidates = response_json.get("candidates", [])

        if not candidates:
            raise RuntimeError(
                "Gemini returned no candidates."
            )

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        text = "".join(
            part.get("text", "")
            for part in parts
        ).strip()

        if not text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return text

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Gemini API request failed "
            f"({exc.code}): {error_body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to Gemini API: {exc}"
        ) from exc

# ---------------------------------------------------------------------------

# Input handling

# ---------------------------------------------------------------------------


def _load_blocks_json(input_path: Path) -> dict:
    """Load and validate FlowScope's blocks.json artifact."""

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    try:
        payload = json.loads(
            input_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {input_path}: {exc}"
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



def _load_input(input_path: Path) -> str:
    """Load the structured blocks artifact for the AI prompt."""

    payload = _load_blocks_json(input_path)

    # Send compact, structured JSON to Gemini rather than converting the
    # data into Markdown first.
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    )

# ---------------------------------------------------------------------------

# Prompt construction

# ---------------------------------------------------------------------------

def build_prompt(
    blocks_json: str,
    focus: str | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Build the complete Gemini prompt.

    `focus` is a short hint about the objective.
    `custom_prompt` is a full user-supplied instruction for this run.
    The recorded session data remains the source of truth.
    """

    prompt_parts = [
        SYSTEM_PROMPT,
        "",
        "FLOW SCOPE SESSION DATA:",
        "",
        blocks_json,
    ]

    if focus:
        prompt_parts.extend(
            [
                "",
                "USER-SPECIFIED FOCUS:",
                "",
                focus,
            ]
        )

    if custom_prompt:
        prompt_parts.extend(
            [
                "",
                CUSTOM_PROMPT_RULE.strip(),
                "",
                "USER-CUSTOM-PROMPT:",
                "",
                custom_prompt,
            ]
        )

    prompt_parts.extend(
        [
            "",
            "Now produce the final curated Markdown guide.",
        ]
    )

    return "\n".join(prompt_parts)

# ---------------------------------------------------------------------------

# Curation

# ---------------------------------------------------------------------------

def curate_guide(
    input_path: Path,
    api_key: str | None = None,
    model: str = "gemini-2.5-flash",
    focus: str | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Generate a curated Markdown guide from blocks.json."""

    blocks_json = _load_input(input_path)

    prompt = build_prompt(
        blocks_json=blocks_json,
        focus=focus,
        custom_prompt=custom_prompt,
    )

    return _call_gemini_api(
        prompt,
        api_key=api_key,
        model=model,
    )


def curate_file(
    input_path: Path,
    out_path: Path | None = None,
    api_key: str | None = None,
    model: str = "gemini-2.5-flash",
    focus: str | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Curate blocks.json and optionally write the guide to disk."""

    curated = curate_guide(
        input_path=input_path,
        api_key=api_key,
        model=model,
        focus=focus,
        custom_prompt=custom_prompt,
    )

    if out_path:
        out_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        out_path.write_text(
            curated,
            encoding="utf-8",
        )

    return curated

# ---------------------------------------------------------------------------

# CLI

# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "FlowScope AI Curator - convert blocks.json "
            "into a clean technical guide using Gemini."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to FlowScope blocks.json",
    )

    parser.add_argument(
        "--out",
        "-o",
        type=Path,
        help="Path to save the curated Markdown guide",
    )

    parser.add_argument(
        "--model",
        "-m",
        default="gemini-2.5-flash",
        help="Gemini model to use",
    )

    parser.add_argument(
        "--focus",
        "-f",
        help=(
            "Optional objective or focus to guide the curation"
        ),
    )

    parser.add_argument(
        "--prompt",
        "-p",
        dest="custom_prompt",
        help=(
            "Custom instruction to send to Gemini for this curation run"
        ),
    )

    parser.add_argument(
        "--api-key",
        "-k",
        help=(
            "Gemini API key "
            "(or set GEMINI_API_KEY environment variable)"
        ),
    )

    args = parser.parse_args()

    try:
        result = curate_file(
            input_path=args.input,
            out_path=args.out,
            api_key=args.api_key,
            model=args.model,
            focus=args.focus,
            custom_prompt=args.custom_prompt,
        )

        if args.out:
            print("Curated guide successfully written to:")
            print(f"  {args.out}")
        else:
            print(result)

    except Exception as exc:
        sys.exit(f"Error curating guide: {exc}")


if __name__ == "__main__":
    main()