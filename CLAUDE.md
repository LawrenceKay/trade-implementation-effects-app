# Trade Implementation Effects App — CLAUDE.md

## 1. What the Trade Implementation Effects App does

The app helps the user to assess the institutional quality of select countries in implementing trade deals and hence providing a stable, long-term investment climate.

## 2. Who the app is for

Investment analysts, government officials, and trade specialists looking to assess the institutional quality of countries as they consider foreign direct investment.

## 3. Tech stack defaults

| Component | Default | Notes |
|-----------|---------|-------|
| Language | Python | |
| App framework | Streamlit | Fastest to build, looks professional, easy to demo |
| Visualisation | Plotly | Interactive charts, professional-quality aesthetics |
| Mapping | Folium + streamlit-folium | Clickable choropleth and marker maps via Leaflet.js; embed in Streamlit with `st_folium` |
| Mapping (alternative) | Plotly Choropleth (`px.choropleth`) | Simpler clickable country maps; use when Folium is not needed |
| AI/LLM | Claude via the Anthropic API | Model: `claude-opus-4-6` with `thinking: {"type": "adaptive"}`. Use streaming for long outputs |
| Knowledge base | ChromaDB + sentence-transformers | Persistent vector database at `knowledge_base/vectordb/`. Raw documents in `knowledge_base/raw/[THEME]/[LAYER]/`. Corpus managed via `knowledge_base/sources.csv`. Two retrieval patterns: direct API call for structured data; RAG for document-grounded questions. See `knowledge_base/retrieve.py` |
| Vector database | ChromaDB | Local, persistent, no cloud account needed. Shared across all app builds |
| Version control | Git/GitHub | |
| Environment management | Conda | |
| colour palette | Primary green `#00A651`, primary blue `#004B87`, accent orange `#F7941D` | Verify against the documented colour values before use. Use consistently across all Plotly charts |

Services available:

| Service | Purpose |
|---------|---------|
| Notion | Research site |
| Claude in Chrome | AI assistant via browser |

## 4. Data sources

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

## 5. Rules

Rules apply at all times across all stages and all app builds. They are not negotiable.

### Data integrity
- Never fabricate data, statistics, or citations. If data is unavailable, say so explicitly.
- Every data point shown in an app must be traceable to a named source in Section 4 or the knowledge base.
- Data gaps and limitations must be surfaced to the user — never hidden or smoothed over.
- Do not mix figures from different time periods or geographies without clearly labelling the difference.

### AI outputs
- All Claude-generated text in an app must be clearly labelled as AI-generated.
- Outputs must include appropriate caveats — Claude's analysis is a starting point, not a conclusion.
- Do not present Claude's outputs as an official position unless a human has reviewed and approved them.
- Prompts must be framed for a professional policy audience: clear, evidence-based, and appropriately cautious.

### Source and citation standards
- All sources used in the knowledge base must be listed in `sources.csv` with full metadata.
- Academic sources must be cited with author, year, and publication. Policy sources with organisation and year.
- Do not ingest documents whose licence prohibits commercial use without clearing this first.

### Brand and quality
- Apply the colour palette consistently across all Plotly charts.
- Language in all outputs — app text, AI narratives, documents — must be clear, confident, and accessible.
- Do not use internal jargon in any public-facing output.
- All outputs must reflect well on the project.

### Security and compliance
- Never commit API keys, `.env` files, or credentials to version control.
- Do not store personal or third-party data in the knowledge base without explicit permission.
- Do not pass personal or sensitive data to the Claude API without assessing data privacy implications first.
- Flag any compliance concerns to the user immediately — do not proceed past them.

## 6. Skills

_To be defined._

## 7. Agents

_To be defined._

## 8. Orchestrator

_To be defined._

## 9. Knowledge Base

_To be defined._

## 10. Version control

**GitHub account:** `LawrenceKay`
**Repository name:** `trade-implementation-effects-app`
**Repository URL:** `https://github.com/LawrenceKay/trade-implementation-effects-app`
**Visibility:** Private

The app lives in its own dedicated GitHub repository, separate from any other project. Use the `gh` CLI throughout.

### 10.0 Prerequisites (one-time, per machine)

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

### 10.1 First-time setup (once per app)

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
git add .gitignore CLAUDE.md design_brief.md design_criteria.md
git commit -m "Initial commit: project scaffold"
```

**Step 4 — create the private GitHub repo and push:**
```bash
gh repo create trade-implementation-effects-app --private --source=. --remote=origin --push
```

Never commit `.env` files or API keys. Add a `.env.example` file listing variable names without values so collaborators know what is needed.

### 10.2 Prototype checkpoint

Run after the prototype and supporting documentation are complete and tested.

```bash
git add app.py requirements.txt design_brief.md design_criteria.md
git commit -m "Prototype: working prototype and written outputs complete"
git push origin master
```

### 10.3 Release

```bash
git add final_checks_report.md technical_spec.md user_guide.md
git commit -m "Release: all final outputs complete"
git push origin master
git tag -a v1.0.0 -m "Release v1.0.0: ship-ready"
git push origin v1.0.0
```

Use semantic versioning: `v1.0.0` for the first ship-ready release, `v1.1.0` for minor improvements, `v2.0.0` for breaking changes.
