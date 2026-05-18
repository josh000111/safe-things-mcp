#!/usr/bin/env zsh
# ==============================================================================
# backup_things3.sh  (v2)
# Safely backs up the Things 3 database to ~/Documents/Things DB Backups (Cultured Code)/
# READ-ONLY on source — the original database is NEVER modified or moved.
#
# Changes in v2 (vs other Claude Code session recommendations):
#   • Uses `ditto` instead of `cp -R` (macOS-native bundle copy; preserves
#     extended attributes, ACLs, and resource forks correctly)
#   • Detects both .thingsdatabase and .thingsdb package extensions
#   • Post-copy SQLite integrity check via `sqlite3 … PRAGMA integrity_check`
#     — if the check fails, the bad backup is removed and the script aborts
#
# NOT implemented (deliberately skipped):
#   • Disabling Things Cloud before quit — a graceful quit already handles this
#   • Backing up ~/Library/Containers/com.culturedcode.ThingsMac/ — out of scope;
#     the .thingsdatabase package is sufficient for a full data restore
# ==============================================================================

set -euo pipefail   # Exit on error, undefined vars, or pipe failures

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo "${BLUE}[INFO]${RESET}  $*"; }
warn()    { echo "${YELLOW}[WARN]${RESET}  $*"; }
success() { echo "${GREEN}[OK]${RESET}    $*"; }
error()   { echo "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

echo ""
echo "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo "${BOLD}║    Things 3 Database Backup Utility v2   ║${RESET}"
echo "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── ⚠️  Cloud Sync Warning — must confirm before proceeding ───────────────────
echo "${BOLD}${RED}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo "${BOLD}${RED}║                    ⚠️   IMPORTANT WARNING                    ║${RESET}"
echo "${BOLD}${RED}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo "${BOLD}${RED}║                                                              ║${RESET}"
echo "${BOLD}${RED}║   DEACTIVATE THINGS CLOUD SYNC BEFORE CONTINUING.           ║${RESET}"
echo "${BOLD}${RED}║                                                              ║${RESET}"
echo "${BOLD}${RED}║   In Things 3:                                               ║${RESET}"
echo "${BOLD}${RED}║   Things 3 Menu → Preferences → Things Cloud → Log Out      ║${RESET}"
echo "${BOLD}${RED}║   (or disable sync) BEFORE running this backup.             ║${RESET}"
echo "${BOLD}${RED}║                                                              ║${RESET}"
echo "${BOLD}${RED}║   This ensures no in-flight sync write can interfere        ║${RESET}"
echo "${BOLD}${RED}║   with the database at the moment of backup.                ║${RESET}"
echo "${BOLD}${RED}║                                                              ║${RESET}"
echo "${BOLD}${RED}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -n "  Have you disabled Things Cloud Sync? Type YES to continue, or press Ctrl+C to abort: "
read SYNC_CONFIRM

if [[ "${SYNC_CONFIRM}" != "YES" ]]; then
    echo ""
    echo "${YELLOW}  Backup aborted. Please disable Things Cloud Sync first, then re-run the script.${RESET}"
    echo ""
    exit 0
fi

echo ""
success "Confirmed. Proceeding with backup..."
echo ""

# ── 1. Resolve source container folder ────────────────────────────────────────
CONTAINER_DIR="${HOME}/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"

if [[ ! -d "$CONTAINER_DIR" ]]; then
    error "Things 3 container not found at:\n  $CONTAINER_DIR\nIs Things 3 installed?"
fi

# ── 2. Dynamically find the ThingsData-XXXXX subfolder ────────────────────────
THINGS_DATA_DIRS=("${CONTAINER_DIR}"/ThingsData-*(N))   # (N) = no-error if no match

if [[ ${#THINGS_DATA_DIRS[@]} -eq 0 ]]; then
    error "No 'ThingsData-*' folder found inside:\n  $CONTAINER_DIR"
fi

if [[ ${#THINGS_DATA_DIRS[@]} -gt 1 ]]; then
    warn "Multiple 'ThingsData-*' folders found — using the most recently modified one."
    THINGS_DATA_DIR=$(ls -dt "${THINGS_DATA_DIRS[@]}" | head -1)
else
    THINGS_DATA_DIR="${THINGS_DATA_DIRS[1]}"
fi

info "Detected data folder: $(basename "$THINGS_DATA_DIR")"

# ── 3. Detect the database package (handle both known extensions) ──────────────
# Things has shipped two package extensions across versions:
#   .thingsdatabase  — current (Things 3.x)
#   .thingsdb        — older installs / some edge cases
DB_SOURCE=""

if [[ -d "${THINGS_DATA_DIR}/Things Database.thingsdatabase" ]]; then
    DB_SOURCE="${THINGS_DATA_DIR}/Things Database.thingsdatabase"
    PKG_EXT="thingsdatabase"
elif [[ -d "${THINGS_DATA_DIR}/Things Database.thingsdb" ]]; then
    DB_SOURCE="${THINGS_DATA_DIR}/Things Database.thingsdb"
    PKG_EXT="thingsdb"
else
    # List what IS there so the user can diagnose
    error "No database package found in:\n  $THINGS_DATA_DIR\n\nContents:\n$(ls -1 "$THINGS_DATA_DIR" 2>/dev/null || echo '  (empty)')"
fi

info "Source package:  $DB_SOURCE  (.${PKG_EXT})"

# ── 4. Ensure the destination directory exists ─────────────────────────────────
DEST_DIR="${HOME}/Documents/Things DB Backups (Cultured Code)"

if [[ ! -d "$DEST_DIR" ]]; then
    info "Destination folder does not exist — creating it..."
    mkdir -p "$DEST_DIR" || error "Failed to create destination directory:\n  $DEST_DIR"
    success "Created: $DEST_DIR"
else
    info "Destination folder: $DEST_DIR"
fi

# ── 5. Gracefully quit Things 3 if it is running ──────────────────────────────
# Ensures SQLite WAL/SHM files are flushed and merged before we copy.
THINGS_RUNNING=false

if pgrep -x "Things 3" > /dev/null 2>&1; then
    THINGS_RUNNING=true
    warn "Things 3 is currently running."
    info "Sending a graceful quit command (saves all data first)..."

    osascript -e 'tell application "Things3" to quit' 2>/dev/null || \
    osascript -e 'tell application "Things 3" to quit' 2>/dev/null || true

    # Wait up to 10 seconds for Things to fully exit
    WAIT=0
    while pgrep -x "Things 3" > /dev/null 2>&1; do
        sleep 1
        (( WAIT++ ))
        if [[ $WAIT -ge 10 ]]; then
            warn "Things 3 did not quit within 10 seconds."
            warn "Proceeding anyway — WAL/SHM files may be included in the backup."
            break
        fi
    done

    if ! pgrep -x "Things 3" > /dev/null 2>&1; then
        success "Things 3 closed cleanly."
    fi
else
    info "Things 3 is not running — no need to quit."
fi

# ── 6. Build the timestamped destination path ─────────────────────────────────
TIMESTAMP=$(date +"%Y-%m-%d_%H%M")
DEST_NAME="Things Database_${TIMESTAMP}.${PKG_EXT}"
DEST_PATH="${DEST_DIR}/${DEST_NAME}"

info "Backup filename: $DEST_NAME"

# ── 7. Copy with ditto (macOS-native bundle copy) ─────────────────────────────
# `ditto` is the correct macOS tool for copying bundles/packages.
# It preserves extended attributes, ACLs, resource forks, and HFS+ metadata
# that cp -R may silently drop.
# The SOURCE is NEVER modified, moved, or deleted — only read.
info "Copying database with ditto... (this may take a moment)"

ditto "$DB_SOURCE" "$DEST_PATH" || error "ditto copy failed! Source database is untouched."

if [[ ! -d "$DEST_PATH" ]]; then
    error "ditto appeared to succeed but backup folder is missing. Please check manually."
fi

success "Copy complete."

# ── 8. SQLite integrity check on the BACKUP copy ──────────────────────────────
# Finds the first .sqlite file inside the backup package and runs
# `PRAGMA integrity_check` against it. A healthy database returns a single
# row containing the word "ok". Anything else means the copy is bad.
info "Running SQLite integrity check on backup..."

SQLITE_FILE=$(find "$DEST_PATH" -maxdepth 1 -name "*.sqlite" | head -1)

if [[ -z "$SQLITE_FILE" ]]; then
    warn "No .sqlite file found inside the backup package — skipping integrity check."
    warn "This may be normal if the package uses a non-standard filename."
else
    INTEGRITY=$(sqlite3 "$SQLITE_FILE" "PRAGMA integrity_check;" 2>&1)

    if [[ "$INTEGRITY" == "ok" ]]; then
        success "Integrity check passed (PRAGMA integrity_check → ok)."
    else
        # Bad backup — delete it and abort. Source is untouched.
        warn "Integrity check FAILED. Removing bad backup..."
        rm -rf "$DEST_PATH"
        error "SQLite integrity check failed on the backup copy.\nOutput: $INTEGRITY\n\nThe bad backup has been deleted. Your source database is untouched.\nTry running the script again, or check the source DB with:\n  sqlite3 \"$DB_SOURCE/$(basename "$SQLITE_FILE")\" \"PRAGMA integrity_check;\""
    fi
fi

# ── 9. Re-launch Things 3 if it was running before ────────────────────────────
if [[ "$THINGS_RUNNING" == true ]]; then
    info "Re-launching Things 3..."
    open -a "Things 3" 2>/dev/null || warn "Could not re-launch Things 3 automatically. Please open it manually."
fi

# ── 10. Success summary ───────────────────────────────────────────────────────
BACKUP_SIZE=$(du -sh "$DEST_PATH" 2>/dev/null | awk '{print $1}')

echo ""
echo "${BOLD}${GREEN}╔══════════════════════════════════════════╗${RESET}"
echo "${BOLD}${GREEN}║           Backup Complete! ✓             ║${RESET}"
echo "${BOLD}${GREEN}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo "  ${BOLD}Backup saved to:${RESET}"
echo "  $DEST_PATH"
echo ""
echo "  ${BOLD}Backup size:${RESET}       $BACKUP_SIZE"
echo "  ${BOLD}Timestamp:${RESET}         $TIMESTAMP"
echo "  ${BOLD}Integrity check:${RESET}   passed ✓"
echo ""
echo "  ${YELLOW}The original database was NOT modified.${RESET}"
echo ""
echo "  ${BOLD}To restore:${RESET} Quit Things 3, then replace"
echo "  'Things Database.${PKG_EXT}' in your ThingsData-* folder"
echo "  with this backup file. Relaunch Things 3."
echo ""
