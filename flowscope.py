"""FlowScope - Terminal Session Recorder and Guide Generator.

FlowScope pipeline:

    Phase 1: Recorder
        ↓
    session.json
        ↓
    Phase 2: Parser
        ↓
    reconstructed terminal data
        ↓
    Phase 3: Heuristics
        ↓
    blocks.json
        ├──────────────→ Phase 4: Markdown Export
        │                         ↓
        │                    transcript.md
        │
        └──────────────→ Phase 5: AI Curator
                                  ↓
                             curated.md
                                  ↓
                           Phase 6: PDF Export
                                  ↓
                               guide.pdf

The recorded session and blocks.json are treated as source artifacts.
AI curation produces a separate guide and does not modify the source data.
"""

from __future__ import annotations

import codecs
import errno
import json
import os
import re
import select
import signal
import struct
import sys
import time
import uuid

try:
    import fcntl
    import pty
    import termios
except ImportError:
    fcntl = None  # type: ignore
    pty = None  # type: ignore
    termios = None  # type: ignore

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

try:
    from rich.console import Console
    import typer
except ImportError:
    def _find_venv() -> Path | None:
        """Find a project virtual environment."""

        curr = Path(__file__).resolve().parent

        for path in [curr, *curr.parents]:
            candidate_dir = path / ".venv"

            if not candidate_dir.is_dir():
                continue

            subdir = (
                "Scripts"
                if sys.platform == "win32"
                else "bin"
            )

            for executable in ["python.exe", "python"]:
                executable_path = (
                    candidate_dir
                    / subdir
                    / executable
                )

                if executable_path.exists():
                    return executable_path

        return None

    venv_python = _find_venv()

    if (
        venv_python
        and sys.executable != str(venv_python.resolve())
    ):
        os.execv(
            str(venv_python),
            [str(venv_python)] + sys.argv,
        )

    else:
        sys.exit(
            "Error: 'typer' and 'rich' are required. "
            "Run FlowScope inside its virtual environment."
        )


# ---------------------------------------------------------------------------
# CLI application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="flowscope",
    help="FlowScope - Terminal Session Recorder",
    add_completion=False,
)

console = Console()

READ_CHUNK = 4096

# Matches runs of characters that aren't safe/readable in a filename, so a
# user-supplied --title can be folded into the session filename without
# risking path separators, spaces, or other filesystem-unfriendly bytes.
_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify(text: str, max_length: int = 60) -> str:
    """Turn an arbitrary title into a short, filesystem-safe slug.

    Returns "" if nothing usable is left after cleaning (e.g. the title
    was pure punctuation/whitespace), so callers can fall back cleanly.
    """

    slug = _SLUG_RE.sub("-", text.strip()).strip("-")

    return slug[:max_length].strip("-")


def _unique_session_dir(day_dir: Path, base_name: str) -> tuple[Path, str]:
    """Pick a session folder name under `day_dir`, avoiding collisions.

    Just returns `base_name` as-is in the (overwhelmingly common) case
    where nothing by that name exists yet under the day folder. Only
    falls back to `base_name-2`, `base_name-3`, ... if a same-day
    session already used that exact name -- so names stay clean and
    title-only unless a real collision forces a disambiguator.
    """

    candidate = base_name
    n = 2

    while (day_dir / candidate).exists():
        candidate = f"{base_name}-{n}"
        n += 1

    return day_dir / candidate, candidate


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """A single input or output event from the terminal session."""

    time: str
    type: str
    text: str


@dataclass
class Session:
    """Raw FlowScope terminal session."""

    session_id: str
    started_at: str
    shell: str
    columns: int = 80
    title: str = ""
    ended_at: str = ""
    duration: float = 0.0
    events: list[Event] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "shell": self.shell,
            "columns": self.columns,
            "title": self.title,
            "events": [
                asdict(event)
                for event in self.events
            ],
            "ended_at": self.ended_at,
            "duration": self.duration,
        }


# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------

def _get_size() -> tuple[int, int]:
    """Return terminal size as (rows, columns).

    Falls back to 24x80 both when the OS call fails outright (no
    controlling terminal) and when it "succeeds" but reports a
    degenerate 0x0 size (seen on some ptys before a size has been set,
    e.g. under certain multiplexers/CI runners) -- a 0-column screen
    silently breaks pyte's line reconstruction downstream instead of
    raising, so it has to be caught here.
    """

    try:
        size = os.get_terminal_size()

        if size.lines <= 0 or size.columns <= 0:
            return 24, 80

        return size.lines, size.columns

    except OSError:
        return 24, 80


def _set_pty_size(
    fd: int,
    rows: int,
    cols: int,
) -> None:
    """Set the size of the pseudo-terminal."""

    winsize = struct.pack(
        "HHHH",
        rows,
        cols,
        0,
        0,
    )

    fcntl.ioctl(
        fd,
        termios.TIOCSWINSZ,
        winsize,
    )


# ---------------------------------------------------------------------------
# Phase 1 - Recorder
# ---------------------------------------------------------------------------

def _get_windows_shell() -> list[str]:
    """Return the Windows shell command used to host the recording.

    Prefer PowerShell 7 when available, then Windows PowerShell, then cmd.exe.
    The returned value is a command + arguments list suitable for Popen.
    """

    if os.environ.get("COMSPEC"):
        cmd = os.environ["COMSPEC"]

    else:
        cmd = "cmd.exe"

    # PowerShell 7 is nicer for interactive use and is commonly installed.
    for candidate in ("pwsh.exe", "powershell.exe"):
        try:
            import shutil

            found = shutil.which(candidate)
        except Exception:
            found = None

        if found:
            # -NoLogo/-NoProfile reduce startup noise and make recordings cleaner.
            return [
                found,
                "-NoLogo",
                "-NoProfile",
            ]

    return [cmd]


def _record_windows_session(
    session: Session,
    session_path: Path,
    started_dt: datetime,
) -> Path:
    """Record a Windows shell using redirected pipes.

    Windows does not expose the POSIX PTY interface used by the Unix
    recorder.  The shell is therefore started with redirected stdin/stdout.

    Important detail:
    PowerShell/cmd echo commands that arrive through redirected stdin.
    Those echoes are *display output*, but they are not terminal output that
    FlowScope should record because the command is already stored as an
    ``input`` event.  The recorder below removes only the shell's immediate
    echo of each command from the output stream.  This prevents JSON from
    containing:

        input:  "git status\\n"
        output: "g"
        output: "it status\\n"

    while preserving the actual command result.
    """

    import collections
    import subprocess
    import threading

    shell_cmd = _get_windows_shell()
    session.shell = shell_cmd[0]

    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        process = subprocess.Popen(
            shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            bufsize=0,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Could not start Windows shell ({shell_cmd[0]}): {exc}"
        ) from exc

    output_decoder = codecs.getincrementaldecoder("utf-8")(
        errors="replace"
    )

    # Commands written to the redirected shell stdin are echoed by the
    # shell.  Keep them here so the output reader can remove that echo.
    pending_echoes: collections.deque[str] = collections.deque()
    echo_lock = threading.Lock()

    # Text waiting to be classified as either an input echo or genuine
    # command output.  This is necessary because one OS read may contain
    # only "g" while the next contains "it status\\n".
    echo_buffer = ""

    def add_input_echo(text: str) -> None:
        with echo_lock:
            pending_echoes.append(text)

    def remove_command_echo(text: str) -> str:
        """Remove only known shell command echoes from the beginning of text."""

        nonlocal echo_buffer

        with echo_lock:
            echo_buffer += text

            while pending_echoes:
                expected = pending_echoes[0]

                # Shells normally echo exactly what was sent, but normalize
                # CRLF/LF so the comparison works for both PowerShell and cmd.
                current = echo_buffer.replace("\r\n", "\n")
                expected_normalized = expected.replace("\r\n", "\n")

                if current.startswith(expected_normalized):
                    # If the complete echo has not arrived yet, wait for the
                    # next read instead of leaking a partial "g" into output.
                    if len(current) < len(expected_normalized):
                        return ""

                    echo_buffer = current[len(expected_normalized):]
                    pending_echoes.popleft()
                    continue

                # The beginning does not match the pending command.  It is
                # real shell output, so flush it.
                break

            # If the buffer is only a partial prefix of the pending command,
            # hold it until the next read.
            if pending_echoes:
                expected = pending_echoes[0].replace("\r\n", "\n")
                current = echo_buffer.replace("\r\n", "\n")

                if expected.startswith(current):
                    return ""

            result = echo_buffer
            echo_buffer = ""
            return result

    stop_reader = threading.Event()

    def record_output(text: str) -> None:
        if not text:
            return

        clean_text = remove_command_echo(text)

        if clean_text:
            session.events.append(
                Event(
                    time=datetime.now(timezone.utc).isoformat(),
                    type="output",
                    text=clean_text,
                )
            )

    def read_output() -> None:
        nonlocal echo_buffer
        try:
            while not stop_reader.is_set():
                data = process.stdout.read(READ_CHUNK)  # type: ignore[union-attr]

                if not data:
                    break

                # Decode once, then remove only the echoed command.
                text = output_decoder.decode(data)
                clean_text = remove_command_echo(text)

                if clean_text:
                    try:
                        sys.stdout.write(clean_text)
                        sys.stdout.flush()
                    except (BrokenPipeError, OSError):
                        pass

                    session.events.append(
                        Event(
                            time=datetime.now(timezone.utc).isoformat(),
                            type="output",
                            text=clean_text,
                        )
                    )

        except (OSError, ValueError):
            pass

        finally:
            try:
                final_text = output_decoder.decode(b"", final=True)

                if final_text:
                    clean_text = remove_command_echo(final_text)

                    if clean_text:
                        try:
                            sys.stdout.write(clean_text)
                            sys.stdout.flush()
                        except (BrokenPipeError, OSError):
                            pass

                        session.events.append(
                            Event(
                                time=datetime.now(timezone.utc).isoformat(),
                                type="output",
                                text=clean_text,
                            )
                        )
            except Exception:
                pass

            # Anything still in echo_buffer is genuine output only if it
            # could not possibly complete a known command echo.  In normal
            # operation this should be empty.
            with echo_lock:
                if echo_buffer and not pending_echoes:
                    leftover = echo_buffer
                    echo_buffer = ""
                else:
                    leftover = ""

            if leftover:
                try:
                    sys.stdout.write(leftover)
                    sys.stdout.flush()
                except (BrokenPipeError, OSError):
                    pass

                session.events.append(
                    Event(
                        time=datetime.now(timezone.utc).isoformat(),
                        type="output",
                        text=leftover,
                    )
                )

    reader = threading.Thread(
        target=read_output,
        name="flowscope-windows-output",
        daemon=True,
    )
    reader.start()

    console.print(
        "[dim]FlowScope is recording this Windows shell. "
        "Type commands normally and press Enter. "
        "Type `exit` to stop.[/dim]"
    )

    try:
        while process.poll() is None:
            try:
                line = input()
            except EOFError:
                break
            except KeyboardInterrupt:
                # Ctrl+C here belongs to the outer Python recorder.  Ask
                # the child shell to stop without writing ^C into the JSON.
                try:
                    process.send_signal(subprocess.CTRL_BREAK_EVENT)
                except (AttributeError, OSError, ValueError):
                    try:
                        process.terminate()
                    except (OSError, ValueError):
                        pass
                break

            if process.poll() is not None:
                break

            if process.stdin is None:
                break

            data = (
                line + "\n"
            ).encode(
                getattr(sys.stdin, "encoding", None) or "utf-8",
                errors="replace",
            )

            # Register the expected shell echo BEFORE writing the command.
            add_input_echo(line + "\n")

            try:
                process.stdin.write(data)
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                break

            session.events.append(
                Event(
                    time=datetime.now(timezone.utc).isoformat(),
                    type="input",
                    text=line + "\n",
                )
            )

            # `exit` should finish immediately instead of waiting for the
            # outer recorder's cleanup timeout.
            if line.strip().lower() in {"exit", "logout"}:
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    pass
                break

    finally:
        stop_reader.set()

        if process.poll() is None:
            try:
                if process.stdin is not None:
                    process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

            try:
                process.terminate()
            except (OSError, ValueError):
                pass

        try:
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except (OSError, ValueError):
                pass

            try:
                process.wait(timeout=1)
            except Exception:
                pass

        reader.join(timeout=2)

    ended_dt = datetime.now(timezone.utc)

    session.ended_at = ended_dt.isoformat()
    session.duration = (ended_dt - started_dt).total_seconds()

    session_path.write_text(
        json.dumps(
            session.to_dict(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return session_path


def _record_unix_session(
    session: Session,
    session_path: Path,
    shell: str,
    rows: int,
    cols: int,
    started_dt: datetime,
) -> Path:
    """Record a Unix session using the original PTY implementation."""

    if (
        pty is None
        or termios is None
        or fcntl is None
    ):
        raise RuntimeError(
            "Unix PTY support is unavailable. "
            "Install/use a Unix environment such as Linux or macOS."
        )

    is_tty = sys.stdin.isatty()
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()

    old_settings = (
        termios.tcgetattr(stdin_fd)
        if is_tty
        else None
    )

    pid, master_fd = pty.fork()

    if pid == 0:
        os.execvp(shell, [shell])
        os._exit(1)

    _set_pty_size(master_fd, rows, cols)

    if is_tty:
        import tty
        tty.setraw(stdin_fd)

    def _handle_winch(signum, frame) -> None:
        try:
            new_rows, new_cols = _get_size()
            _set_pty_size(master_fd, new_rows, new_cols)
        except OSError:
            pass

    have_winch = hasattr(signal, "SIGWINCH")
    old_winch_handler = (
        signal.signal(signal.SIGWINCH, _handle_winch)
        if have_winch
        else None
    )

    input_decoder = codecs.getincrementaldecoder("utf-8")(
        errors="replace"
    )
    output_decoder = codecs.getincrementaldecoder("utf-8")(
        errors="replace"
    )

    console.print(
        "[dim]FlowScope is recording this session. "
        "Exit the shell (e.g. `exit` or Ctrl-D) to stop.[/dim]"
    )

    try:
        while True:
            try:
                readable, _, _ = select.select(
                    [stdin_fd, master_fd],
                    [],
                    [],
                    0.25,
                )
            except InterruptedError:
                continue
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise

            if master_fd in readable:
                try:
                    data = os.read(master_fd, READ_CHUNK)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        data = b""
                    else:
                        raise

                if not data:
                    break

                os.write(stdout_fd, data)

                text = output_decoder.decode(data)
                if text:
                    session.events.append(
                        Event(
                            time=datetime.now(timezone.utc).isoformat(),
                            type="output",
                            text=text,
                        )
                    )

            if stdin_fd in readable:
                try:
                    data = os.read(stdin_fd, READ_CHUNK)
                except OSError:
                    data = b""

                if data:
                    os.write(master_fd, data)

                    text = input_decoder.decode(data)
                    if text:
                        session.events.append(
                            Event(
                                time=datetime.now(timezone.utc).isoformat(),
                                type="input",
                                text=text,
                            )
                        )

            try:
                waited_pid, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break

            if waited_pid == pid:
                break

    finally:
        if have_winch and old_winch_handler is not None:
            signal.signal(signal.SIGWINCH, old_winch_handler)

        if old_settings is not None:
            termios.tcsetattr(
                stdin_fd,
                termios.TCSADRAIN,
                old_settings,
            )

        try:
            os.close(master_fd)
        except OSError:
            pass

    ended_dt = datetime.now(timezone.utc)

    session.ended_at = ended_dt.isoformat()
    session.duration = (ended_dt - started_dt).total_seconds()

    session_path.write_text(
        json.dumps(
            session.to_dict(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return session_path


def record_session(
    sessions_dir: Path = Path("sessions"),
    title: str | None = None,
) -> Path:
    """Record an interactive terminal session on Windows, Linux, or macOS.

    Windows uses a subprocess pipe recorder because POSIX PTYs are not
    available there.  Unix systems continue to use the original PTY path.

    All platforms write the same session.json structure, so the parser,
    heuristics, Markdown export, AI curator, and PDF export remain unchanged.
    """

    session_id = str(uuid.uuid4())

    started_dt = datetime.now(timezone.utc)

    date_str = started_dt.strftime("%Y-%m-%d")

    title = title or ""
    slug = _slugify(title)

    base_name = slug or f"session-{session_id[:8]}"

    session_dir, session_name = _unique_session_dir(
        sessions_dir / date_str,
        base_name,
    )

    session_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    session_path = session_dir / f"{session_name}.json"

    rows, cols = _get_size()

    # On Windows, do not use $SHELL, /bin/bash, pty, termios, or fcntl.
    if sys.platform == "win32":
        shell_cmd = _get_windows_shell()
        shell_name = shell_cmd[0]

        session = Session(
            session_id=session_id,
            started_at=started_dt.isoformat(),
            shell=shell_name,
            columns=cols,
            title=title,
        )

        return _record_windows_session(
            session=session,
            session_path=session_path,
            started_dt=started_dt,
        )

    # Linux/macOS: preserve the PTY implementation.
    shell = os.environ.get(
        "SHELL",
        "/bin/bash",
    )

    session = Session(
        session_id=session_id,
        started_at=started_dt.isoformat(),
        shell=shell,
        columns=cols,
        title=title,
    )

    return _record_unix_session(
        session=session,
        session_path=session_path,
        shell=shell,
        rows=rows,
        cols=cols,
        started_dt=started_dt,
    )


# ---------------------------------------------------------------------------
# Pipeline glue (Phases 2-6)
# ---------------------------------------------------------------------------

def _run_guide_pipeline(
    session_path: Path,
    api_key: str | None = None,
    model: str = "gemini-3.6-flash",
    focus: str | None = None,
) -> None:
    """Run Phases 2-6 on a recorded session: parse -> blocks -> transcript
    -> AI-curated guide -> PDF. Each artifact is written next to the
    session file and never overwrites the source session/blocks data."""

    # Imported lazily so `flowscope record --no-guide` and plain
    # recording don't require pyte/reportlab/etc. to be installed.
    from flowscope_heuristics import session_blocks_payload
    from flowscope_markdown import render_markdown
    from flowscope_curator import curate_file
    from flowscope_pdf import render_markdown_to_pdf

    stem = session_path.stem

    blocks_path = session_path.with_name(f"{stem}.blocks.json")
    transcript_path = session_path.with_name(f"{stem}.transcript.md")
    curated_path = session_path.with_name(f"{stem}.guide.md")
    pdf_path = session_path.with_name(f"{stem}.guide.pdf")

    console.print("[dim]Parsing session and grouping command blocks...[/dim]")

    payload = session_blocks_payload(session_path)
    blocks_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"[green]Blocks:[/green]     {blocks_path}")

    transcript = render_markdown(blocks_path)
    transcript_path.write_text(transcript, encoding="utf-8")
    console.print(f"[green]Transcript:[/green] {transcript_path}")

    console.print(
        "[dim]Sending session data to Gemini to identify the goal and "
        "draft an efficient guide...[/dim]"
    )

    try:
        curated = curate_file(
            input_path=blocks_path,
            out_path=curated_path,
            api_key=api_key,
            model=model,
            focus=focus,
        )
    except Exception as exc:
        console.print(f"[red]AI curation failed:[/red] {exc}")
        console.print(
            "[dim]The transcript above is unaffected. Retry curation "
            f"later with: flowscope curate {blocks_path}[/dim]"
        )
        return

    console.print(f"[green]Curated guide:[/green] {curated_path}")

    render_markdown_to_pdf(curated, pdf_path)
    console.print(f"[green]PDF guide:[/green]    {pdf_path}")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@app.command()
def record(
    sessions_dir: Path = typer.Option(
        Path("sessions"),
        "--dir",
        "-d",
        help="Directory to store the recorded session.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        "-t",
        help="Optional title for the session, folded into the filename and stored in session.json.",
    ),
    guide: bool = typer.Option(
        True,
        "--guide/--no-guide",
        help="Generate parse/blocks/transcript/AI guide/PDF right after recording.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Gemini API key (or set GEMINI_API_KEY).",
    ),
    model: str = typer.Option(
        "gemini-3.6-flash",
        "--model",
        "-m",
        help="Gemini model to use for curation.",
    ),
    focus: str | None = typer.Option(
        None,
        "--focus",
        "-f",
        help="Optional hint about the goal of the session, to help curation.",
    ),
) -> None:
    """Record a terminal session, then (by default) turn it into a guide."""

    try:
        session_path = record_session(sessions_dir=sessions_dir, title=title)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Session recorded:[/green] {session_path}")

    if guide:
        _run_guide_pipeline(
            session_path,
            api_key=api_key,
            model=model,
            focus=focus,
        )
    else:
        console.print(
            f"[dim]Run `flowscope guide {session_path}` "
            "whenever you're ready to generate the guide.[/dim]"
        )


@app.command()
def guide(
    session_path: Path = typer.Argument(
        ...,
        help="Path to a recorded session.json.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Gemini API key (or set GEMINI_API_KEY).",
    ),
    model: str = typer.Option(
        "gemini-3.6-flash",
        "--model",
        "-m",
        help="Gemini model to use for curation.",
    ),
    focus: str | None = typer.Option(
        None,
        "--focus",
        "-f",
        help="Optional hint about the goal of the session, to help curation.",
    ),
) -> None:
    """Run the full Phase 2-6 pipeline on an existing recorded session."""

    if not session_path.exists():
        console.print(f"[red]Session file not found:[/red] {session_path}")
        raise typer.Exit(code=1)

    _run_guide_pipeline(
        session_path,
        api_key=api_key,
        model=model,
        focus=focus,
    )


@app.command()
def curate(
    blocks_path: Path = typer.Argument(
        ...,
        help="Path to a blocks.json produced by the heuristics phase.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Where to write the curated Markdown guide.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Gemini API key (or set GEMINI_API_KEY).",
    ),
    model: str = typer.Option(
        "gemini-3.6-flash",
        "--model",
        "-m",
        help="Gemini model to use for curation.",
    ),
    focus: str | None = typer.Option(
        None,
        "--focus",
        "-f",
        help="Optional hint about the goal of the session, to help curation.",
    ),
) -> None:
    """Send an existing blocks.json to Gemini and print/save the curated guide."""

    from flowscope_curator import curate_file

    try:
        curated = curate_file(
            input_path=blocks_path,
            out_path=out,
            api_key=api_key,
            model=model,
            focus=focus,
        )
    except Exception as exc:
        console.print(f"[red]AI curation failed:[/red] {exc}")
        raise typer.Exit(code=1)

    if out:
        console.print(f"[green]Curated guide written to:[/green] {out}")
    else:
        console.print(curated)


if __name__ == "__main__":
    app()