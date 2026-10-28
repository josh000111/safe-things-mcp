#!/usr/bin/env bash
# Pack the signed binary build into a Claude Desktop .mcpb extension -- a
# one-click install alternative to the manual JSON-config path. Wraps the
# EXISTING signed build (build_signed.sh); this script only stages and packs.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$REPO_DIR/build_tools"
SIGNED_BIN="$REPO_DIR/dist_signed/safe-things-mcp/safe-things-mcp"
STAGING="$BUILD/mcpb_staging"
OUT_DIR="$REPO_DIR/dist_mcpb"
OUT_FILE="$OUT_DIR/safe-things-mcp.mcpb"

cd "$REPO_DIR"

# 1) Make sure the signed onedir build exists -- rebuild it if missing.
#    build_signed.sh is idempotent/safe to re-run, so just invoke it.
if [ ! -x "$SIGNED_BIN" ]; then
  echo "==> Signed binary not found, running build_signed.sh first"
  "$BUILD/build_signed.sh"
fi

# 2) Stage a clean bundle dir: manifest at the root, onedir output at server/
#    so "${__dirname}/server/safe-things-mcp" resolves inside the packed .mcpb.
echo "==> Staging MCPB bundle"
rm -rf "$STAGING"
mkdir -p "$STAGING/server"
cp "$BUILD/mcpb/manifest.json" "$STAGING/manifest.json"
cp -R "$REPO_DIR/dist_signed/safe-things-mcp/." "$STAGING/server/"

# 3) Pack it with the official MCPB CLI.
echo "==> Packing .mcpb with @anthropic-ai/mcpb"
mkdir -p "$OUT_DIR"
rm -f "$OUT_FILE"
npx -y @anthropic-ai/mcpb pack "$STAGING" "$OUT_FILE"

cat <<EOF

==> Done. Claude Desktop extension:
    $OUT_FILE

Install it: Claude Desktop -> Settings -> Extensions -> drag $OUT_FILE in
(or click "Install Extension" and pick the file). On the install form, paste
your Things auth token from Things -> Settings -> General -> Manage.
EOF
