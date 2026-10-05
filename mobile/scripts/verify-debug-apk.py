"""Verify a real Gradle-produced APK before creating an artifact report.

Requires the Android SDK/JDK on a build runner. Never manufactures an APK.
"""
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path


def main():
    mobile = Path(__file__).resolve().parents[1]
    apk = mobile / 'android/app/build/outputs/apk/debug/app-debug.apk'
    if not apk.is_file() or apk.stat().st_size < 100_000:
        raise SystemExit('Verification failed: no plausible Gradle-produced debug APK exists.')
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        raise SystemExit('Verification requires the Android SDK on the build runner.')
    tools = Path(sdk) / 'build-tools/36.0.0'
    for tool in ['apksigner', 'aapt2']:
        if not (tools / tool).is_file():
            raise SystemExit(f'Verification tool is missing: {tool}')
    subprocess.run([str(tools / 'apksigner'), 'verify', str(apk)], check=True, capture_output=True)
    badging = subprocess.run([str(tools / 'aapt2'), 'dump', 'badging', str(apk)], check=True, capture_output=True, text=True).stdout
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'", badging, re.M)
    target_sdk = re.search(r"^targetSdkVersion:'(\d+)'", badging, re.M)
    min_sdk = re.search(r"^sdkVersion:'(\d+)'", badging, re.M)
    settings = json.loads((mobile / 'mobile.settings.json').read_text())
    info = json.loads((mobile / 'build-info.json').read_text())
    if not package or package.groups() != (settings['appId'], str(settings['versionCode']), settings['versionName']):
        raise SystemExit('APK identity/version differs from mobile.settings.json.')
    if not target_sdk or target_sdk.group(1) != '36' or not min_sdk or min_sdk.group(1) != '24':
        raise SystemExit('APK SDK metadata does not match the expected API 24 / 36 configuration.')
    if not re.search(r"^launchable-activity:", badging, re.M):
        raise SystemExit('APK has no launchable activity.')
    if not re.search(r'^application-debuggable', badging, re.M):
        raise SystemExit('Expected a debug APK; refusing to mislabel another artifact.')
    with zipfile.ZipFile(apk) as bundle:
        if bundle.testzip() is not None:
            raise SystemExit('APK ZIP integrity verification failed.')
        required = {'AndroidManifest.xml', 'classes.dex', 'assets/capacitor.config.json'}
        if not required.issubset(bundle.namelist()):
            raise SystemExit('APK is missing required Android/Capacitor components.')
        config = json.loads(bundle.read('assets/capacitor.config.json'))
        if config['appId'] != settings['appId'] or config.get('server', {}).get('url'):
            raise SystemExit('Unexpected packaged Capacitor identity or remote-URL configuration.')
        for name in ['index.html', 'app.js', 'styles.css', 'native.js', 'icon.svg']:
            packaged = bundle.read('assets/public/' + name)
            if packaged != (mobile / 'www' / name).read_bytes():
                raise SystemExit(f'Packaged asset differs from the prepared build: {name}')
    report = {
        'verified': True,
        'artifact': 'app-debug.apk',
        'artifact_type': 'debug APK',
        'application_id': package.group(1),
        'version_code': int(package.group(2)),
        'version_name': package.group(3),
        'min_sdk': 24,
        'target_sdk': 36,
        'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
        'bytes': apk.stat().st_size,
        'backend_configured': bool(info['backendConfigured']),
        'signature_verified': True,
        'bundled_assets_verified': True,
        'device_installation_tested': False,
        'source_commit': os.environ.get('GITHUB_SHA'),
    }
    destination = mobile / 'artifacts/debug-apk-verification.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('Verified real debug APK: signature, launch activity, application ID, version, SDK metadata, ZIP integrity and bundled UI.')


if __name__ == '__main__':
    main()
