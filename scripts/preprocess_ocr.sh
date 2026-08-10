#!/bin/bash
# Wrapper: delegates to the ocr-image-text-extract skill's preprocess script.
# The audit checker expects scripts/ at the skill root.
exec ~/.agents/skills/ocr-image-text-extract/scripts/preprocess_ocr.sh "$@"
