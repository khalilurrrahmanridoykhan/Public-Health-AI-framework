# Upgrading to 1.0

PHFrame promises that a project created against any `0.9` preview keeps working
on `1.0` and later `1.x` releases. Run the upgrade once per project after
installing a new PHFrame release:

```bash
phframe upgrade --check   # report what would change
phframe upgrade           # apply it
```

`phframe upgrade` is safe to run on an already-upgraded project: it reports
nothing pending and changes nothing. Run it again after every PHFrame upgrade;
most releases have nothing to do, but it is the one command that is always
safe to run.

## What it upgrades

### `phframe.yaml` configuration version

A `0.9` preview `phframe.yaml` has no `version` key and is read with warnings
(see [`configuration.md`](configuration.md)). `phframe upgrade` adds
`version: 1` as the first line, leaving every other line untouched, once the
file validates against the version 1 schema. If it does not validate, the
command lists the offending keys and makes no changes; fix them, then rerun
`phframe upgrade`.

### Site settings

`data/phframe-settings.json` is read and written by the application, not by
`phframe.yaml`, so its shape changed across `0.9` previews independently of
the configuration version:

- `0.8.0a9`–`0.9.0a3` stored each dashboard's data source under a single
  `dataset` key. Dashboards are now independent workspaces that can combine
  several datasets, stored under a `datasets` list. `phframe upgrade` adds
  the equivalent `datasets` list to any dashboard that only has the legacy
  `dataset` key, so dashboards built before multi-dataset support — including
  ones made only of KPI widgets, which never carried a `dataset` field of
  their own — keep their data source after the upgrade instead of losing it.
- Releases before HTML footers stored a plain-text `footer_text` key.
  `phframe upgrade` converts it to the current `footer_html` key.

The application already tolerates both legacy shapes at read time, so a
project kept running correctly before an explicit upgrade; `phframe upgrade`
rewrites `data/phframe-settings.json` so the file on disk matches what the
application has been serving, instead of relying on that in-memory
normalization indefinitely.

### Database schema

`phframe upgrade` finishes by running the same additive dataset-table
migration as [`phframe migrate`](api-stability.md#configuration-schema):
creating any dataset table or optional column that configuration changes
have added since the project's database was last migrated. As with
`phframe migrate`, destructive changes — removing a field or changing a
required constraint — are never automatic and are reported as an error
instead.

## What it does not do

`phframe upgrade` only changes files it fully understands: `phframe.yaml`'s
version line, `data/phframe-settings.json`'s known legacy shapes, and
additive database columns. It never removes data, never rewrites branding,
pages, connectors, or AI history, and never touches anything outside the
current project directory.
