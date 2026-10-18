# Public API stability policy

PHFrame 1.0 promises that applications, scripts, and plugins built against a 1.x release keep working on later 1.x releases. This document defines what that promise covers and how it is enforced.

## Stable surface

The stable surface is recorded in [`public-api-contract.json`](public-api-contract.json):

| Surface | What is covered |
|---|---|
| Python | Names exported from `public_health_framework.__all__` |
| CLI | `phframe` commands, subcommands, options, and positional arguments |
| HTTP | Route paths and methods served by a default project |
| Plugins | The `phframe.plugins` entry-point group and the `setup(app, config)` hook |

Everything else, including private modules, underscore-prefixed names, the browser UI markup, and the internal database layout, may change in any release. Database changes always ship with a `phframe migrate` path.

## What counts as a breaking change

- removing or renaming a covered Python name, CLI command, option, HTTP route, or method;
- changing the meaning of an existing option, request field, or response field;
- removing a response field or making an optional request field required;
- changing the plugin entry-point group or hook signature.

Adding new names, commands, options, routes, methods, or optional response fields is additive and allowed in minor releases.

## Deprecation cycle

1. Mark the item deprecated in the changelog under **Deprecated**, naming its replacement.
2. Keep it working for at least one minor release. Python callers receive a `DeprecationWarning`; HTTP responses carry a `Deprecation` header.
3. Remove it only in the next major release, listed under **Removed**.

## Enforcement

`tests/test_api_contract.py` compares the live surface with the reviewed snapshot. It fails when anything is removed (a breaking change) or added without review. After an intentional, reviewed change, regenerate the snapshot:

```bash
python -m public_health_framework.contract > docs/public-api-contract.json
```

The snapshot diff then shows reviewers exactly which public surface changed.

## HTTP request and response schemas

[`http-api.md`](http-api.md) and the OpenAPI 3.1 document [`openapi.json`](openapi.json) describe the parameters, request bodies, and responses of every HTTP route; applications also serve the document at `/api/openapi.json`. Both files are generated from `public_health_framework/http_reference.py`. `tests/test_http_reference.py` fails when a route in the contract has no documented operation, when a live response uses an undocumented status or does not match its schema, or when the generated files are stale. Regenerate them after a reviewed change:

```bash
python -m public_health_framework.http_reference --write docs
```

Documented response fields are stable. Responses may gain fields in minor releases, so clients should ignore fields they do not recognise.
