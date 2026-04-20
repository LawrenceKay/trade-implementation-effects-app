# Design Criteria — Trade Implementation Effects App

## 1. Functional requirements

These are the things the app must do. Each criterion has a clear pass/fail test.

### 1.1 Map
| Criterion | Test |
|-----------|------|
| A choropleth world map loads on startup | Map renders within 3 seconds of launching the app |
| Countries are shaded by Gap Score using a diverging green–red colour scale | Visual inspection: green = low gap, red = high gap |
| Hovering over a country shows a tooltip with: country name, Gap Score, Commitment Score, Implementation Score, and a one-line interpretation | Hover over 5 countries and confirm all five fields appear |
| Countries with no data are shown in grey with a "no data" tooltip | Hover over a country with missing data and confirm the grey shading and label |
| Clicking a country opens a detail panel | Click 3 countries and confirm the panel opens each time |

### 1.2 Gap Score
| Criterion | Test |
|-----------|------|
| The Gap Score is computed as: Commitment Score minus Implementation Score, both normalised to 0–100 | Run the scoring script on 5 known countries and verify outputs by hand |
| The Commitment Score aggregates: number of agreements, DTA depth score, DESTA design score, and tariff liberalisation rate | Inspect the scoring function: confirm all four inputs are present |
| The Implementation Score aggregates: WTO dispute rate, ISDS dispute rate, GTA distortion ratio, NTM coverage ratio, STC count, and AVE of NTMs | Inspect the scoring function: confirm all six inputs are present |
| Default weighting is equal across all measures within each dimension | Inspect weights config: all values equal |
| User can adjust weights via a sidebar slider and the map updates in real time | Change one weight slider and confirm the map re-renders with updated scores |
| Countries are assigned to one of four quadrants based on their Commitment and Implementation Scores | Check that every country in the dataset has a quadrant label |

### 1.3 Country detail panel
| Criterion | Test |
|-----------|------|
| Clicking a country opens a side panel | Confirmed in 1.1 |
| The panel shows a radar chart with the country's scores on all individual measures | Inspect chart: confirm all 10 measures appear as axes |
| The panel shows a bar chart comparing the country to a user-selected peer group | Select a peer group and confirm the bar chart updates |
| The panel shows a Claude-generated narrative summarising the country's record | Trigger narrative generation and confirm output appears, clearly labelled as AI-generated |
| All data points in the panel are traceable to a named source | Each data point shows a source label or footnote |

### 1.4 Filters and controls
| Criterion | Test |
|-----------|------|
| User can filter the map by region | Select "Southeast Asia" and confirm only Southeast Asian countries are highlighted |
| User can filter by agreement type (bilateral, regional, WTO-plus) | Select each filter and confirm the scoring updates accordingly |
| User can compare up to three countries side by side | Select three countries and confirm a comparison view appears |
| User can export the Gap Score table as CSV | Click export and confirm a valid CSV downloads |

---

## 2. Data requirements

### 2.1 Coverage
| Criterion | Test |
|-----------|------|
| The app covers the top 60 countries by FDI inflows as the initial dataset | Count rows in the country dataset: ≥ 60 |
| All 10 measures have data for at least 40 of the 60 countries | Run a coverage report: confirm ≥ 40 non-null values per measure |
| Countries with fewer than 6 of 10 measures available are flagged as "limited data" in the UI | Identify 3 such countries in the dataset and confirm the flag appears in the app |

### 2.2 Sources and integrity
| Criterion | Test |
|-----------|------|
| Every data point is traceable to a named source listed in `sources.csv` | Cross-check 10 random data points against `sources.csv` |
| No data is fabricated or estimated without explicit labelling | Code review: no hardcoded country scores or synthetic fills without a label |
| Data vintage is displayed in the app (e.g. "DTA data: 2023 edition") | Inspect the UI: confirm vintage labels appear in the data sources section |
| Missing data is shown explicitly in the UI — never imputed silently | Set one value to null in test data and confirm the UI shows "no data" |

---

## 3. Visual and interaction design

### 3.1 Layout
| Criterion | Test |
|-----------|------|
| The map occupies the full width of the main panel on load | Visual inspection at 1440px viewport width |
| The sidebar contains: region filter, agreement type filter, weight sliders, and country comparison selector | Visual inspection |
| The country detail panel opens to the right of or below the map without obscuring it | Open a country panel and confirm the map remains visible |
| The app is usable on a 13-inch laptop screen (1280 × 800) without horizontal scrolling | Test at 1280px width |

### 3.2 Colour and typography
| Criterion | Test |
|-----------|------|
| The choropleth uses the primary green (`#00A651`) for low-gap countries and red for high-gap countries, with a neutral midpoint | Visual inspection of colour scale |
| All Plotly charts use the colour palette: green `#00A651`, blue `#004B87`, orange `#F7941D` | Inspect chart traces: confirm hex values |
| Font is consistent throughout and readable at standard zoom | Visual inspection |
| AI-generated text is visually distinguished (e.g. italicised or in a labelled box) | Visual inspection of the narrative component |

### 3.3 Performance
| Criterion | Test |
|-----------|------|
| The map loads within 3 seconds on a standard laptop | Time the load from `streamlit run app.py` to first render |
| Switching between countries in the detail panel takes under 2 seconds | Time 5 country switches |
| The Claude narrative generates within 15 seconds | Time narrative generation for 3 countries |

---

## 4. Quality gates

The app is ready to demo when all of the following are true:

- [ ] All 1.1–1.4 functional criteria pass
- [ ] Data covers ≥ 60 countries with ≥ 6 measures each
- [ ] Gap Score is reproducible by hand for any country in the dataset
- [ ] The map, radar chart, and bar chart all render without errors
- [ ] The Claude narrative generates without errors and is clearly labelled as AI-generated
- [ ] No API keys or credentials are committed to version control
- [ ] The app runs from a clean `conda` environment using only `requirements.txt`
- [ ] A five-minute demo walkthrough has been rehearsed end-to-end
