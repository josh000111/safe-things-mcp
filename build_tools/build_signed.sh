#!/usr/bin/env bash
# Build a signed, standalone safe-things-mcp binary with a STABLE code identity.
#
# WHY: macOS only "remembers" the "would like to access data from other apps"
# permission for a program that has a stable, signed identity. The plain Python
# interpreter is ad-hoc signed (effectively anonymous), so macOS re-prompts every
# launch. Freezing the server into one binary and signing it with a reused
# certificate gives it a stable identity macOS can remember.
#
# IMPORTANT: this only stops the recurring prompt on MCP clients that launch the
# server DIRECTLY (Cursor, VS Code, Codex, Claude Code CLI). Claude Desktop
# launches add-ons through a `disclaimer` middleman that prevents macOS from
# remembering the grant for ANY add-on regardless of signing — see the README
# "macOS Permission Prompts" section (upstream bug: anthropics/claude-code#36832).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$REPO_DIR/build_tools"
CERT="$BUILD/selfsign_cert.pem"
KEY="$BUILD/selfsign_key.pem"
P12="$BUILD/selfsign.p12"
IDENTITY="safe-things-mcp-selfsigned"
P12_PASS="safe-things-mcp-build"

cd "$REPO_DIR"

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
if ! security find-certificate -c "$IDENTITY" >/dev/null 2>&1; then
  echo "==> Importing certificate into login keychain"
  # -legacy: modern OpenSSL (3.x+) defaults to a PKCS12 MAC/cipher that macOS
  # Keychain's older parser rejects with "MAC verification failed" even with
  # the correct password. -legacy forces the RC2/SHA1 format Keychain expects.
  openssl pkcs12 -export -legacy -inkey "$KEY" -in "$CERT" -out "$P12" \
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

# 3) Sign with the stable identity.
echo "==> Signing the binary"
codesign --force --sign "$IDENTITY" "$REPO_DIR/dist_signed/safe-things-mcp/safe-things-mcp"
codesign -dv --verbose=2 "$REPO_DIR/dist_signed/safe-things-mcp/safe-things-mcp" 2>&1 \
  | grep -E "Authority|Signature|Identifier" || true

BIN="$REPO_DIR/dist_signed/safe-things-mcp/safe-things-mcp"
cat <<EOF

==> Done. Signed program:
    $BIN

Paste this into your client config (Claude Desktop:
~/Library/Application Support/Claude/claude_desktop_config.json), replacing
PASTE-YOUR-THINGS-TOKEN with the token from Things -> Settings -> General -> Manage:

{
  "mcpServers": {
    "safe-things-mcp": {
      "command": "$BIN",
      "env": {
        "THINGS_AUTH_TOKEN": "PASTE-YOUR-THINGS-TOKEN",
        "SAFE_THINGS_MCP_ALLOW_APPLESCRIPT": "1"
      }
    }
  }
}

Then fully quit and reopen the client. You'll get ONE "safe-things-mcp would like to
access data from other apps" prompt -- click Allow.

- Direct-launch clients (Cursor, VS Code, Codex): the approval should be
  remembered, so you won't be asked again. If it DOES recur, trust the
  certificate once:
      sudo security add-trusted-cert -d -r trustRoot -p codeSign \\
          -k /Library/Keychains/System.keychain "$CERT"
- Claude Desktop: the prompt recurs every launch regardless of signing
  (upstream bug anthropics/claude-code#36832) -- but it will at least say
  "safe-things-mcp" so you know what you're approving.
EOF
