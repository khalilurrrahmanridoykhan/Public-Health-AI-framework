# Production certification evidence

## Internal release gates

Every change to `main` must pass the `Production certification gates` workflow:

- complete Python test suite on the supported runtime;
- PyPA `pip-audit` with zero known dependency vulnerabilities;
- Bandit with zero medium or high confidence security findings;
- recovery tests for database backup and restore;
- HTTP security, request-size, authentication, audit, and readiness tests;
- deterministic liveness baseline and frontend accessibility-contract checks;
- wheel and source distribution construction with Twine metadata validation.

The security baseline is OWASP ASVS 5.0. The accessibility target is WCAG 2.2 AA. Automated checks do not establish conformance by themselves.

## Required independent sign-off before a deployment is certified

- penetration test of the deployed URL, network, identity provider, and infrastructure;
- manual WCAG 2.2 AA evaluation using keyboard, zoom, VoiceOver and NVDA;
- load and endurance test with representative record volumes and concurrency;
- encrypted PostgreSQL backup restoration into an isolated environment;
- privacy impact assessment and applicable legal/regulatory review;
- incident response, monitoring, ownership, recovery-time and recovery-point approval.

Record assessor, scope, environment, date, evidence links, exceptions, expiration date, and approving authority. Certification belongs to a specific deployed system and cannot be inherited solely from the framework package.
