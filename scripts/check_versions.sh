#!/usr/bin/env bash
set -e
for bin in python3 g++ cmake ninja git; do
  if ! command -v "$bin" >/dev/null 2>&1; then echo "Missing: $bin"; exit 1; fi
  case "$bin" in
    python3) python3 --version ;;
    *) "$bin" --version | head -1 ;;
  esac
done
for bin in clang genmc nidhugg; do
  if command -v "$bin" >/dev/null 2>&1; then echo "$bin: installed"; else echo "$bin: not installed (optional)"; fi
done
