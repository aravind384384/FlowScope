# FlowScope Repository Environment and Git Status Check

## Overview

This guide documents a terminal session where the user verified shell responsiveness, inspected the working directory contents of the FlowScope project, checked the Git branch and status, and ended the terminal session.

## Step 1: Test Terminal Echo [SETUP]

Verify shell responsiveness by echoing a basic text string.

```bash
echo hi
```

```
hi
```

## Step 2: List Directory Contents [VERIFICATION]

Display the files and subdirectories present in the `FlowScope` project directory to review project assets.

```bash
ls
```

```
    Directory: C:\Users\gvnar\OneDrive\Desktop\FlowScope


Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
d-----        14-09-2026     10:55                flowscope-ui
d-----        14-09-2026     10:51                prj
d-----        16-09-2026     09:33                sessions
d-----        16-09-2026     13:08                __pycache__
-a----        14-09-2026     12:04             66 .gitignore
-a----        14-09-2026     10:48            107 .gitmodules
-a----        16-09-2026     12:07          32004 flowscope.py
-a----        16-09-2026     13:26          14043 flowscope_curator.py
-a----        16-09-2026     00:32           1612 flowscope_debug.py
-a----        16-09-2026     11:51          20602 flowscope_heuristics.py
-a----        14-09-2026     11:54           5403 flowscope_markdown.py
-a----        16-09-2026     12:47          12093 flowscope_parser.py
-a----        15-09-2026     12:37          14596 flowscope_pdf.py
-a----        14-09-2026     10:54             88 package-lock.json
-a----        15-09-2026     00:46          12613 README.md
-a----        15-09-2026     09:56            715 requirements.txt
```

## Step 3: Check Git Branch [VERIFICATION]

Determine the current active Git branch.

```bash
git branch
```

```
* main
```

## Step 4: Check Working Directory Git Status [VERIFICATION]

Inspect local modifications and untracked files in the repository.

```bash
git status
```

```
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   flowscope.py
	modified:   flowscope_curator.py
	modified:   flowscope_parser.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	sessions/2026-09-16/Parser-Test-10/
	sessions/2026-09-16/Parser-Test-11/
	sessions/2026-09-16/Parser-Test-6/
	sessions/2026-09-16/Parser-Test-8/
	sessions/2026-09-16/Parser-Test-9/
	sessions/2026-09-16/Test-11/

no changes added to commit (use "git add" and/or "git commit -a")
```

## Step 5: Execute User Identity Check [VERIFICATION]

Attempt to run a command to verify user identity. The command contained a typographical error (`whoam` instead of `whoami`) and failed.

```bash
whoam
```

```
whoam : The term 'whoam' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the name, or if a path
was included, verify that the path is correct and try again.
At line:1 char:1
+ whoam
+ ~~~~~
    + CategoryInfo          : ObjectNotFound: (whoam:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

## Step 6: Terminate Terminal Session [CLEANUP]

Close the active PowerShell session.

```bash
exit
```

## Result

The working environment for FlowScope was inspected. The repository was confirmed to be on the `main` branch with 3 modified core source files (`flowscope.py`, `flowscope_curator.py`, `flowscope_parser.py`) and multiple untracked session folders.