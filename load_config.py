import json
import os

# This ensures it finds the config.json file no matter where you run the script from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "config.json")

with open(config_path, "r") as f:
    config = json.load(f)