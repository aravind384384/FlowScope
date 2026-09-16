"""FlowScope Phase 2 - Parser.

Takes a raw session log and reconstructs clean terminal data.

Linux/macOS:
    Uses pyte to replay a real PTY output stream.

Windows:
    The Recorder uses subprocess pipes rather than ConPTY/pywinpty.
    Therefore the output is normalized directly instead of being replayed
    through a terminal emulator.

The Parser produces the same ParsedSession/ParsedLine structures for both
platforms so downstream phases remain unchanged.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import pyte
except ImportError:
    sys.exit(
        "The 'pyte' package is required for parsing.\n"
        "Install it with: pip install pyte"
    )


DEFAULT_COLUMNS = 80
DEFAULT_SCROLLBACK_ROWS = 20_000


@dataclass
class ParsedLine:
    index: int
    text: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedSession:
    session_id: str
    shell: str
    started_at: str
    ended_at: str
    duration: float
    columns: int
    lines: list[ParsedLine]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "shell": self.shell,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.duration,
            "columns": self.columns,
            "lines": [line.to_dict() for line in self.lines],
        }

    def as_text(self) -> str:
        return "\n".join(line.text for line in self.lines)


# ---------------------------------------------------------------------------
# Windows pipe helpers
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(
    r"""
    \x1B
    (?:
        \[[0-?]*[ -/]*[@-~]
        |
        \][^\x07]*(?:\x07|\x1B\\)
        |
        [()][0-2]
        |
        [=>]
    )
    """,
    re.VERBOSE,
)


_PROMPT_COMMAND_RE = re.compile(
    r"^(.*[#$%>])\s+(.+)$"
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI/control sequences from Windows pipe output."""

    return _ANSI_RE.sub("", text)


def _is_prompt_command_line(line: str) -> bool:
    """Return True when a line looks like a shell prompt followed by a command."""

    return bool(_PROMPT_COMMAND_RE.match(line.strip()))


def _extract_command_from_prompt(line: str) -> str | None:
    """Extract the command portion from a prompt + command line."""

    match = _PROMPT_COMMAND_RE.match(line.strip())

    if not match:
        return None

    command = match.group(2).strip()

    if not command:
        return None

    return command

def _normalize_windows_output(text: str) -> str:
    """Normalize Windows pipe output."""

    text = text.replace("\x00", "")
    text = _strip_ansi(text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    return text


def _parse_windows_pipe_session(
    data: dict,
    columns: int,
) -> ParsedSession:
    """Parse a Windows pipe session.

    The Windows Recorder stores user input separately from shell output.
    We use the input event as the authoritative command and ignore the
    shell's duplicate echo of that command.
    """

    events = data.get("events", [])

    lines: list[ParsedLine] = []

    buffer = ""

    waiting_for_echo = None

    for event in events:

        event_type = event.get("type")

        # ---------------------------------------------------------------
        # USER INPUT
        # ---------------------------------------------------------------

        if event_type == "input":

            command = str(
                event.get("text", "")
            ).rstrip("\r\n")

            if not command:
                continue

            waiting_for_echo = command

            # The prompt is already sitting in the buffer.
            #
            # Example:
            #
            # buffer = "PS C:\\FlowScope> "
            # command = "git status"
            #
            # becomes:
            #
            # "PS C:\\FlowScope> git status"

            if buffer:
                buffer += command

            else:
                buffer = command

            continue

        # ---------------------------------------------------------------
        # OUTPUT
        # ---------------------------------------------------------------

        if event_type != "output":
            continue

        text = str(
            event.get("text", "")
        )

        if not text:
            continue

        text = _normalize_windows_output(text)

        timestamp = event.get(
            "time",
            data.get("ended_at", ""),
        )

        i = 0

        while i < len(text):

            # -----------------------------------------------------------
            # If the shell is echoing the command we just typed,
            # consume exactly that echo.
            # -----------------------------------------------------------

            if waiting_for_echo:

                remaining = text[i:]

                if remaining.startswith(
                    waiting_for_echo
                ):

                    i += len(
                        waiting_for_echo
                    )

                    waiting_for_echo = None

                    continue

                # Echo may be split across multiple output events.
                #
                # Example:
                #
                # event 1 -> "g"
                # event 2 -> "it status\n"
                #
                # If the current output is only a prefix of the command,
                # consume it and wait for the next event.

                if waiting_for_echo.startswith(
                    remaining
                ):

                    waiting_for_echo = (
                        waiting_for_echo[
                            len(remaining):
                        ]
                    )

                    i = len(text)

                    continue

                waiting_for_echo = None

            char = text[i]

            # -----------------------------------------------------------
            # New line
            # -----------------------------------------------------------

            if char == "\n":

                lines.append(
                    ParsedLine(
                        index=len(lines),
                        text=buffer.rstrip(),
                        timestamp=timestamp,
                    )
                )

                buffer = ""

            # -----------------------------------------------------------
            # Backspace
            # -----------------------------------------------------------

            elif char == "\b":

                if buffer:
                    buffer = buffer[:-1]

            else:

                buffer += char

            i += 1

    # ---------------------------------------------------------------
    # Preserve final unfinished line.
    # ---------------------------------------------------------------

    if buffer.strip():

        lines.append(
            ParsedLine(
                index=len(lines),
                text=buffer.rstrip(),
                timestamp=data.get(
                    "ended_at",
                    "",
                ),
            )
        )

    # Remove trailing blank lines.

    while lines and not lines[-1].text:
        lines.pop()

    # Re-index.

    for index, line in enumerate(lines):
        line.index = index

    return ParsedSession(
        session_id=data.get(
            "session_id",
            "",
        ),
        shell=data.get(
            "shell",
            "",
        ),
        started_at=data.get(
            "started_at",
            "",
        ),
        ended_at=data.get(
            "ended_at",
            "",
        ),
        duration=data.get(
            "duration",
            0.0,
        ),
        columns=columns,
        lines=lines,
    )
# ---------------------------------------------------------------------------
# Unix PTY parser
# ---------------------------------------------------------------------------

def _parse_unix_pty_session(
    data: dict,
    columns: int,
) -> ParsedSession:
    """Replay a real Unix PTY through pyte."""

    screen = pyte.Screen(
        columns,
        DEFAULT_SCROLLBACK_ROWS,
    )

    stream = pyte.Stream(screen)

    finalize_times: dict[int, str] = {}
    last_cursor_y = 0

    for event in data.get("events", []):
        if event.get("type") != "output":
            continue

        stream.feed(event.get("text", ""))

        cur_y = screen.cursor.y

        if cur_y > last_cursor_y:
            for row in range(last_cursor_y, cur_y):
                finalize_times.setdefault(
                    row,
                    event.get(
                        "time",
                        data.get("ended_at", ""),
                    ),
                )

        last_cursor_y = cur_y

    ended_at = data.get("ended_at", "")

    highest_row = max(
        screen.cursor.y,
        max(finalize_times.keys(), default=-1),
    )

    lines: list[ParsedLine] = []

    for row in range(0, highest_row + 1):

        text = screen.display[row].rstrip()

        timestamp = finalize_times.get(
            row,
            ended_at,
        )

        lines.append(
            ParsedLine(
                index=row,
                text=text,
                timestamp=timestamp,
            )
        )

    return ParsedSession(
        session_id=data.get("session_id", ""),
        shell=data.get("shell", ""),
        started_at=data.get("started_at", ""),
        ended_at=ended_at,
        duration=data.get("duration", 0.0),
        columns=columns,
        lines=lines,
    )


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------

def parse_session(
    session_path: Path,
    columns: int | None = None,
) -> ParsedSession:
    """Parse a FlowScope session.

    Windows sessions recorded using pipe mode are parsed directly.

    Linux/macOS sessions continue using the original pyte-based
    terminal reconstruction.
    """

    data = json.loads(
        session_path.read_text(
            encoding="utf-8"
        )
    )

    cols = columns or data.get(
        "columns",
        DEFAULT_COLUMNS,
    )

    if sys.platform == "win32":
        return _parse_windows_pipe_session(
            data,
            cols,
        )

    return _parse_unix_pty_session(
        data,
        cols,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:

    if len(sys.argv) < 2:
        sys.exit(
            f"Usage: {sys.argv[0]} "
            "<session.json> [--out parsed.json]"
        )

    session_path = Path(
        sys.argv[1]
    )

    out_path = None

    if "--out" in sys.argv:
        out_path = Path(
            sys.argv[
                sys.argv.index("--out") + 1
            ]
        )

    parsed = parse_session(
        session_path
    )

    if out_path:

        out_path.write_text(
            json.dumps(
                parsed.to_dict(),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"Parsed session written to {out_path}"
        )

    else:
        print(
            parsed.as_text()
        )


if __name__ == "__main__":
    main()