import os
import sys

# Add this `third_party` directory to the Python package search path
# so that we can import libraries like `MotionPhoto2` from outside.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
