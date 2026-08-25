# PHFrame Data Intelligence and Professional Dashboard Plan

## Status

- Planning document only
- No implementation is included in this change
- Proposed delivery: Phase 7, divided into independently testable work packages

## Problem statement

PHFrame can ingest records and generate dashboards, but imported columns currently do not carry enough semantic meaning for consistently useful visualizations. A technically valid file can still contain duplicate rows, missing values, invalid dates, inconsistent category labels, impossible coordinates, broken administrative hierarchies, or identifiers that are not understandable to dashboard users.

The next phase should therefore treat dashboard creation as the final step of a governed data pipeline:

```text
Source → staging → profiling → validation → repair/approval → semantic model
       → geographic model → dashboard recommendation → professional dashboard
```

No imported or synchronized data should silently become a dashboard. PHFrame should first explain what it found, what is safe to use, what requires attention, and how every selected visualization relates to the data model.

## Goals

1. Apply the same ingestion workflow to files, DHIS2, KoboToolbox, ODK Central, and REST APIs.
2. Stage data before it reaches production datasets or dashboards.
3. Profile every column and infer both its storage type and public-health meaning.
4. Detect duplicates, missingness, invalid values, outliers, inconsistent categories, geographic problems, and structural problems.
5. Give users row-level and column-level explanations with safe repair actions.
6. Require explicit human approval for destructive cleaning or ambiguous type decisions.
7. Model country-to-facility administrative hierarchies without assuming Bangladesh-specific columns.
8. Generate dashboard filters and visualizations from compatible semantic types.
9. Produce polished dashboards with hierarchy, context, accessible presentation, and responsive layouts.
10. Preserve provenance and an audit trail from source record to published dashboard.

## Non-goals

- PHFrame will not silently delete or alter source data.
- PHFrame will not claim that a dataset is epidemiologically correct solely because it passes technical validation.
- PHFrame will not infer diagnoses or make clinical decisions.
- PHFrame will not hard-code Bangladesh, DHIS2, or any particular programme into the universal data model.
- Dashboard templates will not select arbitrary charts solely because a column is numeric.

## 1. Unified ingestion and staging

All sources should produce the same internal staging package:

- source type and connection identifier;
- source filename, endpoint, form, or DHIS2 dataset UID;
- import/sync timestamp;
- immutable source-row identifier;
- raw values exactly as received;
- normalized preview values;
- inferred schema candidates;
- source metadata and labels where available;
- validation results;
- transformation and approval history.

### Source adapters

| Source | Metadata to retain | Special handling |
|---|---|---|
| CSV/Excel | sheet, row, original headers | encoding, merged headers, empty rows, formula cells |
| JSON/XML | record path and source paths | nested objects, arrays, repeated elements |
| REST API | endpoint, pagination, response path | schema drift and rate limits |
| DHIS2 | dataset, data element, category combinations, period, org unit | resolve UIDs to display names and import organisation hierarchy |
| KoboToolbox | asset, question names, labels, choices | repeated groups and multilingual labels |
| ODK Central | project, form, field paths, choices | repeat tables and OData types |

### Import states

1. `received`
2. `profiling`
3. `review_required`
4. `approved`
5. `importing`
6. `ready`
7. `rejected` or `failed`

Dashboards should use only approved dataset versions by default.

## 2. Column profiler and semantic type inference

PHFrame should create one profile row for every source column. Each profile should show:

- source name and proposed display label;
- inferred storage type;
- inferred semantic role;
- confidence score and reasons;
- non-null, unique, duplicate, and invalid counts;
- minimum, maximum, mean, median, and percentiles where applicable;
- category cardinality and most common values;
- example values with protected values masked;
- recommended transformations;
- user-selected final type.

### Storage types

- string/text
- integer
- decimal/number
- boolean
- date
- datetime
- JSON/object
- list/multiple choice
- binary/file reference

### Semantic public-health types

- identifier
- protected identifier/PII
- category/choice
- multi-select category
- free text
- count
- continuous measurement
- numerator
- denominator
- percentage/proportion
- rate/ratio
- currency
- reporting period
- epidemiological week
- age or age group
- sex/gender
- disease/programme code
- organisation-unit UID
- organisation-unit name
- administrative level
- facility
- country/ISO code
- latitude
- longitude
- geographic point
- polygon/multipolygon
- GeoJSON geometry
- boundary identifier
- address/location label

### Inference strategy

Inference should combine:

1. source metadata types;
2. normalized column names and labels;
3. sampled and full-column value checks;
4. uniqueness and cardinality;
5. known public-health patterns;
6. paired-field detection such as latitude plus longitude;
7. hierarchy relationships between columns;
8. connector-specific metadata such as DHIS2 value types;
9. user confirmation when confidence is below a defined threshold.

The user must always be able to override an inference. Overrides should be audited and reused as mapping rules in future syncs.

## 3. Data-quality framework

The quality engine should combine generic data engineering checks with public-health validation dimensions commonly used in routine health information systems.

### Quality dimensions

- **Completeness:** required fields and expected reports are present.
- **Uniqueness:** duplicate records and duplicate identifiers are detected.
- **Validity:** values match type, range, format, and allowed categories.
- **Consistency:** related fields agree within and across records.
- **Timeliness:** reports fall inside expected reporting windows.
- **Integrity:** identifiers, foreign keys, and hierarchy parents resolve correctly.
- **Plausibility:** values, changes, and ratios are operationally credible.
- **Concordance:** aggregates reconcile with component values when rules exist.
- **Geographic quality:** coordinates, boundaries, and administrative levels are valid.
- **Privacy readiness:** protected fields are classified before analysis or publication.

### Core rule library

#### Row and identity checks

- exact duplicate row;
- duplicate primary identifier;
- probable duplicate based on configurable field combinations;
- blank row;
- missing required identifier;
- conflicting versions of the same record.

#### Type and format checks

- invalid integer or decimal;
- invalid date or reporting period;
- ambiguous date format;
- invalid boolean or category;
- malformed JSON/GeoJSON;
- invalid latitude or longitude range;
- invalid polygon or self-intersection;
- invalid ISO code or organisation UID format.

#### Public-health logic checks

- negative counts where prohibited;
- numerator greater than denominator;
- percentage outside 0–100;
- age outside configured plausible limits;
- onset date after report date;
- future reporting period;
- impossible epidemiological week;
- missing denominator for a rate;
- facility not belonging to the selected administrative unit.

#### Statistical and time-series checks

- outlier by robust interquartile or median-absolute-deviation method;
- sudden spike or drop relative to recent periods;
- flat-line reporting;
- repeated identical values across many periods;
- unexpected zero or missing-report pattern;
- large revision from a previous synchronized version.

Rules must have configurable severity: `information`, `warning`, `error`, or `blocking`.

## 4. Data-quality review workspace

After profiling, PHFrame should show a guided review instead of immediately opening a dashboard.

### Summary header

- overall readiness score;
- total rows and columns;
- valid, warning, error, and blocking counts;
- duplicate count;
- protected-field count;
- geographic readiness;
- dashboard readiness;
- source and last refresh time.

The score must never hide the underlying results. It is a navigation aid, not a certification.

### Issue explorer

Users should be able to filter by:

- severity;
- rule;
- column;
- row;
- administrative unit;
- reporting period;
- source;
- resolved/unresolved state.

Each issue should contain:

- plain-language explanation;
- affected row and field;
- original value;
- expected format or rule;
- suggested correction;
- impact on indicators or dashboards;
- repair, exclude, ignore-with-reason, and inspect-source actions.

### Repair actions

- trim spaces and normalize casing;
- parse numbers and dates;
- map category aliases to canonical values;
- replace recognized missing-value markers;
- merge or remove confirmed duplicates;
- exclude invalid rows from an approved analytical view;
- map organisation units;
- correct coordinate order;
- assign or change a semantic type.

All bulk changes require a preview showing affected-row counts. Original data remains immutable, and every accepted change becomes a versioned transformation.

## 5. Geographic and administrative hierarchy model

PHFrame should support an arbitrary number of administrative levels rather than named country-specific columns.

Example:

```text
Country → Division/Region → District → Subdistrict → Ward → Facility
Bangladesh → Dhaka → Dhaka South → Jatrabari → Ward 50 → Clinic A
```

### Detection

- infer likely parent-child columns from names, cardinality, and containment;
- recognize codes and names as separate attributes of the same level;
- use DHIS2 organisation-unit metadata when available;
- identify latitude/longitude, point, polygon, and boundary-key columns;
- compare values with installed boundary layers;
- report ambiguous or orphaned nodes for human mapping.

### Canonical structure

Each geographic entity should have:

- stable internal ID;
- source ID and source system;
- name and optional aliases;
- level number and configurable level label;
- parent ID;
- country ISO3;
- geometry or centroid when available;
- validity dates;
- mapping confidence and approval state.

### Dashboard behavior

- hierarchy-aware cascading filters;
- drill-down and drill-up on maps and charts;
- automatic map zoom to selected geography;
- comparison within the same administrative level;
- clear handling of records that do not map to a boundary;
- optional facility-point overlay on choropleth maps.

## 6. Analytical semantic model

Dashboard generation should use explicit analytical roles rather than raw columns.

### Field roles

- dimension
- measure
- time dimension
- geographic dimension
- identifier
- descriptive attribute
- protected/excluded field

### Measure definitions

A measure should define:

- aggregation: count, distinct count, sum, average, median, minimum, maximum;
- numerator and denominator where relevant;
- multiplier such as 100, 1,000, or 100,000;
- unit and number format;
- valid filters;
- missing-value behavior;
- comparison period;
- privacy threshold for publication.

Raw DHIS2 UIDs should be resolved to labels before dashboard generation whenever metadata permission allows.

## 7. Visualization compatibility engine

The background recommendation engine should rank visualizations using field roles, cardinality, data volume, hierarchy, time coverage, and quality results.

| Data shape | Recommended visualizations | Avoid by default |
|---|---|---|
| Single validated measure | KPI, progress card, bullet chart | pie/donut |
| Measure over ordered time | line, area, column, sparkline | unordered pie |
| Measure by low-cardinality category | sorted bar, column, dot plot | line chart |
| Part-to-whole with 2–6 categories | stacked bar, donut when labels are short | donut with many slices |
| Two continuous measures | scatter plot | categorical bar |
| Distribution of a continuous value | histogram, box plot | donut |
| Administrative boundary plus measure | choropleth map | tile blocks |
| Latitude/longitude plus measure | point, bubble, or cluster map | choropleth without boundary key |
| Parent-child geography | drill-down map, hierarchical table | flat unrelated filters |
| Many categories | searchable table, ranked bar with Top N | full unbounded legend |
| Numerator and denominator | percentage/rate KPI plus trend | raw sum without context |

Every recommendation should include a short reason. Incompatible visualization choices should be disabled or clearly warned, not silently rendered badly.

## 8. Dashboard generation workflow

### Step 1: Select approved dataset version

Show source, refresh status, quality score, unresolved issues, and time/geographic coverage.

### Step 2: Confirm analytical meaning

Confirm measures, dimensions, time field, geographic hierarchy, labels, and units.

### Step 3: Choose dashboard purpose

- executive overview;
- surveillance monitoring;
- programme coverage;
- service delivery;
- commodity/stock monitoring;
- data-quality operations;
- geographic situation room;
- custom blank canvas.

### Step 4: Preview recommendations

PHFrame should propose a complete dashboard and explain why each component was chosen. The user may accept all, select individual components, or start blank.

### Step 5: Review and publish

Check accessibility, responsiveness, privacy thresholds, unresolved quality risks, source attribution, and publication mode.

## 9. Professional dashboard anatomy

A generated dashboard should have a deliberate information hierarchy:

1. **Context header:** title, programme, reporting period, source freshness, quality badge.
2. **Global filter bar:** period, geography, programme/category, reset, active-filter summary.
3. **Headline KPIs:** 3–5 meaningful measures with unit, comparison, and trend.
4. **Primary analytical story:** time trend, target progress, or geographic pattern.
5. **Breakdowns:** ranked categories, facility/area comparisons, demographic groups.
6. **Map section:** only when geographic readiness passes.
7. **Data-quality callout:** completeness, timeliness, and unresolved risks.
8. **Detail table:** searchable and exportable, with privacy controls.
9. **Method/source footer:** definitions, last updated, source systems, and limitations.

### Visual requirements

- consistent spacing, typography, and card hierarchy;
- readable chart labels rather than raw codes;
- responsive reflow without internal scrollbars where avoidable;
- useful empty, loading, error, and stale-data states;
- accessible color palettes and non-color encodings;
- configurable organization branding without damaging contrast;
- chart annotations and tooltips with units and context;
- Top N plus “Other” handling for high-cardinality categories;
- compact edit controls separated from the public viewing mode.

## 10. Global filters

Filters should be derived from semantic roles and apply consistently to every compatible widget.

Required capabilities:

- reporting-period range and presets;
- cascading administrative hierarchy;
- organisation unit/facility;
- categorical and multi-select values;
- saved filter views;
- clear-all and active-filter chips;
- URL-serializable filter state for shareable views;
- widget-level opt-out or override;
- filter impact preview and record count;
- keyboard and mobile accessibility.

## 11. Data model additions

Proposed entities:

- `IngestionRun`
- `SourceSnapshot`
- `DatasetVersion`
- `ColumnProfile`
- `SemanticField`
- `QualityRule`
- `QualityIssue`
- `RepairAction`
- `TransformationRecipe`
- `ApprovalDecision`
- `GeographicEntity`
- `GeographicMapping`
- `MeasureDefinition`
- `VisualizationRecommendation`
- `DashboardTemplateVersion`

All entities should include creation time, actor, source/version references, and audit metadata.

## 12. API and job boundaries

Long-running tasks must become background jobs with progress reporting:

- profiling;
- duplicate detection;
- rule evaluation;
- geographic matching;
- transformation preview/application;
- large import approval;
- dashboard recommendation generation.

The browser should receive job state and summarized results rather than waiting on a single long request.

## 13. Delivery work packages

### 7.1 — Staging and profiling foundation

- unified staging package;
- dataset versions and provenance;
- column statistics and semantic type candidates;
- profile API and initial review screen.

**Exit criteria:** every supported connector and file import creates the same inspectable profile before approval.

### 7.2 — Quality rules and issue review

- generic and public-health rule library;
- duplicate detection;
- severity and readiness calculation;
- issue explorer and row/column detail.

**Exit criteria:** users can identify why records are unsafe or unsuitable for analysis.

### 7.3 — Repair, approval, and audit

- transformation previews;
- safe bulk fixes;
- exclusions and ignore-with-reason;
- immutable originals and approved versions.

**Exit criteria:** no destructive change occurs without preview, approval, and audit history.

### 7.4 — Geography and hierarchy intelligence

- hierarchy inference and mapping;
- DHIS2 organisation-unit metadata resolution;
- coordinate and geometry validation;
- cascading geographic filters and drill-down.

**Exit criteria:** country-to-facility hierarchies and map readiness are explicitly validated.

### 7.5 — Semantic measures and visualization compatibility

- analytical roles;
- measure builder;
- compatibility/ranking engine;
- label and metadata resolution.

**Exit criteria:** every recommended chart is traceable to compatible typed fields and a defined aggregation.

### 7.6 — Professional dashboard generator

- purpose-based templates;
- global filter header;
- polished responsive components;
- quality/freshness context;
- preview, customization, and publication checks.

**Exit criteria:** generated dashboards contain an intentional analytical story, readable labels, appropriate filters, and no duplicate filler charts.

## 14. Testing strategy

### Unit tests

- type inference and confidence;
- each quality rule;
- duplicate matching;
- hierarchy detection;
- measure calculations;
- visualization compatibility.

### Contract tests

- Excel/CSV/JSON/XML staging;
- DHIS2, Kobo, ODK, and REST metadata normalization;
- schema drift between synchronization runs.

### Integration tests

- ingestion through approval;
- repair preview and audit;
- approved version to dashboard;
- filter propagation;
- geographic drill-down;
- published snapshot privacy checks.

### UX and accessibility tests

- keyboard-only review and dashboard use;
- screen-reader labels and issue announcements;
- mobile and narrow viewport layouts;
- color contrast and non-color status indicators;
- large dataset loading and progress states.

### Reference datasets

Maintain synthetic fixtures containing known duplicates, missing reports, invalid dates, category aliases, hierarchy errors, outliers, points, and polygons. Expected results must be deterministic.

## 15. Acceptance criteria for the complete phase

- All ingestion methods enter staging before dashboard generation.
- Every column receives a profile, inferred type, confidence, and user-confirmable role.
- Duplicate, missing, invalid, inconsistent, outlier, timeliness, and geographic checks are available.
- Users can inspect affected rows and approve reversible corrections.
- Raw source data remains unchanged and transformations are auditable.
- Administrative hierarchies are configurable and not country-specific.
- Dashboard filters cascade correctly across time, geography, and categories.
- Visualization recommendations enforce semantic compatibility.
- Raw connector codes are replaced by human-readable labels where metadata exists.
- Generated dashboards include context, KPIs, primary analysis, breakdowns, quality status, and methods/source information.
- Dashboards work responsively and meet the existing accessibility baseline.
- Publication continues to block protected row-level data.
- Performance targets are defined and verified for small, medium, and large datasets.

## 16. Recommended implementation order

Implement 7.1 through 7.6 in sequence. The professional dashboard generator should not be rebuilt first, because its quality depends on the semantic model, validated dataset version, resolved labels, measures, time fields, and geographic hierarchy produced by the earlier work packages.

The first implementation milestone should therefore be **7.1 — Staging and profiling foundation**.
