FlowScope

Capture. Reconstruct. Understand.

FlowScope is a terminal-session capture and reconstruction tool with an optional AI-powered documentation pipeline.

It records terminal sessions, reconstructs the useful terminal activity, detects command and interaction blocks, and transforms the session into clean, human-readable documentation.

FlowScope supports Linux, macOS, and Windows. On Unix-like systems it uses the native PTY-based recording approach. On Windows, the recorder uses Windows-compatible process/console handling so the same downstream FlowScope pipeline can be used without requiring WSL.

✨ What FlowScope Does

FlowScope turns a messy terminal session into structured documentation:

Terminal Session
       │
       ▼
┌─────────────────┐
│    Recorder     │  Capture terminal input/output
└────────┬────────┘
         ▼
┌─────────────────┐
│     Parser      │  Reconstruct terminal data
└────────┬────────┘
         ▼
┌─────────────────┐
│    Heuristics   │  Detect commands & interactions
└────────┬────────┘
         ▼
┌─────────────────┐
│ Markdown Export │  Create clean transcript
└────────┬────────┘
         ▼
┌─────────────────┐
│   AI Curator    │  Extract intent & useful steps
└────────┬────────┘
         ▼
┌─────────────────┐
│   PDF Export    │  Generate printable guide
└─────────────────┘

Example

A raw debugging session might contain:

$ systemctl status nginx
...

$ vim /etc/nginx/nginx.conf
...

$ systemctl restart nginx
...

FlowScope can turn that session into a structured guide such as:

Fixing an Nginx Configuration

Open the Nginx configuration file.

Correct the configuration.

Restart the Nginx service.

Verify that the service is running correctly.

The goal is to preserve what actually happened while removing the noise of an interactive terminal session.

🚀 Key Features

🖥️ Cross-platform recording — supports Linux, macOS, and Windows.

🖥️ Terminal-level recording — captures real terminal interaction rather than relying only on shell history.

🔄 Terminal reconstruction — uses pyte on the Unix PTY path to reproduce cursor movement, overwrites, and ANSI escape sequences.

🪟 Windows compatibility — records Windows terminal sessions without requiring WSL.

🧠 Command-block detection — groups related terminal activity into meaningful blocks.

⌨️ Interactive session support — preserves terminal interactions and screen-oriented activity where supported by the recorder.

📝 Deterministic transcripts — converts sessions into clean Markdown transcripts.

🤖 AI-powered curation — optionally uses Gemini to transform raw sessions into concise technical guides.

📄 PDF generation — converts curated guides into printable PDF documents.

📁 Date-based session organization — keeps recorded sessions organized automatically.

🏗️ Architecture

Component

File

Responsibility

Recorder

flowscope.py

Starts the shell and records raw terminal events

Parser

flowscope_parser.py

Reconstructs terminal data and normalizes recorded output

Heuristics

flowscope_heuristics.py

Identifies command blocks and interactive sessions

Markdown Exporter

flowscope_markdown.py

Produces clean session transcripts

AI Curator

flowscope_curator.py

Generates focused technical guides using Gemini

PDF Exporter

flowscope_pdf.py

Converts guides into PDF documents

🔄 Processing Pipeline

Stage

Output

Description

1. Recording

session.json

Raw terminal input/output events

2. Parsing

Reconstructed terminal lines

Normalizes and reconstructs terminal data

3. Heuristics

*.blocks.json

Groups terminal activity into logical blocks

4. Markdown

*.transcript.md

Generates a deterministic transcript

5. AI Curation

*.guide.md

Produces a streamlined technical guide

6. PDF

*.guide.pdf

Creates a printable PDF

A key design goal is that platform-specific recording differences are handled in the Recorder and Parser layers, while the downstream heuristics, Markdown, AI, and PDF stages remain platform-independent.

💻 Requirements

Operating System

FlowScope supports:

Linux ✅

macOS ✅

Windows ✅

Windows

Windows recording is implemented using Windows-compatible process/console handling rather than the Unix-only modules used by the Unix recorder.

WSL is not required.

The Windows environment may use the pywinpty dependency included in requirements.txt for Windows terminal/process support.

Python

Python 3.x

📦 Installation

1. Clone the repository

git clone <repository-url>
cd FlowScope

2. Create a virtual environment

Linux / macOS

python3 -m venv .venv
source .venv/bin/activate

Windows PowerShell

python -m venv prj
.\prj\Scripts\Activate.ps1

If PowerShell blocks script execution for the current session, run:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\prj\Scripts\Activate.ps1

3. Install dependencies

The project dependencies are listed in requirements.txt.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

On Windows, this installs the Windows-specific dependency:

pywinpty==3.0.5

🔑 Gemini API Configuration

AI curation is optional.

If you want to use the Gemini-powered documentation pipeline, configure your API key.

Linux / macOS

export GEMINI_API_KEY="your_gemini_api_key"

Windows PowerShell

$env:GEMINI_API_KEY="your_gemini_api_key"

python-dotenv can also be used to load the key from a .env file.

Tip: Never commit your API key or .env file to Git.

🚀 Quick Start

1. Record a terminal session

Start FlowScope:

flowscope record --title "Fix Nginx Config"

Work normally inside the recorded shell.

When you're finished:

exit

or press:

Ctrl-D

The recorded session is automatically stored under a date-based directory.

Example:

sessions/
└── 2026-09-17/
    └── fix-nginx-config/
        ├── fix-nginx-config.json
        ├── fix-nginx-config.blocks.json
        ├── fix-nginx-config.transcript.md
        ├── fix-nginx-config.guide.md
        └── fix-nginx-config.guide.pdf

The exact files produced depend on the commands/options used during processing.

2. Windows Example

After activating the virtual environment on Windows:

flowscope record --title "Windows Test"

FlowScope records the Windows shell session and stores the resulting session data in the normal sessions/ directory structure.

No WSL installation is required for the Windows recording workflow.

3. Record Without AI

If you only want to capture and process the terminal session without making external AI calls:

flowscope record \
    --no-guide \
    --title "Fix Nginx Config"

This is the recommended option when recording sessions that may contain sensitive information.

🤖 Generate an AI Guide

You can generate a guide from a previously recorded session:

flowscope guide \
    sessions/2026-09-17/fix-nginx-config/fix-nginx-config.json \
    --focus "Document the final working configuration and remove failed attempts"

The --focus option lets you tell the curator what information matters most.

For example:

--focus "Create a step-by-step troubleshooting guide"

or:

--focus "Keep only the commands that solved the problem"

🧠 Curate Existing Block Data

If you already have a blocks.json file, you can run the AI curation step directly:

flowscope curate \
    sessions/2026-09-17/fix-nginx-config/fix-nginx-config.blocks.json \
    --out guide.md

This is useful when you want to regenerate documentation without recording the session again.

🛠️ CLI Reference

Show available commands

flowscope --help

Record a session

flowscope record --title "My Session"

Specify an output directory

flowscope record --dir ./my-sessions

Generate a guide

flowscope guide <session.json>

Provide a custom focus

flowscope guide <session.json> \
    -f "Create a step-by-step runbook"

Curate existing blocks

flowscope curate <blocks.json> --out guide.md

Specify a Gemini model

flowscope record --model gemini-3.6-flash

🔒 Security & Privacy

⚠️ Important: FlowScope records raw terminal input and output.

Because FlowScope operates at the terminal interaction level, recorded sessions may contain sensitive information such as:

Passwords

API keys

Authentication tokens

Environment variables

Private configuration files

Editor contents from vim or nano

Commands containing secrets

Full-screen application buffers

These may be stored in:

session.json
blocks.json

Before using AI curation

Always inspect your recorded files for sensitive information before sending them to an external AI service.

In particular, pay attention to:

block_type: "interactive"

Interactive blocks may contain complete or detailed terminal buffer contents.

Recommended practices

Use test or disposable credentials when possible.

Review session.json before sharing it.

Review blocks.json before AI processing.

Never commit recorded sessions containing secrets to Git.

Add sensitive session directories to .gitignore when appropriate.

Example:

.env
sessions/
*.json

📂 Project Structure

FlowScope/
│
├── flowscope.py
├── flowscope_parser.py
├── flowscope_heuristics.py
├── flowscope_markdown.py
├── flowscope_curator.py
├── flowscope_pdf.py
│
├── sessions/
│   └── YYYY-MM-DD/
│
├── README.md
└── requirements.txt

🎯 Platform-Aware Recording

FlowScope separates recording from the rest of the documentation pipeline.

Unix-like systems

User
 │
 ▼
┌─────────────┐
│    Shell    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     PTY     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Recorder   │
└─────────────┘

The Unix recorder uses the native PTY mechanism and terminal emulation through pyte.

Windows

User
 │
 ▼
┌────────────────┐
│ Windows Shell  │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Windows Process│
│ / Console I/O  │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│    Recorder    │
└────────────────┘

The Windows recorder uses Windows-compatible process/console handling instead of depending on Unix-only modules such as pty, termios, and fcntl.

The resulting session data is passed to the same downstream FlowScope pipeline:

Recorder
   ↓
session.json
   ↓
Parser
   ↓
Heuristics
   ↓
blocks.json
   ↓
Markdown
   ↓
AI Curator
   ↓
PDF

This allows the core documentation workflow to remain consistent across platforms.

🧪 Example Use Cases

FlowScope can be useful for:

📚 Learning

Record a troubleshooting or programming session and turn it into a study guide.

🛠️ Troubleshooting

Capture the complete process of diagnosing and fixing a system problem.

📖 Documentation

Convert real terminal workflows into reusable technical runbooks.

👨‍💻 Development

Document complex setup, deployment, or debugging procedures.

🔍 Session Reconstruction

Review what happened during an interactive terminal session.

🪟 Windows Development

Capture Windows development, debugging, configuration, and command-line workflows without requiring WSL.

🗺️ Roadmap

Potential future improvements include:

Better secret detection and automatic redaction

More robust shell/command detection

Additional AI providers

Session search and indexing

Web-based session viewer

Improved interactive application detection

More export formats

Further cross-platform improvements

Improved Windows terminal emulation and interactive application handling

🤝 Contributing

Contributions, ideas, and bug reports are welcome.

If you'd like to contribute:

Fork the repository.

Create a feature branch.

Make your changes.

Test your changes on the relevant platform(s).

Open a pull request.

📄 License

Add your project's license information here.

<p align="center">
  <b>FlowScope</b><br>
  Capture your terminal. Reconstruct the session. Document the solution.
</p>