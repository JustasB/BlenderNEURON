#!/usr/bin/env python3
"""Run selected compatibility lanes; CircleCI runs one lane per parallel job."""
from compatibility.integration import main

if __name__ == '__main__':
    raise SystemExit(main())
