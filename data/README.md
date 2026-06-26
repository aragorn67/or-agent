# `data/` — inventory

Project data lives here. Large / copyrighted reference material is gitignored
(see `data/literature/`); committed files are demo workbooks and this README.

## Layout

```
data/
├── README.md           # this file (committed)
├── examples/           # demo xlsx workbooks (committed)
├── literature/         # reference PDFs (GITIGNORED — see below)
├── loaders/            # placeholder (empty)
└── mappers/            # placeholder (empty)
```

## `examples/` — demo workbooks (committed)

Used by the xlsx fast-path tests and the demo deliverables.

| file                              | domain      | baseline objective |
| --------------------------------- | ----------- | ------------------ |
| `transport_ex0.xlsx`              | transport   | $153,675           |
| `transport_fixed_charge_ex1.xlsx` | transport   | 1660 (fixed-charge MIP) |
| `scheduling_demo.xlsx`            | scheduling  | makespan 3.5       |

## `literature/` — reference PDFs (GITIGNORED)

Textbooks + RAG corpus, consolidated here so reference material isn't scattered
across the repo. Not committed (large, copyrighted). To repopulate, download the
files from their original sources.

### Textbooks (used by the real-data benchmark — backlog #1)

| file                                                                    | use                                            |
| ----------------------------------------------------------------------- | ---------------------------------------------- |
| `operation-research-aplications-and-algorithms.pdf`                     | Winston, *OR: Applications and Algorithms*, 4th ed. (Brooks/Cole, 2004). Source for textbook problems with published optima (Powerco §7.1, Machineco §7.5, Widgetco §7.6, Post Office §3.5, etc.). |
| `Wolsey, Laurence A - Integer Programming (2021, Wiley).pdf`            | Wolsey, *Integer Programming*, 2nd ed. (Wiley, 2021). Reference for MIP formulations + lot-sizing (§5.2, §14.4) + fixed-cost network flows (§3.7). |

### RAG corpus (archived; used historically for retrieval-augmented runs)

| file                                                                    | topic |
| ----------------------------------------------------------------------- | ----- |
| `Ahuja_Magnanti_Orlin-Network_Flows.pdf`                                | Network flows |
| `Claire S. Adjiman, Christodoulos A. Floudas ... Encyclopedia of Optimization (2001, Springer).pdf` | Optimization reference |
| `Lawrence V. Snyder ... Fundamentals of Supply Chain Theory (2019, Wiley).pdf` | Supply chain theory |
| `intro_to_optimization.pdf`                                             | Optimization intro |
| `supply_chain_optimization_berkeley.pdf`                                | Supply chain (lecture notes) |
| `ghsupply_chain_optimization.pdf`                                       | Supply chain |
| `nike_supply_chain_case_study.pdf`                                      | Nike supply-chain case |
| `production_scheduling_case_study.pdf`                                  | Production scheduling case |

RAG itself was tested and rejected on evidence (50% vs LLM's 70% on real
problems). See `ML_RAG_archive/README.md` and memory `project_ml_rag_archive`.

## Related data outside `data/`

For completeness — useful reference material elsewhere in the repo:

- `ML_RAG_archive/ML_approaches/ML/FINAL_ML_DATASET.csv` (committed) — 523 OR
  problem instances spanning 24 problem types; built for the ML classifier
  experiment. See `ML_RAG_archive/ML_approaches/ML/SOURCES.md`.
- `ML_RAG_archive/ML_approaches/RAG/vectorstore/` (gitignored) — Chroma store
  built from the RAG corpus. Regenerate from `data/literature/` if needed.
- `tests/or_problem_repository.py` (committed) — central registry of curated
  problem descriptions used by tests + the real-data benchmark.
- `deliverables/*.pdf` (committed) — project deliverables (Overview, Windows
  guide). Not literature; these are outputs.

## How to repopulate `data/literature/`

The PDFs are sourced from publicly searchable academic / library locations.
Drop them back into `data/literature/` with the filenames above and gitignore
keeps them out of git.
