# Deploying LifeLink to Vercel

Vercel runs the Flask app as a serverless function (`api/index.py`, routed by `vercel.json`).
It **cannot** reach a MySQL server on your own PC (`127.0.0.1`), so the app needs a cloud MySQL database.

## 1. Create a free MySQL database (TiDB Cloud, MySQL-compatible)

Easiest: in the Vercel dashboard → your project → **Storage** (or **Integrations / Marketplace**) → **TiDB Cloud** → Create/Connect.
It adds the database credentials to the project's env vars.

Or sign up at https://tidbcloud.com → create a free *Starter/Serverless* cluster → **Connect** → copy the
connection string, which looks like `mysql://USER:PASSWORD@HOST:4000/DBNAME`.

## 2. Set Environment Variables in Vercel (Project → Settings → Environment Variables)

| Name | Value |
|------|-------|
| `DATABASE_URL` | `mysql://USER:PASSWORD@HOST:4000/lifelink_db` (if the integration added `TIDB_*` vars instead, build this from them, or copy it from TiDB Cloud → Connect) |
| `SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | `production` |

SSL is turned on automatically for any non-local database host (`DB_SSL_MODE=AUTO`).

## 3. Create the tables (run once, from your PC)

Put the same `DATABASE_URL` in your local `.env`, then:

```bash
pip install -r requirements.txt
python scripts/init_db.py          # add --seed for demo data
python scripts/init_admin.py       # creates the admin account from ADMIN_* in .env
```

⚠️ `init_db.py` drops existing LifeLink tables first, so only run it on a new database.

## 4. Redeploy

Push to GitHub (Vercel redeploys automatically) or click **Redeploy** in Vercel.
Check `https://<your-app>.vercel.app/health`: it should return `"connected": true`.
