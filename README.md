# Cybersecurity Lab: Password Hash Cracking & Web Authentication

## Project overview

A small FastAPI web application used as the **authentication target** in a
university Cybersecurity course lab exercise. Students receive a leaked
username + password hash pair (out of band, not from this app) and a
candidate password list, write their own Python cracking script, and then
use the recovered username/password to log in here.

## Educational purpose

- Teaches how MD5, SHA-1, SHA-256, and SHA-512 are trivially reversible via
  dictionary/candidate attacks when used **unsalted** for password storage.
- Gives students a real (but controlled, synthetic) target to validate a
  password they cracked themselves.
- This application does **not** perform any cracking itself, and it does not
  contact any external system. It only verifies a submitted password against
  a pre-stored hash using the algorithm assigned to that account.

## Architecture

```
Student's own cracking script (outside this app)
        |
        v
  recovered username + password
        |
        v
   POST /login  ---->  hash(password, assigned algorithm) == stored hash?
        |                                   (hmac.compare_digest)
        v
   session cookie (signed, HttpOnly)
        |
        v
   GET /success (BINGO page + submission form)
        |
        v
   POST /submit  ---->  INSERT INTO successful_students
        |
        v
   session cleared, GET /admin (instructor-only) shows results table
```

## Project structure

```
secure-password-lab/
├── app/
│   ├── __init__.py
│   ├── main.py            FastAPI routes, session handling
│   ├── database.py        SQLite schema, seed data, queries
│   ├── security.py        hash_password() / verify_password()
│   └── templates/
│       ├── login.html
│       ├── success.html
│       ├── result.html
│       └── admin.html
├── data/
│   └── lab.db              created automatically at startup (gitignored)
├── reset_results.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation (local or Codespaces)

```bash
pip install -r requirements.txt
```

## GitHub Codespaces instructions

1. Push this project to a GitHub repo and open (or create) a Codespace on it.
   No devcontainer/Docker configuration is required — the default Codespaces
   image already includes Python 3.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables for this terminal session:
   ```bash
   export SESSION_SECRET="replace-with-a-long-random-secret"
   export ADMIN_PASSWORD="replace-with-instructor-password"
   ```
   For anything beyond a quick test, set these as **Codespaces Secrets**
   instead (repo/organization Settings → Secrets and variables →
   Codespaces) so they persist across rebuilds and aren't typed into a
   shared terminal.
4. Start the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. Open the **Ports** panel, find port 8000, and open it in the browser.
6. Set **Port Visibility** appropriately:
   - **Private** (default): only you (the repo owner) can open it, even with
     the link. Fine for solo testing, useless for a class.
   - **Organization**: anyone signed in to the same GitHub org/enterprise can
     open it. Reasonable if all your students are in your GitHub
     organization.
   - **Public**: anyone with the link can open it, no GitHub login required.
     Simplest for students who aren't in your GitHub org, but means the URL
     itself is the only thing gating access — don't rely on it as a secret.

   Choose the **least permissive** option that still lets your actual
   students reach the app.

## Environment variables

| Variable         | Required | Purpose                                                        |
|-------------------|----------|-----------------------------------------------------------------|
| `SESSION_SECRET`  | Recommended | Signs the session cookie. If unset, a random key is generated per process start (sessions won't survive a restart) and a warning is printed. |
| `ADMIN_PASSWORD`  | Required for `/admin` | Instructor password for the results dashboard. If unset, `/admin/login` refuses all attempts rather than allowing a blank/default password. |

Never hardcode either value in source code.

## How authentication works

1. `POST /login` receives `username` and `password`.
2. The server looks up `username` in the `users` table and reads its stored
   `password_hash` and `hash_algorithm`.
3. It hashes the submitted password with the **same algorithm assigned to
   that account** (`hashlib.md5`, `sha1`, `sha256`, or `sha512` — see
   `app/security.py`).
4. It compares the freshly computed hash against the stored hash using
   `hmac.compare_digest()` (constant-time comparison).
5. On success, `authenticated_username` is stored in a signed session
   cookie — never the password or its hash.
6. On failure, the same generic message is shown regardless of whether the
   username existed, the password was wrong, or anything else:
   *"Incorrect username or password. Please try again."* A dummy
   hash/verify call also runs on unknown usernames so a failed lookup takes
   a similar code path to a failed comparison.

There is **intentionally no rate limiting or lockout** on `/login` — this is
a controlled classroom simulation, and students are expected to try their
recovered credentials (and typos) freely.

## How the four hashing algorithms are verified

`app/security.py` exposes:

```python
hash_password(password: str, algorithm: str) -> str
verify_password(password: str, stored_hash: str, algorithm: str) -> bool
```

`algorithm` must be one of `md5`, `sha1`, `sha256`, `sha512` (case-insensitive).
Any other value causes `verify_password` to return `False` — it fails
closed instead of raising or defaulting to a "safe-looking" algorithm.

## How student results are stored

After a successful login, `GET /success` shows the **BINGO!** page and a
form for **Student ID** and **Full Name**. `POST /submit`:

1. Requires an authenticated session (see Access Control below).
2. Validates Student ID (5–20 digits) and Full Name (required, non-empty
   after trimming).
3. Inserts a row into `successful_students` (`student_id`, `student_name`,
   `login_username`, `submitted_at` — timestamp is set by SQLite via
   `CURRENT_TIMESTAMP`).
4. `student_id` has a `UNIQUE` constraint — a second submission with the
   same Student ID is rejected with *"This Student ID has already
   submitted a result."* instead of a duplicate row.
5. Clears the session (the student is effectively logged out) and shows the
   confirmation page.

## Access control (success/submission pages)

`GET /success` and `POST /submit` both check
`request.session.get("authenticated_username")`. If it's missing, the
request is redirected to `/login` — there is no way to reach the
submission form by guessing the URL. The session is cleared immediately
after a successful submission, so the link can't be reused to submit a
second result for the same login.

## How the instructor accesses `/admin`

- `GET /admin` shows an admin login form unless `request.session["is_admin"]`
  is already set, in which case it shows the results table instead.
- `POST /admin/login` compares the submitted password to `ADMIN_PASSWORD`
  using `hmac.compare_digest()`. If `ADMIN_PASSWORD` isn't set, login is
  refused outright (fail closed) rather than silently allowing anything.
- `POST /admin/logout` clears the admin flag from the session.
- The table shows all rows from `successful_students`, newest first
  (`No.`, `Student ID`, `Student Name`, `Recovered Account`, `Submitted At`).
  Regular students never see this data through any route.

## How to reset lab results

Run from the project root, outside the running server:

```bash
python reset_results.py
```

It asks for a `y` confirmation, then deletes every row from
`successful_students` only — the four synthetic accounts in `users` are
never touched.

## Database security considerations

- `data/lab.db` is created automatically at startup if missing, and lives
  outside any template/static directory.
- The app never mounts the project root or `data/` as static files, and has
  no generic/arbitrary file-download route — there is no HTTP path that can
  return `lab.db`'s contents.
- **This does not protect the database from someone with direct filesystem
  or repository access.** Preventing HTTP access to `lab.db` does not stop
  a person who has collaborator access to your GitHub repo, or shell access
  to your running Codespace, from reading the file directly.

  For an actual class deployment:
  - Students should only ever be given the forwarded web URL, nothing else.
  - Students should **not** be added as collaborators to the instructor's
    repository or given access to the instructor's running Codespace.
  - If you distribute this repository to students (e.g. so they can read
    the source), strip out `data/lab.db` first — don't hand out the live
    results database.

## Classroom safety statement

This application is a closed, self-contained teaching tool. It does not
call out to the internet, does not accept file uploads, and does not expose
any endpoint beyond the ones documented above. The synthetic accounts and
passwords in this repository exist solely for this exercise and should not
be reused anywhere else.

> **Warning:** This application intentionally uses MD5, SHA-1, SHA-256, and
> SHA-512 **without salt** for cybersecurity education. These algorithms
> must not be used directly for password storage in production systems.
> Modern applications should use password hashing algorithms such as
> Argon2id, scrypt, bcrypt, or PBKDF2 with appropriate configuration.

## Instructor test credentials

For verifying the deployed app only — do not share with students:

| Username   | Password            | Algorithm |
|------------|----------------------|-----------|
| student01  | `Moodeng#Lucky9`     | MD5       |
| student02  | `Nadech&Yaya33`      | SHA-1     |
| student03  | `Nv!dia_J3nsen`      | SHA-256   |
| student04  | `Docker$Container8`  | SHA-512   |
