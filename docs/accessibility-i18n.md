# Accessibility and internationalization

PHFrame targets WCAG 2.2 AA. All custom controls must be keyboard reachable, expose accessible names, retain visible focus, use semantic landmarks, announce asynchronous status, respect `prefers-reduced-motion`, and pass light, dark, and high-contrast review. Test at 200% zoom and with VoiceOver or NVDA before production release.

Set `ui.locale` in `phframe.yaml`. Built-in English and Bangla messages are available; override or add messages through `ui.translations`. Translations must preserve placeholders, avoid embedding HTML, and be reviewed by a fluent public-health practitioner. Dates returned by APIs use ISO 8601; browser views localize display values without changing stored data.
