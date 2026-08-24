# Changelog

All notable changes to PHFrame will be documented here. The project intends to follow [Semantic Versioning](https://semver.org/) after the alpha preview.

## [Unreleased]

## [0.7.0a4] - 2026-08-24

### Added

- Add guided browser setup for generic REST API, DHIS2, KoboToolbox, and ODK Central connectors.
- Add eight-direction dashboard resize handles with container-responsive chart content.
- Add editable brand name, header title, dashboard title, navigation, footer, primary color, and default theme.
- Add project logo and favicon uploads plus a packaged transparent PHFrame logo.
- Add optional public/private access modes, salted PBKDF2 password storage, signed HTTP-only sessions, login, and logout.

### Changed

- Redesign the header around project branding and make it responsive across desktop, tablet, and mobile widths.

## [0.7.0a3] - 2026-08-24

### Added

- Add freeform pointer resizing plus dashboard visualization add/remove controls.
- Add browser-managed optional typed columns with safe additive database migrations.
- Add direct dashboard visualizations for typed numeric, categorical, and date fields.
- Add JSON and XML imports in the browser and CLI plus downloadable CSV, JSON, and XML examples.
- Add browser-managed generic JSON REST API connectors with nested paths, mapping, scheduling, and environment-based authentication.

### Changed

- Replace Bangladesh-specific generated-project defaults with a worldwide-neutral country, administrative-area, and example organisation hierarchy.
- Expand the import and connector screens with guided formats, creation forms, removal controls, and clearer empty states.

## [0.7.0a2] - 2026-08-24

### Added

- Add browser-saved dashboard layouts with drag-and-drop and accessible move controls.
- Add per-widget size controls and number, gauge, bar, donut, line, column, tile-map, and table visualizations.

### Changed

- Redesign the application dashboard with a modern responsive grid, clearer visual hierarchy, improved charts, and purposeful empty states.

## [0.7.0a1] - 2026-08-24

### Added

- Add a browser CSV/Excel preview, mapping, validation, and atomic import workflow.
- Add reusable server-side browser import mappings and structured run error reports.
- Add a connector registry with environment-based credentials, nested mappings, pagination, timeouts, and a page safety limit.
- Add DHIS2 data-value-set, KoboToolbox v2 submission, and ODK Central OData adapters.
- Add atomic connector synchronization with dedicated audit history.
- Add `phframe sync`, due-schedule evaluation, sync history APIs, and a browser connector console.

## [0.5.0a1] - 2026-08-24

### Added

- Add continuous integration across Python 3.10–3.12.
- Add contribution and security guidance.
- Improve package metadata and project documentation.
- Add declarative count, sum, average, rate, ratio, and percentage indicators.
- Add indicator metadata and result APIs with field filters and reporting-period ranges.
- Add total-cases and incidence indicators to newly generated surveillance projects.
- Add ISO-week, calendar-month, and quarter reporting periods to indicator queries.
- Add declarative completeness, numeric-range, and allowed-value data-quality rules.
- Add data-quality metadata and evaluation APIs.
- Add reusable saved filters for indicator and dimension queries.
- Add declarative dimensions with grouped-count APIs.
- Add declarative surveillance thresholds with severity and alert messages.
- Add threshold evaluation APIs that support periods and saved filters.
- Add reusable identifier, disease-code, age, sex, case-classification, epidemiological-week, reporting-period, organisation-unit, and facility field types.
- Add domain validation and portable storage mappings for public-health field types.
- Add declarative organisation-unit hierarchies with parent and cycle validation.
- Add hierarchy discovery APIs and organisation-unit referential validation for record writes and imports.
- Add a packaged Web Component application shell with client-side routing.
- Add metadata-driven record forms, tables, saved filters, and organisation-unit selection.
- Add declarative dashboards with KPI, grouped chart, epidemiological curve, and tile choropleth components.
- Add light, dark, and high-contrast design-token themes.
- Add English and Bengali localization foundations with project translation overrides.
- Add accessible skip navigation, data-table chart fallbacks, live notifications, modal dialogs, confirmations, and reduced-motion support.

## [0.2.0a1] - 2026-07-21

### Added

- Generated projects with declarative dataset schemas.
- SQLite and PostgreSQL persistence.
- Generated collection and record APIs.
- Safe schema migration checks.
- Atomic CSV and Excel imports with saved column mappings.
- Import audit history.
- Portable HTML dashboard export.

[Unreleased]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a4...HEAD
[0.7.0a4]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a3...v0.7.0a4
[0.7.0a3]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a2...v0.7.0a3
[0.7.0a2]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a1...v0.7.0a2
[0.7.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.5.0a1...v0.7.0a1
[0.5.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.2.0a1...v0.5.0a1
[0.2.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/releases/tag/v0.2.0a1
