# Shraz — first runnable release

A mobile-first coaching web app based on the supplied Shraz Flexible Dieting Solution requirements. Includes a working Python/SQLite backend and client, coach and admin interfaces. No runtime package installation or API keys are needed for the core app.

**This is the first core-workflow release, not completion of all 22 sections of the specification.** It is not an Android APK or an iOS App Store build. External services and production hosting have not been connected.

## Run it

1. Install Python **3.11 or later**.
2. Extract this folder and open a terminal inside it.
3. Run:

```sh
python server.py --port 8080
```

On Windows, `py server.py --port 8080` also works. If the port is occupied, choose another, such as `--port 8081`.

4. Open **http://127.0.0.1:8080** on the same computer.
5. Create the owner account. There are no default credentials or pre-created production accounts.

The app creates `shraz.sqlite3` beside `server.py`; records persist across restarts. The database includes private progress photos. Keep it out of source control and public file storage.

### First coaching session

1. In **Business**, create a coach and client, or have the client register from the sign-in page.
2. Assign the client to their coach.
3. Select the client in the header. In **Nutrition** and **Training**, create and publish their plans. Starter templates are examples requiring coach review.
4. Create a membership plan with your actual pricing, term and pause rules. Activate it manually after arranging payment separately.
5. The client signs in, completes their profile, tracks meals/training/water, logs measurements, uploads photos and submits a check-in.
6. The assigned coach can review the check-in, publish a revised plan and reply in the coaching conversation.

The avatar button in the header signs out on mobile and desktop.

## Included and functional

| Area | First-release functionality |
| --- | --- |
| Accounts | First-owner setup, client registration, email/password sign-in, sign-out, hashed passwords, expiring HTTP-only cookie sessions |
| Authorization | Clients access only their own records; coaches access assigned clients; administrators manage the business; enforced by the API |
| Profile | Adult onboarding: age, height, goals, activity, diet preference and food restrictions |
| Nutrition | Coach plan editor, daily calorie/macronutrient targets, meals with ingredient/portion instructions, completion/undo and water logging |
| Training | Coach exercise editor, sets/reps/rest instructions, completion and actual sets/reps/load logs |
| Progress | Weight and waist measurements, date-based trends, private front/side/back JPEG/PNG uploads |
| Check-ins | Energy/sleep/hunger/adherence scores, notes, coach review status and feedback |
| Messages | Persisted client/coach text conversations; refresh to load new replies |
| Plan history | New version on each coach publish; earlier versions are viewable in the editor |
| Memberships | Admin-created terms, INR reference pricing, manual activation, expiry, configurable pause allowance/minimum/maximum, approval/rejection and expiry extension |
| Admin | Client/coach creation, assignment, business counts, membership overview, pause queue and action audit trail |
| Interface | Responsive desktop/mobile screens, empty states, form validation, keyboard focus, reduced-motion support, home-screen manifest |

## Scope and launch dependencies

Not yet implemented: payment gateway/webhooks/refunds/receipts; coupon/referral/buddy memberships; AI assistance; OTP/email verification/password recovery; password-change/account-disable/deletion/export screens; push/email/SMS reminders; chat attachments/read receipts/realtime delivery; weekly meal/exercise scheduling, grocery lists and food database; advanced exercise media and measurement types; automated backups/monitoring; native mobile packaging and store submissions.

Important first-release behavior:

- There is **one current daily nutrition plan and one current workout programme**, not a weekly calendar. Tracking is selected by date. Prior plan JSON is retained, but the current plan supplies meal totals/labels; this is not an immutable historical nutrition ledger.
- Water has a 2.5 L display fallback when no coach-set target exists. Coaches should set individual targets.
- Check-ins are limited to one submission per client per server calendar day. There is no automatic weekly scheduler yet.
- The server's calendar date governs pause dates and date validation. Client timezone settings are not yet implemented.
- Only weight and waist are numeric measurements in this release. No automatic body-composition estimates.
- Pause approval starts immediately on the approval date. An unexpired membership cannot be replaced or renewed early in this release. Expired memberships can be replaced, with past pause requests archived.
- Plan configurations are created as new records; editing existing commercial plans and advanced renewal rules require the next development phase.
- Prices are display/reference amounts in INR. Manual activation is **not a payment record or receipt**.
- Uploaded photos are resized in the browser; only JPEG/PNG payloads are accepted and served through authenticated endpoints. Production-grade image decoding/validation and storage quotas remain to be added.
- All core data, including photos, resides in SQLite. PostgreSQL/object storage migration is needed before scaling to a large client base.
- First-owner setup must be completed privately before any deployment is made publicly reachable. The local server defaults to loopback. The Python standard-library HTTP server is intended for local evaluation, not a production traffic stack.
- The signup notice documents the first-release data access model; it is not a substitute for the business's reviewed privacy policy and terms.

### Hosting / phone use

To use the real app from a phone, deploy it to an HTTPS host with persistent storage. The localhost address on your computer is not a public phone-accessible link. No live server or public URL was created with this delivery.

Before production: adopt a production application server/reverse proxy, use HTTPS with `--secure-cookie`, complete private owner setup, configure data backups/restore testing, add the missing account-lifecycle features, review privacy/terms, and connect the selected services. These are deployment tasks, not already-completed features.

The manifest enables a standalone home-screen experience on supporting browsers once hosted securely. It does not provide offline account/data access. API responses and private photos are never service-worker cached. Install behavior on actual iOS/Android devices has not been verified.

## Tests

```sh
python -m unittest -v test_app
```

Eight integration test groups exercise owner setup, role escalation prevention, client/coach isolation, profile/log persistence, plan version history, check-in review, messaging, private media access, membership pauses and replay prevention, CSRF origin checks, headers and logout.

The tests create and remove their own temporary SQLite database and bind only to loopback. Tests never touch your application database. Browser screenshots use fictional names, prices, targets and records.

## Files

- `server.py`: HTTP API, validation, authorization, schema version 1 and SQLite persistence.
- `static/app.js`: client/coach/admin screens and API integration.
- `static/styles.css`: responsive visual design.
- `static/index.html`, `icon.svg`, `manifest.webmanifest`, `sw.js`: browser shell and install metadata.
- `test_app.py`: isolated backend integration tests.
- `QA.md`: verification record and remaining checks.
- `API.md`: API map and representative request bodies.

An accompanying standalone HTML preview is demonstration-only. It uses fictional local data and resets on reload. Run the Python app for actual account separation and durable storage.
