# README

TODO

- run browser control locally via Playwright as proposed by contributors (instead of the
  default, cloud-based, pay-for Browserbase)
- use skill-tracker (community plugin) or setting `skills.write_approval` (human review)

Cool

- `/learn` command: e.g.
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
