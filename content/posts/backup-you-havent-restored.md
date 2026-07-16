---
title: "A Backup You Haven't Restored Is a Hypothesis"
date: 2026-07-16T21:45:00+10:00
draft: false
description: "The identity provider quietly became load-bearing, and it had no backup. Building one taught me more about database internals than the identity provider did."
tags: ["homelab", "backups", "postgres", "sqlite", "age", "encryption", "bash", "cron", "authentik", "vaultwarden"]
series: ["Home Lab"]
---

The identity provider quietly became load-bearing and had no backup. Building one taught me more about database internals than building the identity provider did.

**Stack:** Bash · Postgres · SQLite · age · cron · OneDrive

---

## 1. Purpose

The [identity provider](/posts/identity-provider-authentik-grafana-sso/) started as a nice-to-have. Single sign-on for a dashboard — pleasant, not critical.

Then it [took over the firewall's login](/posts/pfsense-authentik-ldap-radius/).

That's the moment the risk profile changed, and it changed **without any decision being made about it**. Nobody sat down and said "let's make the firewall depend on this container." It happened one integration at a time, and the dependency graph grew quietly underneath.

That's worth naming, because it's how it happens everywhere: **services become critical by accretion, not by declaration.** The time to notice is when you stop and ask what actually breaks if a given box dies — not when it dies.

So: what breaks?

---

## 2. What's actually at risk

Ranking this properly matters, because the answers aren't equally bad:

| Data | If lost |
|---|---|
| **Password vault database** | **Irreplaceable.** Nothing rebuilds it. |
| **Identity provider database** | Rebuildable — ~2 hours of clicking, and the firewall is stuck on break-glass the whole time |
| **`.env` files** | Tiny, but hold the IdP secret key, DB password, DNS API token |
| **TLS certificates** | Auto-reissue. Nice to keep for rate limits; not critical. |

Which reframed the job. This wasn't an identity provider backup — it was **one lab backup**, and the same script closes the [vault](/posts/self-hosted-vaultwarden-caddy-duckdns/) gap that had been open since the day I built it.

Worth noticing: the *cheapest* thing to rebuild (the IdP) is the one that prompted the work, and the *impossible* thing (the vault) had been sitting unbacked for a week. Prompts and priorities aren't the same thing.

---

## 3. Consistency: the part that actually matters

Anyone can `tar` a directory. The question is whether what you get back is **coherent**.

### Postgres

```bash
docker compose exec -T postgresql pg_dump -U authentik authentik | gzip > db.sql.gz
```

Not a copy of the data directory. A live Postgres data directory copied under load is a *corrupt* Postgres data directory — pages get written while you're reading, and you capture a state that never existed. `pg_dump` produces a logical snapshot that's internally consistent by construction.

The `-T` is easy to miss: it disables TTY allocation. Without it, Docker injects control characters into the stream and mangles the dump.

### SQLite — where I made exactly the mistake I'd just avoided

The vault's first backup was this:

```bash
tar czf vault.tar.gz -C ~/vaultwarden data
```

Then I listed what was actually inside:

```
data/db.sqlite3
data/db.sqlite3-shm
data/db.sqlite3-wal
```

**WAL mode.** The `-wal` file holds committed transactions not yet folded into the main database; `-shm` is the shared-memory index that coordinates them.

And `tar` isn't atomic. It reads `db.sqlite3`, then reads `-wal` a moment later. Any write landing in between gives you a main file and a WAL that disagree about reality.

Which is *precisely* the reasoning that made me use `pg_dump` for Postgres. I applied it carefully to one engine, then walked straight into it on the other — because SQLite "is just a file," and that intuition is wrong the moment WAL is involved.

The fix is SQLite's own equivalent:

```bash
sqlite3 ~/vaultwarden/data/db.sqlite3 ".backup '$DEST/vault-db.sqlite3'"
```

`.backup` uses SQLite's online backup API: it takes a proper lock, and produces a guaranteed-consistent copy of a live database. `pg_dump` for SQLite.

Then the remaining files separately, minus what we've now handled properly:

```bash
tar czf "$DEST/vaultwarden-files.tar.gz" \
  -C ~/vaultwarden --exclude='data/db.sqlite3*' data
```

**The generalisable rule: every database has a supported way to be copied while running. Use it. "It's just a file" is how you get a backup that restores into a corrupt database — and you find out on the worst day.**

---

## 4. The script

```bash
#!/bin/bash
set -euo pipefail

HOME_DIR=/home/student
STAMP=$(date +%F-%H%M)
DEST=$HOME_DIR/backups/$STAMP
mkdir -p "$DEST"

# Identity provider: logical dump
docker compose -f $HOME_DIR/authentik/docker-compose.yml exec -T postgresql \
  pg_dump -U authentik authentik | gzip > "$DEST/authentik-db.sql.gz"

# Vault: consistent snapshot via SQLite's backup API
sqlite3 "$HOME_DIR/vaultwarden/data/db.sqlite3" ".backup '$DEST/vault-db.sqlite3'"
gzip -f "$DEST/vault-db.sqlite3"

# Vault: keys and attachments (db handled above)
tar czf "$DEST/vaultwarden-files.tar.gz" \
  -C "$HOME_DIR/vaultwarden" --exclude='data/db.sqlite3*' data

# Config and secrets
tar czf "$DEST/config.tar.gz" -C $HOME_DIR \
  authentik/.env authentik/docker-compose.yml \
  authentik/docker-compose.override.yml \
  caddy/.env caddy/Caddyfile caddy/docker-compose.yml caddy/Dockerfile

# Encrypt and drop into cloud-synced storage
AGE_PUB="age1..."
OD=$HOME_DIR/OneDrive/lab-backups
mkdir -p "$OD"
tar cz -C "$DEST" . | age -r "$AGE_PUB" -o "$OD/$STAMP.tar.gz.age"
chown student:student "$OD/$STAMP.tar.gz.age"

# Retention
ls -1dt $HOME_DIR/backups/*/ | tail -n +8 | xargs -r rm -rf
ls -1t "$OD"/*.age 2>/dev/null | tail -n +8 | xargs -r rm -f

echo "Backup complete: $DEST"
```

### The most important line

```bash
set -euo pipefail
```

- `-e` exit on any error
- `-u` exit on undefined variables
- `-o pipefail` — **the one that matters here.** By default, a pipeline reports the exit status of its *last* command. So `pg_dump | gzip` returns success if gzip succeeded, **even if pg_dump died.** You get a valid gzip file containing nothing, a cheerful "Backup complete", and a green cron log for six months.

It earned its place during this build. A tar failure stopped the script dead rather than printing success over a broken archive.

---

## 5. Four small bugs, each a lesson

**`~` isn't a path, it's an expansion.**
```
open /root/authentik/docker-compose.yml: no such file or directory
```
`sudo ~/script.sh` runs as root, so `~` becomes `/root`. Every path missed. Hardcoding the directory fixes it — and this matters far more for cron, which also runs as root and would fail *silently at 20:30 with nobody watching*.

**Tar's options are positional.**
```
tar: --exclude 'data/db.sqlite3*' has no effect
```
GNU tar options only affect arguments that follow them. `--exclude` at the end does nothing. The proof it was fixed was the archive dropping from 26K to 1.5K — a number, not a feeling.

**Interactive prompts are cron poison.**
```
gzip: vault-db.sqlite3.gz already exists; do you wish to overwrite (y or n)?
```
Harmless by hand. Under cron it hangs forever waiting for input nobody will type. `gzip -f`.

**Your shell has no `set -u`.**
Pasting a script's line directly into the terminal expands `$DEST` to nothing, and `tar -C "$DEST"` becomes `tar -C /`. The script would have refused; the shell happily aimed at the root of the filesystem. **Test by running the script, not its lines.**

---

## 6. Testing the restore

This is the part everyone skips, and skipping it means you don't have a backup — you have a *hypothesis about a backup*.

The test has to be non-destructive, so: restore into a throwaway container that never touches production.

```bash
docker run --rm -d --name pgtest \
  -e POSTGRES_USER=authentik -e POSTGRES_PASSWORD=test -e POSTGRES_DB=authentik \
  postgres:16-alpine

zcat backups/<stamp>/authentik-db.sql.gz | docker exec -i pgtest psql -U authentik -d authentik
```

Same image version as production — restoring into an older Postgres can fail on newer syntax.

Then the only question that matters. Not "did it run" — **"is my data there?"**

```sql
select username, type from authentik_core_user;
```
```
 AnonymousUser                               | internal
 ak-outpost-9ea968a1...                      | internal_service_account
 ak-outpost-7125ffe0...                      | internal_service_account
 ak-outpost-735010d3...                      | internal_service_account
 pfsense-user                                | service_account
 akadmin                                     | internal
```
```sql
select name from authentik_core_group;
```
```
 authentik Admins
 authentik Read-only
 Grafana Admins
 admins
```

Real accounts, real groups, recovered from a compressed file into a clean database. `docker rm -f pgtest` and nothing lingers.

A useful cheap check before that, too:

```bash
zcat authentik-db.sql.gz | grep -c "CREATE TABLE"
# 215
```

215 tables. A gzipped error message would have said 0 — and would have been a plausible-looking file of plausible-looking size sitting in a directory called `backups`.

---

## 7. Encryption, and one very sharp edge

Off-box means cloud, and cloud means someone else's disk. Look at what's in `config.tar.gz`:

- the identity provider's secret key — signs every session and token
- the database password
- the DNS provider API token

Plaintext. Uploading that unencrypted hands over the identity provider.

**`age`**, with the design detail that makes it work unattended:

```bash
age-keygen -o ~/.age-key.txt        # prints a public key
...
tar cz -C "$DEST" . | age -r "$AGE_PUB" -o "$OD/$STAMP.tar.gz.age"
```

**Public-key encryption means no passphrase at backup time.** Nothing to prompt for, so cron works. And there's a real security property: the machine only ever holds the *public* key. Compromise the box and an attacker can create backups but not read them.

### The circular dependency

The private key lives at `~/.age-key.txt` — **on the machine being backed up.**

Lose the machine, lose the ability to decrypt the backups of the machine. Perfectly circular, and it's the single most common way encrypted backups turn into expensive noise.

The obvious fix — "put it in the password manager!" — is worse, because **the password manager is one of the things being restored.** You'd need the vault to decrypt the backup that contains the vault.

The key has to live somewhere the system can't take with it when it goes: printed on paper, a USB stick, a note in an account reachable from a bare machine. Explicitly **not** the cloud storage holding the backups — that hands over both halves and undoes the encryption entirely.

It's two lines of text. It's also the whole thing.

---

## 8. What this survives

| Failure | Covered |
|---|---|
| "I broke the identity provider" | ✅ — and by far the most likely |
| Container or volume lost | ✅ |
| VM won't boot | ✅ via the cloud copy |
| Physical disk dies | ✅ via the cloud copy |
| Fire or theft | ✅ via the cloud copy |
| Lost the age private key | ❌ — **nothing helps** |

That last row is the honest one. Encryption converts "backups an attacker could read" into "backups nobody can read without one specific file." That's a trade, not a free win, and it's only correct if you take the other half seriously.

A note on what *doesn't* work: copying to the host machine. A VM's virtual disk is a file on the host's physical disk — same drive, same failure. It protects against VM-level mistakes and nothing else. That intuition is easy to get wrong, because "another machine" sounds like it should be enough.

---

## 9. Lessons

- **Criticality creeps.** No decision made the firewall depend on a container. It happened one integration at a time. The audit is what catches it, not the design.
- **Every database has a supported live-copy path.** `pg_dump`, `.backup`. "It's just a file" is a trap, and knowing it for one engine doesn't stop you walking into it on the next.
- **`set -euo pipefail`**, always. Especially `pipefail` — silent success is worse than loud failure.
- **`~` is an expansion, not a path.** Under sudo and cron it means something else, and cron fails where nobody's watching.
- **Test the restore.** A backup that has never been restored is an untested assumption with a comforting filename.
- **Encrypt what leaves your network** — and then take the key management as seriously as the encryption, because you've just made a single file the thing everything depends on.

The through-line: **backups are easy, and correct backups are not.** Every single failure mode here — the torn WAL, the silent pipe, the `~`, the positional flag, the circular key — produces a file of plausible size in a directory called `backups`. All of them look fine right up until the day they matter.

Which is why the restore test isn't optional. It's the only part of this that's actually evidence.

---

*Next: an always-on host — so the identity provider stops being a service that sleeps at night, and the backups stop needing to run before bedtime.*
