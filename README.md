# conta

[![ci](https://github.com/filias/conta/actions/workflows/ci.yml/badge.svg)](https://github.com/filias/conta/actions/workflows/ci.yml)

Deadlines, how-to guides and reminders for freelancers (*trabalhadores
independentes*) in Portugal. Live at [conta.filias.dev](https://conta.filias.dev).

- **Public:** a yearly calendar of IRS, IVA and Segurança Social obligations, a
  subscribable `.ics` feed of it, and video guides on how to do each one.
- **Private (logged in):** my own deadlines filtered to my situation, ticking
  them off with the amount paid/invoiced, yearly totals, private notes and videos,
  a private calendar feed with alarms, and daily email / push reminders.

> Not tax advice. Deadlines are encoded as of 2026 — check the
> [AT calendário fiscal](https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/calendario_fiscal/Pages/Quadro_res_Decl_2026.aspx)
> when the law changes.

## What's public

**Everything in this repo is public-safe.** Personal data never goes in git:

| Where | What | In git? |
| --- | --- | --- |
| `content/guides/*.md`, `conta/static/videos/` | Public guides and videos | yes |
| `private/guides/*.md`, `private/videos/` | Private notes/videos, served only when logged in | no (`.gitignore`) |
| `conta.db` | What's done, amounts, settings | no |
| `.env` | Password hash, secrets, SMTP | no |

Back up `private/` and `conta.db` on the server — git won't.

## Setup

```bash
uv sync
cp .env.example .env
uv run flask --app conta hash-password   # paste into ADMIN_PASSWORD_HASH
uv run flask --app conta run --debug     # http://127.0.0.1:5000
```

Then log in (footer link), open **Settings** and pick what applies to you.

## How it works

- `conta/obligations.py` — the rules. Each obligation has a schedule that yields
  `(period, date)` per year; deadlines on a weekend/holiday move to the next
  business day (`conta/holidays.py`). Personal routines (`personal=True`, e.g.
  the monthly invoice) only show on the private side.
- `conta/ics.py` — calendar feeds. `/calendar/public.ics` has everything;
  `/calendar/<CALENDAR_TOKEN>.ics` has only what applies to you, with alarms at
  09:00 N days before (Settings → reminder days). Apple Calendar honours the
  alarms; Google Calendar ignores alarms in subscribed feeds.
- `conta/reminders.py` — `flask --app conta remind` sends one digest when
  something is N days away or overdue, by email (`SMTP_*`) and/or
  [ntfy](https://ntfy.sh) push (`NTFY_URL`). `--dry-run` prints it.
- `conta/guides.py` — Markdown guides with front matter (`title`, `summary`,
  `youtube` or `video`, `order`, `category`).

### Adding a guide with a video

Record the screen, upload to YouTube, then create `content/guides/<slug>.md`:

```markdown
---
title: Submitting the IVA quarterly return
summary: Declaração periódica on the Portal das Finanças, step by step.
youtube: <video id>
category: iva
order: 30
---

Steps…
```

For a private one, put the file in `private/guides/` and the video in
`private/videos/` with `video: file.mp4`. (Unlisted YouTube videos are still
viewable by anyone with the link, so use `private/videos/` for anything
sensitive.)

## Deploy

Same pattern as the other filias.dev apps: Caddy → gunicorn under systemd, and
a webhook that runs `git pull && uv sync && systemctl restart conta` on push to
`main`.

One-time server setup:

1. DNS: an `A` record for `conta` → the server IP (Namecheap).
2. `git clone git@github.com:filias/conta.git /opt/conta && cd /opt/conta && uv sync`
3. Create `/opt/conta/.env` from `.env.example` (`SESSION_COOKIE_SECURE=1`).
4. `cp deploy/*.service deploy/*.timer /etc/systemd/system/`, put
   `WEBHOOK_SECRET=…` in `/etc/conta-webhook.env`, then
   `systemctl enable --now conta conta-webhook conta-remind.timer`.
5. Add `deploy/Caddyfile`'s block to `/etc/caddy/Caddyfile`, `caddy reload`.
6. GitHub → Settings → Webhooks: `https://conta.filias.dev/deploy`,
   content type `application/json`, the same secret, push events.

Ports: app `8007`, webhook `9007` (localhost only).

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```
