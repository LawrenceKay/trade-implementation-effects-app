# Trade Implementation Effects App — CLAUDE.md

## 1. What the Trade Implementation Effects App does

The app helps the user to assess potential trade partners on their centrality within trade networks and their economic complexity.

## 2. Who the app is for

Investment analysts, government officials, and trade specialists looking to assess countries' trade network position and economic complexity as they consider trade partnerships and foreign direct investment.

## 3. Tech stack defaults

| Component | Default | Notes |
|-----------|---------|-------|
| Language | Python | |
| App framework | Streamlit | Fastest to build, looks professional, easy to demo |
| Visualisation | Plotly | Interactive charts, professional/publication-quality aesthetics |
| Mapping | Folium + streamlit-folium | Clickable choropleth and marker maps via Leaflet.js; embed in Streamlit with `st_folium` |
| Mapping (alternative) | Plotly Choropleth (`px.choropleth`) | Simpler clickable country maps; use when Folium is not needed |
| AI/LLM | Claude via the Anthropic API | Model: `claude-opus-4-6` with `thinking: {"type": "adaptive"}`. Use streaming for long outputs |
| Network analysis | NetworkX (`networkx>=3.0`) | Eigenvector centrality computation for FTA network pipeline |
| Knowledge base | ChromaDB + sentence-transformers | Persistent vector database at `knowledge_base/vectordb/`. Raw documents in `knowledge_base/raw/[THEME]/[LAYER]/`. Corpus managed via `knowledge_base/sources.csv`. Two retrieval patterns: direct API call for structured data; RAG for document-grounded questions. See `knowledge_base/retrieve.py` |
| Vector database | ChromaDB | Local, persistent, no cloud account needed. Shared across all app builds |
| Version control | Git/GitHub | |
| Environment management | Conda | |


Services available:

| Service | Purpose |
|---------|---------|
| Notion | Research site |
| Claude in Chrome | AI assistant via browser |

## 4. Data sources

### FTA Network and Economic Complexity

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| WB DTA 2.0 — Bilateral Information | World Bank | Country-pair-year panel keyed by WBID; sole source of FTA network topology, depth, and eigenvector centrality (see `Extentionslimitations.md`, "Base network source mismatch") | `datatopics.worldbank.org/dta` → Saved to `data/raw/DTA 2.0 - Vertical Content (v2).xlsx` |
| Harvard Atlas of Economic Complexity (country-year) | Harvard Growth Lab (CID) | ECI scores by country and year; 2012 data downloaded from CID GitHub | `github.com/cid-harvard/atlas-data` → `Atlas/new_observatory_cy.csv` · Processed to `data/processed/eci_scores.csv` |

### Trade Agreements — Structure and Design

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Deep Trade Agreements (DTA) 2.0 | World Bank | Provisions and depth scores for 280+ trade agreements across 18 policy areas | `datatopics.worldbank.org/dta` |

## 5. Current build state

### Scripts

| File | Purpose | Status |
|------|---------|--------|
| `network_example.py` | Main Streamlit app — 3D force-directed network of ~180 WB countries; 6 sidebar buttons for node sizing | Working |
| `centrality_pipeline.py` | Computes FTA eigenvector centrality following Fan et al. (2025); reads WB DTA 2.0, outputs `centrality_scores.csv` | Working |

Run the network app:
```bash
conda activate trade-app && streamlit run network_example.py
```

Re-run the centrality pipeline (e.g. after updating WB DTA 2.0 data):
```bash
conda activate trade-app && python centrality_pipeline.py --show
```

### Data files

| File | Contents | Source |
|------|---------|--------|
| `data/raw/DTA 2.0 - Vertical Content (v2).xlsx` | WB DTA 2.0 provision-level coding for 400 agreements (`STATA` sheet: 1,007 binary + 64 categorical provisions), a bilateral country-pair-year panel keyed by WBID (`Bilateral Information` sheet), and per-agreement Status/entry-date metadata (`Agreements` sheet) — sole data source for the FTA network pipeline | Downloaded manually from `datatopics.worldbank.org/dta` |
| `data/processed/centrality_scores.csv` | Eigenvector centrality (overall, non-natural, natural, ED, ING), income_group, n_agreements, n_partners, avg/max_enforceable for 210 countries | Output of `centrality_pipeline.py` |
| `data/raw/CLASS_2026_07_01.xlsx` | WB Country and Lending Groups classification — region + income group per country, used for natural/non-natural region split and the ED/ING developed/developing split | Downloaded manually from `datahelpdesk.worldbank.org/knowledgebase/articles/906519` |
| `data/raw/dist_cepii.dta` | CEPII GeoDist bilateral distance dataset — `distw` (bilateral weighted geographic distance) drives the natural/non-natural centrality split | Downloaded from `cepii.fr/distance/dist_cepii.dta`, Etalab 2.0 licence |
| `data/processed/fta_network_edges.csv` | Network edges (iso1, iso2, weight) for the app's what-if centrality simulation | Output of `centrality_pipeline.py` |
| `data/processed/agreements.csv` | Per-pair-agreement listing (iso1, iso2, WBID, agreement name, entry_year) | Output of `centrality_pipeline.py`; feeds `network_example.py`'s `PARTNER_MAP`/`AGREEMENTS_MAP`/`PAIR_AGREEMENTS` |
| `data/processed/eci_scores.csv` | ECI scores and ranks for 219 countries (2012) | Harvard Atlas via CID GitHub |

### network_example.py — sidebar buttons

| Button | Label | Metric | Data source |
|--------|-------|--------|------------|
| AG | Agreements | `n_agreements` | Real — `centrality_scores.csv` (WB DTA 2.0, unique valid `WBID` count per country) |
| AV | Avg. provisions | `avg_enforceable` | Real — `centrality_scores.csv` (WB DTA 2.0, mean binary-provision count across a country's own agreements) |
| MX | Max. provisions | `max_enforceable` | Real — `centrality_scores.csv` (WB DTA 2.0, max binary-provision count across a country's own agreements) |
| PT | Partners | `n_partners` | Real — `centrality_scores.csv` (WB DTA 2.0 network degree) |
| CT | Centrality | `overall_centrality` | Real — `centrality_scores.csv` (WB DTA 2.0 + Fan et al. method) |
| EC | Complexity | `eci_score` | Real — `eci_scores.csv` (Harvard Atlas 2012) |

## 6. Known limitations and next steps

Moved to [`Extentionslimitations.md`](Extentionslimitations.md) — the resolved decision trail for the DESTA→WB DTA 2.0 migration, the natural/non-natural and developed/developing splits, and the open Explanation/Evaluation/Design next-steps list.

## 7. Rules

Rules apply at all times across all stages and all app builds. They are not negotiable.

### Data integrity
- Never fabricate data, statistics, or citations. If data is unavailable, say so explicitly.
- Every data point shown in an app must be traceable to a named source in Section 4 or the knowledge base.
- Data gaps and limitations must be surfaced to the user — never hidden or smoothed over.
- Do not mix figures from different time periods or geographies without clearly labelling the difference.

### Source and citation standards
- All sources used in the knowledge base must be listed in `sources.csv` with full metadata.
- Academic sources must be cited with author, year, and publication. Policy sources with organisation and year.
- Do not ingest documents whose licence prohibits commercial use without clearing this first.

### Security and compliance
- Never commit API keys, `.env` files, or credentials to version control.
- Do not store personal or third-party data in the knowledge base without explicit permission.
- Do not pass personal or sensitive data to the Claude API without assessing data privacy implications first.
- Flag any compliance concerns to the user immediately — do not proceed past them.

## 8. Version control

**GitHub account:** `LawrenceKay`
**Repository name:** `trade-implementation-effects-app`
**Repository URL:** `https://github.com/LawrenceKay/trade-implementation-effects-app`
**Visibility:** Private

The app lives in its own dedicated GitHub repository, separate from any other project. Use the `gh` CLI throughout.

### 8.0 Prerequisites (one-time, per machine)

The `gh` CLI must be installed and authenticated before running any of the steps below.

```bash
# Install gh (macOS) — skip if already installed
brew install gh

# Authenticate (run this if the token has expired or is missing)
gh auth login
```

Follow the prompts: select GitHub.com, HTTPS, and authenticate via browser.

Verify authentication is working before proceeding:
```bash
gh auth status
```

### 8.1 First-time setup (once per app)

Run these commands from inside the `trade_implementation_effects_app` directory.

**Step 1 — initialise a fresh git repo:**
```bash
git init
```

**Step 2 — create a `.gitignore`:**
```
.env
__pycache__/
*.pyc
*.pyo
.DS_Store
knowledge_base/vectordb/
```

**Step 3 — stage and commit the initial files:**
```bash
git add .gitignore CLAUDE.md
git commit -m "Initial commit: project scaffold"
```

**Step 4 — create the private GitHub repo and push:**
```bash
gh repo create trade-implementation-effects-app --private --source=. --remote=origin --push
```

Never commit `.env` files or API keys. Add a `.env.example` file listing variable names without values so collaborators know what is needed.

### 8.2 Prototype checkpoint

Run after the prototype and supporting documentation are complete and tested.

```bash
git add app.py requirements.txt
git commit -m "Prototype: working prototype and written outputs complete"
git push origin master
```

### 8.3 Release

```bash
git add final_checks_report.md technical_spec.md user_guide.md
git commit -m "Release: all final outputs complete"
git push origin master
git tag -a v1.0.0 -m "Release v1.0.0: ship-ready"
git push origin v1.0.0
```

Use semantic versioning: `v1.0.0` for the first ship-ready release, `v1.1.0` for minor improvements, `v2.0.0` for breaking changes.

## 9. Possible extensions

Larger, more speculative pieces of work that go beyond fixing a known limitation — new data pipelines or capabilities rather than bug fixes.

### Trade Economist advisory agent

**Idea.** A conversational agent embedded in the app that would let the user interrogate a selected country's trade position across the three dimensions the app measures — FTA network centrality, agreement depth and breadth, and economic complexity — grounding its answers in the academic literature held in a knowledge base and citing sources rather than generating unsupported claims. Not yet built: no chat interface exists in `network_example.py` today. The knowledge-base infrastructure this extension would draw on — location, ingestion pipeline, retrieval helper, seed corpus — is specified in [`Extentionslimitations.md`](Extentionslimitations.md), since it exists on disk as scaffolding but isn't wired into the live app.

**What it could do.** Explain what a country's centrality, depth, and ECI scores mean in economic terms; summarise what the literature says about mechanisms linking FTA network position to complexity outcomes; identify which partner countries the literature flags as high-value for knowledge transfer and complexity gains; compare a country's profile to literature-reported thresholds and typical ranges; and flag the app's known data limitations (2012 ECI vintage, binary centrality weights) when relevant.

**What it couldn't do.** Access real-time data outside the knowledge base; run new regressions or produce quantitative estimates; speak to country-specific political or diplomatic considerations not covered in the literature corpus.
