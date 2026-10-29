# Cassandra V19 — English summary

*The documentation is written in French (the project's working language). This page is a short summary for English-speaking readers; the full README is [`README.md`](README.md).*

**Cassandra is a sovereign, self-hosted AI that administers your machines, your websites and your daily work, alongside you rather than waiting for you.** It installs on
your own server, depends on no mandatory third-party service, and is driven from a web interface. You choose the language model: an API key, an OpenAI-compatible server,
or a local Ollama.

## What it does

- **Watches** the machine and its surroundings: disk, memory, failed services, expiring certificates, missing or stale backups, drifting DNS, slow or down websites, open
  ports, silently failing scheduled tasks. It says when a source is *silent* instead of answering "all good".
- **Understands**: correlated anomalies become one story (an incident), not twenty alerts.
- **Acts**: renew a certificate, restart a service, ban an address, fix a DNS record, run a backup, rotate a key. **Every action has a proof** (it re-reads what it did)
  **and a rollback** (it knows how to undo it); an action without both does not exist.
- **Remembers**: dated, proven facts, correctable in one sentence, that can say "I don't know".
- **Helps with daily work**: mail, calendar, tasks, projects, notes, contacts, documents. Everything belongs to the person: the administrator cannot read your notes
  or your mailbox.
- **Runs a trade**: a complete ticketing module (online sales, box office, entrance control, resellers, artists, commissions, accounting).

Two agents share the work. **Cassandra** looks after the machine; **Itare** looks after the person's desk.

## Design principles

- **Safety comes from reversibility, not from asking permission**: proof, rollback, journal. The administrator sets how autonomous the agents may be (a *tier*); that
  caution is a setting, never a hard-coded prohibition.
- **Data is never an instruction.** What an agent reads on the web or in an email gives it no order; after an outside read it cannot send or act under mandate without human
  approval. The recipient of a send never comes from the request.
- **A tiny kernel and modules that declare themselves.** Each module is an independent folder with a manifest (rights, capabilities, menus, permissions). The kernel enforces
  rights, proof, rollback, isolation and the journal for every module.
- **Two kinds of code.** The **nexus (CN)** — identity, access, effects on the world, data, proof, operations — is written and signed by the repository and never evolves by
  itself. **Evolution code (EC)** is limited to *pure functions* declared as evolution points; a variant is judged by a deterministic evaluator on a replay corpus of real calls,
  runs in shadow, and ramps up in stages (10%, 50%, 100%) with instant rollback. See "Deux sortes de code" in the README.
- **Several companies in one instance**, in the spirit of Dolibarr Multicompany: every account belongs to a company; the main company owns the instance; each company has its
  own modules, roles ("functions") and optionally its own database per module; the superadministrator decides what is shared between companies.
- **Secrets live in Vaultwarden**, the free self-hosted Bitwarden-compatible server, driven through `bw serve`. Each company can have its own vault, even on its own server.

## State of the project

| Version | State | Where |
|---|---|---|
| **V18** | production version, a product to install on Debian or Ubuntu | repository [`cassandra`](https://github.com/Marplestrange/cassandra) |
| **V19** | modular rewrite (this repository): a small kernel plus 45 modules | here |
| V3.2 – V14 | the history of the project | repository `cassandra`, folders `V3.2` … `V14` |

All V18 modules are ported to V19 and tested with unit tests plus browser tests. External services (Stripe, PayPal, HelloAsso, SMTP, Dolibarr, FastPanel) are tested against
local doubles, not yet against the real services. A third-party module cannot yet be confined in its own process: install only packages from publishers you trust.

## Try it

Python 3.11 or later and the `cryptography` library.

```
python CN_main.py verifier            check manifests, isolation, install order
python tests-ui/serveur_dev.py        a throw-away test server on 127.0.0.1:9005 (fictitious test account, see the README)
python -m unittest discover -s tests -p "CN_test*.py"
```

## Contributing and security

The V19 is built for contributions: see [`CONTRIBUTING.md`](CONTRIBUTING.md) (French). Report vulnerabilities **privately**: [`SECURITY.md`](SECURITY.md).

## Who is behind it

Cassandra is carried by **La Maison Bohème**, a French non-profit association (loi 1901) that accepts donations and issues tax receipts. AGPL-3.0-or-later.
Cassandra is independent software, with no affiliation with the third-party products it can read or drive (FastPanel, Tailscale, Vaultwarden, Bitwarden, SearxNG, Telegram).
