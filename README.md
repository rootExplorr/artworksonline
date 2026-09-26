# ArtOnline

Angular Material frontend with a FastAPI and MySQL backend for listing, sorting, and uploading artwork.

## Backend

Create the database once in MySQL:

```sql
CREATE DATABASE artonline CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

In PowerShell, from the repository root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Set `DATABASE_URL` in `backend/.env` to your MySQL credentials. The API creates its tables on startup. Uploaded images are stored under `backend/uploads/artworks/` and served from `/uploads/`.

Configure the single admin account in `backend/.env`. Generate an Argon2 password hash and signing secret from `backend/`:

```powershell
python -c "from getpass import getpass; from pwdlib import PasswordHash; print(PasswordHash.recommended().hash(getpass()))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated values as `ADMIN_PASSWORD_HASH` and `AUTH_SECRET_KEY`; set `ADMIN_USERNAME` to the desired login name. Keep `AUTH_COOKIE_SECURE=false` only for local HTTP development; set it to `true` behind HTTPS. Artwork viewing and reviews are public. Adding, editing, and deleting artworks require the admin login.

Open `http://localhost:4200/login` to sign in to the admin account. Admin sessions expire after eight hours.

Run the backend unit tests with `python -m unittest discover -s tests` from `backend/`.

## Development servers

After configuring `backend/.env` and installing dependencies, run `\.\start-dev.ps1` from the repository root. It opens separate PowerShell windows for the API and frontend, and skips either server if its port is already in use. Uvicorn reloads when files under `backend/app/` change; Angular refreshes the browser when frontend files change. Stop each server with Ctrl+C in its window.

## Frontend

Install frontend dependencies from the repository root once:

```powershell
npm --prefix frontend install
```

Open `http://127.0.0.1:4200`. The frontend calls the API at `http://localhost:8000`.
