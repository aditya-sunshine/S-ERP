# School ERP Demo — Vercel Deployment

Live demo of **Green Valley Public School** ERP.

## Login

| Role        | Username     | Password        |
|-------------|--------------|-----------------|
| Admin       | admin        | ChangeMe123!    |
| Accountant  | accountant   | Accountant@1    |
| Teacher     | teacher1     | Teacher@123     |

## Deploy to Vercel

```bash
# 1. Install Vercel CLI (once)
npm i -g vercel

# 2. Login
vercel login

# 3. From this folder
vercel

# 4. Production
vercel --prod
```

Or connect the GitHub repo in the Vercel dashboard and deploy.

## Important limitations (Vercel free / serverless)

- SQLite lives in `/tmp` → **data resets** when the serverless function is recycled (cold start).
- Demo data is automatically re-seeded when the database is empty.
- Not suitable for production multi-user use. For a permanent demo use Render, Railway, or a VPS.

## Local run

```bash
pip install -r requirements.txt
python app.py
```
