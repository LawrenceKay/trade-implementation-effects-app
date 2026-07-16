# Trade partner intelligence for growth and diversification 

The location of a country within a network of trade agreements has been found to affect the depth and breadth of its economic capabilities, and the app developed here implements that insight for policy-makers. Fan Z etal (2025) found that when a country [insert], the complexity of its good output can [insert]. The app adopts the framework of Fan Z etal (2025), with developments for usability and policy relevance. 

 Barriers to trade, market access, and comparative advantage are the standard concepts for advising policy-makers on international trade. The lower the barriers to trade between one country and another, the more that the two will be able to search for the optimal allocation of resources according to their production capabilities. They will hence come to focus on their comparative advantages, increasing output and the gains from trade, and hence welfare for the two countries. Trade is likely to be greater when two countries are geographically closer, adjusting for economic size, as per the gravity model [insert equation].   

 Thinking about a country's trade policy in terms of its centrality within a network of trade agreements is a novel addition to the standard framework. Fan Z etal (2025) see [insert]. The app allows users to explore their framework in thinking about a country's trade policy.  

 ## Installation

Run the network app:
```bash
conda activate trade-app && streamlit run network_example.py
```

Re-run the centrality pipeline (e.g. after updating WB DTA 2.0 data):
```bash
conda activate trade-app && python centrality_pipeline.py --show
```

 ## Data

### Data sources

#### FTA Network and Economic Complexity

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| WB DTA 2.0 — Bilateral Information | World Bank | Country-pair-year panel keyed by WBID; sole source of FTA network topology, depth, and eigenvector centrality (see `Extentionslimitations.md`, "Base network source mismatch") | `datatopics.worldbank.org/dta` → Saved to `data/raw/DTA 2.0 - Vertical Content (v2).xlsx` |
| Harvard Atlas of Economic Complexity (country-year) | Harvard Growth Lab (CID) | ECI scores by country and year; 2012 data downloaded from CID GitHub | `github.com/cid-harvard/atlas-data` → `Atlas/new_observatory_cy.csv` · Processed to `data/processed/eci_scores.csv` |

#### Trade Agreements — Structure and Design

| Dataset | Provider | What it provides | Access |
|---------|----------|-----------------|--------|
| Deep Trade Agreements (DTA) 2.0 | World Bank | Provisions and depth scores for 280+ trade agreements across 18 policy areas | `datatopics.worldbank.org/dta` |

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

 ## Complementary literature

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

 ## Extentions and limitations

Known limitations, resolved design decisions, and the open next-steps list are tracked separately in [`Extentionslimitations.md`](Extentionslimitations.md).

 ## Licence

MIT — see [`LICENSE`](LICENSE).

 ## Contact

Please get in touch to discuss extensions for the app and any errors that I might have made.