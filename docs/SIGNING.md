# Release signing

The verification half is built and tested (ADR-0012). This file covers the half
that cannot be automated: who holds the key, where the public half is
published, and what a signature does and does not prove.

**Current state: no key exists, so every release so far is unsigned.**
`docs/HARDENING.md` tracks that as an open prerequisite.

## Generating the key

Run this on the machine that will cut releases. Not in CI, not in a container
that gets reclaimed, and not anywhere the private half can be read back out.

```bash
umask 077
openssl genpkey -algorithm ed25519 -out gov-harness-release.pem
openssl pkey -in gov-harness-release.pem -pubout -out gov-harness-release.pub.pem
chmod 400 gov-harness-release.pem
```

The private half must never enter this repository, a CI secret store that
prints it, a chat transcript, or an agent's context. A key that has been
transmitted attests to nothing, because the property being claimed is that only
the publisher ever held it.

Back it up the way you would back up anything whose loss is unrecoverable. If
the private key is lost, every signature it made stays valid and no new release
can join them: you publish a new key and tell consumers to switch.

## Publishing the public half

Commit `gov-harness-release.pub.pem` to this repository and reference it here.
That is deliberate and it is not circular:

- the **archive** is served from release assets, a different surface;
- the **key** lives in git history, behind different credentials.

Compromising the asset host is then not enough to forge a release — the
attacker also has to alter the repository, visibly, in a history consumers can
inspect. That is the whole gain, and it is worth stating plainly rather than
implying the signature makes the release unforgeable.

Consumers fetch the key once, out of band, and pass it at install:

```bash
python3 harness.py init --project . ... --public-key /path/to/gov-harness-release.pub.pem
```

The path is recorded in `.harness.lock`, so later syncs keep demanding a valid
signature without repeating the flag.

## Cutting a signed release

```bash
python3 scripts/package_release.py --version <tag> --sign-key /path/to/gov-harness-release.pem
# emits dist/SHA256SUMS.sig alongside the archive
```

Attach all three assets to the GitHub release: the archive, `SHA256SUMS`, and
`SHA256SUMS.sig`. Without `--sign-key` the packager prints `NOT SIGNED` to
stderr rather than quietly producing an unsigned release.

## Rotation

There is no automated rotation, on purpose: rotation is a trust event, and a
tool that performs it silently defeats the reason for having a key.

1. Generate a new pair as above.
2. Publish the new public key here, keeping the old one listed and dated so
   signatures made under it stay verifiable.
3. Sign the next release with the new key.
4. Consumers update the path they trust, deliberately, as a reviewed change to
   their own repository.

A compromised key is the same procedure with one addition: say so here, with
the date, and treat every release signed after the suspected compromise as
unverified until re-cut.

## What the signature proves

It proves the archive is the one this repository published, and nothing more.

It does **not** prove the release is correct, that its tests passed, or that
the third-party content vendored inside it is trustworthy. Those are separate
claims with separate evidence — `EVID-G` for the work, the two digests in the
manifest for vendored bytes, and reviewer judgment for the rest.

It also does not cover the first install unless the consumer supplies a key.
With no key configured, `harness.py` verifies the archive against a
`SHA256SUMS` served by the same host, which proves the download was not
corrupted and says nothing about who produced it.
