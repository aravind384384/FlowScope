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

The original session.json and blocks.json are never modified by the AI.
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

Your job is NOT to reproduce the raw transcript.

Your job is to transform the recorded work into a clean, minimal,
step-by-step technical guide that explains the successful procedure.

IMPORTANT PRINCIPLES:

1. IDENTIFY THE CORE GOAL

   Determine what the user was actually trying to accomplish in the
   terminal session.

   The final guide should focus on that goal rather than reproducing
   everything the user typed.

2. REMOVE NOISE

   Omit commands that are not necessary for accomplishing the core goal,
   including when appropriate:

   - ls
   - pwd
   - whoami
   - clear
   - directory navigation used only for inspection
   - repeated inspection commands
   - accidental commands
   - obvious typos
   - failed attempts
   - redundant commands
   - commands unrelated to the final successful procedure

   Do NOT remove a command merely because it looks simple. Keep it if it
   is required for the procedure.

3. HANDLE FAILED ATTEMPTS CAREFULLY

   Prefer the successful procedure.

   Failed attempts should normally be omitted.

   However, if a failure reveals an important prerequisite, configuration
   requirement, or troubleshooting step that is necessary to understand
   the final solution, you may mention it briefly.

4. PRESERVE ACTUAL COMMANDS

   Do not invent commands that were not present in the session unless
   absolutely necessary to make the guide understandable.

   Prefer commands that actually appeared in the recorded session.

   Do not silently replace a recorded command with a different command.

5. CLASSIFY STEPS

   Assign each retained step one of these categories:

   - SETUP
   - DEPENDENCY
   - CONFIG
   - BUILD
   - EXECUTION
   - VERIFICATION
   - CLEANUP

6. EXPLAIN EACH STEP

   For every retained command, provide a concise explanation of:

   - what the command does
   - why the step is necessary

   Do not write long explanations for simple commands.

7. EXPECTED OUTPUT

   Include expected output only when it is useful for confirming that
   the step succeeded.

   Do not reproduce large amounts of terminal output.

8. DO NOT CONFUSE THE TRANSCRIPT WITH THE GUIDE

   The recorded session is evidence of what happened.

   The final guide should represent the useful procedure extracted from
   that session.

9. DO NOT MODIFY THE SOURCE DATA

   The input JSON is historical session data.

   Treat it as read-only.

10. OUTPUT FORMAT

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

   <Concise explanation of what the step does and why it is needed.>

   ```bash
   <command>
````

   <Optional concise expected result if useful.>

## Step 2: <Step Title> [CATEGORY]

...

## Result

   <Brief description of the final successful result.>

Do not include analysis, commentary, JSON, or explanations outside the
Markdown guide.
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
) -> str:
    """Build the complete Gemini prompt."""

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
) -> str:
    """Generate a curated Markdown guide from blocks.json."""

    blocks_json = _load_input(input_path)

    prompt = build_prompt(
        blocks_json=blocks_json,
        focus=focus,
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
) -> str:
    """Curate blocks.json and optionally write the guide to disk."""

    curated = curate_guide(
        input_path=input_path,
        api_key=api_key,
        model=model,
        focus=focus,
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