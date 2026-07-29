# Lessons

## L1 — Private release assets are API resources, not authenticated browser URLs (2026-07-29)

Symptom: the first real network `init` received 404 from a private GitHub
release asset even though the request carried a valid Bearer token; local
`--from-dir` tests had all passed.

Cause: private release downloads require resolving the release asset through
the GitHub API and requesting the asset API URL with
`application/octet-stream`. Adding authorization to the public browser URL
does not turn it into the private API flow.

Rule: every private-release transport must be tested from outside the source
checkout and must resolve an asset ID through the provider API; local archive
tests do not prove authenticated distribution. Remove authorization on a
redirect to a different storage host.

Source: `v0.1.0-rc.1` network-init reproduction and ADR-0001.

