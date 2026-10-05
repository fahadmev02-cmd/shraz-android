# Shraz — GitHub-ready Android source

**Current goal: build the first real debug APK on a GitHub-hosted Ubuntu runner.**

This repository packages the existing Shraz HTML/CSS/JavaScript with Capacitor 8.5.2. The Python/SQLite backend and original browser UI are included intact. Neither an APK nor a signed AAB has been produced during repository preparation.

## What to push

Push the **contents of this entire repository root**, not just `mobile/`, `mobile/android/`, the old ZIP, or the interactive preview.

Prepared local worktree:

```text
/workspace/projects/default/shraz-android-github
```

Expected GitHub repository layout:

```text
<repository root>/
├── .github/workflows/android-debug-apk.yml
├── .gitignore
├── .gitattributes
├── README.md
├── server.py
├── test_app.py
├── API.md
├── QA.md
├── docs/WEB-APP.md
├── static/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── icon.svg
│   ├── manifest.webmanifest
│   └── sw.js
└── mobile/
    ├── package.json
    ├── package-lock.json
    ├── capacitor.config.json
    ├── mobile.settings.json
    ├── src/
    ├── scripts/
    ├── tests/
    └── android/
        ├── gradlew
        ├── gradlew.bat
        ├── gradle/wrapper/gradle-wrapper.jar
        ├── gradle/wrapper/gradle-wrapper.properties
        ├── settings.gradle
        ├── build.gradle
        ├── variables.gradle
        ├── gradle.properties
        ├── capacitor.settings.gradle
        └── app/
            ├── build.gradle
            ├── capacitor.build.gradle
            ├── proguard-rules.pro
            └── src/                 Java Activity, manifest and Android resources
```

### Required source inputs

- `.github/workflows/android-debug-apk.yml`: must be at the GitHub repository root's `.github/workflows/` path.
- `static/`: the real existing UI, which the packaging script reads from `../static/`.
- `server.py` and `test_app.py`: required by the existing backend regression-test step; the backend is not deployed or rebuilt by this workflow.
- All committed `mobile/` files: npm manifests/lockfile, Capacitor settings, native adapter, preparation/build/verification scripts, tests, and Android source/resources/wrapper.
- Documentation is included to explain use and current limitations.

Do not upload `node_modules`, generated `www`, copied Android assets, Gradle caches, build outputs, SQLite databases, `.env` files, keystores, screenshots or source ZIPs. The ignore rules cover these. **Do include `gradle-wrapper.jar`**—it is source build infrastructure, not an APK.

Capacitor's generated Cordova compatibility directory and copied web assets are intentionally absent from Git. `npm run android:sync` recreates them on a fresh runner before Gradle runs.

## First GitHub build — debug APK only

The repository has been initialized locally on branch `main`, with the source staged for its first commit. An initial commit and remote are still needed before pushing. No GitHub repository was created and no workflow was dispatched during preparation.

After reviewing the source and choosing an empty GitHub repository (without an auto-created README, license or Git history), the usual commands are:

```sh
git add .
git commit -m "Prepare Shraz Android debug build"
git remote add origin <YOUR-GITHUB-REPOSITORY-URL>
git push -u origin main
```

Run them from the repository root. The destination placeholder is not an actual configured remote. A Git identity must already be configured for the commit. No Git configuration was changed during this preparation.

If using the supplied source ZIP on another computer, extract it, enter `shraz-android-github/`, and first run `git init -b main` because the ZIP does not include local `.git` metadata. Ensure hidden `.github/`, `.gitignore`, and `.gitattributes` files are included when transferring the source.

On GitHub:

1. Ensure Actions is enabled and `main` is the repository's default branch.
2. Open **Actions → Build Shraz Debug APK → Run workflow**.
3. Leave `backend_url` blank for the first configuration-only APK, or enter the actual HTTPS backend origin if already available.
4. Wait for the workflow to succeed.
5. Download the **`shraz-debug-apk-<run number>`** artifact.
6. Extract **`app-debug.apk`** from GitHub's artifact ZIP and install that APK on an Android test phone.

Once authorized and connected to the repository, the equivalent GitHub CLI command is:

```sh
gh workflow run android-debug-apk.yml --repo OWNER/REPOSITORY --ref main
```

For a configured backend, add `-f backend_url=https://YOUR-ACTUAL-BACKEND-ORIGIN`. This is an illustrative command, not one executed during preparation.

## Workflow steps and artifact verification

The workflow is manual-only (`workflow_dispatch`) and runs on `ubuntu-24.04`:

1. Set up Node 24, Python 3.11, Temurin JDK 21 and Android SDK on the **GitHub runner**.
2. Install `platform-tools`, `platforms;android-36`, and `build-tools;36.0.0` there.
3. Run `npm ci`, mobile tests, asset preparation/Capacitor sync, and consistency checks.
4. Run the existing Python backend tests using temporary test databases.
5. Run `npm run build:apk`, which invokes Gradle `:app:assembleDebug` through the committed Gradle 8.14.3 wrapper.
6. Verify the APK's signature, manifest metadata, launchable Activity, debug flag, ZIP integrity, and bundled UI files.
7. Only after verification, upload the real APK and a JSON verification report with its SHA-256.

The output APK path is:

```text
mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Verification metadata is created at:

```text
mobile/artifacts/debug-apk-verification.json
```

No prebuilt or dummy APK is committed. Missing compilation output or failed verification stops the workflow; the artifact upload step requires actual files and only runs after successful prior steps.

## Secrets and variables

### For this debug build

**No user-supplied GitHub secrets are required.** Android generates a debug signing key on the runner automatically. The workflow uses GitHub's automatic workflow credentials for checkout/artifact storage with `contents: read` permission.

Optional public configuration, in precedence order:

1. Manual workflow input: `backend_url`.
2. GitHub repository **variable**: `SHRAZ_BACKEND_URL`.
3. Committed `mobile/mobile.settings.json` field: `backendUrl`.

All are currently unset/blank. Use an HTTPS origin only, without `/api`, paths, credentials or query strings. Do not put an API key or password in the URL.

`JAVA_HOME` and the Android SDK path are provided by the runner setup steps; they are not secrets you need to supply.

**A blank backend still permits APK compilation, but the installed app will show the backend-configuration/reconnect message. Sign-in and coaching features require the existing backend to be reachable.** The UI is bundled; the Python backend is not embedded in the APK.

### Later, for a signed Play Store AAB

The current workflow contains no release build branch and reads no Play Store signing secrets. A separate release workflow can later use these planned private inputs:

- `SHRAZ_KEYSTORE_BASE64`: publisher-controlled upload keystore, encoded for transport.
- `SHRAZ_KEYSTORE_PASSWORD`.
- `SHRAZ_KEY_ALIAS`.
- `SHRAZ_KEY_PASSWORD`.

That workflow would create an ephemeral keystore path for `SHRAZ_KEYSTORE_PATH` and supply `BUNDLETOOL_JAR` for bundle validation. Neither is a signing secret value by itself. Manual Play Console AAB upload does not require a Play service-account JSON key in this repository. No release credentials have been created, requested or configured now.

## Installation notes

Current application ID: `com.shraz.flexibledieting`; version `0.1.0`, code `1`; minimum API 24, target API 36.

The first successful build still needs real-device tests for installation, session cookies, file picking, private photos and navigation. Fresh GitHub runners can generate different debug signing certificates; replacing a previously installed debug APK may require uninstalling it first, which removes that installation's local app data.

The debug APK is not a Google Play release AAB and does not imply Play Store readiness. The existing web release's unfinished features are documented in `docs/WEB-APP.md`.

## Current preparation status

- Git source worktree initialized and source staged; no commit or remote configured.
- Debug-only workflow prepared; no cloud run dispatched.
- No Android SDK/JDK installed in this container.
- APK generated: **no**.
- AAB generated: **no**.

See `docs/REPOSITORY-VALIDATION.md` for the local checks performed during this handoff.
