/*
 * Main executable of SafeThingsMCP.app.
 *
 * WHY: macOS grants access to Things' data (an App Group container) to the signed
 * app BUNDLE, keyed by bundle ID. Claude Desktop launches this executable as the
 * MCP server, so it is the TCC "responsible process"; the real server must run as
 * its CHILD so the app stays responsible and the grant applies.
 *
 * It must spawn, never exec: exec would replace the app's code identity with the
 * bare server binary, which macOS keys by file path, and the grant would not
 * apply. It also must not disclaim responsibility for the child.
 *
 * Because it holds that permission, it also (1) refuses to start if its own bundle
 * was modified after signing and (2) strips loader/Python/PyInstaller injection
 * variables from the child's environment.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <Security/Security.h>
#include <errno.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

/* Set before the forwarding handlers can fire (signals are blocked around spawn). */
static volatile pid_t child_pid = 0;

static void forward_signal(int sig) {
    int saved_errno = errno; /* don't clobber the EINTR the waitpid loop checks */
    pid_t pid = child_pid;
    if (pid > 0) {
        kill(pid, sig);
    }
    errno = saved_errno;
}

/*
 * The app holds the user's Things permission, so it must not start from files that
 * changed after signing. kSecCSStrictValidate plus default flags also checks the
 * resource seal (added/removed/modified files under Contents/Resources).
 *
 * Limits: this catches files modified BEFORE launch (offline tampering). It does not
 * protect files swapped while the server is running (PyInstaller loads some libraries
 * lazily, after this check). It is defense in depth, not runtime integrity.
 * Returns an OSStatus, 0 = valid.
 */
static OSStatus verify_own_signature(void) {
    SecCodeRef self = NULL;
    SecStaticCodeRef static_code = NULL;
    OSStatus st = SecCodeCopySelf(kSecCSDefaultFlags, &self);
    if (st == errSecSuccess) {
        st = SecCodeCopyStaticCode(self, kSecCSDefaultFlags, &static_code);
    }
    if (st == errSecSuccess) {
        st = SecStaticCodeCheckValidity(static_code, kSecCSDefaultFlags | kSecCSStrictValidate, NULL);
    }
    if (static_code != NULL) {
        CFRelease(static_code);
    }
    if (self != NULL) {
        CFRelease(self);
    }
    return st;
}

/*
 * True for variables that change what code the child loads: dynamic-loader
 * (DYLD_*, LD_*), the Python interpreter (PYTHON*), and the PyInstaller bootloader
 * (_PYI_*, PYINSTALLER_*). Matched by prefix on the name, so new variants in these
 * families are covered without maintaining a list.
 */
static int is_blocked_env(const char *entry) {
    static const char *const prefixes[] = {"DYLD_", "LD_", "PYTHON", "_PYI_", "PYINSTALLER_"};
    for (size_t i = 0; i < sizeof(prefixes) / sizeof(prefixes[0]); i++) {
        if (strncmp(entry, prefixes[i], strlen(prefixes[i])) == 0) {
            return 1;
        }
    }
    return 0;
}

/* Heap copy of environ minus blocked variables; NULL on allocation failure. */
static char **scrubbed_environ(void) {
    size_t count = 0;
    while (environ != NULL && environ[count] != NULL) {
        count++;
    }
    char **out = calloc(count + 1, sizeof(char *));
    if (out == NULL) {
        return NULL;
    }
    size_t k = 0;
    for (size_t i = 0; i < count; i++) {
        if (!is_blocked_env(environ[i])) {
            out[k++] = environ[i];
        }
    }
    out[k] = NULL;
    return out;
}

/* Absolute, symlink-free path of this executable; NULL on failure. */
static char *self_path(char *out) {
    char raw[PATH_MAX];
    uint32_t size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &size) != 0) {
        return NULL;
    }
    return realpath(raw, out);
}

int main(int argc, char **argv) {
    (void)argc;
    OSStatus sig_status = verify_own_signature();
    if (sig_status != errSecSuccess) {
        fprintf(stderr,
                "safe-things-mcp launcher: app signature check failed (OSStatus %d); "
                "refusing to start a modified app. Reinstall the extension.\n",
                (int)sig_status);
        return 126;
    }
    char exe[PATH_MAX];
    if (self_path(exe) == NULL) {
        fprintf(stderr, "safe-things-mcp launcher: cannot resolve own path: %s\n", strerror(errno));
        return 127;
    }

    /* <app>/Contents/MacOS/<exe> -> <app>/Contents/Resources/server/safe-things-mcp */
    char *slash = strrchr(exe, '/');
    if (slash == NULL) {
        fprintf(stderr, "safe-things-mcp launcher: unexpected executable path %s\n", exe);
        return 127;
    }
    *slash = '\0';
    char candidate[PATH_MAX];
    int n = snprintf(candidate, sizeof(candidate), "%s/../Resources/server/safe-things-mcp", exe);
    if (n < 0 || (size_t)n >= sizeof(candidate)) {
        fprintf(stderr, "safe-things-mcp launcher: server path too long\n");
        return 127;
    }
    char server[PATH_MAX];
    if (realpath(candidate, server) == NULL) {
        fprintf(stderr, "safe-things-mcp launcher: cannot start %s: %s\n", candidate, strerror(errno));
        return 127;
    }

    /* Child argv: server path, then our arguments forwarded verbatim (NULL-terminated). */
    argv[0] = server;

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = forward_signal;
    sigemptyset(&sa.sa_mask);
    const int fwd[] = {SIGTERM, SIGINT, SIGHUP, SIGQUIT};
    const size_t nfwd = sizeof(fwd) / sizeof(fwd[0]);

    sigset_t block, old;
    sigemptyset(&block);
    for (size_t i = 0; i < nfwd; i++) {
        sigaddset(&block, fwd[i]);
    }
    sigprocmask(SIG_BLOCK, &block, &old);
    for (size_t i = 0; i < nfwd; i++) {
        sigaction(fwd[i], &sa, NULL);
    }

    /* Reset the child's signal mask/handlers so it does not inherit our blocked set. */
    posix_spawnattr_t attr;
    posix_spawnattr_init(&attr);
    sigset_t defaults;
    sigemptyset(&defaults);
    for (size_t i = 0; i < nfwd; i++) {
        sigaddset(&defaults, fwd[i]);
    }
    posix_spawnattr_setsigdefault(&attr, &defaults);
    posix_spawnattr_setsigmask(&attr, &old);
    posix_spawnattr_setflags(&attr, POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK);

    char **child_env = scrubbed_environ();
    if (child_env == NULL) {
        fprintf(stderr, "safe-things-mcp launcher: out of memory\n");
        return 127;
    }
    pid_t pid = 0;
    int rc = posix_spawn(&pid, server, NULL, &attr, argv, child_env);
    posix_spawnattr_destroy(&attr);
    free(child_env);
    if (rc != 0) {
        fprintf(stderr, "safe-things-mcp launcher: cannot start %s: %s\n", server, strerror(rc));
        return 127;
    }
    child_pid = pid;
    sigprocmask(SIG_SETMASK, &old, NULL);

    int status = 0;
    for (;;) {
        pid_t w = waitpid(pid, &status, 0);
        if (w == pid) {
            break;
        }
        if (w < 0 && errno != EINTR) {
            fprintf(stderr, "safe-things-mcp launcher: waitpid failed: %s\n", strerror(errno));
            return 127;
        }
    }

    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        int sig = WTERMSIG(status);
        signal(sig, SIG_DFL);
        sigset_t unblock;
        sigemptyset(&unblock);
        sigaddset(&unblock, sig);
        sigprocmask(SIG_UNBLOCK, &unblock, NULL);
        raise(sig);
        _exit(128 + sig);
    }
    return 1;
}
