# Gratitude Text App

A nightly gratitude practice delivered by SMS. Every evening at 9pm ET you get a prompt, reply with your thoughts, and the app tracks your streak and sends a weekly digest every Sunday.

## Features

- Nightly prompt at 9pm (30 rotating questions)
- Streak tracking with encouraging responses
- Sunday weekly digest replacing the regular prompt
- SMS commands: `STREAK`, `HISTORY`, `HELP`
- Multi-user ready (add people via CLI)

## Setup

### 1. Twilio (free trial — no credit card needed to start)

1. Sign up at [twilio.com](https://twilio.com) — you get $15 free credit
2. Go to **Console → Phone Numbers → Manage → Buy a number** — get a US number (~$1.15/month after trial)
3. Note your **Account SID**, **Auth Token**, and phone number

### 2. Local setup

```bash
git clone <this-repo>
cd <this-repo>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your Twilio credentials in .env
```

### 3. Add yourself as a user

```bash
python manage.py add_user +12125550100 "Your Name"
```

### 4. Run locally

```bash
python app.py
```

To test with real SMS locally, expose port 5000 with [ngrok](https://ngrok.com):

```bash
ngrok http 5000
```

Then in Twilio Console → your phone number → **Messaging Configuration → Webhook**, set:

```
https://<your-ngrok-id>.ngrok-free.app/sms
```

Send a test message:

```bash
python manage.py send_test +12125550100
```

### 5. Deploy (so the nightly job runs reliably)

**Railway** (recommended — ~$5/month, always on):

1. Push this repo to GitHub
2. New project on [railway.app](https://railway.app) → Deploy from GitHub
3. Add environment variables from `.env`
4. Copy the Railway URL and set it as the Twilio webhook (same as step 4 above)

**Render** also works — use the free tier with a keep-alive ping, or the $7/month paid tier.

## SMS Commands

| Reply | Response |
|-------|----------|
| Anything | Saves as today's gratitude entry |
| `STREAK` | Your current streak |
| `HISTORY` | Last 7 entries |
| `HELP` | Command list |
| `STOP` | Unsubscribe (handled automatically by Twilio) |

## Managing users

```bash
python manage.py list_users
python manage.py add_user +12125550100 "Name" "America/New_York"
python manage.py deactivate +12125550100
```
