## Limitations

The simulation of adding new trade partners is static. When new countries are added to a country's network the
user is only given a score that represents the greater complexity exposure that it will enjoy. There is no
calculation of how it will dynamically affect the country's output profile. 

**Resolved (2026-07-17): stale bloc-membership pairs (e.g. UK–Syria, UK–Armenia).** The app was showing the UK
as having current trade agreements with Syria, Armenia, and ~94 other countries via defunct EU-era coverage —
WB DTA 2.0's `Status` field stays `"In Force"` for agreements like "EU - Syria" because the EU and the partner
are still parties, even though the UK's own participation lapsed at Brexit (31-Dec-2020). Fixed in
`centrality_pipeline.py` (`get_valid_pairs`): a pair now only counts as a live network edge if the exact
(iso1, iso2, WBID) triple's own year coverage in the `Bilateral Information` panel spans the reference year,
not just the agreement-level Status. This is a general fix, not UK-specific — it also correctly drops e.g.
Russia/Armenia's old CIS free-trade pairing (superseded by the EAEU in 2015) and similar lapsed bloc pairs
elsewhere in the dataset. Verified against WB DTA 2.0's own ~38 standalone UK post-Brexit continuity WBIDs
(e.g. "United Kingdom - Japan", "United Kingdom - Georgia") — those now correctly attribute to the UK's real
agreement, not the old EU one; Syria and Armenia have no standalone UK WBID at all, so those edges are
correctly dropped rather than reattributed.

**Known residual limitation:** the fix relies on annual-panel granularity (a pair's min/max year in Bilateral
Information), not the exact day recorded in the Agreements sheet's free-text "Specific Entry/Exit dates"
field. For an exit that falls within the dataset's most recent year, this can't distinguish "active for part
of that year" from "active all year" — e.g. Russia-Ukraine's Common Economic Zone (WBID 152) exited
21-Jul-2023, but 2023 is also WB DTA 2.0's latest data year, so that pair still shows as connected through
2023. This is a narrow edge case (the only one of its kind found on inspection), not systemic.

### Zero-depth continuity agreements (proxied 2026-07-17)

A second, distinct bug surfaced while investigating the fix above: some of the UK's own post-Brexit
continuity agreements — real, currently in-force deals — have **no provision-level depth coding at all** in
WB DTA 2.0's `STATA` sheet (every `agree_<WBID>` cell blank). Their raw computed depth was therefore exactly
`0`, and `centrality_pipeline.py`'s network-building loop (`if depth > lookup.get(key, 0)`) silently treats a
`0`-depth pair identically to "no agreement" — the edge never gets added to the graph at all, even though the
agreement correctly appears in the app's own agreement listing (`agreements.csv`). Verified against a
concrete case: the UK-Faroe Islands FTA (signed 2019, WBID 360) is entirely uncoded in WB DTA 2.0.

**Fix.** Since a UK continuity agreement was negotiated to replicate the EU agreement it succeeded as closely
as possible, **the listed depth scores for the UK's agreements with the countries below are taken from that
EU precursor agreement's own (fully-coded) depth** — not from WB DTA 2.0's own coding of the UK deal, which
doesn't exist yet. This is a deliberate, labelled proxy, not sourced WB DTA 2.0 data for the UK agreement
itself; see `UK_CONTINUITY_DEPTH_PROXY_WBID` in `centrality_pipeline.py`.

| UK agreement | EU precursor | Precursor depth |
|---|---|---|
| Colombia, Ecuador and Peru | EU – Colombia, Ecuador and Peru | 355 |
| CARIFORUM States | EU – CARIFORUM States | 283 |
| Central America | EU – Central America | 352 |
| Chile | EU – Chile | 262 |
| Côte d'Ivoire | EU – Côte d'Ivoire | 86 |
| Eastern and Southern Africa States | EU – Eastern and Southern Africa States | 84 |
| Faroe Islands | EU – Faroe Islands | 69 |
| Georgia | EU – Georgia | 332 |
| Jordan | EU – Jordan | 169 |
| Lebanon | EU – Lebanon | 106 |
| Morocco | EU – Morocco | 131 |
| Pacific States | EU – Pacific States | 101 |
| Palestine | EU – Palestine | 117 |
| Tunisia | EU – Tunisia | 136 |
| Ukraine | EU – Ukraine | 397 |
| Albania | EU – Albania | 170 |
| Cameroon | EU – Cameroon | 118 |
| Egypt | EU – Egypt | 141 |
| Ghana | EU – Ghana | 77 |
| Moldova, Republic of | EU – Moldova, Republic of | 358 |
| North Macedonia | EU – North Macedonia | 157 |
| Serbia | EU – Serbia | 197 |
| Singapore | EU – Singapore | 354 |
| Viet Nam | EU – Viet Nam | 438 |
| Pacific States – Accession of Samoa | EU – Pacific States – Accession of Samoa | 41 |
| Pacific States – Accession of Solomon Islands | EU – Pacific States – Accession of Solomon Islands | 41 |

**SACU and Mozambique — no exact-name EU precursor.** "United Kingdom - SACU and Mozambique" has no
identically-named EU agreement, but "EU - SADC" (the EU-Southern African Development Community EPA) covers
the same partner set (South Africa, Botswana, Lesotho, Namibia, Eswatini, plus Mozambique). **The listed
depth score for the UK's agreement with these countries is taken from the EU-SADC precursor's depth (136).**

**Iceland, Liechtenstein and Norway — bundled agreement, no single precursor.** "United Kingdom - Iceland,
Liechtenstein and Norway" (WBID 392) covers three EFTA states under one WBID, but each has its own separate
EU relationship: Iceland (EU – Iceland) and Norway (EU – Norway) each have their own EU deal, and
Liechtenstein's runs through EU – Switzerland – Liechtenstein (shared with Switzerland). **The EU precursor
depth is assigned to the UK's bilateral relationship in the dataset with each country individually**, not
uniformly across the WBID: Iceland → 67, Norway → 68, Liechtenstein → 69 (though in practice Liechtenstein's
live network edge ends up at 98, not 69, because the UK-Switzerland-Liechtenstein agreement, WBID 372, is
separately and already fully depth-coded in WB DTA 2.0, and the pipeline correctly takes the higher, real
value where more than one valid agreement connects the same pair).

**Kenya and Kosovo — no EU precursor exists at all.** WB DTA 2.0 has no "EU - Kenya"/"EU - EAC" or "EU -
Kosovo" agreement coded anywhere in the dataset to borrow from. **These two are assigned the UK's own average
depth score**, computed across the UK's other valid agreements (including the proxied ones above) once those
proxies are applied — 218.5 as of this run (38 agreements). This is a materially weaker proxy than the
EU-precursor approach: it reflects the UK's typical agreement depth generally, not anything about Kenya's or
Kosovo's specific relationship with the UK, and should be treated as a placeholder pending real WB DTA 2.0
coding or another source.

### Zero-depth agreements unrelated to Brexit (proxied 2026-07-17)

Six other currently-in-force agreements have the same zero-provision-coding problem as the UK continuity
deals above, but with no Brexit connection and no single already-coded precursor agreement to borrow depth
from: Protocol on Trade Negotiations (PTN), PACER Plus, Mexico–Cuba, Mexico–Paraguay, Morocco–United Arab
Emirates, and Indonesia–Pakistan. Two different proxy methods were used, both implemented in
`centrality_pipeline.py` (`get_lowest_of_two_depth_proxy`, `build_depth_lookup`) and both deliberately
conservative — again, these are explicit, labelled stand-ins, not WB DTA 2.0's own coding of these specific
agreements.

**Protocol on Trade Negotiations (PTN), Morocco–United Arab Emirates, Indonesia–Pakistan — "lowest of the two
countries" method.** PTN is a 1971 GATT-era plurilateral preference scheme among 15 developing countries
(Bangladesh, Brazil, Chile, Egypt, Israel, South Korea, Mexico, Pakistan, Peru, Philippines, Paraguay,
Serbia, Tunisia, Türkiye, Uruguay), covering 105 bilateral pairs — WB DTA 2.0's Bilateral Information panel
also carries a historical "Yugoslavia" (YUG) code under this WBID, a defunct state excluded from the app
entirely (see "Filtered: historical/defunct-state codes" below) rather than treated as a 16th party. For each
pair, and for the two standalone bilaterals (Morocco–UAE,
Indonesia–Pakistan), **the assigned depth is the lowest depth score found across either of the two
countries' other real bilateral relationships** — i.e. for pair (A, B), the minimum value in the pooled set
of A's other agreement depths and B's other agreement depths. This is deliberately the *lowest* available
figure, not an average, so it errs on the side of understating rather than overstating these countries'
commitments. Results from this run: Morocco–UAE → 10, Indonesia–Pakistan → 11, and PTN pairs ranging as low
as single digits up to whatever each pair's weakest-linked country's other portfolio allows (e.g.
Bangladesh–Egypt → 11).

**PACER Plus — same method, plus an assumption about ratification.** PACER Plus entered into force in
December 2020, but as of this WB DTA 2.0 extract one signatory, Nauru, had signed but not yet ratified — WB
DTA 2.0 accordingly flags the agreement's Status as "In force for at least one Party" rather than a clean "In
Force." Per instruction, **this is treated as if PACER Plus is ratified and in force for all 11 signatories**
(Australia, Cook Islands, Kiribati, Nauru, New Zealand, Niue, Samoa, Solomon Islands, Tonga, Tuvalu, Vanuatu)
— in practice this made no difference to pair *coverage*, since WB DTA 2.0's Bilateral Information sheet
already carries the full 55-pair complete graph across all 11 countries regardless of Nauru's ratification
status. Depth is assigned using the same lowest-of-the-two-countries method as PTN above (no alternative
method was specified, so the existing method was extended here for consistency) — e.g. Nauru–Kiribati → 36.

**Mexico–Cuba and Mexico–Paraguay — Mexico's own LAIA average.** Both are bilateral agreements under the
Latin American Integration Association (LAIA/ALADI) framework, which Mexico, Cuba, and Paraguay are all
members of alongside Argentina, Bolivia, Brazil, Chile, Colombia, Ecuador, Panama, Peru, Uruguay, and
Venezuela. **Both are assigned Mexico's own average depth across its real, already-resolved relationships
with the other ten LAIA members** (excluding Cuba and Paraguay themselves, since their depth is exactly what's
being computed) — 199.5 as of this run, averaged across Argentina (37), Bolivia (93), Brazil (47), Chile
(545), Colombia (247), Ecuador (37), Panama (212), Peru (545), Uruguay (195), and Venezuela (37). Both
Mexico–Cuba and Mexico–Paraguay get this identical flat value; unlike the lowest-of-two method, this doesn't
vary by the specific counterpart, since the intent here was specifically "Mexico's typical depth with a LAIA
partner," per instruction, not the counterpart's own portfolio.

**Caveat applying to all of the above.** Every proxy in this document is a modelling assumption introduced to
stop a real, in-force agreement from silently vanishing from the network graph — none of it is sourced,
provision-level WB DTA 2.0 coding for the specific agreement it's attached to. If WB DTA 2.0 later codes any
of these agreements directly, that coding should replace the corresponding proxy here.

### Filtered: historical/defunct-state codes (2026-07-17)

While computing the PTN proxy above, "Yugoslavia" (ISO code YUG) turned up as a 211th network node — a state
that hasn't existed since the 1990s, present in WB DTA 2.0's Bilateral Information panel purely as a legacy
row-history artefact under the Protocol on Trade Negotiations (WBID 317, entered into force 1973), with no
other agreement referencing it anywhere in the dataset. It's excluded outright in `centrality_pipeline.py`
(`HISTORICAL_ISO_EXCLUDE`), dropped from `bilateral` before any other processing, so it can't appear as a
selectable country, accrue agreement stats, or feed into another country's depth-proxy pool (it was one of
PTN's original 16 signatories per WB DTA 2.0's historical panel, brought down to the 15 real, current
countries listed above once removed). If another defunct-state code is ever found elsewhere in the dataset,
add it to the same set.

## Possible extensions

Larger, more speculative pieces of work that go beyond fixing a known limitation — new data pipelines or capabilities rather than bug fixes.

### Trade Economist advisory agent

**Idea.** A conversational agent embedded in the app that would let the user interrogate a selected country's trade position across the three dimensions the app measures — FTA network centrality, agreement depth and breadth, and economic complexity — grounding its answers in the academic literature held in a knowledge base and citing sources rather than generating unsupported claims. Not yet built: no chat interface exists in `network_example.py` today. The knowledge-base infrastructure this extension would draw on is specified below.

**What it could do.** Explain what a country's centrality, depth, and ECI scores mean in economic terms; summarise what the literature says about mechanisms linking FTA network position to complexity outcomes; identify which partner countries the literature flags as high-value for knowledge transfer and complexity gains; compare a country's profile to literature-reported thresholds and typical ranges; and flag the app's known data limitations (2012 ECI vintage, binary centrality weights) when relevant.

**What it couldn't do.** Access real-time data outside the knowledge base; run new regressions or produce quantitative estimates; speak to country-specific political or diplomatic considerations not covered in the literature corpus.

### Knowledge Base

This is infrastructure for the Trade Economist advisory agent above. The scaffolding below exists on disk at `knowledge_base/` but is **not wired into the live app** — `network_example.py` and `centrality_pipeline.py` have zero references to it. Grounding the agent's answers in this literature corpus, with inline source citations rather than unsupported claims, is how that extension would be implemented.

**Dependency note (2026-07-16):** `chromadb` and `sentence-transformers`, which `ingest.py` and `retrieve.py` both need, were removed from the repo's root `requirements.txt` when trimming it for a lean Streamlit Community Cloud deploy of `network_example.py` (which doesn't need them). `ingest.py` also imports `pypdf`, which was never in the root `requirements.txt` to begin with. Anyone running the knowledge-base scripts should `pip install -r knowledge_base/requirements.txt` separately.

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
