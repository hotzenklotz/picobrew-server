#!/bin/bash
set -eEuo pipefail
# Pylint doesn't lint files in directories that don't have an __init__.py
# This will maybe be fixed by https://github.com/PyCQA/pylint/issues/352
find . -not -path '*/\.*' -type f -name '*.py' | xargs python -m pylint 