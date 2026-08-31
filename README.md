# youth-backend

Backend API for a church youth ministry mobile app: profiles, groups,
events, QR attendance, and (planned) notifications, volunteer rostering,
prayer/rides/inbox/forms, decisions, and reporting. Product spec lives in
`/docs` as planning spreadsheets.

Stack: Django + Django REST Framework + Django Channels (websockets) +
SimpleJWT. SQLite for local dev.

## Getting started

```
source venv/bin/activate
cd youthbackend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py test
```

## Implemented

- **Accounts & people** (`users`) - JWT auth (`/api/token/`), sign-up
  (`POST /api/users/`), profile fields (role, status, DOB, school year,
  guardian/emergency contact, QR token, first-time-visitor flag), scoped
  people search (`/api/users/search/`), visitor quick-create
  (`/api/users/visitors/`).
- **Groups** (`groups`) - unified Connect/volunteer/ministry group model,
  membership management scoped to the groups a Leader actually leads, "My
  Groups" endpoint.
- **Events** (`events`) - draft/scheduled/published/expired/archived
  lifecycle, audience targeting by group/school-year/everyone.
- **Attendance** (`attendance`) - QR + manual sign-in/out, live on-site
  dashboard, end-of-night reconciliation, realtime updates over Django
  Channels (`ws/attendance/<session_id>/?token=<jwt>`).
- **Core** (`core`) - shared audit trail, role-based permissions,
  pagination, JWT auth for websockets.
- Automated tests for the flows/security fixes above (`python manage.py test`).

## Not built yet

- Google / Apple sign-in (current auth is username/password + JWT)
- Notifications (push/email preferences, quiet hours, reminders)
- Volunteer rostering
- Prayer requests, ride requests, inbox messaging, forms & consent
- Decisions & follow-up
- Newsfeed / dynamic navigation CMS
- Reporting / leadership dashboard
- Rock RMS integration is permanently out of scope (explicit product
  decision, not an oversight)

## Project memory

Architecture decisions, deliberate simplifications, fixed gotchas, and
detailed build status are kept in GitHub Copilot's repo memory for this
workspace (`/memories/repo/` from Copilot's point of view). It isn't
committed to git - it lives in the editor's local workspace storage, so
ask Copilot to check it when resuming work here. Three files:

- `project-overview.md` - product summary distilled from `/docs`
- `architecture.md` - stack choices, app layout, deliberate
  simplifications, fixed gotchas, dev commands
- `roadmap-status.md` - what's built vs deferred, suggested next steps
