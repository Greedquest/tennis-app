# Copilot Instructions

This file provides guidance for AI coding agents working on this repository.

## Marimo Skills

This project uses [marimo](https://marimo.io) for interactive notebooks.
Skills are installed via `npx skills add marimo-team/skills` and live in:

```
.agents/skills/          ← canonical source (GitHub Copilot reads here)
.claude/skills/          ← symlinks → .agents/skills/ (Claude Code reads here)
skills-lock.json         ← tracks installed skill versions
```

Available skills: `add-molab-badge`, `anywidget-generator`, `auto-paper-demo`,
`implement-paper`, `implement-paper-auto`, `jupyter-to-marimo`, `marimo-batch`,
`marimo-notebook`, `streamlit-to-marimo`, `wasm-compatibility`.

To update skills: `npx skills update`
