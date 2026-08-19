#!/usr/bin/env python3
"""
EXECUTION WRAPPER - Run engine and capture full output
"""
import subprocess
import sys
import json
import os

# Install dependencies
print("Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "numpy==1.26.0", "scipy==1.11.0", "requests==2.31.0"], check=True)

# Set environment
os.environ['PARLAY_API_KEY'] = '14559e0db9853f9d4ac8211f25d042b0'

# Run the engine
print("\n" + "="*80)
print("EXECUTING UNIFIED DUAL-CORE DFS HANDICAPPING ENGINE v9.0")
print("="*80 + "\n")

# Execute main.py with full output capture
result = subprocess.run([sys.executable, "main.py"], capture_output=False, text=True)
sys.exit(result.returncode)
