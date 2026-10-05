# Verification record

## Passed

- Python syntax and JavaScript syntax validation.
- Eight HTTP integration test groups in `test_app.py`, using temporary databases.
- API-enforced own-client and assigned-coach access; cross-client photo and messaging access rejected.
- Persisted daily logs/profile/measurements read back through a separate signed-in session.
- Plan versions preserved on publish; invalid duplicate item IDs rejected.
- Check-in submission/review and two-way text messaging through the API.
- Membership pause limits, duplicate pending requests, transactional approval and approval replay rejection.
- Browser owner setup, client meal toggle, water increment, exercise log persistence, coach plan publishing and coach feedback were exercised during the initial browser session.
- Actual desktop and mobile screenshots of the initial UI were captured and visually inspected. A mobile hero illustration/text overlap was identified and corrected in CSS; mobile sign-out was also added.

## Verification limits

The browser automation connection became unreliable during the last verification pass. End-to-end browser execution after the final small UI refinements is not claimed as a complete pass. The backend integration tests remain independently runnable. Updated screenshot generation and a full cross-browser/accessibility pass should be repeated on the deployment host.

No production deployment, payment/AI integration, real-phone installation, email/push delivery, load test, backup restore or native mobile store submission was performed. The supplied screenshots and standalone preview contain fictional QA data.

## Repeat before release

1. Run the included integration suite.
2. Test owner → coach/client creation → assignment → plan publication → client tracking → check-in review on the final HTTPS host.
3. Test phone layouts at 360px and 390px, keyboard-only interaction, upload permissions and sign-out.
4. Verify actual iOS Safari / Android Chrome home-screen behavior and secure cookies.
5. Complete and test the production dependencies listed in `README.md`.
