#!/usr/bin/env bash
# Build SafeThingsMCP.app: the PyInstaller server wrapped in a signed app bundle.
#
# WHY: Things 3's data lives in an App Group container protected by macOS TCC
# ("Data shared by Things and affiliated apps"). macOS never shows a popup for it:
# the first read is silently denied and an entry appears in System Settings >
# Privacy & Security > Files & Folders. For a bare binary that entry is keyed by
# file path and the toggle will not stay on; for a signed .app bundle it is keyed
# by bundle ID, so the toggle sticks. The grant is tied to BUNDLE_ID plus this
# Mac's self-signed certificate: change either and users must re-enable it once.
# User step: enable "Data shared by Things and affiliated apps" for "SafeThingsMCP".
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$REPO_DIR/build_tools"
CERT="$BUILD/selfsign_cert.pem"
KEY="$BUILD/selfsign_key.pem"
P12="$BUILD/selfsign.p12"
APP_NAME="SafeThingsMCP"  # matches the .app file name, which is what System Settings shows
APP_DIR_NAME="SafeThingsMCP.app"
# Changing BUNDLE_ID or the certificate forces every user to re-enable the toggle.
BUNDLE_ID="io.github.josh000111.safe-things-mcp"
IDENTITY="safe-things-mcp-selfsigned"
P12_PASS="safe-things-mcp-build"
APP="$REPO_DIR/dist_signed/$APP_DIR_NAME"

cd "$REPO_DIR"

# The native launcher is compiled with clang, which ships with the Command Line Tools.
xcode-select -p >/dev/null 2>&1 || { echo "Install Xcode Command Line Tools first: xcode-select --install"; exit 1; }

# 1) Ensure a STABLE self-signed code-signing certificate exists + is importable.
#    Reusing the same cert keeps the signing identity constant across rebuilds,
#    which is what lets macOS keep remembering your permission across upgrades.
if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
  echo "==> Creating stable self-signed code-signing certificate"
  openssl req -newkey rsa:2048 -nodes -keyout "$KEY" -x509 -days 3650 \
    -out "$CERT" -subj "/CN=$IDENTITY" \
    -addext "extendedKeyUsage=critical,codeSigning" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature"
fi
# Look for a usable signing identity (cert + private key), not just a cert. Captured
# into a variable first: piping into `grep -q` under pipefail can false-negative.
EXISTING_IDS="$(security find-identity -p codesigning 2>/dev/null || true)"
if [[ "$EXISTING_IDS" != *"\"$IDENTITY\""* ]]; then
  echo "==> Importing certificate into login keychain"
  # Keychain only reads the legacy PKCS12 format (newer formats fail with "MAC
  # verification failed"). OpenSSL 3+ needs -legacy to write it; macOS's built-in
  # LibreSSL writes it by default and rejects the flag, so detect support.
  LEGACY_FLAG=""
  case "$(openssl pkcs12 -help 2>&1 || true)" in *-legacy*) LEGACY_FLAG="-legacy" ;; esac
  # shellcheck disable=SC2086  # intentionally unquoted: empty means no flag
  openssl pkcs12 -export $LEGACY_FLAG -inkey "$KEY" -in "$CERT" -out "$P12" \
    -passout "pass:$P12_PASS" -name "$IDENTITY"
  security import "$P12" -k "$HOME/Library/Keychains/login.keychain-db" \
    -P "$P12_PASS" -T /usr/bin/codesign -A
fi

# 2) Freeze the server into one standalone bundle.
echo "==> Building standalone binary with PyInstaller"
rm -rf "$REPO_DIR/dist_signed" "$BUILD/pyi_work" "$BUILD/safe-things-mcp.spec"
uv run --with pyinstaller pyinstaller \
  --noconfirm --onedir --name safe-things-mcp \
  --collect-submodules mcp.server --collect-all things --collect-submodules safe_things_mcp \
  --exclude-module typer --exclude-module mcp.cli \
  --distpath "$REPO_DIR/dist_signed" --workpath "$BUILD/pyi_work" --specpath "$BUILD" \
  "$BUILD/freeze_entry.py"

# 3) Assemble the app bundle around the onedir build.
echo "==> Assembling $APP_DIR_NAME"
VERSION="$(uv run python -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
ditto "$REPO_DIR/dist_signed/safe-things-mcp" "$APP/Contents/Resources/server"
clang -O2 -Wall -Wextra -Werror -mmacosx-version-min=12.0 \
  -framework Security -framework CoreFoundation \
  -o "$APP/Contents/MacOS/safe-things-mcp" "$BUILD/app_launcher.c"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleExecutable</key><string>safe-things-mcp</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>SafeThingsMCP controls Things 3 for delete-to-Trash, reordering and AI tagging, only when you enable AppleScript operations.</string>
</dict>
</plist>
PLIST
plutil -lint "$APP/Contents/Info.plist"

# A symlink would not survive the .mcpb zip round-trip and would break the seal.
if [ -n "$(find "$APP" -type l)" ]; then
  echo "ERROR: $APP contains symlinks; the signature would not survive packing."
  exit 1
fi

# 4) Sign inner code first, then the bundle (no --deep).
#    Hardened runtime (--options runtime) makes dyld ignore DYLD_* variables, so nobody
#    can inject a dylib into a process that holds the Things permission.
echo "==> Signing the app"
ENTITLEMENTS="$BUILD/server.entitlements"
APP_ENTITLEMENTS="$BUILD/app.entitlements"
plutil -lint "$ENTITLEMENTS"
plutil -lint "$APP_ENTITLEMENTS"
# Only the server needs disable-library-validation: PyInstaller's bundled libs are ad-hoc signed.
codesign --force --options runtime --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" \
  "$APP/Contents/Resources/server/safe-things-mcp"
# The launcher is the TCC responsible process, so it needs the Apple Events entitlement
# for the server's osascript calls to work under hardened runtime.
codesign --force --options runtime --entitlements "$APP_ENTITLEMENTS" --sign "$IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"
codesign -dv --verbose=2 "$APP" 2>&1 | grep -E "Identifier|Authority|flags=" || true

echo
echo "==> Done. Signed app:"
echo "    $APP"
# build_mcpb.sh calls this script; only point at it when run on its own.
if [ -z "${SAFE_THINGS_MCP_CALLED_BY_MCPB:-}" ]; then
  echo
  echo "Next: ./build_tools/build_mcpb.sh   (packs it for Claude Desktop)"
fi
