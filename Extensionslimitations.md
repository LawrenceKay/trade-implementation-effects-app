## Possible extensions

Larger, more speculative pieces of work that go beyond fixing a known limitation — new data pipelines or capabilities rather than bug fixes.

### Trade Economist advisory agent

**Idea.** A conversational agent embedded in the app that would let the user interrogate a selected country's trade position across the three dimensions the app measures — FTA network centrality, agreement depth and breadth, and economic complexity — grounding its answers in the academic literature held in a knowledge base and citing sources rather than generating unsupported claims. Not yet built: no chat interface exists in `network_example.py` today. The knowledge-base infrastructure this extension would draw on is specified below.

**What it could do.** Explain what a country's centrality, depth, and ECI scores mean in economic terms; summarise what the literature says about mechanisms linking FTA network position to complexity outcomes; identify which partner countries the literature flags as high-value for knowledge transfer and complexity gains; compare a country's profile to literature-reported thresholds and typical ranges; and flag the app's known data limitations (2012 ECI vintage, binary centrality weights) when relevant.

**What it couldn't do.** Access real-time data outside the knowledge base; run new regressions or produce quantitative estimates; speak to country-specific political or diplomatic considerations not covered in the literature corpus.

### Knowledge Base

This is infrastructure for the Trade Economist advisory agent above. The scaffolding below exists on disk at `knowledge_base/` but is **not wired into the live app** — `network_example.py` and `centrality_pipeline.py` have zero references to it. Grounding the agent's answers in this literature corpus, with inline source citations rather than unsupported claims, is how that extension would be implemented.

**Dependency note (2026-07-16):** `chromadb` and `sentence-transformers`, which `ingest.py` and `retrieve.py` both need, were removed from the repo's root `requirements.txt` when trimming it for a lean Streamlit Community Cloud deploy of `network_example.py` (which doesn't need them). `ingest.py` also imports `pypdf`, which was never in `requirements.txt` to begin with. Anyone actually running the knowledge-base scripts needs to `pip install chromadb sentence-transformers pypdf` separately — this isn't yet captured in its own requirements file.

**Location.** `knowledge_base/` at the project root.

**Structure.**

```
knowledge_base/
  raw/                        # Source documents before ingestion
    fta_networks/             # Papers on FTA network structure and trade flows
    economic_complexity/      # Papers on ECI, product space, complexity theory
    agreement_depth/          # Papers on PTA depth, provisions, and enforcement
  vectordb/                   # ChromaDB persistent store (gitignored)
  sources.csv                 # Metadata registry for all ingested documents
  ingest.py                   # Ingestion script: chunk → embed → store
  retrieve.py                 # Retrieval helper: query → top-k chunks
```

**Sources.csv schema.** One row per document.

| Column | Description |
|--------|-------------|
| `id` | Unique slug (e.g. `fan_etal_2025`) |
| `title` | Full title |
| `authors` | Comma-separated author surnames |
| `year` | Publication year |
| `journal` | Journal or publisher |
| `theme` | One of: `fta_networks`, `economic_complexity`, `agreement_depth` |
| `layer` | `academic` or `policy` |
| `file` | Relative path to the raw document |
| `licence` | Licence or access status |
| `notes` | Any ingestion caveats |

**Ingestion pipeline (`ingest.py`).** Reads each document in `raw/`, splits into chunks of ~500 tokens with 50-token overlap, embeds using `sentence-transformers/all-MiniLM-L6-v2`, and upserts into a ChromaDB collection named `trade_knowledge`. Metadata stored per chunk: `id`, `authors`, `year`, `title`, `theme`.

**Retrieval helper (`retrieve.py`).** Accepts a query string and optional theme filter; returns the top-k chunks as a formatted string with inline source labels ready to paste into a prompt.

**Seed corpus.** The four papers listed in the README's "Complementary literature" section (Fan et al. 2025; Sopranzetti 2018; Yang & Liu 2024; Guo 2026) are the initial seed documents. All are publicly available. Additional documents should be cleared for licence before ingestion (see CLAUDE.md Rules, Section 6).
