#!/usr/bin/env python3
"""Mechanical text diagnostics; advisory, never an authorship verdict.

The checks live in the shared core (studio_core.text_checks); this keeps Blog Studio's
command line, `python3 text_checks.py lint|preserve|count ...`, and its module names.
"""

import sys

from studio_core import text_checks as _shared
from studio_core.text_checks import (  # noqa: F401  Blog Studio's names, kept.
    COMMON_WORDS,
    EXAMPLE_CHARS,
    EXAMPLE_LIMIT,
    FUNCTION_WORDS,
    NOTE_START,
    PROTECTED,
    READER_FACING_NOTE,
    SHINGLE,
    URL,
    carried_over,
    facts,
    lint,
    mask_protected,
    preserve,
    reader_facing_notes,
)


def main(argv=None):
    return _shared.main('Blog Studio', argv)


if __name__ == '__main__':
    sys.exit(main())
