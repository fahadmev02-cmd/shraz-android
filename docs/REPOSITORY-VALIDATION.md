# Repository preparation validation

## Completed locally

- Created a separate source worktree at `/workspace/projects/default/shraz-android-github` and initialized Git on `main`.
- Copied the existing source and Android project; omitted dependencies, generated assets, databases, build artifacts and credentials from repository candidates.
- Compared `server.py`, `test_app.py` and all six original `static/` files byte-for-byte against the existing Shraz project: unchanged.
- Installed only the pinned **Node dependencies** in the new worktree with `npm ci` to check fresh-checkout reproducibility.
- Ran all eight mobile adapter/settings tests: passed.
- Ran all eight original backend integration test groups: passed.
- Regenerated `www`, native assets and the Capacitor compatibility module using `npm run android:sync`: succeeded.
- Ran `npm run check`: source hashes, synchronized assets and Android configuration passed.
- Parsed the debug-only workflow YAML and checked that its only trigger is manual dispatch and that it references no user-supplied secrets.
- Parsed every workflow shell block with `bash -n`.
- Parsed the new APK verifier as Python and ran its missing-output case: it correctly failed, producing neither an APK nor a success report.
- Confirmed Git ignores dependency trees, generated Android assets, `.env`, SQLite data and keystores, while including the Gradle wrapper JAR.
- Corrected the generated device-test template's default application ID to match Shraz; this instrumented test has not been run on a device.

These checks verify source preparation and fail-closed behavior. They do **not** substitute for native compilation or device installation.

## Not performed

- No Android SDK, JDK, Gradle distribution or emulator installation in this container.
- No native Android compilation.
- No initial Git commit, remote configuration or push.
- No GitHub repository creation or workflow execution.
- No release-signing credential configuration.
- No APK/AAB artifact generation or real-device test.

## First external build must establish

The manually triggered workflow must successfully compile the native source, verify the actual APK with Android tools, match its metadata and bundled assets against the prepared project, and upload the resulting APK plus its verification report. The uploaded report must contain the actual binary SHA-256, not a source-archive hash.

A blank backend address only permits a configuration-only debug shell. Native account/session/photo/navigation tests require a real backend and Android device after the build succeeds.
