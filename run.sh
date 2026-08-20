#!/usr/bin/env python3
"""
EXECUTION WRAPPER - Run engine and capture full output.
API key must be set via environment variable PARLAY_API_KEY.
Copy .env.template to .env and fill in your key before running.
"""
import subprocess
import sys
import os

# Install dependencies
print("Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)

# Validate that the API key is set (do NOT hardcode secrets here)
if not os.environ.get("PARLAY_API_KEY"):
    print("ERROR: PARLAY_API_KEY environment variable is not set.")
    print("Copy .env.template to .env, fill in your key, and source it before running.")
    sys.exit(1)

# Run the engine
print("\n" + "="*80)
print("EXECUTING UNIFIED DUAL-CORE DFS HANDICAPPING ENGINE v9.0")
print("="*80 + "\n")

result = subprocess.run([sys.executable, "main.py"], capture_output=False, text=True)
sys.exit(result.returncode)

