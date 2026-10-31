#!/usr/bin/env bash
# Pack the signed SafeThingsMCP.app into a Claude Desktop .mcpb extension.
# Always rebuilds the app first so the package never carries stale code.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$REPO_DIR/build_tools"
APP="$REPO_DIR/dist_signed/SafeThingsMCP.app"
STAGING="$BUILD/mcpb_staging"
OUT_DIR="$REPO_DIR/dist_mcpb"
OUT_FILE="$OUT_DIR/safe-things-mcp.mcpb"
# Pinned so builds are reproducible and a new upstream release can't change what signs/packs.
MCPB_VERSION="2.1.2"

cd "$REPO_DIR"

# Fail before the multi-minute build, not after it.
command -v npx >/dev/null 2>&1 || {
  echo "Node.js is required to pack the extension (npx not found). Install it from https://nodejs.org or with: brew install node"
  exit 1
}

# 1) Always rebuild: a stale app would silently ship old code.
SAFE_THINGS_MCP_CALLED_BY_MCPB=1 "$BUILD/build_signed.sh"

# 2) Stage: manifest at the root, the app under server/ so the manifest's
#    "${__dirname}/server/SafeThingsMCP.app/..." path resolves after install.
echo "==> Staging MCPB bundle"
rm -rf "$STAGING"
mkdir -p "$STAGING/server"
cp "$BUILD/mcpb/manifest.json" "$STAGING/manifest.json"
ditto "$APP" "$STAGING/server/SafeThingsMCP.app"
if [ -n "$(find "$STAGING" -type l)" ]; then
  echo "ERROR: staging contains symlinks; the signature would not survive packing."
  exit 1
fi

# 3) Pack it with the official MCPB CLI.
echo "==> Packing .mcpb with @anthropic-ai/mcpb"
mkdir -p "$OUT_DIR"
rm -f "$OUT_FILE"
npx -y "@anthropic-ai/mcpb@$MCPB_VERSION" pack "$STAGING" "$OUT_FILE"

# 4) The zip round-trip must leave the app's code-signature seal intact.
echo "==> Verifying the packed app signature"
CHECK_DIR="$(mktemp -d)"
trap 'rm -rf "$CHECK_DIR"' EXIT
unzip -q "$OUT_FILE" -d "$CHECK_DIR"
if ! codesign --verify --strict --verbose=2 "$CHECK_DIR/server/SafeThingsMCP.app"; then
  echo "ERROR: packing broke the app signature"
  exit 1
fi
# Start the packed entry point exactly as the manifest names it: proves the path
# matches, exec bits survived, and launcher -> frozen server works (no Things access).
ENTRY="$(plutil -extract server.entry_point raw -o - "$CHECK_DIR/manifest.json")"
if ! "$CHECK_DIR/$ENTRY" --version </dev/null; then
  echo "ERROR: the packed server does not start ($ENTRY)"
  exit 1
fi

cat <<EOM

==> Done. Claude Desktop extension:
    $OUT_FILE

Install: drag the .mcpb into Claude Desktop > Settings > Extensions and paste your
Things auth token (Things > Settings > General > Manage).

First use: ask Claude something like "what's in my Things inbox?". macOS silently
blocks that first read (no popup is ever shown). Open System Settings > Privacy &
Security > Files & Folders > "SafeThingsMCP" and turn on "Data shared by Things
and affiliated apps". No restart needed.

Updates: pull, re-run this script, drag the new file in. The permission is kept
as long as you build on the same Mac.
EOM
