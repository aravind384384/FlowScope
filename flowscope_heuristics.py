"""FlowScope Phase 3 - Heuristics.

Groups the Parser's flat list of reconstructed lines into command blocks:
{prompt, command, output}. This is what answers "what produced this
output" -- the Parser intentionally doesn't know, because deciding what
counts as a command shouldn't require hardcoding a shell's prompt format.

Core heuristic:
    A line is a *command* line if a human was actually pressing keys
    while that row was being built; it's an *output* line if nothing was
    typed during that window. This comes straight from the raw log's
    `input` events and doesn't need to know anything about PS1, bash vs.
    zsh, colors, etc. -- it works the same way regardless of prompt
    style.

    Once lines are tagged, consecutive output lines are attached to the
    nearest preceding command line to form a block.

Secondary heuristic (best-effort, documented limitation below):
    For a command line's raw text (e.g. "user@host:~$ echo hi"), we
    split off the "command" part by finding the *last* occurrence of a
    common shell prompt terminator ($, #, %, >) followed by whitespace.
    This works for typical prompts but can misfire if the command text
    itself contains one of those characters followed by a space before
    the real prompt terminator (e.g. weird edge cases are more likely
    than the prompt itself containing one). When it can't confidently
    split, the whole line is returned as `command` with an empty
    `prompt`, rather than guessing wrong.

Interactive-session heuristic (this module's third pass):
    Full-screen programs (vim, top, less, tmux, ...) redraw the screen
    constantly, and the user is typically pressing keys the entire
    time. Fed through the core per-line heuristic above, that looks
    like an unbroken flood of "command lines" -- one new (bogus) block
    per redrawn row -- and whatever ends up in `output` is a jumble of
    cursor-repositioned fragments, not real output. Trying to line-diff
    or otherwise reconstruct that content is what garbles it.

    Instead of reconstructing it, we detect these sessions and collapse
    them into a single opaque `block_type="interactive"` block, using
    two independent signals combined:

      1. Alt-screen escape codes (DEC private modes 47/1047/1049) in
         the raw output stream. This is the precise signal -- programs
         that switch to the alternate screen buffer bracket the whole
         session with an exact enter/exit escape, so we get exact
         start/end timestamps straight from the terminal protocol
         itself, independent of anything the per-line/per-command
         heuristics above are doing (and their noise inside the span).

      2. A small table of known full-screen program names (vim, less,
         top, nano, ...), matched against the launching command. This
         catches programs that don't use the alternate screen buffer
         (e.g. nano, by default) where signal #1 never fires. Without
         an escape-coded boundary, the span end is inferred as "the
         next block that still looks like a genuine shell prompt" --
         weaker than signal #1, and documented as such below.

    Once a span is found, every raw *output* event inside it is kept
    verbatim in `raw_output` on the collapsed block -- nothing is
    dropped -- while `output` gets one short human-readable placeholder
    line so downstream phases (Markdown export, AI curation) have
    something sane to render without needing to understand the new
    fields.

    Deliberately NOT attempted here: diffing the filesystem around an
    editor session (e.g. showing what a vim invocation actually changed
    in the edited file) to give interactive *editor* blocks a real
    summary instead of a placeholder. That's a natural follow-up but a
    separate piece of work -- it needs before/after file state, which
    this module has no access to -- and is left for later rather than
    bolted on here.

Requires: flowscope_parser.py (Phase 2) in the same directory.
"""

from __future__ import annotations

import bisect
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from flowscope_parser import parse_session, ParsedSession, ParsedLine

# Matches "...<prompt-terminator><whitespace><command>" using the LAST
# occurrence of a terminator char, since prompts commonly end in one of
# these followed by a space before the typed command begins.
_PROMPT_SPLIT_RE = re.compile(r"^(.*[#$%>])\s+(.*)$")

# Sentinel used when comparing against an open-ended (never-closed) span,
# so plain string comparison on ISO timestamps still works.
_FAR_FUTURE = "9999-12-31T23:59:59+00:00"

# DEC private modes for the alternate screen buffer. 'h' = set (enter),
# 'l' = reset (leave). Covers the three variants terminals/terminfo
# entries actually use in the wild (1049 saves/restores cursor too;
# 47/1047 are older equivalents without that).
_ALT_SCREEN_RE = re.compile(r"\x1b\[\?(?:47|1047|1049)([hl])")

# First-token program names known to take over the whole screen. Not
# exhaustive -- extend as needed. Deliberately excludes REPLs (python,
# node, etc.): those scroll normally and their output is real content,
# not a full-screen redraw, so the base per-line heuristic handles them
# fine on its own.
_KNOWN_TUI_COMMANDS = {
    "vim", "vi", "nvim", "view", "nvi",
    "nano", "pico", "emacs",
    "less", "more", "most", "man",
    "top", "htop", "btop", "atop", "glances", "iotop", "iftop", "nethogs",
    "watch",
    "tmux", "screen",
    "mc", "ranger", "nnn", "lf", "vifm",
    "tig", "lazygit", "lazydocker", "k9s",
    "ncdu",
    "nmtui", "alsamixer",
    "fzf",
}

# Wrapper commands whose *next* token is the program that actually
# matters (e.g. "sudo vim /etc/hosts" is a vim session, not a "sudo"
# one). Also skips leading VAR=value assignments.
_WRAPPER_COMMANDS = {"sudo", "doas", "env", "nice", "ionice", "time"}


@dataclass
class CommandBlock:
    line_index: int       # index of the command line in the parsed session
    prompt: str             # best-effort prompt text (may be empty if we couldn't split it)
    command: str             # best-effort typed command (falls back to the full line)
    output: list[str]         # lines produced in response, in order
    started_at: str            # timestamp the command line was finalized (Enter pressed)
    ended_at: str                # timestamp of the last associated output line
    block_type: str = "command"                # "command" | "interactive"
    interactive_program: str | None = None      # best-effort program name, e.g. "vim"
    interactive_trigger: str | None = None      # "alt-screen" | "known-command" | "alt-screen+known-command"
    raw_output: str | None = None               # verbatim captured text for interactive blocks (escape codes and all) -- kept so nothing is lost even though `output` only holds a placeholder

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _AltScreenSpan:
    start: str
    end: str  # "" means the session ended before the matching exit fired


@dataclass
class _InteractiveSpan:
    start: str
    end: str  # "" means open-ended (ran to end of session)
    program: str | None
    trigger: str  # "alt-screen" | "known-command" | "alt-screen+known-command"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _line_has_input_activity(
    window_start: str, window_end: str, input_events: list[dict]
) -> bool:
    start, end = _parse_ts(window_start), _parse_ts(window_end)
    for ev in input_events:
        t = _parse_ts(ev["time"])
        if start < t <= end:
            return True
    return False


def _split_prompt_and_command(text: str) -> tuple[str, str]:
    m = _PROMPT_SPLIT_RE.match(text)
    if m:
        return m.group(1), m.group(2)
    return "", text


def _command_program(command: str) -> str | None:
    """Best-effort extraction of the "real" program from a typed command
    line: skips wrapper commands (sudo, env, ...) and leading VAR=value
    assignments, then strips any path prefix off the remaining token."""
    tokens = command.strip().split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            i += 1
            continue
        if tok in _WRAPPER_COMMANDS:
            i += 1
            continue
        return Path(tok).name
    return None


def classify_lines(
    session_path: Path, raw: dict | None = None
) -> tuple[ParsedSession, list[bool]]:
    """Returns the parsed session plus a parallel list of booleans:
    True where a line had input activity (a "command" line), False
    where it was pure program output."""
    if raw is None:
        raw = json.loads(session_path.read_text(encoding="utf-8"))
    input_events = [e for e in raw.get("events", []) if e.get("type") == "input"]

    parsed = parse_session(session_path)

    is_command: list[bool] = []
    prev_ts = raw.get("started_at", "")
    for line in parsed.lines:
        is_command.append(_line_has_input_activity(prev_ts, line.timestamp, input_events))
        prev_ts = line.timestamp

    return parsed, is_command


def _find_alt_screen_spans(events: list[dict]) -> list[_AltScreenSpan]:
    """Scan raw *output* events for DEC alt-screen-buffer escape codes
    and return the [enter, exit) time spans. Depth-counted so a nested
    enter/exit (e.g. vim launched from inside tmux, both of which use
    the alternate screen) doesn't close the span early -- only a return
    to depth 0 does.

    Matched against the concatenation of all output events' raw text
    rather than event-by-event, since a single escape sequence can land
    split across two PTY reads (each read is capped at 4KB) -- matching
    per-event would silently miss those.
    """
    output_events = [e for e in events if e.get("type") == "output"]
    if not output_events:
        return []

    offsets: list[int] = []
    parts: list[str] = []
    pos = 0
    for ev in output_events:
        offsets.append(pos)
        text = ev.get("text", "")
        parts.append(text)
        pos += len(text)
    full_text = "".join(parts)

    def _time_at(offset: int) -> str:
        idx = bisect.bisect_right(offsets, offset) - 1
        idx = max(0, min(idx, len(output_events) - 1))
        return output_events[idx]["time"]

    spans: list[_AltScreenSpan] = []
    depth = 0
    open_start: str | None = None

    for m in _ALT_SCREEN_RE.finditer(full_text):
        mode = m.group(1)
        t = _time_at(m.start())
        if mode == "h":
            if depth == 0:
                open_start = t
            depth += 1
        else:
            if depth > 0:
                depth -= 1
                if depth == 0 and open_start is not None:
                    spans.append(_AltScreenSpan(start=open_start, end=t))
                    open_start = None

    # Recording stopped (or the shell was killed) while still in the
    # alternate screen -- keep the span, left open, rather than
    # dropping it because there was no matching exit code.
    if depth > 0 and open_start is not None:
        spans.append(_AltScreenSpan(start=open_start, end=""))

    return spans


def _label_alt_screen_spans(
    alt_spans: list[_AltScreenSpan], blocks: list[CommandBlock]
) -> list[_InteractiveSpan]:
    """Attach a best-effort program name to each alt-screen span, taken
    from whichever command block most recently started before it."""
    labeled: list[_InteractiveSpan] = []
    for a in alt_spans:
        program: str | None = None
        for block in blocks:
            if block.started_at <= a.start:
                program = _command_program(block.command) or program
            else:
                break
        labeled.append(
            _InteractiveSpan(start=a.start, end=a.end, program=program, trigger="alt-screen")
        )
    return labeled


def _find_known_command_spans(
    blocks: list[CommandBlock], alt_spans: list[_AltScreenSpan]
) -> list[_InteractiveSpan]:
    """Fallback for full-screen programs that don't use the alternate
    screen buffer (e.g. nano, by default): open a span when the typed
    command matches the known-TUI table, and close it at the next block
    that still looks like a genuine shell prompt (non-empty `prompt`)
    -- or at the end of the session if the recording stopped first.

    This is weaker than the alt-screen signal: without an escape-coded
    boundary we're relying on the same per-line classifier that gets
    noisy inside interactive sessions to tell us where the "real" next
    prompt is. Commands already covered by an alt-screen span don't
    need this fallback and are skipped here.
    """
    spans: list[_InteractiveSpan] = []

    for i, block in enumerate(blocks):
        program = _command_program(block.command)
        if program not in _KNOWN_TUI_COMMANDS:
            continue
        if any(a.start <= block.started_at < (a.end or _FAR_FUTURE) for a in alt_spans):
            continue  # already handled by the precise alt-screen signal

        end = ""
        for later in blocks[i + 1 :]:
            if later.prompt:
                end = later.started_at
                break

        spans.append(
            _InteractiveSpan(start=block.started_at, end=end, program=program, trigger="known-command")
        )

    return spans


def _merge_spans(spans: list[_InteractiveSpan]) -> list[_InteractiveSpan]:
    """Merge overlapping/touching spans -- e.g. an alt-screen span and a
    known-command span both covering the same vim session -- into one,
    combining their trigger labels instead of double-counting."""
    if not spans:
        return []

    ordered = sorted(spans, key=lambda s: s.start)
    merged = [ordered[0]]

    for s in ordered[1:]:
        last = merged[-1]
        last_end = last.end or _FAR_FUTURE
        if s.start <= last_end:
            new_end = "" if (not last.end or not s.end) else max(last.end, s.end)
            triggers = sorted(set(last.trigger.split("+")) | set(s.trigger.split("+")))
            merged[-1] = _InteractiveSpan(
                start=last.start,
                end=new_end,
                program=last.program or s.program,
                trigger="+".join(triggers),
            )
        else:
            merged.append(s)

    return merged


def _collapse_interactive_spans(
    blocks: list[CommandBlock], spans: list[_InteractiveSpan], events: list[dict]
) -> list[CommandBlock]:
    """Fold every block whose start falls inside an interactive span
    into a single opaque block, carrying the raw output verbatim."""
    if not spans:
        return blocks

    output_events = [e for e in events if e.get("type") == "output"]

    def _raw_text_in(start: str, end: str) -> str:
        end_key = end or _FAR_FUTURE
        return "".join(e.get("text", "") for e in output_events if start <= e["time"] < end_key)

    result: list[CommandBlock] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]

        span = next(
            (s for s in spans if s.start <= block.started_at < (s.end or _FAR_FUTURE)),
            None,
        )

        if span is None:
            result.append(block)
            i += 1
            continue

        end_key = span.end or _FAR_FUTURE
        group: list[CommandBlock] = []
        while i < len(blocks) and span.start <= blocks[i].started_at < end_key:
            group.append(blocks[i])
            i += 1

        span_end = span.end or (group[-1].ended_at if group else span.start)
        raw_output = _raw_text_in(span.start, span_end)

        duration_note = ""
        try:
            secs = (_parse_ts(span_end) - _parse_ts(span.start)).total_seconds()
            duration_note = f", {secs:.1f}s"
        except ValueError:
            pass

        program_label = span.program or "unknown program"
        placeholder = (
            f"[interactive session: {program_label}{duration_note} "
            f"({span.trigger}) -- output omitted here to avoid a garbled "
            f"full-screen redraw; verbatim capture kept in raw_output]"
        )

        result.append(
            CommandBlock(
                line_index=group[0].line_index,
                prompt=group[0].prompt,
                command=group[0].command,
                output=[placeholder],
                started_at=span.start,
                ended_at=span_end,
                block_type="interactive",
                interactive_program=span.program,
                interactive_trigger=span.trigger,
                raw_output=raw_output,
            )
        )

    return result


def build_blocks(session_path: Path) -> list[CommandBlock]:
    raw = json.loads(session_path.read_text(encoding="utf-8"))
    parsed, is_command = classify_lines(session_path, raw=raw)

    blocks: list[CommandBlock] = []
    current: CommandBlock | None = None

    for line, cmd_flag in zip(parsed.lines, is_command):
        if cmd_flag:
            if current is not None:
                blocks.append(current)
            prompt, command = _split_prompt_and_command(line.text)
            current = CommandBlock(
                line_index=line.index,
                prompt=prompt,
                command=command,
                output=[],
                started_at=line.timestamp,
                ended_at=line.timestamp,
            )
        else:
            if current is None:
                # Output with no preceding command in this session (e.g.
                # the initial prompt banner before anything was typed).
                # Skip rather than inventing a fake command line.
                continue
            # The trailing empty row the Parser leaves at the very end
            # of a session is a display artifact, not real output.
            is_trailing_blank = (
                line is parsed.lines[-1] and line.text == ""
            )
            if not is_trailing_blank:
                current.output.append(line.text)
            current.ended_at = line.timestamp

    if current is not None:
        blocks.append(current)

    events = raw.get("events", [])
    alt_spans = _find_alt_screen_spans(events)
    interactive_spans = _merge_spans(
        _label_alt_screen_spans(alt_spans, blocks)
        + _find_known_command_spans(blocks, alt_spans)
    )
    blocks = _collapse_interactive_spans(blocks, interactive_spans, events)

    return blocks


def session_blocks_payload(session_path: Path) -> dict:
    """Self-contained artifact: session metadata + blocks together, so
    downstream phases (Markdown Export, AI Classification, AI Captions)
    can work from this file alone without re-touching the raw session
    log or re-running terminal emulation."""
    parsed = parse_session(session_path)
    blocks = build_blocks(session_path)
    return {
        "session_id": parsed.session_id,
        "shell": parsed.shell,
        "started_at": parsed.started_at,
        "ended_at": parsed.ended_at,
        "duration": parsed.duration,
        "columns": parsed.columns,
        "blocks": [b.to_dict() for b in blocks],
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <session.json> [--out blocks.json]")

    session_path = Path(sys.argv[1])
    out_path = None
    if "--out" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--out") + 1])

    payload = session_blocks_payload(session_path)

    if out_path:
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Blocks written to {out_path}")
    else:
        for b in payload["blocks"]:
            if b["block_type"] == "interactive":
                print(f"$ {b['command']}")
                print(f"  {b['output'][0]}")
            else:
                print(f"$ {b['command']}")
                for line in b["output"]:
                    print(f"  {line}")
            print()


if __name__ == "__main__":
    main()