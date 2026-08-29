#!/usr/bin/env python3
"""Rewrite RCBot botprofiles skill/aim fields for a difficulty preset.

Matches the Easy/Normal/Hard/Nightmare tables in zombiemod-mysql.sma.
Use when gm_rcbot_profiles is unset and you want to patch profiles offline,
or to preview values before enabling in-plugin patching.

Usage:
  set-bot-difficulty-profiles.py <easy|normal|hard|nightmare> [profiles_dir]
  set-bot-difficulty-profiles.py check [profiles_dir]

Default profiles_dir: /home/tsserver/serverfiles/rcbot/botprofiles
"""
from __future__ import print_function

import os
import re
import sys

DEFAULT_DIR = "/home/tsserver/serverfiles/rcbot/botprofiles"

PRESETS = {
    "easy": {"skill": 40, "aim_skill": 0.05, "aim_time": 1.50, "aim_speed": 0.15},
    "normal": {"skill": 90, "aim_skill": 0.20, "aim_time": 1.00, "aim_speed": 0.25},
    "hard": {"skill": 95, "aim_skill": 0.50, "aim_time": 0.50, "aim_speed": 0.40},
    "nightmare": {"skill": 100, "aim_skill": 0.80, "aim_time": 0.25, "aim_speed": 0.60},
}

SKILL_RE = re.compile(r"^skill\s*=\s*.*$", re.I | re.M)
AIM_SKILL_RE = re.compile(r"^aim_skill\s*=\s*.*$", re.I | re.M)
AIM_TIME_RE = re.compile(r"^aim_time\s*=\s*.*$", re.I | re.M)
AIM_SPEED_RE = re.compile(r"^aim_speed\s*=\s*.*$", re.I | re.M)


def patch_file(path, preset):
    with open(path, "r") as f:
        text = f.read()
    original = text
    text = SKILL_RE.sub("skill=%d" % preset["skill"], text, count=1)
    text = AIM_SKILL_RE.sub("aim_skill=%.2f" % preset["aim_skill"], text, count=1)
    text = AIM_TIME_RE.sub("aim_time=%.2f;" % preset["aim_time"], text, count=1)
    text = AIM_SPEED_RE.sub("aim_speed=%.2f" % preset["aim_speed"], text, count=1)
    if text == original:
        return False
    with open(path, "w") as f:
        f.write(text)
    return True


def list_inis(directory):
    out = []
    for name in os.listdir(directory):
        if name.endswith(".ini") and name[:-4].isdigit():
            out.append(os.path.join(directory, name))
    return sorted(out, key=lambda p: int(os.path.basename(p)[:-4]))


def check(directory):
    files = list_inis(directory)
    if not files:
        print("No numbered .ini profiles in %s" % directory)
        return 1
    print("Profiles in %s (%d):" % (directory, len(files)))
    for path in files[:5]:
        skill = aim_skill = aim_time = aim_speed = "?"
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.lower().startswith("skill="):
                    skill = line.split("=", 1)[1]
                elif line.lower().startswith("aim_skill="):
                    aim_skill = line.split("=", 1)[1]
                elif line.lower().startswith("aim_time="):
                    aim_time = line.split("=", 1)[1].rstrip(";")
                elif line.lower().startswith("aim_speed="):
                    aim_speed = line.split("=", 1)[1]
        print("  %s  skill=%s aim_skill=%s aim_time=%s aim_speed=%s"
              % (os.path.basename(path), skill, aim_skill, aim_time, aim_speed))
    if len(files) > 5:
        print("  ... and %d more" % (len(files) - 5))
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    cmd = argv[1].lower()
    directory = argv[2] if len(argv) > 2 else DEFAULT_DIR
    if not os.path.isdir(directory):
        print("Not a directory: %s" % directory, file=sys.stderr)
        return 1
    if cmd == "check":
        return check(directory)
    if cmd not in PRESETS:
        print("Unknown difficulty %r (use easy|normal|hard|nightmare|check)" % cmd,
              file=sys.stderr)
        return 2
    preset = PRESETS[cmd]
    changed = 0
    for path in list_inis(directory):
        if patch_file(path, preset):
            changed += 1
    print("Patched %d profiles to %s in %s" % (changed, cmd, directory))
    print("  skill=%d aim_skill=%.2f aim_time=%.2f aim_speed=%.2f"
          % (preset["skill"], preset["aim_skill"], preset["aim_time"],
             preset["aim_speed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
