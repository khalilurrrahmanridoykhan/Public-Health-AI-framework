# PHFrame Development Plan

## Vision

PHFrame will be an open-source framework for building public-health data systems, surveillance platforms, registries, dashboards, and AI-assisted reporting tools.

It should offer the extensibility of a backend framework and the reusable interface model of a frontend framework without requiring application developers to use Django or React directly. PHFrame will expose its own public APIs, conventions, component system, and development workflow while relying on stable lower-level standards and libraries.

The framework's main differentiator will be built-in understanding of public-health data, including indicators, reporting periods, organisation units, surveillance, data-quality rules, privacy, and interoperability.

## Product Identity

- **Framework name:** PHFrame
- **CLI command:** `phframe`
- **Repository:** `public-health-framework`
- **Initial specialization:** Disease surveillance
- **Long-term scope:** Configurable public-health information systems

The intended developer experience is:

```bash
pip install phframe
phframe new malaria-surveillance
cd malaria-surveillance
phframe serve
```

## Guiding Principles

1. Public-health workflows come before generic framework features.
2. Developers should be able to extend every major subsystem.
3. Verified calculations must remain deterministic and testable.
4. AI assists professionals but does not make autonomous clinical decisions.
5. Privacy, security, auditability, accessibility, and localization are core requirements.
6. Local development should work with SQLite and minimal configuration.
7. Production deployments should support PostgreSQL and background workers.
8. Offline and low-bandwidth environments must be considered in architectural decisions.
9. PHFrame will use proven protocols and low-level libraries instead of recreating database drivers, cryptography, or HTTP servers.
10. A real surveillance application will guide framework development.

## High-Level Architecture

```text
┌───────────────────────────────────────────┐
│ Public-health applications                │
│ Surveillance · Registries · Dashboards    │
├───────────────────────────────────────────┤
│ PHFrame UI                                │
│ Forms · Tables · Charts · Maps · Filters  │
├───────────────────────────────────────────┤
│ Public-health engine                      │
│ Indicators · Validation · Aggregation     │
├───────────────────────────────────────────┤
│ Backend framework                         │
│ Models · APIs · Auth · Jobs · Plugins     │
├───────────────────────────────────────────┤
│ Data and integration layer                │
│ Excel · DHIS2 · Kobo · FHIR · Databases   │
└───────────────────────────────────────────┘
```

## Technology Direction

### Backend

- Python as the primary framework language
- ASGI as the server protocol
- SQLite for development and small deployments
- PostgreSQL for production deployments
- SQLAlchemy or a thin PHFrame persistence abstraction
- Background jobs for imports, synchronization, reports, and AI processing
- OpenAPI-compatible HTTP APIs

Users will program against PHFrame concepts rather than Django concepts:

```python
from phframe import Application, Dataset, Indicator

app = Application("Malaria Surveillance")

cases = Dataset(
    name="malaria_cases",
    fields={
        "district": "location",
        "report_date": "date",
        "confirmed_cases": "integer",
        "population": "integer",
    },
)

incidence = Indicator(
    name="Malaria incidence",
    numerator="confirmed_cases",
    denominator="population",
    multiplier=100_000,
)

app.register(cases)
app.register(incidence)
```

### Frontend

- TypeScript for maintainable browser code
- Standards-based Custom Elements and Web Components
- HTML and CSS design tokens
- No React requirement
- Reusable public-health components
- Server-provided metadata and dashboard definitions
- Progressive enhancement for low-bandwidth environments

Example component API:

```html
<ph-kpi indicator="malaria-incidence" period="2026-Q1"></ph-kpi>

<ph-epi-curve
  dataset="malaria-cases"
  date-field="onset_date">
</ph-epi-curve>

<ph-map boundary="district" indicator="confirmed-cases"></ph-map>
```

## Core Subsystems

### 1. Application Framework

Responsibilities:

- Project creation and discovery
- Configuration and environment handling
- Development and production modes
- Application lifecycle
- Plugin registration
- Routing
- Logging
- Error handling
- Database migrations
- Deployment configuration

Planned commands:

```bash
phframe new <project-name>
phframe serve
phframe migrate
phframe import <source>
phframe check
phframe test
phframe build
```

### 2. Public-Health Data Models

PHFrame will provide health-specific field types and metadata:

- Patient or case identifier
- Protected personally identifiable information
- Disease and diagnosis codes
- Organisation units
- Administrative locations
- Health facilities
- Geographic points and boundaries
- Age and age groups
- Sex and gender
- Epidemiological week
- Reporting period
- Case classification
- Laboratory result
- Numerator and denominator
- Program targets

Example:

```python
class CaseRecord(Model):
    patient_id = Identifier(protected=True)
    disease = DiseaseCode(required=True)
    onset_date = Date()
    facility = OrganisationUnit()
    location = GeoPoint()
    status = Choice(["suspected", "probable", "confirmed"])
```

### 3. API Layer

PHFrame should generate and support:

- Create, read, update, and delete APIs
- Validation
- Filtering and pagination
- Aggregate queries
- Indicator results
- Metadata discovery
- Import and export operations
- API documentation
- Versioned APIs
- Extension hooks

### 4. Authentication and Authorization

Public-health deployments commonly require hierarchical access. PHFrame should support:

- User accounts and secure sessions
- Role-based permissions
- Organisation-unit-based permissions
- National, regional, district, and facility scopes
- Field-level protection
- Data de-identification
- Approval workflows
- Audit logs
- Data-retention policies
- Single sign-on extensions

### 5. Background Jobs

Background processing will handle:

- Large file imports
- Scheduled DHIS2 synchronization
- KoboToolbox and ODK synchronization
- Report generation
- Notifications
- Data-quality evaluation
- Outbreak detection
- AI-assisted analysis

### 6. Frontend Components

The initial UI library should include:

- Application shell
- Navigation and routing
- KPI card
- Indicator chart
- Epidemiological curve
- Choropleth map
- Case line list
- Pivot table
- Date and reporting-period filters
- Organisation-unit selector
- Data-quality panel
- Alert panel
- Import wizard
- Metadata-driven form builder
- Accessible modal, notification, and confirmation components

### 7. Indicator Engine

The indicator engine is a central PHFrame capability. It should support:

- Counts
- Sums and averages
- Rates
- Ratios
- Percentages
- Coverage
- Positivity rates
- Incidence and prevalence
- Mortality rates
- Case-fatality rates
- Dropout rates
- Cumulative totals
- Moving averages
- Target achievement
- Disaggregation by location, time, age, sex, and other dimensions

Indicators should be definable in Python or configuration:

```yaml
indicators:
  malaria_incidence:
    label: Malaria incidence
    numerator: confirmed_cases
    denominator: population
    multiplier: 100000
    dimensions:
      - district
      - reporting_period
```

### 8. Data-Quality Engine

The engine should evaluate:

- Completeness
- Timeliness
- Internal consistency
- Duplicate records
- Outliers
- Impossible values
- Numerators exceeding denominators
- Missing organisation units
- Invalid geographic codes
- Reporting gaps
- Cross-field rules

Example rules:

```yaml
rules:
  - field: onset_date
    must_be_before: notification_date

  - expression: confirmed_cases <= tested
    message: Confirmed cases cannot exceed tested cases
```

### 9. Surveillance Engine

Surveillance-specific capabilities should include:

- Epidemiological weeks and periods
- Case definitions
- Case line lists
- Epidemic curves
- Alert thresholds
- Outbreak alerts
- Contact-tracing data models
- Outbreak investigations
- Geographic clustering
- Weekly surveillance bulletins

### 10. Integration Layer

Connectors will use a stable extension interface:

```python
class KoboConnector(Connector):
    def extract(self): ...
    def transform(self): ...
    def synchronize(self): ...
```

Integration priorities:

1. CSV and Excel
2. SQLite and PostgreSQL
3. KoboToolbox and ODK
4. DHIS2
5. Geographic boundary files
6. FHIR
7. OpenMRS
8. Laboratory information systems
9. Messaging and notification services

Connectors should support saved mappings, repeatable synchronization, error reports, and synchronization history.

## AI Strategy

AI will be optional, provider-independent, and protected by an explicit privacy layer.

### Initial AI Capabilities

- Suggest column mappings during imports
- Explain data-quality problems
- Recommend visualizations
- Generate dashboard descriptions
- Summarize weekly surveillance changes
- Draft situation reports and bulletins
- Generate indicator definitions from plain language
- Help developers create validation rules
- Answer authorized questions about aggregated datasets
- Explain unusual changes and anomalies with supporting evidence

Example command:

```bash
phframe ask "Which districts had an unusual increase in dengue this month?"
```

### AI Architecture

```python
app.ai.configure(
    provider="openai",
    model="configured-by-deployment",
    protected_fields=["patient_name", "phone"],
)
```

The abstraction should allow cloud and locally hosted models.

### AI Safety Requirements

- Remove or mask personally identifiable information before external requests.
- Require authorization before accessing sensitive data.
- Record prompts, outputs, models, and relevant configuration.
- Provide evidence for generated conclusions.
- Display uncertainty and limitations.
- Require human approval for reports and alerts.
- Support local model deployment.
- Never make autonomous diagnoses or treatment decisions.
- Never use AI-generated values in place of deterministic indicator calculations.

## Plugin System

Plugins will allow health programs and implementers to extend PHFrame without modifying its core.

Proposed plugin structure:

```text
phframe-malaria/
├── phframe_plugin.toml
├── models/
├── indicators/
├── dashboards/
├── components/
├── translations/
└── tests/
```

Potential official plugins:

- `phframe-malaria`
- `phframe-dengue`
- `phframe-immunization`
- `phframe-nutrition`
- `phframe-maternal-health`
- `phframe-outbreak`
- `phframe-dhis2`
- `phframe-kobo`
- `phframe-ai`

## Proposed Repository Structure

The project should begin as a monorepo. Subsystems can become separately published packages only after their public interfaces are stable.

```text
public-health-framework/
├── packages/
│   ├── phframe-core/
│   ├── phframe-data/
│   ├── phframe-indicators/
│   ├── phframe-server/
│   ├── phframe-cli/
│   ├── phframe-ui/
│   ├── phframe-maps/
│   └── phframe-ai/
├── connectors/
│   ├── excel/
│   ├── kobo/
│   └── dhis2/
├── examples/
│   ├── malaria-surveillance/
│   └── immunization-dashboard/
├── docs/
└── tests/
```

The initial implementation may retain a simpler source tree while interfaces are being discovered.

## Development Roadmap

### Phase 1: Framework Foundation

**Estimated scope:** 6–10 weeks

Deliverables:

- `phframe new`
- `phframe serve`
- Project configuration
- Dataset schemas
- SQLite and PostgreSQL persistence
- Automatic CRUD API
- Database migrations
- Import framework
- Plugin interface
- Development server
- Logging and structured errors
- Test helpers

Success criterion:

```bash
phframe new surveillance
cd surveillance
phframe serve
```

This starts a customizable application with a persistent database and working APIs.

### Phase 2: Public-Health Engine

**Estimated scope:** 6–8 weeks

Deliverables:

- Indicator definitions
- Aggregation engine
- Epidemiological periods
- Data-quality rules
- Organisation-unit hierarchy
- Saved dimensions and filters
- Surveillance thresholds
- Reusable public-health field types

Success criterion: developers can define a dataset and its indicators without writing custom aggregation endpoints.

### Phase 3: Frontend System

**Estimated scope:** 8–12 weeks

Deliverables:

- Web Component foundation
- Application shell and routing
- Form generator
- Tables and filters
- KPI and chart components
- Epidemiological curve
- Map component
- Dashboard configuration
- Themes and design tokens
- Localization foundation

Success criterion: a complete dashboard can be declared through configuration and extended with custom components.

### Phase 4: Connectors

**Estimated scope:** 6–10 weeks

Deliverables:

- Improved Excel and CSV import wizard
- Saved import templates
- DHIS2 connector
- KoboToolbox and ODK connector
- Scheduled synchronization
- Import history and error reports

### Phase 5: AI Assistance

**Estimated scope:** 6–8 weeks

Deliverables:

- AI provider abstraction
- Privacy and de-identification layer
- Column-mapping assistant
- Data-quality explanations
- Evidence-backed dataset questions
- Surveillance summary generator
- Human approval interface
- Complete audit trail

### Phase 6: Production Readiness

Deliverables:

- Security review
- Audit logging
- Performance and load testing
- Deployment templates
- Backups and recovery
- Migration strategy
- Documentation website
- Plugin development kit
- Internationalization
- Accessibility testing
- Reference production applications

## First Vertical Slice: Malaria Surveillance

The framework should initially be developed through one real application rather than disconnected infrastructure.

The first reference application must:

1. Define a malaria case-reporting schema.
2. Import CSV and Excel data.
3. Store records in SQLite.
4. Expose validated CRUD and aggregate APIs.
5. Display a filterable case line list.
6. Calculate incidence and test positivity.
7. Generate an epidemiological curve.
8. Evaluate data-quality rules.
9. Produce an AI-assisted weekly summary.
10. Preserve an audit history for imports and AI outputs.

This application will function as:

- A proof of concept
- An integration test
- A documentation example
- A demonstration for public-health organizations
- A basis for discovering stable framework APIs

## Immediate Next Release: PHFrame 0.2

The current version creates a one-time HTML dashboard. Version 0.2 should introduce a persistent, customizable application.

### Required Scope

- Rename and stabilize the `phframe` CLI
- Add `phframe new <project-name>`
- Generate a standard project structure
- Add project configuration
- Add `phframe serve`
- Provide an ASGI application
- Store imported records in SQLite
- Define datasets through Python or YAML
- Generate basic CRUD APIs
- Preserve the current HTML dashboard as an export feature
- Add framework-level unit and integration tests

### Explicitly Out of Scope for 0.2

- A complete React-like rendering engine
- All health-program plugins
- Full DHIS2 synchronization
- Clinical decision support
- Automatic diagnosis
- Advanced forecasting
- Multi-tenant enterprise deployment

## Milestones

| Milestone | Outcome |
|---|---|
| 0.1 | CSV/Excel to portable HTML dashboard |
| 0.2 | Create and run a persistent PHFrame application |
| 0.3 | Dataset schemas, CRUD APIs, and database migrations |
| 0.4 | Indicators, reporting periods, and data-quality rules |
| 0.5 | Web Component application shell and dashboard UI |
| 0.6 | Organisation units, maps, and surveillance functions |
| 0.7 | Saved imports and Kobo/DHIS2 connectors |
| 0.8 | Privacy-aware AI assistance |
| 0.9 | Plugin SDK, security hardening, and deployment tools |
| 1.0 | Stable public APIs and production-ready reference application |

## Measures of Success

PHFrame should be considered successful when:

- A developer can create a working surveillance application in less than one hour.
- A public-health specialist can define common indicators without programming.
- Monthly imports can reuse saved mappings and validation rules.
- Applications work in low-bandwidth environments.
- Sensitive information remains protected and auditable.
- AI-generated summaries cite the underlying aggregates and require review.
- Health-program functionality can be installed as plugins.
- Reference applications are deployable by small public-health teams.

## Current Priority

The next engineering priority is **PHFrame 0.2: create and run a customizable malaria surveillance application with a persistent backend, API, and development server**.

New features should be accepted when they strengthen this vertical slice or establish a clearly required framework interface. Features unrelated to the reference application should wait until the foundation is stable.

