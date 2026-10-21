import os
import sys

# The pipeline modules import each other as top-level names (digest.py puts
# src/ on sys.path itself), so the tests do the same.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
