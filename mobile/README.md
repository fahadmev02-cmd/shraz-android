# Android source

Start with the [repository README](../README.md).

The current GitHub Actions workflow is **debug-APK-only** and needs no signing secrets. It prepares assets from the sibling `static/` folder, runs the existing tests, builds the APK and verifies the actual binary before artifact upload.

Local/cloud build commands (on a host with JDK 21 and the Android SDK):

```sh
npm ci
npm test
npm run android:sync
npm run check
npm run build:apk
python scripts/verify-debug-apk.py
```

Run these from `mobile/`. Generated outputs are ignored by Git. This container is used only for Node/source checks, not Android SDK/JDK installation or native compilation.

The previous release-signing build script is retained for later work, but the current workflow never invokes it and no release-signing inputs have been configured.
