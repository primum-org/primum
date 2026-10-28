# 0004. A project is a workspace of files with internal extensions

- Status: Accepted
- Date: 2026-10-28

## Context
A single project document does not scale: users need to organise many sequences, reuse parts
and keep things in folders.

## Decision
- A project is a **folder of files** with a `project.json` manifest.
- Internal file types: `.sec` (sequence), `.auto` (automation), `.evt` (event), `.prog`
  (schedule), `.vars` (variables and constants), `.hw` (boards and elements).
- Files are JSON text with their own extension. Each has an `id` (UUID), a `kind` and a
  `schemaVersion`. **Files reference each other by id**, never by path.
- Internal files are not exported on their own. A whole project is saved or shared as a single
  **`.primum`** file (an archive of the folder). Sharing reusable parts between projects, if it
  comes, will use a branded library file as well, never loose internal files.
- The compiler flattens the workspace into one deployment package per board; the runtime never
  sees folders.

## Alternatives considered
- One big project document: simple at first, painful to organise and to merge.
- References by path: break on every rename or move.

## Consequences
- Files can be diffed and versioned with git; cloud sync can work file by file.
- `core` needs a workspace loader, a reference resolver and cycle detection.
- Primum Studio and the web UI need a file explorer and one icon per file type.
