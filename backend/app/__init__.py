# Empty file to mark directory as Python package 

import os
import sys
from pathlib import Path

# Set TRANSFORMERS_CACHE environment variable if not already set
# This helps ensure the app looks in the same location for models
if "TRANSFORMERS_CACHE" not in os.environ:
    default_cache = os.path.join(str(Path.home()), '.cache', 'huggingface', 'transformers')
    os.environ["TRANSFORMERS_CACHE"] = default_cache
    print(f"Set TRANSFORMERS_CACHE to {default_cache}") 