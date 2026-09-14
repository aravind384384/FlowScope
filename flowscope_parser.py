"""FlowScope Phase 2 - Parser.

Takes a raw session log (per-keystroke input/output events, full of ANSI
escape codes) and replays the `output` stream through a real terminal
emulator to reconstruct what the terminal actually displayed: clean,
plain-text lines.

Why a terminal emulator and not regex/string stripping:
    A session log contains carriage returns that overwrite text in place,
    cursor-positioning escapes, bracketed-paste toggles, color codes, and
    prompt redraws. Stripping ANSI codes with a regex leaves all of that
    *positioning* behavior on the table -- e.g. a line that was typed,
    backspaced over, and retyped would show both versions concatenated
    instead of just the final one. A terminal emulator resolves it the
    same way your real terminal did: by actually interpreting the codes.

Scope / known limitation:
    This assumes a scrolling shell session (the common case: a prompt,
    commands, their output). Full-screen TUI programs (vim, htop, less)
    move the cursor around non-monotonically to redraw a whole viewport,
    which breaks the "cursor moved to a new row -> the row above it is
    finished" heuristic used here for per-line timestamps. The final
    reconstructed *text* is still correct in that case (it's just the
    real terminal state), but per-line timestamps for TUI screens will be
    unreliable. Detecting/handling full-screen apps is future work.

Requires: pip install pyte
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import pyte
except ImportError:  # pragma: no cover
    sys.exit(
        "The 'pyte' package is required for parsing.\n"
        "Install it with: pip install pyte"
    )

DEFAULT_COLUMNS = 80
# Tall enough that a normal recording session never scrolls content off
# pyte's visible screen, so screen.display always holds the full
# transcript at the end. (No scrollback/history buffer is used here for
# that reason -- everything just stays "on screen".)
DEFAULT_SCROLLBACK_ROWS = 20_000


@dataclass
class ParsedLine:
    index: int          # row number in the reconstructed transcript, 0-based
    text: str            # plain text, ANSI/control codes resolved away
    timestamp: str        # best-effort: when this row was first completed

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
            "lines": [l.to_dict() for l in self.lines],
        }

    def as_text(self) -> str:
        """Plain scrollback text, one reconstructed line per row."""
        return "\n".join(l.text for l in self.lines)


def parse_session(session_path: Path, columns: int | None = None) -> ParsedSession:
    data = json.loads(session_path.read_text(encoding="utf-8"))

    # Sessions recorded before dimensions were persisted fall back to a
    # sane default; sessions that do record their pty size use that.
    cols = columns or data.get("columns", DEFAULT_COLUMNS)

    screen = pyte.Screen(cols, DEFAULT_SCROLLBACK_ROWS)
    stream = pyte.Stream(screen)

    finalize_times: dict[int, str] = {}
    last_cursor_y = 0

    for event in data.get("events", []):
        # Only the output stream reflects what was actually displayed.
        # Input events are the raw keystrokes sent -- useful for later
        # phases (e.g. reconstructing exact typing cadence) but replaying
        # them here too would double-feed the terminal, since bash's own
        # echo of the input already comes back through output.
        if event.get("type") != "output":
            continue

        stream.feed(event["text"])

        cur_y = screen.cursor.y
        if cur_y > last_cursor_y:
            # The cursor moved down past one or more rows -- treat each
            # of those rows as "finished" as of this event's timestamp.
            # (See module docstring for why this doesn't hold for
            # full-screen TUI programs.)
            for row in range(last_cursor_y, cur_y):
                finalize_times.setdefault(row, event["time"])
        last_cursor_y = cur_y

    ended_at = data.get("ended_at", "")
    highest_row = max(screen.cursor.y, max(finalize_times.keys(), default=-1))

    lines: list[ParsedLine] = []
    for row in range(0, highest_row + 1):
        # Pull text from the *final* screen state, not a mid-stream
        # snapshot, so a row that got overwritten after our heuristic
        # first "finalized" it still ends up correct.
        text = screen.display[row].rstrip()
        timestamp = finalize_times.get(row, ended_at)
        lines.append(ParsedLine(index=row, text=text, timestamp=timestamp))

    return ParsedSession(
        session_id=data.get("session_id", ""),
        shell=data.get("shell", ""),
        started_at=data.get("started_at", ""),
        ended_at=ended_at,
        duration=data.get("duration", 0.0),
        columns=cols,
        lines=lines,
    )


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <session.json> [--out parsed.json]")

    session_path = Path(sys.argv[1])
    out_path = None
    if "--out" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--out") + 1])

    parsed = parse_session(session_path)

    if out_path:
        out_path.write_text(json.dumps(parsed.to_dict(), indent=2), encoding="utf-8")
        print(f"Parsed session written to {out_path}")
    else:
        print(parsed.as_text())


if __name__ == "__main__":
    main()