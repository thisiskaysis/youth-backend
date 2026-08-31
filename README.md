# youth-backend

Backend API for a church youth ministry mobile app: profiles, groups,
events, QR attendance, notifications, volunteer rostering, prayer, rides,
inbox messaging, forms/consent, decisions & follow-up, reporting, and a
newsfeed/navigation CMS. Product spec lives in `/docs` as planning
spreadsheets.

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
  Channels (`ws/attendance/<session_id>/?token=<jwt>`). Cron-able
  `send_attendance_reminders` command nudges Leaders/Admins about sessions
  still open with people on site.
- **Notifications** (`notifications`) - per-category push/email
  preferences with quiet hours (`/api/notifications/preferences/me/`),
  device token registration (`/api/notifications/device-tokens/`), an
  in-app inbox (`/api/notifications/`), and a pluggable push backend
  (console/log by default - swap in Expo/FCM/APNs later). Cron-able
  `send_due_notifications` command dispatches anything scheduled. Already
  wired into event publishing/changes; other domains call
  `notifications.services.notify()` as they're built.
- **Core** (`core`) - shared audit trail, role-based permissions,
  pagination, JWT auth for websockets.
- **Volunteer rostering** (`volunteers`) - positions per team
  (`/api/volunteers/positions/`), roster/assignment workflow
  (`/api/volunteers/assignments/`: draft, publish, respond, cancel), a
  member-first candidate flow (assigning an outsider requires an explicit
  `add_to_group` flag), soft overlapping-call-time conflict warnings, and
  self-managed availability (`/api/volunteers/availability/`). Cron-able
  `send_volunteer_reminders` command handles pending-response and
  serving-soon/today reminders.
- **Prayer** (`prayer`) - public/leaders-only/anonymous requests
  (`/api/prayer/requests/`), moderation with escalation to Admins, an
  "I prayed" toggle, and leader responses that arrive as an Inbox message.
- **Rides** (`rides`) - transport requests (`/api/rides/requests/`) with a
  REQUESTED→ARRANGING→CONFIRMED/COMPLETED/CANCELLED status workflow and
  notifications on confirm/cancel.
- **Inbox** (`inbox`) - controlled one-way Leader→youth messages
  (`/api/inbox/messages/`), scoped to people a Leader is authorised to
  contact; reused by Prayer for responses.
- **Forms & consent** (`forms_app`) - form definitions with a JSON
  schema, assignment/submission tracking (`/api/forms/definitions/`,
  `/api/forms/assignments/`), and a cron-able `send_form_reminders`
  command (7-day/48-hour due + overdue).
- **Decisions & follow-up** (`decisions`) - structured decision records
  (`/api/decisions/`) and accountable follow-up (`/api/decisions/follow-ups/`),
  Leader/Admin only with no youth-facing visibility at all. Cron-able
  `send_followup_reminders` command handles due-soon/overdue nudges.
- **Reporting** (`reporting`) - leadership dashboard (`/api/reporting/dashboard/`)
  covering attendance, school-year breakdown, group participation,
  decisions, prayer volume, rides, and outstanding consent, plus
  drill-down list endpoints and per-event roster/attendance-trend reports.
  No models of its own - reads every other domain app.
- **Content/CMS** (`content`) - newsfeed posts (`/api/content/`) with the
  same draft/scheduled/published/expired/archived lifecycle as Events, and
  the same audience targeting (shared `groups.audience.AudienceTargetMixin`).
  Cron-able `publish_scheduled_content` handles scheduled publish/expiry.
- **Dynamic navigation** (`navigation`) - custom menu items
  (`/api/navigation/`) with bulk reorder (`PATCH /api/navigation/reorder/`),
  Admin-only protected items that can never be deleted via the API, and
  destination validation. Cron-able `publish_scheduled_navigation` mirrors
  content's scheduling.
- Automated tests for the flows/security fixes above (`python manage.py test`).

## Not built yet

- Google / Apple sign-in (current auth is username/password + JWT)
- Weekly ministry summary digest email (explicitly declined - not planned)
- Registration/tags/segmentation (post-launch per the original spec)
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
