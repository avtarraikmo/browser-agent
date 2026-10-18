#!/bin/bash
# Always write a reward, even if the verifier crashes.
mkdir -p /logs/verifier
python3 -I "$(dirname "$0")/verify.py" || echo 0 > /logs/verifier/reward.txt
