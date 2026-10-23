# README

## TODO

Connect my Calendar

Full read access to all my email one year back

Let Eddie place a draft in my real email account

RAG (file access, ro file acccess, https://share.gemini.google/vxL1XAhPnoaF)

use skill-tracker (community plugin) or setting `skills.write_approval` (human review)

## Tasks for Hermes

Get regular updates:
- news in AI (speciific areas..?) => send daily email
- global, geopolitical news => send daily email
- breaking news in any area (once-a-month event)=> send whatsapp
- generally: hot stuff people talk about - large scale ideas concerning the future of work and everything

Manage TODOs

Whatsapp: "Send me a Google Maps link to that meeting with the Notar in two weeks"

Book hairdresser appointment

Check picture of boat rental contract => anything out of the ordinary?

Find apartments


## Cool

`/learn` command: e.g.
- `/learn /path/to/local/dir`
- `/learn https://docs.example.com/api/quickstart`
- `/learn how I just deployed the staging server` (a workflow I just ran in the conversation)
- `/learn filing an expense: open the portal, New > Expense, attached the receipt, submit`
- More: https://claude.ai/share/20100be6-dc26-4a4b-85a0-d6ec8a9eedaf

## Deploy on VPS

Run it and check:

```bash
cd ~/code/hermes/docker
docker compose up -d hermes
docker logs --tail 100 hermes-agent
```

### Proton-internal email exception

Compose builds a custom Hermes image from the official image pinned in
`docker/Dockerfile.hermes`. The tracked patch in `docker/patches/` adds a
per-profile option; it is disabled by default. Build and test it before deployment:

```bash
cd ~/code/hermes/docker
docker compose build hermes
docker run --rm --entrypoint python --workdir /opt/hermes \
  -e HERMES_HOME=/tmp/hermes-tests \
  -v "$(pwd)/../tests:/tmp/regression:ro" \
  hermes-agent-proton-internal:local \
  -m unittest discover -s /tmp/regression -v
```

Enable only in the `config.yaml` of a profile using a trusted Proton Bridge:

```yaml
platforms:
  email:
    enabled: true
    require_authenticated_sender: true
    allow_proton_internal_without_auth_results: true
```

Keep `EMAIL_ALLOWED_USERS` configured and allow-all access disabled. The exception
only admits an allowlisted sender with a single unambiguous From address, exactly
one `X-Pm-Origin: internal` header and one
`X-Pm-Content-Encryption: end-to-end` header, and no `Authentication-Results` header.
It never overrides a failed authentication result. This trusts Proton to strip or
replace externally supplied copies of its headers, which has been verified for
this deployment; do not enable it for another mail provider. Acceptance is logged
as a `Proton-internal exception`, separately from SPF/DKIM/DMARC authentication.

After enabling, run `docker compose up -d --no-deps hermes`. Validate with a fresh
harmless email from an allowlisted Proton address. Existing messages are skipped
at startup and are not replayed.

To roll back, set `allow_proton_internal_without_auth_results: false` and restart
Hermes. To remove the patch entirely, restore the official image reference from
the Dockerfile in Compose, remove the service's `build` section, and recreate only
Hermes with `docker compose up -d --no-deps hermes`.

The original adapter SHA-256 is checked before patching. On an upstream upgrade,
review the adapter changes, rebase the patch, update the base image pin and
checksum, then rerun the regressions plus upstream email and secret-scope tests
from the image's `org.opencontainers.image.revision`. The initial source revision
is `118984d7a02f8a8baec11255002cbbab7c202e06`. A checksum mismatch must stop the build.

Configure user:

```bash
docker exec -u 10000 -e HOME=/opt/data hermes-agent \
  hermes config set dashboard.basic_auth.username mpcal@pm.me

docker exec -it -u 10000 -e HOME=/opt/data hermes-agent python -c \
'from getpass import getpass; from plugins.dashboard_auth.basic import hash_password; import subprocess; subprocess.run(["hermes", "config", "set", "dashboard.basic_auth.password_hash", hash_password(getpass("Dashboard password: "))], check=True)'

docker restart hermes-agent
```

Configure models:

```bash
  docker exec -it hermes-agent hermes model
```

## Create login

1. Produce hashed password

    docker exec hermes-agent python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('something-complicated...'))"

2. copy the printed hash, then:

    docker exec hermes-agent hermes config set dashboard.public_url "https://hermes.skybuddy.ch"
    docker exec hermes-agent hermes config set dashboard.basic_auth.username 'username...'
    docker exec hermes-agent hermes config set dashboard.basic_auth.password_hash 'scrypt...'
    docker compose restart hermes
