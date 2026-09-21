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


## Create login

1. Produce hashed password

    docker exec hermes-agent python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('b4hBgZ4Xw1RKRn2gSnPTNyvZ3hTA0wysSRM2cm7f4Q'))"

2. copy the printed hash, then:

    docker exec hermes-agent hermes config set dashboard.public_url "https://hermes.skybuddy.ch"
    docker exec hermes-agent hermes config set dashboard.basic_auth.username 'username...'
    docker exec hermes-agent hermes config set dashboard.basic_auth.password_hash 'scrypt...'
    docker compose restart hermes
