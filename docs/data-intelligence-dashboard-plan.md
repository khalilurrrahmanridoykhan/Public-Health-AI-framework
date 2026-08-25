# PHFrame Data Intelligence and Professional Dashboard Plan

## Status

- Implementation started on 2026-08-25.
- Work package 7.1 is in progress: browser files and connector syncs now share staging, immutable dataset versions, provenance, deterministic column profiling, semantic candidates, profile APIs, and the initial review interface.
- Remaining 7.1 scope: add explicit version-management controls and finish profiling/background-job performance safeguards for very large sources.
- Proposed delivery remains divided into independently testable work packages.

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

## 13. Intelligence expansion: minimum-work, expert-quality dashboards

### North-star experience

For a well-structured source, PHFrame should turn an import or connector sync into a useful draft dashboard without manual chart construction:

1. Connect or upload data.
2. Profile, enrich, validate, and fingerprint it automatically.
3. Present one Data Health Report and only decisions that cannot be resolved safely.
4. Generate three ranked options: **Recommended**, **Executive**, and **Programme operations**. Add a **Data quality** dashboard when issues merit it.
5. Let the user preview, approve, and publish; every generated decision remains editable and reversible.

When confidence is high, the target is no more than three user decisions before the first useful dashboard. Low-confidence semantics, privacy risks, invalid denominators, and destructive repairs must always stop for review.

### Progressive autonomy

- **Preview:** PHFrame suggests but changes nothing.
- **Assisted:** safe metadata enrichment and reversible normalization can be accepted in one batch; analytical meaning still needs approval.
- **Guarded automatic:** previously approved project rules can run after future syncs, with a change summary and rollback point.

The system must never silently invent an indicator definition, denominator, geographic join, or clinical interpretation.

### Deterministic-first intelligence architecture

AI is a planning and explanation layer, not the calculation engine. The trusted pipeline is:

`source -> immutable staging -> deterministic profiler -> quality engine -> semantic model -> constrained dashboard specification -> renderer`

AI may propose inputs, but typed validators reject unsupported fields, formulas, joins, filters, chart types, and privacy-unsafe output. Aggregate calculations remain reproducible SQL/Python operations with visible formulas and lineage.

The intelligence layer contains:

- a metadata resolver for source-native labels, units, option sets, aggregation rules, periods, and organisation hierarchies;
- a versioned public-health indicator and dashboard knowledge catalogue;
- retrieval that selects only relevant, attributable definitions and templates;
- a constrained planner that emits typed `SemanticProposal`, `RepairProposal`, and `DashboardSpec` objects;
- deterministic validation, scoring, preview-diff, approval, audit, and rollback services.

### Dataset fingerprint and living data contract

Each approved version receives a fingerprint containing its schema signature, semantic roles, time and geographic grain, key candidates, category vocabularies, missingness, cardinality, ranges, duplicates, and quality score. Approved inferences become a versioned data contract.

Every later sync checks renamed or missing columns, changed types, new categories, unit and code-list changes, hierarchy changes, unusual volume, and altered time coverage. Drift creates a review task and safe dashboard preview; it never silently changes a published dashboard.

### Source-aware metadata enrichment

- **DHIS2:** resolve UIDs to names, descriptions, value types, units, aggregation operators, period types, category option combinations, organisation-unit paths, coordinates, and data-set membership.
- **KoboToolbox/ODK:** resolve question labels, choices, groups, repeats, constraints, language variants, and form versions.
- **Files and REST APIs:** infer semantics from names and values, then offer mappings to recognized roles and code systems for confirmation.

Raw identifiers remain in lineage but must not appear as dashboard labels when readable metadata exists.

### Versioned public-health knowledge packs

Ship curated packs for routine service delivery, maternal and child health, immunization, disease surveillance, malaria, nutrition, supply availability, and data quality. Each indicator includes:

- name, purpose, version, and authoritative source link;
- numerator, denominator, exclusions, multiplier, unit, directionality, and valid aggregation;
- required semantic roles and compatible time/geographic grains;
- expected ranges, companion quality checks, and limitations;
- recommended KPI, trend, comparison, table, and map views;
- privacy classification and minimum safe aggregation.

AI may retrieve and recommend a pack but cannot change its formula. A custom indicator remains **project-defined** until a person approves it.

### Bounded intelligence assistants

- **Schema Copilot:** proposes storage types, roles, keys, units, and readable labels.
- **Quality Copilot:** groups issues, explains impact, and proposes repair recipes.
- **Indicator Copilot:** matches fields to governed measures and states what is missing.
- **Geography Copilot:** detects hierarchy levels, boundary keys, points, and ambiguous joins.
- **Dashboard Designer:** ranks templates and compiles the dashboard specification.
- **Insight Copilot:** explains approved aggregate results with evidence, freshness, and limitations.
- **Maintenance Copilot:** detects drift, broken cards, stale data, and changed recommendations.

Every proposal shows confidence, evidence, affected fields/rows, expected dashboard impact, and reversibility. Low-confidence items become questions, not automatic changes.

### Smart repair recipes

- **Safe and reversible:** trim whitespace, normalize empty markers, parse unambiguous dates, and resolve labels from authoritative metadata.
- **Review required:** deduplicate, impute, map unknown categories, change units, repair hierarchy, or exclude outliers.
- **Forbidden automatically:** fabricate observations, infer patient outcomes, overwrite source values, probabilistically merge people, or weaken privacy controls.

A repair preview shows before/after samples, affected rows, rationale, quality-score change, and impacted visualizations. Approved decisions may become project-scoped recipes; they must not train a cross-project model or expose another project's data.

### Dashboard recommendation, scoring, and refinement

Score candidates for semantic correctness, quality readiness, decision usefulness, visual diversity, readability, accessibility, privacy, geographic validity, and rendering cost. Automatically reject:

- duplicate charts answering the same question;
- identifiers or high-cardinality fields used as categories;
- pies/donuts with excessive categories;
- ratios without valid denominators;
- misleading axes;
- maps without reliable geographic matches;
- low contrast, crowded legends, and unreadable labels;
- cards based on stale, blocked, or low-quality fields.

Every card includes **Why this view**, fields, formula, filters, aggregation, freshness, quality status, and limitations. The header includes reporting period, geography, programme, freshness, and filter chips. Layout density and chart detail adapt to both width and height.

### Natural-language Dashboard Studio

Users may ask, “Build a district immunization dashboard for the last 12 months” or “Replace this donut with a trend and filter to Region A.” PHFrame translates the request into its constrained dashboard schema, presents a visual and semantic diff, validates it, and waits for approval. It must not execute arbitrary SQL, Python, HTML, or external URLs supplied through imported data.

Quick actions include: make this clearer; explain this chart; find a better denominator; show missing data by facility; compare periods; create an executive version; repair safe issues; and update the published dashboard after approval.

### Continuous intelligence after publication

After each import or sync, PHFrame recalculates fingerprints, rules, measures, and card health. It produces a change brief covering new periods, revised values, categories, quality, schema drift, and affected publications. Safe data refreshes may update an existing deployment URL under an approved policy; structural or semantic changes require preview and approval.

### Privacy, security, and human control

- Local deterministic analysis is the default.
- External AI receives no row-level or protected fields; only minimum approved, de-identified aggregate context may leave the server.
- Imported text is untrusted and cannot override instructions, invoke tools, or introduce executable content.
- AI output must follow strict schemas, reference real fields and knowledge entries, and pass authorization and privacy checks.
- Prompts, evidence, proposals, approvals, rejections, provider/model/version, and final changes are auditable.
- A person approves publication, destructive repair, semantic changes, and official AI-generated narrative.

### Intelligence evaluation and product metrics

Maintain golden datasets and expert-reviewed dashboard specifications. Release gates measure semantic inference, duplicate/quality false positives, indicator matching, invalid-formula rejection, geographic joins, recommendation acceptance, post-generation edit distance, accessibility, responsiveness, performance, and time to first approved dashboard. Track the percentage of high-confidence datasets completed in three decisions or fewer. Unsupported factual or numerical claims have a target of zero.

Evaluation must include adversarial imported text, ambiguous columns, schema changes, sparse data, mixed units, invalid denominators, and protected data.

### Source-informed design basis

Core quality reporting should align with WHO dimensions covering completeness/timeliness, internal consistency, external consistency, and comparison with population or denominator data. Knowledge packs should favor a limited, standardized set of decision-relevant indicators and understandable displays instead of every possible chart. AI governance should follow the NIST AI RMF functions **Govern, Map, Measure, and Manage**, emphasizing validity, transparency, explainability, privacy, and human oversight.

- WHO Data Quality Assurance: https://www.who.int/data/data-collection-tools/health-service-data/data-quality-assurance-dqa
- WHO routine health-facility analysis toolkit: https://www.who.int/data/data-collection-tools/analysis-use-health-facility-data
- WHO RHIS general principles: https://www.who.int/publications/i/item/9789240063938
- NIST AI RMF and Playbook: https://airc.nist.gov/ and https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook

## 14. Delivery work packages

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
- dataset fingerprints, living contracts, and drift detection;
- source-aware metadata enrichment.

**Exit criteria:** every recommended chart is traceable to compatible typed fields and a defined aggregation.

### 7.6 — Professional dashboard generator

- purpose-based templates;
- global filter header;
- polished responsive components;
- quality/freshness context;
- preview, customization, and publication checks.
- dashboard linting, scoring, refinement, and explanation cards;
- Recommended, Executive, Programme operations, and Data quality variants.

**Exit criteria:** generated dashboards contain an intentional analytical story, readable labels, appropriate filters, and no duplicate filler charts.

### 7.7 — Governed knowledge packs and intelligence copilot

- versioned indicator, visualization, and programme packs with attribution;
- constrained schema, quality, indicator, geography, and dashboard proposals;
- natural-language Dashboard Studio with diff, validation, approval, and undo;
- local-first processing, structured output, prompt-injection defenses, and audit history.

**Exit criteria:** intelligence reduces work without bypassing formula governance, privacy checks, reproducibility, or human approval.

### 7.8 — Continuous dashboard assurance

- re-score data, measures, and dashboards after every sync;
- produce drift briefs and previews of affected dashboards;
- support approved refresh-in-place for existing public URLs;
- add golden-dataset evaluation and intelligence release gates.

**Exit criteria:** data changes cannot silently make an approved or published dashboard misleading.

## 15. Testing strategy

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

## 16. Acceptance criteria for the complete phase

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
- A high-confidence dataset produces its first useful dashboard in three decisions or fewer.
- PHFrame offers ranked variants and explains every recommendation.
- Dashboard labels contain no raw source IDs when readable metadata exists.
- AI cannot publish, destructively repair, invent formulas, or alter semantics without approval.
- Every AI proposal is structured, validated, attributable, confidence-scored, auditable, and reversible.
- Later syncs detect contract drift and preview effects on existing dashboards before structural updates.
- Golden-dataset evaluations meet documented quality, safety, accessibility, and recommendation thresholds.

## 17. Recommended implementation order

Implement 7.1 through 7.8 in sequence. The professional dashboard generator should not be rebuilt first, because its quality depends on the semantic model, validated dataset version, resolved labels, measures, time fields, and geographic hierarchy produced by the earlier work packages. AI copilots follow the deterministic foundation and generator so they can propose changes against enforceable schemas instead of producing unverified charts.

The first implementation milestone should therefore be **7.1 — Staging and profiling foundation**.
