#!/usr/bin/env python3
"""Single-image MinerU Precision Parse worker.

Called as: python3 mineru_one.py <abs_image_path>
cwd must be the desired output parent — precision_parse writes ./output_<stem>/.

Uses precision_parse DIRECTLY, not parse_with_fallback: SKILL.md mandates
"只用 Precision Parse；显式失败不静默退到 Agent", but run_mineru.py's CLI
entrypoint calls parse_with_fallback which tries the Agent API first.
"""
import sys
sys.path.insert(0, "/Users/jacky/.agents/skills/mineru")
from run_mineru import precision_parse

precision_parse(sys.argv[1], timeout=300)
