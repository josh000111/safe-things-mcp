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

# 4) The zip round-trip must leave the app's code-signature seal intact. Every check
#    below runs on throwaway extracted copies, never on staging/ or dist_*.
echo "==> Verifying the packed app signature"
CHECK_DIR="$(mktemp -d)"
TMP_DIRS=("$CHECK_DIR")  # every temp dir lands here so the trap removes all of them
cleanup() {
  local d
  for d in "${TMP_DIRS[@]}"; do
    rm -rf "$d"
  done
}
trap cleanup EXIT

# Fresh extraction of the .mcpb into a new temp dir; sets EXTRACTED (not echoed, so the
# TMP_DIRS update survives: command substitution would run in a subshell).
EXTRACTED=""
extract_fresh() {
  EXTRACTED="$(mktemp -d)"
  TMP_DIRS+=("$EXTRACTED")
  unzip -q "$OUT_FILE" -d "$EXTRACTED"
}

unzip -q "$OUT_FILE" -d "$CHECK_DIR"
PACKED_APP="$CHECK_DIR/server/SafeThingsMCP.app"
PACKED_SERVER="$PACKED_APP/Contents/Resources/server/safe-things-mcp"
if ! codesign --verify --strict --verbose=2 "$PACKED_APP"; then
  echo "ERROR: packing broke the app signature"
  exit 1
fi

# Hardened runtime must be on both the launcher (app) and the inner server binary.
# Output is captured first: `cmd | grep -q` under pipefail can false-negative.
assert_runtime_flag() {
  local label="$1" path="$2" out
  out="$(codesign -dv "$path" 2>&1)"
  if ! grep -Eq 'flags=.*runtime' <<<"$out"; then
    echo "ERROR: $label is not signed with the hardened runtime (no 'runtime' in codesign flags)"
    exit 1
  fi
}
echo "==> Verifying hardened runtime flags"
assert_runtime_flag "the app launcher" "$PACKED_APP"
assert_runtime_flag "the inner server" "$PACKED_SERVER"

# Entitlements must be exactly what we intend: no loader/JIT/debug exceptions anywhere.
# Usage: assert_entitlements <label> <path> <required-key>... -- <forbidden-key>...
assert_entitlements() {
  local label="$1" path="$2" ents key
  shift 2
  ents="$(codesign -d --entitlements - --xml "$path" 2>/dev/null || true)"
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
    key="$1"
    if ! grep -q "$key" <<<"$ents"; then
      echo "ERROR: $label is missing entitlement $key"
      exit 1
    fi
    shift
  done
  shift  # the "--" separator
  for key in "$@"; do
    if grep -q "$key" <<<"$ents"; then
      echo "ERROR: $label carries forbidden entitlement $key"
      exit 1
    fi
  done
}
echo "==> Verifying entitlements"
assert_entitlements "the app launcher" "$PACKED_APP" \
  com.apple.security.automation.apple-events -- \
  com.apple.security.cs.disable-library-validation \
  com.apple.security.cs.allow-dyld-environment-variables \
  com.apple.security.cs.allow-unsigned-executable-memory \
  com.apple.security.get-task-allow
assert_entitlements "the inner server" "$PACKED_SERVER" \
  com.apple.security.cs.disable-library-validation -- \
  com.apple.security.cs.allow-dyld-environment-variables \
  com.apple.security.cs.allow-unsigned-executable-memory \
  com.apple.security.get-task-allow

# Start the packed entry point exactly as the manifest names it: proves the path
# matches, exec bits survived, and launcher -> frozen server works (no Things access).
ENTRY="$(plutil -extract server.entry_point raw -o - "$CHECK_DIR/manifest.json")"
if ! "$CHECK_DIR/$ENTRY" --version </dev/null; then
  echo "ERROR: the packed server does not start ($ENTRY)"
  exit 1
fi
# Hardened runtime + env scrub: an injected-library variable must be ignored. Without
# them dyld tries to load the (missing) library and aborts.
echo "==> Verifying injected libraries are ignored"
if ! DYLD_INSERT_LIBRARIES=/nonexistent/stm-inject-check.dylib "$CHECK_DIR/$ENTRY" --version </dev/null >/dev/null 2>&1; then
  echo "ERROR: DYLD_INSERT_LIBRARIES affected the packed server (hardened runtime missing?)"
  exit 1
fi
# Run the inner server directly (no launcher scrub in front): it must ignore the variable
# on its own, which proves the server binary itself is hardened, not just shielded.
if ! DYLD_INSERT_LIBRARIES=/nonexistent/stm-inject-check.dylib "$PACKED_SERVER" --version </dev/null >/dev/null 2>&1; then
  echo "ERROR: DYLD_INSERT_LIBRARIES affected the inner server binary (hardened runtime missing?)"
  exit 1
fi

# Negative checks: each case breaks the resource seal differently on its own fresh copy,
# and the launcher's self-check must refuse to start (exit 126).
echo "==> Verifying the launcher rejects a modified app"
SEALED_REL="Contents/Resources/server/_internal/base_library.zip"
expect_tamper_rejected() {
  local case_name="$1" mutate="$2" rc=0
  extract_fresh
  local app="$EXTRACTED/server/SafeThingsMCP.app"
  if [ "$mutate" = "add" ]; then
    echo tamper > "$app/Contents/Resources/tamper-check.txt"
  else
    if [ ! -f "$app/$SEALED_REL" ]; then
      echo "ERROR: tamper test needs $SEALED_REL but it is not in the packed app"
      exit 1
    fi
    if [ "$mutate" = "append" ]; then
      chmod u+w "$app/$SEALED_REL"
      printf 'x' >> "$app/$SEALED_REL"
    else
      rm -f "$app/$SEALED_REL"
    fi
  fi
  "$EXTRACTED/$ENTRY" --version </dev/null >/dev/null 2>&1 || rc=$?
  rm -rf "$EXTRACTED"
  if [ "$rc" -ne 126 ]; then
    echo "ERROR: launcher did not exit 126 for tamper case '$case_name' (got $rc)"
    exit 1
  fi
}
expect_tamper_rejected "added file" add
expect_tamper_rejected "modified sealed file" append
expect_tamper_rejected "deleted sealed file" delete

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
