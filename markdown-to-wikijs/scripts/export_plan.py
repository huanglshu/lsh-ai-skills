#!/usr/bin/env python3
"""Backward-compatible entry point for creating a Wiki.js publish plan."""

from __future__ import annotations

from publish_wikijs import main


if __name__ == "__main__":
    raise SystemExit(main(["plan", *__import__("sys").argv[1:]]))
