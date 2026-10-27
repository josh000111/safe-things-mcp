"""PyInstaller entry point for a frozen, signable safe-things-mcp binary.

This exists so the frozen executable IS the process that opens the Things
database, giving it a single stable code-signing identity that macOS TCC can
remember (unlike the shared, ad-hoc-signed Homebrew Python).
"""
from safe_things_mcp.server import main

if __name__ == "__main__":
    main()
