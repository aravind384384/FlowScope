# FlowScope

<p align="center">
  <strong>Capture. Reconstruct. Understand.</strong>
</p>

<p align="center">
  A cross-platform terminal-session recorder that transforms real terminal activity into clean, reusable technical documentation.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Linux-supported-success?logo=linux" alt="Linux">
  <img src="https://img.shields.io/badge/macOS-supported-success?logo=apple" alt="macOS">
  <img src="https://img.shields.io/badge/Windows-supported-success?logo=windows" alt="Windows">
  <img src="https://img.shields.io/badge/AI-Gemini-purple" alt="Gemini">
</p>

---

## 🧠 What is FlowScope?

**FlowScope** records what actually happens inside a terminal session and turns it into structured documentation.

Instead of relying on shell history, FlowScope captures the **real terminal interaction**, reconstructs the session, identifies meaningful command blocks, and optionally uses AI to turn the result into a concise technical guide.

### The idea

```text
Messy Terminal Session
        │
        ▼
   ┌──────────┐
   │ Recorder │
   └────┬─────┘
        ▼
   ┌──────────┐
   │  Parser  │
   └────┬─────┘
        ▼
   ┌────────────┐
   │ Heuristics │
   └─────┬──────┘
         ▼
   ┌───────────────┐
   │    Markdown   │
   └───────┬───────┘
           ▼
   ┌────────────┐
   │ AI Curator │
   └─────┬──────┘
         ▼
   ┌────────────┐
   │ PDF Export │
   └────────────┘
```

The result is a progression from:

**Terminal → Session Data → Structured Blocks → Documentation → Guide → PDF**

---

## ✨ Why FlowScope?

Terminal sessions are useful, but they are often messy.

They contain:

- Failed commands
- Repeated commands
- Terminal control sequences
- Interactive applications
- Debugging attempts
- Temporary output
- Commands that only make sense in context

FlowScope preserves the session while removing the noise.

### Example

A raw session might look like:

```bash
$ systemctl status nginx

$ vim /etc/nginx/nginx.conf

$ systemctl restart nginx

$ systemctl status nginx
```

FlowScope can turn this into a reusable guide:

```text
Fixing an Nginx Configuration

1. Open the Nginx configuration file.
2. Correct the configuration.
3. Restart the Nginx service.
4. Verify that the service is running correctly.
```

The goal is simple:

> **Preserve what actually happened while making the result understandable and reusable.**

---

# 🚀 Features

| Feature | Description |
|---|---|
| 🖥️ **Cross-platform** | Supports Linux, macOS, and Windows |
| 🎥 **Terminal recording** | Captures real terminal input and output |
| 🔄 **Session reconstruction** | Reconstructs terminal activity and ANSI behavior |
| 🪟 **Windows support** | Records Windows sessions without requiring WSL |
| 🧠 **Command detection** | Groups related terminal activity into meaningful blocks |
| ⌨️ **Interactive sessions** | Preserves screen-oriented terminal activity where supported |
| 📝 **Markdown export** | Produces deterministic, readable transcripts |
| 🤖 **AI curation** | Uses Gemini to extract useful steps and intent |
| 📄 **PDF export** | Generates printable technical guides |
| 📁 **Session organization** | Automatically organizes sessions by date |

---

# 🏗️ Architecture

FlowScope is divided into independent processing stages.

| Component | File | Responsibility |
|---|---|---|
| **Recorder** | `flowscope.py` | Starts the shell and records terminal events |
| **Parser** | `flowscope_parser.py` | Reconstructs and normalizes terminal data |
| **Heuristics** | `flowscope_heuristics.py` | Detects commands and interaction blocks |
| **Markdown Exporter** | `flowscope_markdown.py` | Generates clean session transcripts |
| **AI Curator** | `flowscope_curator.py` | Creates focused technical guides |
| **PDF Exporter** | `flowscope_pdf.py` | Converts guides into PDF documents |

---

# 🔄 Processing Pipeline

Each recorded session moves through the following stages:

```text
┌─────────────────────┐
│ 1. RECORDING        │
│     session.json    │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. PARSING          │
│ Reconstructed Data  │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. HEURISTICS       │
│    *.blocks.json    │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. MARKDOWN         │
│   *.transcript.md   │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 5. AI CURATION      │
│      *.guide.md     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 6. PDF EXPORT       │
│      *.guide.pdf    │
└─────────────────────┘
```

A major design principle is that **platform-specific behavior is isolated inside the Recorder and Parser layers**.

The downstream documentation pipeline remains platform-independent.

---

# 💻 Platform Support

FlowScope supports:

- ✅ Linux
- ✅ macOS
- ✅ Windows

### Linux / macOS

Unix-like systems use the native PTY-based recording approach and terminal emulation through `pyte`.

### Windows

Windows uses Windows-compatible process and console handling.

**WSL is not required.**

The Windows workflow can use:

```text
pywinpty
```

for Windows terminal/process support.

---

# 📦 Installation

## 1. Clone the repository

```bash
git clone <repository-url>
cd FlowScope
```

## 2. Create a virtual environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
python -m venv prj
.\prj\Scripts\Activate.ps1
```

If PowerShell blocks script execution:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\prj\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, the requirements include the Windows-specific dependency:

```text
pywinpty==3.0.5
```

---

# 🔑 Gemini API Setup

AI curation is **optional**.

If you want FlowScope to generate AI-powered technical guides, configure your Gemini API key.

### Linux / macOS

```bash
export GEMINI_API_KEY="your_gemini_api_key"
```

### Windows PowerShell

```powershell
$env:GEMINI_API_KEY="your_gemini_api_key"
```

You can also use a `.env` file with `python-dotenv`.

> ⚠️ Never commit your API key or `.env` file to Git.

---

# 🚀 Quick Start

## Record a session

Start FlowScope with:

```bash
flowscope record --title "Fix Nginx Config"
```

Now work normally inside the recorded shell.

When finished:

```bash
exit
```

or press:

```text
Ctrl-D
```

FlowScope automatically stores the session in a date-based directory.

Example:

```text
sessions/
└── 2026-09-17/
    └── fix-nginx-config/
        ├── fix-nginx-config.json
        ├── fix-nginx-config.blocks.json
        ├── fix-nginx-config.transcript.md
        ├── fix-nginx-config.guide.md
        └── fix-nginx-config.guide.pdf
```

The exact files generated depend on the processing options used.

---

# 🪟 Windows Example

After activating the virtual environment:

```powershell
flowscope record --title "Windows Test"
```

FlowScope records the Windows shell session and stores the resulting session data in the normal `sessions/` directory.

**No WSL installation is required.**

---

# 🚫 Record Without AI

If you only want to capture and process a session without making an external AI request:

```bash
flowscope record \
    --no-guide \
    --title "Fix Nginx Config"
```

This is recommended for sessions that may contain sensitive information.

---

# 🤖 Generate an AI Guide

You can generate a guide from an existing session:

```bash
flowscope guide \
    sessions/2026-09-17/fix-nginx-config/fix-nginx-config.json \
    --focus "Document the final working configuration and remove failed attempts"
```

The `--focus` option tells the AI curator what information matters most.

For example:

```bash
--focus "Create a step-by-step troubleshooting guide"
```

or:

```bash
--focus "Keep only the commands that solved the problem"
```

---

# 🧠 Curate Existing Block Data

If you already have a `blocks.json` file, you can run the curation stage directly:

```bash
flowscope curate \
    sessions/2026-09-17/fix-nginx-config/fix-nginx-config.blocks.json \
    --out guide.md
```

This lets you regenerate documentation without recording the session again.

---

# 🛠️ CLI Reference

### Show available commands

```bash
flowscope --help
```

### Record a session

```bash
flowscope record --title "My Session"
```

### Specify an output directory

```bash
flowscope record --dir ./my-sessions
```

### Generate a guide

```bash
flowscope guide <session.json>
```

### Provide a custom focus

```bash
flowscope guide <session.json> \
    -f "Create a step-by-step runbook"
```

### Curate existing blocks

```bash
flowscope curate <blocks.json> --out guide.md
```

### Specify a Gemini model

```bash
flowscope record --model gemini-3.6-flash
```

---

# 🔐 Security & Privacy

> ⚠️ **Important:** FlowScope records raw terminal input and output.

Because recording happens at the terminal interaction level, sessions may contain sensitive information such as:

- Passwords
- API keys
- Authentication tokens
- Environment variables
- Private configuration files
- Editor contents
- Commands containing secrets
- Full-screen application buffers

Sensitive information may be present in:

```text
session.json
blocks.json
```

## Before using AI curation

Always inspect recorded files before sending them to an external AI service.

Pay particular attention to:

```text
block_type: "interactive"
```

Interactive blocks may contain complete or detailed terminal buffer contents.

### Recommended practices

- Use test or disposable credentials when possible.
- Review `session.json` before sharing it.
- Review `blocks.json` before AI processing.
- Never commit recorded sessions containing secrets.
- Add sensitive session directories to `.gitignore`.

Example:

```gitignore
.env
sessions/
*.json
```

---

# 📂 Project Structure

```text
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
```

---

# 🖥️ Platform-Aware Recording

FlowScope separates **recording** from the rest of the documentation pipeline.

### Unix-like systems

```text
User
 │
 ▼
Shell
 │
 ▼
PTY
 │
 ▼
Recorder
 │
 ▼
session.json
```

The Unix recorder uses the native PTY mechanism and terminal emulation through `pyte`.

### Windows

```text
User
 │
 ▼
Windows Shell
 │
 ▼
Windows Process /
Console I/O
 │
 ▼
Recorder
 │
 ▼
session.json
```

The Windows recorder uses Windows-compatible process and console handling instead of Unix-only modules such as:

```text
pty
termios
fcntl
```

Both platforms eventually enter the same processing pipeline:

```text
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
```

This keeps the core documentation workflow consistent across platforms.

---

# 🎯 Use Cases

### 📚 Learning

Record a programming or troubleshooting session and turn it into a study guide.

### 🛠️ Troubleshooting

Capture the complete process of diagnosing and fixing a system problem.

### 📖 Documentation

Turn real terminal workflows into reusable technical runbooks.

### 👨‍💻 Development

Document complex setup, deployment, debugging, and configuration procedures.

### 🔍 Session Reconstruction

Review exactly what happened during an interactive terminal session.

### 🪟 Windows Development

Capture Windows development and debugging workflows without requiring WSL.

---

# 🗺️ Roadmap

Potential future improvements include:

- [ ] Better secret detection and automatic redaction
- [ ] More robust shell and command detection
- [ ] Additional AI providers
- [ ] Session search and indexing
- [ ] Web-based session viewer
- [ ] Improved interactive application detection
- [ ] More export formats
- [ ] Further cross-platform improvements
- [ ] Improved Windows terminal emulation
- [ ] Better interactive application handling

---

# 🤝 Contributing

Contributions, ideas, and bug reports are welcome.

To contribute:

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test your changes on the relevant platform(s).
5. Open a pull request.

---

# 📄 License

Add your project's license information here.

---

<p align="center">
  <strong>FlowScope</strong><br>
  Capture your terminal. Reconstruct the session. Document the solution.
</p>