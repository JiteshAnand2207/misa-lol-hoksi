# CHANGES

Zluti summary of everything added and changed on misa.lol since the baseline commit.

All changes are committed, the working tree is clean, and the full test suite is green.

---

## What's new

### 1. Ask me anything (asks)
- Visitors submit a name + question.
- Every question lands in the owner's inbox; the owner can answer (answer is shown publicly) or delete it.
- Rendered on the profile page; fully sanitized (no raw HTML/scripts).

### 2. Guestbook (guestbook)
- Visitors sign the guestbook with a name + message.
- Messages are **not public until approved** by the owner (approve / bin flow in the owner panel).
- Approved entries render on the profile; fully sanitized.

### 3. Tally / vote counter (tally)
- A vote counter on the profile — each visitor can vote **once per IP address** (no multi-voting).
- Visual tally bars render the result.
- Owner can clear the tally from the panel.

### 4. Doodles (chalkboard wall)
- Public chalkboard wall where visitors can post doodles.
- Owner moderates: keep or remove entries.

### 5. Secret — word-locked reveal (secret)
- A profile can hold a **secret word-hash, url and label**.
- Visitors see nothing (no word, no hash, no url, no label) until they guess the exact word.
- On a correct match the endpoint returns only the `url` and `label` — the word and the hash are never returned, ever.
- Server-side comparison uses the raw stored `wordHash` (SHA-256), constant-time, with rate limiting per profile and per IP so it cannot be brute-forced.
- Fixed a leak where the reveal url/label were exposed in the public stripped settings (security patch in commit `8aa7417`).

### 6. Owner panel `/me` (moderation hub)
- All moderation in one place: asks, guestbook, doodles, tally, and secret status (whether a word-locked secret is active).
- Reply / approve / delete / clear — all in a single panel.
- New `/me` route in the dashboard navigation.

### 7. Presence + feature render blocks
- Live presence display (who is online right now).
- New feature render blocks: reverse, night, draw, capsule, archive, moon, neighbours, presence.

---

## Changed files

### Backend — new
- `backend/app/api/v1/asks.py`
- `backend/app/api/v1/doodles.py`
- `backend/app/api/v1/guestbooks.py`
- `backend/app/api/v1/tally.py`
- `backend/app/api/v1/secret_reveal.py`
- `backend/app/features/__init__.py`
- `backend/app/features/common.py`
- `backend/app/features/render.py`
- `backend/app/features/sanitize.py`
- `backend/tests/` — 11 new test files
- `backend/conftest.py`
- `backend/pytest.ini`
- `backend/requirements-dev.txt`

### Backend — modified
- `backend/app/api/v1/router.py`
- `backend/app/core/profile_sanitize.py`
- `backend/app/core/profiles.py`
- `backend/app/core/public_profile_html.py`
- `backend/app/db/admin_db.py`
- `backend/app/main.py`
- `backend/requirements.txt`

### Frontend — new
- `frontend/app/me/page.tsx`
- `frontend/components/me/MeView.tsx`
- `frontend/lib/me-moderation.ts`

### Frontend — modified
- `frontend/lib/feature-flags.tsx`
- `frontend/lib/types.ts`
- `frontend/components/dashboard/DashboardShell.tsx`
- `frontend/lib/i18n/` — all 8 language files (en, de, es, fr, pt-BR, ru, tr, ar)

### Repo hygiene
- `.gitignore` — ignores `**/.venv/`, `**/node_modules/`, `**/__pycache__/`, build/dist artifacts.
- Stopped tracking `backend/.venv` (kept on disk locally) — commit `1acfc77`.

---

## Verification

- Backend tests: **68 passed**.
- Frontend: `eslint` exit 0, `tsc --noEmit` exit 0.
- Git: working tree clean at HEAD `1acfc77`.
