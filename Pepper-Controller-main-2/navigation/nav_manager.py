# nav_manager.py - Navigation Target Manager
# Layer: Backend Layer (Python 3)
#
# PURPOSE:
#   Reads navigation_targets.json and exposes a helper function used by the
#   Flask backend (app.py) to serve the /api/navigation_targets endpoint.
#   Can also be run standalone to verify the targets file is valid.
#
# USAGE (standalone):
#   python nav_manager.py

import json
import os
from pathlib import Path

NAV_DIR          = Path(__file__).resolve().parent
NAV_TARGETS_PATH = NAV_DIR / "navigation_targets.json"


def get_navigation_targets():
    """
    Reads navigation_targets.json and returns the list of target dicts.
    Returns an empty list if the file is missing or malformed.
    Each target dict has: id, name, specialty, room_name, coordinates [x, y, theta].
    """
    try:
        with open(str(NAV_TARGETS_PATH), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("targets", [])
    except FileNotFoundError:
        print(f"[NAV_MANAGER] navigation_targets.json not found at: {NAV_TARGETS_PATH}")
        return []
    except json.JSONDecodeError as e:
        print(f"[NAV_MANAGER] Invalid JSON in navigation_targets.json: {e}")
        return []
    except Exception as e:
        print(f"[NAV_MANAGER] Unexpected error reading navigation targets: {e}")
        return []


def add_target(name, specialty, room_name, x, y, theta):
    """
    Appends a new navigation target to navigation_targets.json.
    Useful for adding targets programmatically during setup.
    """
    try:
        with open(str(NAV_TARGETS_PATH), "r", encoding="utf-8") as f:
            data = json.load(f)

        targets = data.get("targets", [])
        new_id  = max((t["id"] for t in targets), default=0) + 1

        targets.append({
            "id":          new_id,
            "name":        name,
            "specialty":   specialty,
            "room_name":   room_name,
            "coordinates": [round(x, 3), round(y, 3), round(theta, 4)]
        })
        data["targets"] = targets

        with open(str(NAV_TARGETS_PATH), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[NAV_MANAGER] Added target: {name} -> {room_name} @ [{x}, {y}, {theta}]")
        return new_id

    except Exception as e:
        print(f"[NAV_MANAGER] Failed to add target: {e}")
        return None


if __name__ == "__main__":
    targets = get_navigation_targets()
    print(f"\nLoaded {len(targets)} navigation targets from:")
    print(f"  {NAV_TARGETS_PATH}\n")
    for t in targets:
        coords = t.get("coordinates", [])
        print(f"  [{t['id']}] {t['name']} ({t['specialty']})")
        print(f"        Room: {t['room_name']}")
        print(f"        Coords: X={coords[0]}m, Y={coords[1]}m, Theta={coords[2]}rad")
        print()
