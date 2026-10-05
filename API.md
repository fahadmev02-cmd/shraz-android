# API map — version 0.1

All writes are JSON POST requests. Sessions are issued in a `shraz_session` HTTP-only, SameSite=Strict cookie. Use `--secure-cookie` behind HTTPS. Keep requests same-origin; cross-origin Origin headers are rejected. Protected responses use `Cache-Control: no-store`.

Errors are JSON `{ "error": "message" }` with 400 (invalid input), 401 (sign-in needed), 403 (permission denied), 404 (missing record), 409 (conflict), 413 (size), 415 (content type), or 429 (authentication rate limit). Successful writes return `{ "ok": true }`, sometimes with an `id`.

## Public/authentication

- `GET /api/session` → `{user: {id,name,email,role} | null, needs_setup: boolean}`
- `POST /api/setup` → first owner only: `{name,email,password,consent:true}`
- `POST /api/register` → client role only: `{name,email,password,consent:true}`
- `POST /api/login` → `{email,password}`
- `POST /api/logout` → `{}`

New passwords must be 12–128 characters. Authentication endpoints permit 20 attempts per IP per five minutes in this local release. Registration cannot choose a staff role.

## Workspace

- `GET /api/clients` → staff-visible client summaries; coaches see only assignments.
- `GET /api/workspace?client=ID&day=YYYY-MM-DD` → selected client profile, current plans, daily logs, measurements, check-ins, photo metadata, messages, membership, pauses and plan versions. Clients can omit `client`; it always resolves to themselves.
- `GET /api/photo/ID?client=ID` → authorized JPEG/PNG bytes; photo ownership must match the selected accessible client.

## Client submissions

- `POST /api/profile`: `{age,height,goal,diet,activity,allergies}`. Age is 18–110; height is cm.
- `POST /api/logs`: `{day,kind,ref,value}`.
  - `kind:"meal"` / `"workout"`: `ref` must be a current-plan item ID; `value` is boolean.
  - `kind:"water"`: use `ref:"today"`; `value` is total ml, 0–10000.
  - `kind:"exercise"`: current workout item ID; `value:{sets,reps,weight}`; weight in kg.
- `POST /api/progress`: `{day,weight,waist:null | number}`; kg and cm. A second save on the same date replaces that date's measurements.
- `POST /api/checkins`: `{energy,sleep,hunger,adherence,notes}`; integer scores 1–10.
- `POST /api/photos`: `{day,view:"front"|"side"|"back",content:"base64 image bytes"}`; max decoded size 2 MB, JPEG/PNG only.
- `POST /api/membership/pause`: `{days:integer}`.

## Coaching

- `POST /api/messages`: `{client_id,body}`; clients and authorized staff. Clients need an assigned coach. Text max 3000 characters.
- `POST /api/checkins/review`: `{client_id,id,status:"reviewed"|"changes required",feedback}`; assigned coach/admin only.
- `POST /api/plan`: `{client_id,kind:"diet"|"workout",plan}`; assigned coach/admin only. New immutable plan version created on every publish.

Diet plan shape:

```json
{
  "title": "Coach-created daily plan",
  "calories": 2000,
  "protein": 130,
  "carbs": 230,
  "fat": 60,
  "water": 2500,
  "items": [{
    "id": "meal-1", "slot": "Lunch", "name": "Meal name",
    "detail": "Coach-entered ingredients, portions and instructions",
    "calories": 650, "protein": 40, "carbs": 75, "fat": 20
  }]
}
```

Workout plan shape:

```json
{
  "title": "Coach-created programme",
  "items": [{
    "id": "exercise-1", "name": "Exercise name", "detail": "Coach instructions",
    "sets": 3, "reps": 10, "rest": 90
  }]
}
```

Plans require 1–30 items with unique IDs. Nutritional amounts are illustrative schema examples, not a suggested personal plan.

## Admin only

- `GET /api/admin` → users, plans, memberships, pending pauses, pending-check-in count, audit events.
- `POST /api/admin/users`: `{name,email,password,role:"client"|"coach"}`.
- `POST /api/admin/assign`: `{client_id,coach_id}`.
- `POST /api/admin/plans`: `{name,months,price,pause_days,min_pause,max_pause}`.
- `POST /api/admin/membership`: `{client_id,plan_id,start:"YYYY-MM-DD"}`; manual activation, no charge.
- `POST /api/admin/pause`: `{id,approve:boolean}`; approval updates allowance and expiry transactionally. A handled request cannot be approved twice.

No payment, AI or third-party credentials are shipped. Those integrations do not have working API routes in this release.
