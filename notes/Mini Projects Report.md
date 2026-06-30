# Mini Projects from Claude Agent on Laptop

> **Report generated:** 30 June 2026
> **User:** Billal Rehmani
> **Platform:** Linux (Debian) — Claude Code CLI

---

## Table of Contents

- [[#Project 1 — System Environment Setup]]
- [[#Project 2 — OneDrive Setup & Office Tooling]]
- [[#Project 3 — Obsidian Vault Optimization & Claude API Integration]]
- [[#Project 4 — Lab Documents Migration to Obsidian]]
- [[#Summary]]

---

## Project 1 — System Environment Setup

| Detail       | Info                        |
|--------------|-----------------------------|
| **Date**     | 23 June 2026                |
| **Directory**| `/home/billal`              |
| **Status**   | Completed                   |

### What Was Done

- Ran `/doctor` to diagnose the Claude Code installation and verify the environment was healthy and correctly configured on the laptop.

---

## Project 2 — OneDrive Setup & Office Tooling

| Detail       | Info                        |
|--------------|-----------------------------|
| **Date**     | 24 June 2026                |
| **Directory**| `/home/billal`              |
| **Status**   | Completed                   |

### What Was Done

- Installed and configured **OneDrive** on Linux via Snap package
- Verified the OneDrive daemon was running and authenticated to the Microsoft account
- Enabled the **background sync daemon** for automatic, persistent file syncing
- Located and performed an initial sync/download of the OneDrive folder
- Installed **LibreOffice Writer** as a Microsoft Word alternative for document creation

### Lab Documents Created

Two guided learning lab documents were generated and saved to OneDrive:

| Document | Description |
|---|---|
| `Linux_Command_Line_Lab.docx` | Guided Linux command reference — includes command types, usage instructions, formatting and examples to build Linux proficiency |
| `Windows_PowerShell_Lab.docx` | Guided Windows PowerShell lab — covers PowerShell commands and syntax to build cross-platform shell skills |

Both documents were formatted in LibreOffice with proper style, headings, and saved directly to OneDrive. Forgot to mention, I also generated docker intro and an apache guided lab.

---

## Project 3 — Obsidian Vault Optimization & Claude API Integration

| Detail       | Info                                              |
|--------------|---------------------------------------------------|
| **Date**     | 24 June 2026                                      |
| **Directory**| `/home/billal/Documents/MynotesonDEB`             |
| **Status**   | Completed                                         |

### Part A — Vault Optimization

The entire Obsidian notes vault was reviewed and restructured for consistency and readability:

- Fixed formatting, indentation, headings, and spacing across **all notes**
- Added **Tables of Contents** to each note
- Removed unnecessary or redundant content
- Created supporting vault documents:
  - `FORMATTING_GUIDE.md` — standards reference for future notes
  - `NEW_NOTE_TEMPLATE.md` — reusable template to keep new notes consistent
  - `_VAULT_OPTIMIZATION_LOG.md` — audit log of all optimization changes made
- Updated the **Canvas diagram** (`Canvas diagram notes.canvas`) to visually represent all current notes and their relationships

### Part B — Claude API Integration with Obsidian

The Claude API (Anthropic) was integrated into the Obsidian workflow to bring AI assistance directly into the note-taking environment:

- Connected the **Claude API** to Obsidian to enable AI-powered note assistance
- Enabled in-vault interactions — allowing Claude to read, suggest edits, and help generate content from within Obsidian notes
- Integrated as part of the vault optimization pipeline so notes can be enhanced, summarized, or reformatted using Claude as a backend agent

> This integration links Claude Code's capabilities directly to the MynotesonDEB vault, making the note-taking system AI-assisted going forward.

---

## Project 4 — Lab Documents Migration to Obsidian

| Detail       | Info                        |
|--------------|-----------------------------|
| **Date**     | 26 June 2026                |
| **Directory**| `/home/billal`              |
| **Status**   | Completed                   |

### What Was Done

- Retrieved the two lab `.docx` files from OneDrive
- Converted and imported them into the Obsidian vault as properly formatted Markdown files, placed in the correct vault folders:

| Obsidian Note | Vault Location |
|---|---|
| `Linux Command Line Lab.md` | `Linux Fundamentals/` |
| `Windows PowerShell Lab.md` | `Cybersecurity Notes/Cluster 2 Notes/` |

- Applied full vault formatting standards to both imported notes:
  - YAML frontmatter with tags
  - Wikilink-style Table of Contents
  - Proper heading hierarchy (H1 → H3)
  - Markdown tables and fenced code blocks
  - Cross-links between the Linux and PowerShell notes

---

## Summary

| # | Project | Date | Outcome |
|---|---|---|---|
| 1 | System Environment Setup | 23 Jun 2026 | Claude Code diagnosed and verified |
| 2 | OneDrive + Office Tooling | 24 Jun 2026 | OneDrive syncing, LibreOffice installed, 2 lab docs created |
| 3 | Obsidian Vault Optimization + Claude API | 24 Jun 2026 | Vault reformatted, templates created, Claude API integrated |
| 4 | Lab Docs Migration to Obsidian | 26 Jun 2026 | Both lab docs converted to Markdown in vault |

> All projects were completed on a **Linux (Debian)** laptop using the **Claude Code CLI** agent.
> Vault location: `/home/billal/Documents/MynotesonDEB`
> OneDrive: synced and active
