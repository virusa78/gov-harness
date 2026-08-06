# ADR-0012: The release is signed, and the verifying key comes from the consumer

## Status

Accepted — 2026-08-06

## Context

The trust chain had a hole at its first link. `harness.py` downloads
`SHA256SUMS` from a release, then verifies the archive against it. That proves
the archive was not corrupted in transit; it proves nothing about who produced
it, because the digest and the bytes it authenticates come from the same place.
Whoever can replace one can replace the other.

After the first install the receipt closes the gap: `.harness.lock` pins the
archive digest, so every later `sync` compares against a value already on the
consumer's disk. The exposure is precisely trust on first use, and it widened
when ADR-0011 let the release carry bytes this repository did not author. A
consumer now installs third-party content on the strength of a digest served by
the same host as the content.

`docs/HARDENING.md` has listed unsigned tags as one of five promotion
prerequisites since `v0.1.0`. Treating it as one checklist item among five
understated it: the other four are process controls, and this one is the only
thing standing between a compromised release host and every consumer.

Constraints shaped the choice. `harness.py` is a single stdlib file that
installs itself into consumer projects, so it may not grow a third-party Python
dependency. Implementing Ed25519 verification by hand inside a trust root is a
worse risk than any dependency: a subtle error there accepts forgeries silently.
`ssh-keygen` was the first candidate and is absent from at least one environment
this work was done in, which is exactly the kind of assumption lesson L4 says to
test rather than declare.

## Decision

1. **Sign `SHA256SUMS`, not the archive.** It names the archive and its digest,
   so one detached signature covers the release transitively and the existing
   verification order is unchanged.

2. **Ed25519 through openssl, on both sides.** `scripts/package_release.py
   --sign-key` produces `SHA256SUMS.sig`; `harness.py` verifies with
   `openssl pkeyutl -verify`. No third-party Python, no hand-rolled
   cryptography, and openssl is present wherever this tool realistically runs.
   Absent openssl is a refusal, never a skip.

3. **The verifying key is supplied by the consumer, out of band.** It is named
   with `--public-key` at install time and never travels inside the release.
   A key shipped by the thing it authenticates is the same self-referential
   hole in a new place.

4. **The requirement is sticky.** The key path is recorded in `.harness.lock`,
   so later syncs keep demanding a valid signature without repeating the flag.
   Dropping the requirement takes a deliberate re-init, never a forgotten
   argument.

5. **Fail closed, specifically.** With a key configured: a missing signature,
   an invalid signature, a missing key file, or an unusable openssl each refuse
   the install with a distinct message. "Configured but unverifiable" is never
   treated as "unconfigured".

6. **`--from-dir` is outside the chain and says so.** Installing from a local
   directory has no archive and no signature; the operator already controls
   those bytes. The lock records no key for such an install, so the absence is
   visible rather than implied.

## Consequences

- Signing is opt-in per consumer. A project that passes no key behaves exactly
  as before, which keeps the change non-breaking, and gets none of the
  protection — an honest default rather than a comfortable one.
- Whoever cuts a release now holds a private key, with everything that implies
  about storage and rotation. Rotation is not automated here: a new key means
  consumers update the path they trust, deliberately.
- The signature covers the release archive. It does not attest that the
  vendored third-party content inside is itself trustworthy; it attests that
  the archive is the one this repository published. Those are different claims
  and the second is the only one being made.
- `docs/HARDENING.md` still reports `NO-GO`. Signing addresses one prerequisite;
  protected `main` with required CI, CODEOWNERS enforcement and an external
  pilot remain open, and a signed release from an unprotected branch is not a
  certified one.

## Implementation status

Built in `v0.5.0-rc.1`: `verify_signature` and `signing_key` in `harness.py`,
the `--public-key` flag on `init`, `select` and `sync`, the recorded key in the
lock, `--sign-key` in `scripts/package_release.py`, and `tests/test_signature.py`
covering a genuine signature, tampered sums, a foreign key, a missing signature,
a missing key, and the lock keeping the requirement when the flag is omitted.

Not built: key rotation tooling, and any published key for this repository —
releases remain unsigned until one exists.
