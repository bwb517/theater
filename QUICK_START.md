# THEATER Deployment Quick Start

Copy-paste reference for GitHub, Railway, and domain setup. Full details in `DEPLOYMENT.md`.

---

## PART 1: GitHub Setup (5 min)

### Create Repository
1. Go to https://github.com/new
2. **Repository name:** `theater`
3. **Public** (for beta testers to access)
4. **Skip** "Initialize with README"
5. Click **Create repository**

You'll see a page with commands. Copy your HTTPS URL (e.g., `https://github.com/YOUR-USERNAME/theater.git`).

### Push Your Code

Open Command Prompt in your THEATER folder (`C:\Users\charl\Desktop\Claude\Sessions\Theater`):

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

**Replace `YOUR-USERNAME`** with your actual GitHub username. You'll be prompted for GitHub credentials.

**Verify:** Visit `https://github.com/YOUR-USERNAME/theater` and confirm files are there.

---

## PART 2: Railway Deployment (10 min)

### Step A: Sign Up

1. Go to https://railway.app
2. Click **Sign Up** → Choose **GitHub** → Authorize Railway
3. Land in dashboard

### Step B: Create Project from GitHub

1. Click **+ New Project**
2. Select **Deploy from GitHub repo**
3. Search for `theater` (your repo)
4. Click the repo → click **Deploy**

Railway will:
- Read `docker-compose.yml`
- Build backend + frontend
- Deploy automatically

**Status:** Wait for logs to show deployment complete (3–5 min). You'll see a temporary URL like:
```
https://theater-production-abc123.up.railway.app
```

**Save this URL.** You can visit it now (backend + frontend are live).

### Step C: Add Environment Variables

1. In Railway dashboard, click your **THEATER project**
2. Go to **Variables** tab (or **Settings** → **Variables**)
3. Click **+ Add Variable** and paste each of these:

```
ANTHROPIC_API_KEY = sk-ant-xxx-your-new-key-from-console.anthropic.com
CLAUDE_MODEL = claude-sonnet-4-6
SECRET_KEY = AIT24fM31MHZmvbplVfIrA-mzfni2Jw2AiC6YpMakFObb0mL-AUC7gbTberP8qTTphRLr5NFzCmiqeRdOZ4DSw
DATABASE_URL = (Railway injects this automatically when PostgreSQL is provisioned — leave blank)
FRONTEND_URL = https://your-domain.com
SITE_ADDRESS = your-domain.com
TOKEN_BUDGET = 1000000
```

**IMPORTANT NOTES:**
- `ANTHROPIC_API_KEY`: Generate a **new** key at https://console.anthropic.com/settings/keys (the dev key is compromised)
- `SECRET_KEY`: Use the one already in your `.env` (I generated it for you), or generate a new one:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- `FRONTEND_URL` and `SITE_ADDRESS`: Replace with your actual domain (e.g., `theater-wargame.com`)
- **Do NOT set `SEED_DEMO_USERS`** — you'll create your own admin next

After adding all vars, click **Deploy** (Railway redeploys with new environment).

---

## PART 3: Domain Setup (5 min)

### Get a Domain Name

1. Go to https://namecheap.com
2. Search for a domain (e.g., `theater-wargame.com`)
3. Add to cart, checkout, and pay (~$12 first year)
4. Confirm purchase email

### Connect Domain to Railway

**In Railway:**
1. Click your **THEATER project**
2. Go to **Settings** tab
3. Scroll to **Domains**
4. Click **+ Add Domain**
5. Enter your domain (e.g., `theater-wargame.com`)
6. Railway shows you a **CNAME record** — copy it

**In Namecheap:**
1. Log in → **Domain List** → click your domain
2. Click **Manage** → go to **Advanced DNS** tab
3. Find the row with **Host = @** (or add a new row if it doesn't exist)
4. Change **Type** to `CNAME`
5. Paste the Railway CNAME as the **Value**
6. **TTL** = `3600` (or default)
7. Click **Save**

**Wait 5–10 minutes** for DNS to propagate. Then visit:
```
https://theater-wargame.com
```

You should see the THEATER login page with a **green lock** (HTTPS). If not yet, wait a few more minutes.

---

## PART 4: Create Your Admin Account

Once the domain is live:

1. Visit `https://theater-wargame.com`
2. Click **Sign Up**
3. Create an account:
   - **Username:** `admin` (or your name)
   - **Email:** your email
   - **Password:** something strong
4. You'll be logged in as **player** role (registration hardcodes it now)

### Promote to Admin (via Railway Terminal)

1. In Railway, click your **backend** service
2. Click the **Terminal** tab
3. Run:

```bash
psql $DATABASE_URL
```

At the `postgres=#` prompt, type:

```sql
UPDATE users SET role = 'admin' WHERE username = 'admin';
SELECT username, role FROM users WHERE username = 'admin';
\q
```

You should see output showing `role = admin`.

Log out and back in — you'll now have **Admin** tab access.

---

## PART 5: Seed Database

In Railway backend **Terminal**, run:

```bash
python seed_data.py
```

Output:
```
✓ Unit templates created (50+)
✓ Scenarios created (5)
• Skipping demo users (set SEED_DEMO_USERS=true to create them)
✓ Demo session IRON WOLF created
```

You now have the unit library, scenarios, and a playable demo session.

---

## Verification Checklist

- [ ] Domain resolves: `https://theater-wargame.com` loads with green lock
- [ ] Redirect works: `http://theater-wargame.com` → `https://`
- [ ] Sign up works: Create a dummy account, confirm role is `player`
- [ ] Admin works: Your account shows **Admin** tab
- [ ] Admin page loads: See user list, session audit
- [ ] API works: `/api/docs` loads (optional; can disable later)
- [ ] Demo works: "IRON WOLF" session is playable

---

## Share with Beta Testers

Copy this link and share:

```
https://theater-wargame.com

Sign up to wargame! Feedback welcome.
```

---

## If Something Breaks

### Check Logs
In Railway, click **backend** → **Deployment Logs**. Look for errors.

### Redeploy
If you fixed code locally:
```bash
git add .
git commit -m "Fix: [description]"
git push origin main
```
Railway auto-redeploys from GitHub.

### Reset Everything (Nuclear Option)
1. Delete the Railway project
2. Go back to Step B and redeploy

Full details in `DEPLOYMENT.md` troubleshooting section.

---

## Next Moves (Not Required Now)

- Rotate API key regularly
- Monitor token usage (check `TokenUsage` table)
- Add password reset flow
- Disable public `/docs` endpoint (hide API surface)

See `DEPLOYMENT.md` for details.

---

**That's it. You're live. 🎭**
