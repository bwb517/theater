# THEATER Deployment Guide

This guide walks you through deploying THEATER to production using Railway.app and a custom domain. The whole process takes ~30 minutes.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Buy a Domain](#step-1-buy-a-domain)
3. [Step 2: Push Code to GitHub](#step-2-push-code-to-github)
4. [Step 3: Deploy with Railway](#step-3-deploy-with-railway)
5. [Step 4: Connect Your Domain](#step-4-connect-your-domain)
6. [Step 5: Configure Environment Variables](#step-5-configure-environment-variables)
7. [Step 6: Seed Database & Create Admin](#step-6-seed-database--create-admin)
8. [Step 7: Verify & Share Link](#step-7-verify--share-link)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

You'll need:
- **GitHub account** (free at [github.com](https://github.com))
- **Railway account** (free at [railway.app](https://railway.app))
- **Domain name** (buy from [Namecheap](https://namecheap.com), ~$12/year)
- **Anthropic API key** (new one, since the dev key is compromised — [console.anthropic.com](https://console.anthropic.com/settings/keys))

Time to gather: ~10 minutes (including domain purchase).

---

## Step 1: Buy a Domain

1. Go to [Namecheap.com](https://namecheap.com)
2. Search for your desired domain (e.g., `theater-wargame.com`)
3. Add to cart, checkout, and pay (~$12 for .com, first year)
4. You'll receive a confirmation email. Don't worry about DNS yet — Railway handles that.

**Save:** Your domain name (e.g., `theater-wargame.com`)

---

## Step 2: Push Code to GitHub

### 2a. Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. **Repository name:** `theater` (or anything you like)
3. **Description:** `AI-powered military wargaming platform`
4. **Public** (beta testers need to access it) or **Private** (if this is sensitive)
5. **Skip** "Initialize with README" (you already have one)
6. Click **Create repository**

You'll see a page with commands. Copy the HTTPS URL from there (looks like `https://github.com/YOUR-USERNAME/theater.git`).

### 2b. Push Your Local Code

Open Command Prompt or PowerShell in your THEATER project folder:

```bash
cd C:\Users\charl\Desktop\Claude\Sessions\Theater
```

Initialize git and push:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

git init
git add .
git commit -m "Initial commit: THEATER platform with security hardening"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/theater.git
git push -u origin main
```

**Replace `YOUR-USERNAME`** with your actual GitHub username.

You may be prompted to log in. Use your GitHub credentials (or [create a personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) if password auth fails).

**Verify:** Go to `https://github.com/YOUR-USERNAME/theater` and confirm your files are there.

---

## Step 3: Deploy with Railway

### 3a. Sign Up & Connect GitHub

1. Go to [railway.app](https://railway.app)
2. Click **Sign Up** → Choose **GitHub** → Authorize Railway
3. You'll land in the dashboard

### 3b. Create a New Project

1. Click **+ New Project**
2. Select **Deploy from GitHub repo**
3. Search for `theater` (the repo you just created)
4. Click it → click **Deploy**

Railway will:
- Read your `docker-compose.yml`
- Build both the backend and frontend
- Start the containers
- Assign a temporary URL like `theater-production-abc123.up.railway.app`

This takes 3–5 minutes. You'll see logs in the Railway dashboard. Once you see "✓ Deployment complete," you're done here.

**Save:** Your Railway URL (e.g., `theater-production-abc123.up.railway.app`)

---

## Step 4: Connect Your Domain

### 4a. In Railway Dashboard

1. Click on your THEATER **project**
2. Go to **Settings** → **Domain**
3. Click **+ Add Domain**
4. Enter your domain name (e.g., `theater-wargame.com`)
5. Railway shows you a **CNAME record** to add

### 4b. In Namecheap (or your registrar)

1. Log in to Namecheap
2. Go to **Domain List** → click your domain
3. Click **Manage** → go to the **Advanced DNS** tab
4. Find or create a **CNAME record**:
   - **Host:** `@` (or blank, depending on the UI)
   - **Value:** Paste the CNAME from Railway (looks like `cname.railway.app`)
   - **TTL:** 3600

5. Click **Save**

**Wait 5–10 minutes** for DNS to propagate. Then visit `https://theater-wargame.com` and confirm it loads (may show "coming up" briefly while Caddy provisions the TLS cert).

---

## Step 5: Configure Environment Variables

### In Railway Dashboard

1. Go to **project** → **Environment**
2. Click **+ Add Variable** for each of these:

| Key | Value | Notes |
|-----|-------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Generate a **new** key from [console.anthropic.com](https://console.anthropic.com/settings/keys) (not the dev one) |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Leave as-is |
| `SECRET_KEY` | Your generated 64-byte key | Generate via: `python -c "import secrets; print(secrets.token_urlsafe(64))"` Run locally and copy the output |
| `DATABASE_URL` | (auto-injected by Railway) | Railway sets this automatically when PostgreSQL is provisioned — do not override |
| `FRONTEND_URL` | `https://theater-wargame.com` | Use **HTTPS** and your domain |
| `SITE_ADDRESS` | `theater-wargame.com` | Tells Caddy your domain (enables auto-TLS) |
| `TOKEN_BUDGET` | `1000000` | Optional; informational token spend cap |
| `SEED_DEMO_USERS` | (leave blank) | **Important:** do NOT set this in prod to avoid seeding known-password demo accounts |

3. Click **Deploy** (Railway redeploys with new vars)

**Critical:** Do **not** set `SEED_DEMO_USERS=true` on the public deploy. You'll create your own admin account next.

---

## Step 6: Seed Database & Create Admin

The database starts empty. You need to:
1. Create the unit library and scenario templates (safe, non-sensitive)
2. Create your own admin account (so you can manage the beta)

### 6a. Seed the Database

In Railway, click your **backend** service → **Deployments** → latest one → **View Logs** (or wait for logs to stream).

Once deployment is stable, click the **Terminal** tab and run:

```bash
python seed_data.py
```

You'll see output:
```
✓ Unit templates created (50+)
✓ Scenarios created (5)
• Skipping demo users (set SEED_DEMO_USERS=true to create them)
✓ Demo session IRON WOLF created
```

(The "Skipping demo users" line is expected and **good** — no well-known backdoor passwords.)

### 6b. Create Your Admin Account

1. Open your deployed site: `https://theater-wargame.com`
2. Click **Sign Up**
3. Create an account with your real email and a strong password:
   - **Username:** `admin` (or anything)
   - **Email:** your-email@example.com
   - **Password:** Something strong (it's auto-assigned role `player`)

4. Click **Sign Up** → you'll get a JWT and be logged in as a **player**

### 6c. Promote to Admin (in Database)

You need to manually update the role to `admin` since registration hardcoded it to `player`.

In Railway **backend** terminal:

```bash
psql $DATABASE_URL
```

Then:

```sql
UPDATE users SET role = 'admin' WHERE username = 'admin';
SELECT username, role FROM users WHERE username = 'admin';
\q
```

You should see `role = admin` in the output.

Done. Log out and back in — you'll now have admin access (user list, session audit, stats).

---

## Step 7: Verify & Share Link

### Verification Checklist

- [ ] Visit `https://theater-wargame.com` and confirm it loads with a green lock (HTTPS)
- [ ] Try `http://theater-wargame.com` and confirm it redirects to HTTPS
- [ ] Log in as your admin account
- [ ] Go to **Admin** tab → see unit library, scenarios, user list
- [ ] Test **Sign Up** with a dummy account → confirm new user is `player` role (not admin)
- [ ] Test the demo IRON WOLF session
- [ ] Go to `/api/docs` and confirm Swagger loads (optional: disable in production later if you want to hide API surface)

### Share with Beta Testers

Send them:

```
Welcome to THEATER Wargaming Beta!

Sign up at: https://theater-wargame.com

Known limitations:
- Password reset not yet implemented (contact admin if locked out)
- Single SQLite database (works fine for <10 concurrent users)
- Feedback welcome — report bugs to [your email]

Enjoy!
```

---

## Troubleshooting

### "Domain not found" after adding CNAME

DNS propagation can take 5–30 minutes. Check your CNAME:

```bash
nslookup theater-wargame.com
```

Should show the Railway CNAME. If it doesn't, wait a few minutes and try again.

### "Certificate not ready" or "insecure connection"

Caddy is provisioning the Let's Encrypt cert. Wait 2–3 minutes and reload. Check Railway backend logs for:
```
caddy | Obtaining certificate...
caddy | Certificate obtained
```

### "403 CORS error" when beta testers try to play

Confirm `FRONTEND_URL=https://your-domain.com` in Railway environment vars. It must match the domain users visit exactly (with HTTPS).

### Backend/frontend not deploying

Check Railway **Deploy Logs**:
- Backend needs `requirements.txt` with all deps ✓
- Frontend needs `npm ci` and `npm run build` ✓
- Both need `Dockerfile`/`docker-compose.yml` ✓

All are in place. If still failing, check:
1. Did you push code to GitHub? (`git push`)
2. Did Railway re-trigger a deploy? (Should auto-trigger on push)
3. Are there any Python syntax errors? (`python -m py_compile backend/*.py`)

### API key usage tracking

Check your token spend:
1. Open backend terminal
2. Run:
```bash
psql $DATABASE_URL -c "SELECT function_name, SUM(input_tokens) AS input, SUM(output_tokens) AS output FROM token_usage GROUP BY function_name;"
```

You'll see per-function token usage. If input tokens spike, a beta tester may have found a loop or runaway scenario.

---

## Next Steps (Optional)

Once beta is running, consider:

1. **Enable password reset** — add an email service (Mailgun, SendGrid)
2. **Public /docs disable** — in `backend/main.py`, remove or gate Swagger UI
3. **Per-user spend cap** — track token usage per user; prevent abuse
4. **Error logging** — add Sentry or similar to catch bugs from testers
5. **Analytics** — Plausible or Mixpanel to track feature usage

---

## Support

If you get stuck:
1. Check Railway **Logs** tab (both backend and caddy)
2. Verify env vars are set (Railway **Environment** tab)
3. Check GitHub repo is up to date (`git status`)
4. DM me or check CLAUDE.md for architecture details

Good luck! 🎭

