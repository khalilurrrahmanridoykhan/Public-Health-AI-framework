# Changelog

All notable changes to PHFrame will be documented here. The project intends to follow [Semantic Versioning](https://semver.org/) after the alpha preview.

## [Unreleased]

## [0.8.0a16] - 2026-08-25

### Added

- Add dataset selection, workspace navigation, full-table search, sticky headers, and 25-row pagination to Records.
- Add schema search and dataset field summaries to Data Builder.
- Add a guided three-step import sidebar and accessible file drop zone.

### Changed

- Redesign Records, Data Builder, and Import as responsive, consistent professional workspaces.
- Separate record browsing from record entry so large datasets no longer create an excessively long page.

## [0.8.0a15] - 2026-08-25

### Changed

- Collapse the header theme control to the active icon and reveal all three theme choices on hover or keyboard focus.
- Animate the theme-choice expansion and return the selected theme to the leading position.

## [0.8.0a14] - 2026-08-25

### Changed

- Replace the labeled theme dropdown with compact accessible light, dark, and high-contrast icon controls.
- Add smooth color, background, border, and shadow transitions when changing themes.
- Redesign Connectors as a responsive sidebar workspace with Add connector, Configured, and Sync history panels.
- Preserve the relevant connector panel after create, delete, test, and synchronization actions.
- Improve connector loading, panel spacing, provider selection, connector cards, form actions, and mobile navigation.

## [0.8.0a13] - 2026-08-24

### Changed

- Replace the split Pages screen with a responsive sidebar workspace for Create page, All pages, and Customize page.
- Open newly created internal pages and existing page-design actions directly in the customization panel.
- Add title and navigation-label editing to the page designer and preserve the active designer after saving.
- Improve page cards, empty states, automatic slug/label suggestions, form layout, and mobile navigation.

### Fixed

- Hide and disable the External URL field for drag-and-drop pages; reveal and require it only for external redirects.

## [0.8.0a12] - 2026-08-24

### Changed

- Widen the desktop floating AI assistant from 32rem to 38rem while preserving its height and mobile layout.
- Hide the standalone AI Assistance navigation item by default now that the assistant is available globally.

## [0.8.0a11] - 2026-08-24

### Added

- Add a floating AI-assistance launcher on every application page with a closable responsive popup.
- Add a professional assistant header, ready/privacy status, suggested questions, evidence badges, trace identifiers, loading state, and mobile full-screen presentation.

### Changed

- Preserve chat sessions while navigating the application and load only conversation data in compact mode.
- Label user messages and public-mode audit actions as `Me`, removing the chat name field and extra identity prompts.
- Refine conversational answer cards, timestamps, composer controls, report actions, and evidence access.

## [0.8.0a10] - 2026-08-24

### Changed

- Replace the long settings card grid with a focused, sticky sidebar and one content panel per configuration area.
- Add accessible keyboard navigation, selected-tab session memory, and a compact horizontal mobile tab bar.
- Refine settings typography, spacing, inputs, file selectors, navigation rows, focus states, and save controls.

### Fixed

- Keep the main settings save message attached to the save control instead of an unrelated panel status region.

## [0.8.0a9] - 2026-08-24

### Added

- Publish a selected dashboard as an aggregate-only snapshot or live Cloudflare Pages site.
- Run a mandatory privacy audit that blocks protected fields and row-level exports before bundling or deployment.
- Download a portable Pages deployment ZIP with security headers and, for live mode, a fixed-origin Worker proxy with edge caching.
- Configure the Cloudflare account, default project, and token environment-variable name without storing the token.
- Create Pages projects, deploy through Wrangler, retain publication history, and expose privacy-reviewed aggregate feeds for externally reachable PHFrame servers.

### Security

- Require HTTPS live data sources and support upstream bearer credentials only through the Cloudflare `UPSTREAM_API_TOKEN` secret.

## [0.8.0a8] - 2026-08-24

### Fixed

- Exclude the searchable country catalog and other non-boundary JSON files from the installed boundary-layer index.
- Tolerate malformed or unrelated JSON files in the project boundary directory instead of returning an API 500 error.

## [0.8.0a7] - 2026-08-24

### Added

- Add a searchable country-name and ISO3 combobox to the geographic boundary settings.
- Add a cached country catalog API populated from the geoBoundaries open collection.

## [0.8.0a6] - 2026-08-24

### Added

- Add a built-in Settings boundary manager for downloading country ADM0–ADM5 layers by ISO3 code.
- Add project-local boundary storage and read APIs backed by simplified geoBoundaries gbOpen GeoJSON.
- Add real SVG administrative polygon choropleths with name-based data matching, hover values, and attribution.

### Changed

- Use the newest installed country boundary layer for geographic dimension maps, retaining tile maps only as a fallback when no boundary is installed.

## [0.8.0a5] - 2026-08-24

### Fixed

- Open the dashboard template gallery from **Create new** instead of the nested visualization dialog.
- Replace the unreliable browser prompt with a dedicated editable-copy dialog for **Customize this dashboard**.
- Ignore stale asynchronous dashboard-manager renders so current buttons retain the correct event handlers.

## [0.8.0a4] - 2026-08-24

### Fixed

- Stop recursive dashboard rendering that repeatedly requested the same visualization data and delayed page loading.
- Deduplicate identical in-flight GET requests made by dashboard widgets.
- Show accessible loading animations for application startup, dashboard preparation, metrics, charts, trends, and maps.
- Show actionable retry controls when application or dashboard loading fails.

## [0.8.0a3] - 2026-08-24

### Added

- Add a server-persisted multi-dashboard workspace with dashboard switching, creation, renaming, deletion, and configurable-dashboard cloning.
- Add Executive overview, Surveillance operations, Programme monitoring, DHIS2 aggregate, Worldwide geospatial, and Blank canvas templates.
- Add schema-aware template recommendations based on numeric, categorical, date, DHIS2, and coordinate columns.
- Add rich dashboard content blocks with editable headings, paragraphs, formatting, lists, and safe hyperlinks.
- Add coordinate-aware worldwide maps and a privacy-reduced geospatial aggregation API.
- Add automatic coordinate-map discovery for latitude/longitude-style numeric columns.

### Changed

- Replace the single fixed dashboard route with a user-managed dashboard selector and template gallery.
- Preserve configured dashboards while allowing users to create editable saved copies without changing project configuration.

## [0.8.0a2] - 2026-08-24

### Added

- Add a chat-first Public Health AI Analyst with persistent browser conversation sessions and follow-up context.
- Add question intent routing for overviews, trends, anomalies, location comparisons, data quality, alerts, and causal-explanation requests.
- Add aggregate time-trend calculations, first-to-latest percentage change, and latest-point z-score anomaly flags.
- Add targeted evidence selection so analyst answers respond to the question instead of repeating the dashboard.
- Add suggested investigation steps while clearly separating observed associations from unproven causes.
- Add one-click promotion of analyst answers into human-reviewable situation-report drafts.
- Add governed Markdown report downloads containing status, review notes, evidence digest, and source endpoints.

### Changed

- Make the AI workspace conversational by default while retaining summaries, de-identification, approvals, and audit tools in an expandable area.

## [0.8.0a1] - 2026-08-24

### Added

- Add a privacy-aware AI workspace with local aggregate evidence synthesis as the safe default.
- Add de-identification previews that remove protected/direct identifier fields and generalize dates and ages.
- Add evidence-backed summaries with numbered source links, evidence snapshots, and SHA-256 evidence digests.
- Add mandatory human approval or rejection with review notes and one-way draft decisions.
- Add append-only audit events for AI generation and review decisions.
- Add privacy receipts showing row-level records, protected fields, and external transfers used for each generation.
- Add an explicitly enabled, HTTPS-only OpenAI-compatible provider using environment-based API keys.

### Security

- Keep external AI disabled by default and prevent API keys from being stored in project settings.
- Send configured aggregate evidence only; protected fields and row-level records are excluded from summary generation.
- Document that technical de-identification reduces exposure but does not certify legal compliance or eliminate re-identification risk.

## [0.7.0a6] - 2026-08-24

### Added

- Add browser-managed internal pages with drag-and-drop text, live table, and visualization blocks.
- Add external URL navigation items that redirect from the application header.
- Add safe rich-text editors for page copy and footer content with formatting, lists, and links.
- Add the PHFrame and Khalilur Rahman Ridoy Khan attribution as the default footer.

### Fixed

- Keep custom primary colors readable in dark mode without changing the selected header brand color.
- Make charts reflow within freely resized dashboard cards and remove unwanted card-level scrollbars.
- Preserve custom plain-text footers created by earlier PHFrame versions.

## [0.7.0a5] - 2026-08-24

### Fixed

- Bind Settings submission to its HTML form so browser `FormData` construction and saving work correctly.

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

[Unreleased]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a16...HEAD
[0.8.0a16]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a15...v0.8.0a16
[0.8.0a15]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a14...v0.8.0a15
[0.8.0a14]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a13...v0.8.0a14
[0.8.0a13]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a12...v0.8.0a13
[0.8.0a12]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a11...v0.8.0a12
[0.8.0a11]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a10...v0.8.0a11
[0.8.0a10]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a9...v0.8.0a10
[0.8.0a9]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a8...v0.8.0a9
[0.8.0a8]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a7...v0.8.0a8
[0.8.0a7]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a6...v0.8.0a7
[0.8.0a6]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a5...v0.8.0a6
[0.8.0a5]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a4...v0.8.0a5
[0.8.0a4]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a3...v0.8.0a4
[0.8.0a3]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a2...v0.8.0a3
[0.8.0a2]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.8.0a1...v0.8.0a2
[0.8.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a6...v0.8.0a1
[0.7.0a6]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a5...v0.7.0a6
[0.7.0a5]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a4...v0.7.0a5
[0.7.0a4]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a3...v0.7.0a4
[0.7.0a3]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a2...v0.7.0a3
[0.7.0a2]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.7.0a1...v0.7.0a2
[0.7.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.5.0a1...v0.7.0a1
[0.5.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/compare/v0.2.0a1...v0.5.0a1
[0.2.0a1]: https://github.com/khalilurrrahmanridoykhan/Public-Health-AI-framework/releases/tag/v0.2.0a1
