# Trade Implementation Effects App — CLAUDE.md

## 1. What the Trade Implementation Effects App does

The app helps the user to assess potential trade partners on their centrality within trade networks, their economic complexity, and their institutional quality.

## 2. Who the app is for

Investment analysts, government officials, and trade specialists looking to assess the institutional quality of countries as they consider trade partnerships and foreign direct investment.

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
| Country codes | pycountry (`pycountry>=22.0`) | Converts numeric ISO codes (used in DESTA) to ISO3 alpha codes |
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
| DESTA — List of Treaties (dyadic form) | University of Bern / ETH Zurich | One row per country-pair per agreement; used to build FTA network and compute eigenvector centrality | `designoftradeagreements.org/downloads` → "List of treaties in dyadic form (CSV)" · Saved to `data/raw/desta_dyads.csv` |
| Harvard Atlas of Economic Complexity (country-year) | Harvard Growth Lab (CID) | ECI scores by country and year; 2012 data downloaded from CID GitHub | `github.com/cid-harvard/atlas-data` → `Atlas/new_observatory_cy.csv` · Processed to `data/processed/eci_scores.csv` |

### Trade Agreements — Structure and Design

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Deep Trade Agreements (DTA) 2.0 | World Bank | Provisions and depth scores for 280+ trade agreements across 18 policy areas | `datatopics.worldbank.org/dta` |
| DESTA — Design of Trade Agreements | University of Bern / ETH Zurich | Coded data on legal design and institutional provisions of PTAs | `designoftradeagreements.org` |

### Dispute Settlement and Enforcement

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Dispute Settlement Body (DSB) records | WTO | Full record of WTO dispute cases, rulings, and compliance status | `wto.org/english/tratop_e/dispu_e` |
| ISDS Navigator | UNCTAD | Investor-state dispute settlement cases, outcomes, and treaty links | `investmentpolicy.unctad.org/isds` |

### Non-Tariff Measures and Regulatory Friction

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Specific Trade Concerns (STCs) | WTO (ePing) | STC filings by country and product; in March 2026 a record 76 STCs were reviewed, signalling peak regulatory friction | `epingalert.org` / `wto.org` |
| NTM Coverage Ratio | UNCTAD | Share of trade affected by non-tariff measures; TBTs and technical regulations now affect two-thirds of world trade (Jan 2026) | `unctad.org/topic/trade-analysis/non-tariff-measures` |
| TRAINS — Non-Tariff Measures | UNCTAD via WITS | Full NTM database by country, product, and measure type | `wits.worldbank.org` |
| Ad Valorem Equivalent (AVE) of NTMs | World Bank (WITS) | Tariff-equivalent cost estimates for non-tariff barriers | `wits.worldbank.org` |

### Trade Flows and Distortions

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Global Trade Alert (GTA) | Simon Evenett / GTA | Real-time database of trade policy interventions — liberalising and distorting — since 2008 | `globaltradealert.org` |
| BACI — International Trade Database | CEPII | Harmonised bilateral trade flows at HS6 level | `cepii.fr` |
| WITS — Trade Flows and Tariff Schedules | World Bank | Bilateral trade flows, tariff schedules, NTMs | `wits.worldbank.org` / `wbdata` |

### Standards and Conformity

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| UK DMAS / EU SEP | UK DBT / European Commission | Designated standards and standardisation request pipeline under UK and EU trade regimes | `gov.uk/dmas` / `ec.europa.eu/growth/single-market` |
| UK/EU PUR Data | UK DBT / European Commission | Product under review data for conformity assessment and mutual recognition | `gov.uk` / `ec.europa.eu` |

## 5. Current build state

### Scripts

| File | Purpose | Status |
|------|---------|--------|
| `network_example.py` | Main Streamlit app — 3D force-directed network of ~180 WB countries; 6 sidebar buttons for node sizing | Working |
| `centrality_pipeline.py` | Computes FTA eigenvector centrality following Fan et al. (2025); reads `desta_dyads.csv`, outputs `centrality_scores.csv` | Working |
| `pipeline.py` | World Bank data pipeline (governance indicators) | Working |
| `score.py` | Institutional quality scoring | Working |

Run the network app:
```bash
conda activate trade-app && streamlit run network_example.py
```

Re-run the centrality pipeline (e.g. after updating DESTA data):
```bash
conda activate trade-app && python centrality_pipeline.py --show
```

### Data files

| File | Contents | Source |
|------|---------|--------|
| `data/raw/desta_dyads.csv` | DESTA dyadic treaties, v2.3 Sept 2025 — 20,569 rows, 203 countries | Downloaded manually from designoftradeagreements.org |
| `data/raw/wb_cache.csv` | World Bank governance indicators for ~60 countries | World Bank API via wbdata |
| `data/processed/centrality_scores.csv` | Eigenvector centrality (overall, non-natural, natural) for 203 countries | Output of `centrality_pipeline.py` |
| `data/processed/eci_scores.csv` | ECI scores and ranks for 219 countries (2012) | Harvard Atlas via CID GitHub |
| `data/processed/scores.csv` | Institutional quality scores | Output of `pipeline.py` + `score.py` |

### network_example.py — sidebar buttons

| Button | Label | Metric | Data source |
|--------|-------|--------|------------|
| AG | Agreements | `n_agreements` | Illustrative (explicit data for 21 key economies) |
| AV | Avg. provisions | `avg_enforceable` | Illustrative |
| MX | Max. provisions | `max_enforceable` | Illustrative |
| PT | Partners | `n_partners` | Illustrative |
| CT | Centrality | `overall_centrality` | Real — `centrality_scores.csv` (DESTA + Fan et al. method) |
| EC | Complexity | `eci_score` | Real — `eci_scores.csv` (Harvard Atlas 2012) |

### Known limitations and next steps

- **Depth weighting**: centrality pipeline uses binary edge weights (agreement present = 1). Fan et al. use Hofmann et al. (2017) depth scores (0–48 scale) from WB DTA 2.0. Adding true depth weights requires downloading the DTA 2.0 agreement-level data and joining by treaty ID.
- **ECI vintage**: ECI data is 2012 (most recent year in the public CID GitHub archive). The Harvard Atlas 2021–2022 data is behind a JavaScript-rendered interface and could not be scraped programmatically.
- **Agreement/provision values**: still illustrative for most countries. Replace `EXPLICIT_DATA` in `network_example.py` with real WB DTA 2.0 exports when available.
- **Regression not implemented**: Fan et al.'s core result (ECI ~ Centrality + controls) has not been replicated. The centrality scores and ECI data are both present and could be used for a regression with WDI controls.

## 6. Rules

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

## 7. Skills

_To be defined._

## 8. Agents

### Trade Economist

**Purpose.** A conversational agent embedded in the app that allows the user to interrogate a selected country's trade position across the three analytical dimensions the app measures: FTA network centrality, agreement depth and breadth, and economic complexity. The agent grounds its responses in the academic literature held in the knowledge base (Section 10), surfacing relevant findings and citing sources rather than generating unsupported claims.

**Trigger.** The agent is invoked from the analysis page once a country has been selected. A text input or chat widget in the sidebar or below the score cards lets the user ask free-form questions such as "Why does centrality matter for this country?" or "What does the literature say about the link between FTA depth and ECI for middle-income economies?"

**Inputs passed to the agent at invocation.**

| Variable | Source | Description |
|----------|--------|-------------|
| `sel_name` | App state | Name of the selected country |
| `cent_pct2` | `centrality_scores.csv` | Eigenvector centrality as % of global max |
| `depth_pct2` | `COUNTRY_DATA` / DTA 2.0 | Agreement depth score (0–100) |
| `own_eci` | `eci_scores.csv` | Harvard Atlas ECI score |
| `_avg_peci` | Computed | Average ECI of FTA partners |
| `len(agreements)` | `desta_dyads.csv` | Number of FTA records |
| `_type_label` | Computed | Integration profile typology label |
| `_cx_label` | Computed | Complexity exposure label |

These are injected into the system prompt so the agent has the country's quantitative profile without the user having to restate it.

**Retrieval.** Before generating a response the agent queries the knowledge base (Section 10) using the user's question as the retrieval query. The top-k chunks (default k=5) are appended to the prompt as grounding context. The agent must cite the source document for any claim it draws from retrieved chunks.

**Model.** `claude-opus-4-7`. Extended thinking disabled by default; enable if the user asks a multi-step analytical question (e.g. "Walk me through the mechanism by which centrality raises ECI").

**System prompt skeleton.**

```
You are a trade economist advising on {sel_name}'s trade strategy.

Country profile:
- FTA network centrality: {cent_pct2} / 100
- Agreement depth (proxy): {depth_pct2} / 100
- Number of FTA records: {n_agreements}
- Economic complexity (ECI): {own_eci} (Harvard Atlas 2012)
- Average partner ECI: {avg_peci}
- Integration profile: {type_label}, {cx_label}

You have access to the following excerpts from the academic literature:
{retrieved_chunks}

Answer the user's question using the data above and the literature excerpts.
Cite sources by author and year. Flag data limitations honestly.
Do not fabricate statistics or citations not present in the excerpts.
Label your response as AI-generated analysis.
```

**What the agent can do.**
- Explain what the country's centrality, depth, and ECI scores mean in economic terms.
- Summarise what the literature says about mechanisms linking FTA network position to complexity outcomes.
- Discuss which partner countries the literature identifies as high-value for knowledge transfer and complexity gains.
- Compare the selected country's profile to findings reported in the literature (e.g. thresholds, typical ranges).
- Flag data limitations (2012 ECI vintage, binary centrality weights, illustrative depth data).

**What the agent cannot do.**
- Access real-time data or sources outside the knowledge base.
- Run regressions or produce new quantitative estimates.
- Speak to country-specific political or diplomatic considerations not covered in the literature corpus.

**Implementation notes.**
- Import `chromadb` and load the persistent collection from `knowledge_base/vectordb/`.
- Use `sentence-transformers` (model: `all-MiniLM-L6-v2`) to embed the user query for retrieval, consistent with how documents were ingested.
- Stream the response to the UI using `anthropic.Anthropic().messages.stream(...)` so the user sees output incrementally.
- Persist the conversation history in `st.session_state["economist_messages"]` as a list of `{"role": ..., "content": ...}` dicts so the user can ask follow-up questions within a session.
- Clear conversation history when the selected country changes.

## 9. Orchestrator

_To be defined._

## 10. Knowledge Base

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

**Seed corpus.** The four papers listed in Section 12 (Fan et al. 2025; Sopranzetti 2018; Yang & Liu 2024; Guo 2026) are the initial seed documents. All are publicly available. Additional documents should be cleared for licence before ingestion (see Rules, Section 6).

## 11. Version control

**GitHub account:** `LawrenceKay`
**Repository name:** `trade-implementation-effects-app`
**Repository URL:** `https://github.com/LawrenceKay/trade-implementation-effects-app`
**Visibility:** Private

The app lives in its own dedicated GitHub repository, separate from any other project. Use the `gh` CLI throughout.

### 11.0 Prerequisites (one-time, per machine)

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

### 11.1 First-time setup (once per app)

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

### 11.2 Prototype checkpoint

Run after the prototype and supporting documentation are complete and tested.

```bash
git add app.py requirements.txt
git commit -m "Prototype: working prototype and written outputs complete"
git push origin master
```

### 11.3 Release

```bash
git add final_checks_report.md technical_spec.md user_guide.md
git commit -m "Release: all final outputs complete"
git push origin master
git tag -a v1.0.0 -m "Release v1.0.0: ship-ready"
git push origin v1.0.0
```

Use semantic versioning: `v1.0.0` for the first ship-ready release, `v1.1.0` for minor improvements, `v2.0.0` for breaking changes.

## 12. Resources

Academic papers relevant to the analytical framework of this app. All concern the network structure of free trade agreements and its effects on trade, complexity, and value chains.

### Trade agreement networks and economic complexity

| Detail | Value |
|--------|-------|
| **Title** | Does centrality within trade agreements network matter to economic complexity? The conditioning effects of network structure |
| **Authors** | Zhaobin Fan, Rui Long, Sajid Anwar, Jinrui Wang |
| **Journal** | International Review of Economics & Finance |
| **Year** | 2025 |
| **What it argues** | A country's centrality in the FTA network yields both a breadth effect (exposure to diverse partners) and a depth effect (access to deeper knowledge transfer), both of which raise economic complexity. The conditioning effect is stronger when central links involve diverse or high-income partners. |
| **Links** | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1059056025000553#sec3) · [IDEAS/RePEc](https://ideas.repec.org/a/eee/reveco/v98y2025ics1059056025000553.html) |

### Overlapping FTAs and international trade flows

| Detail | Value |
|--------|-------|
| **Title** | Overlapping free trade agreements and international trade: A network approach |
| **Author** | Sergio Sopranzetti |
| **Journal** | The World Economy |
| **Year** | 2018 |
| **What it argues** | Characterises the global FTA network and shows that overlapping agreements create a "spaghetti bowl" structure; network centrality and clustering significantly affect bilateral trade flows beyond the direct effect of any single agreement. |
| **Links** | [Working paper (Fondazione Masi)](https://fondazionemasi.it/public/masi/files/PUBBLICAZIONI/WorkingPaper/Overlappingfreetradeagreements.pdf) |

### FTA networks and domestic value added in exports

| Detail | Value |
|--------|-------|
| **Title** | Free trade agreements and domestic value added in exports: An analysis from the network perspective |
| **Authors** | Yichen Yang, Wen Liu |
| **Journal** | Economic Modelling |
| **Year** | 2024 |
| **What it argues** | Using structural gravity modelling across 60 countries (2007–2017), shows that a country's position in the FTA network — not just whether it has agreements — determines how much domestic value is captured in its exports. Network centrality amplifies the domestic value-added gains from trade. |
| **Links** | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0264999324000129) |

### Global value chain networks and agricultural product quality

| Detail | Value |
|--------|-------|
| **Title** | Embedding in global value chains: the impact of trade networks on the quality upgrading of processed agricultural products |
| **Author** | Qianqian Guo |
| **Journal** | Frontiers in Sustainable Food Systems |
| **Year** | 2026 |
| **What it argues** | Examines how a country's position and connectivity within global agricultural trade networks drives quality upgrading of processed food exports through functional specialisation shifts in value chains. Extends the network-centrality argument to a specific sector. |
| **Links** | [Frontiers](https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2026.1772800/full) |
