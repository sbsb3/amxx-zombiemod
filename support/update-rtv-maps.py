#!/usr/bin/env python3
"""Rebuild AMXX maps.ini from every .bsp in the TS maps folder.

RockTheVote, mapchooser, and the admin maps menu all load the vote pool from
addons/amxmodx/configs/maps.ini at map start. Dropping a .bsp into ts/maps
does not add it to RTV until this file is rewritten and the map changes.

mapcycle.txt is a separate rotation list. Pass --mapcycle to append newly
discovered maps to the end of the cycle (existing rotation order is kept).

Usage:
  update-rtv-maps.py              # write maps.ini (backup first)
  update-rtv-maps.py --dry-run    # print the diff, do not write
  update-rtv-maps.py --mapcycle   # also append new maps to mapcycle.txt
  update-rtv-maps.py --exclude ts_office --exclude ts_vertigo
  update-rtv-maps.py --exclude-file maps.ini.exclude
"""
from __future__ import print_function

import argparse
import datetime
import os
import shutil
import sys

DEFAULT_MAPS_DIR = "/home/tsserver/serverfiles/ts/maps"
DEFAULT_MAPS_INI = "/home/tsserver/serverfiles/ts/addons/amxmodx/configs/maps.ini"
DEFAULT_MAPCYCLE = "/home/tsserver/serverfiles/ts/mapcycle.txt"

HEADER = """;
; Maps configuration file
; File location: $moddir/addons/amxmodx/configs/maps.ini
; Used by RockTheVote/nominate plugin and mapchooser
;
; Generated from every .bsp in ts/maps ({count} maps).
;
"""


def load_names(path):
    """Return ordered map names from maps.ini (comments/blank lines skipped)."""
    names = []
    seen = set()
    if not os.path.isfile(path):
        return names
    with open(path, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            name = line.split()[0]
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names


def scan_bsps(maps_dir):
    names = []
    for entry in os.listdir(maps_dir):
        if not entry.lower().endswith(".bsp"):
            continue
        name = entry[:-4]
        if name:
            names.append(name)
    names.sort()
    return names


def load_excludes(path, extra):
    excludes = set(n.lower() for n in extra)
    if not path:
        return excludes
    with open(path, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            excludes.add(line.split()[0].lower())
    return excludes


def render_ini(maps):
    return HEADER.format(count=len(maps)) + "\n".join(maps) + "\n"


def print_diff(old, new):
    old_set = set(n.lower() for n in old)
    added = [n for n in new if n.lower() not in old_set]
    removed = [n for n in old if n.lower() not in set(x.lower() for x in new)]
    print("maps.ini currently: %d" % len(old))
    print("from .bsp files:    %d" % len(new))
    if added:
        print("added (%d):" % len(added))
        for name in added:
            print("  + %s" % name)
    if removed:
        print("removed (%d):" % len(removed))
        for name in removed:
            print("  - %s" % name)
    if not added and not removed:
        print("no maps.ini changes")
    return added, removed


def backup(path):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path + ".bak-" + stamp
    shutil.copy2(path, dest)
    print("backup: %s" % dest)
    return dest


def mapcycle_append(path, names, dry_run):
    current = load_names(path)
    have = set(n.lower() for n in current)
    to_add = [n for n in names if n.lower() not in have]
    print("mapcycle currently: %d" % len(current))
    if not to_add:
        print("no mapcycle changes")
        return 0
    print("mapcycle append (%d):" % len(to_add))
    for name in to_add:
        print("  + %s" % name)
    if dry_run:
        return len(to_add)
    if os.path.isfile(path):
        backup(path)
        with open(path, "r") as fh:
            text = fh.read()
    else:
        text = ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n".join(to_add) + "\n"
    with open(path, "w") as fh:
        fh.write(text)
    print("wrote %d maps to %s" % (len(current) + len(to_add), path))
    return len(to_add)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--maps-dir", default=DEFAULT_MAPS_DIR,
                        help="directory of .bsp files (default: %(default)s)")
    parser.add_argument("--maps-ini", default=DEFAULT_MAPS_INI,
                        help="maps.ini to rewrite (default: %(default)s)")
    parser.add_argument("--exclude", action="append", default=[],
                        help="map name to omit (repeatable)")
    parser.add_argument("--exclude-file", default="",
                        help="file of map names to omit, one per line")
    parser.add_argument("--mapcycle", nargs="?", const=DEFAULT_MAPCYCLE,
                        default=None, metavar="FILE",
                        help="append new maps to mapcycle.txt (default: %s)"
                        % DEFAULT_MAPCYCLE)
    parser.add_argument("--mapcycle-maps", nargs="+", default=None,
                        metavar="MAP",
                        help="maps to append to mapcycle (default: maps added "
                             "to maps.ini this run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the diff and do not write files")
    args = parser.parse_args(argv[1:])

    if not os.path.isdir(args.maps_dir):
        print("Not a directory: %s" % args.maps_dir, file=sys.stderr)
        return 1

    excludes = load_excludes(args.exclude_file, args.exclude)
    maps = [n for n in scan_bsps(args.maps_dir) if n.lower() not in excludes]
    if not maps:
        print("No .bsp maps found in %s" % args.maps_dir, file=sys.stderr)
        return 1

    old = load_names(args.maps_ini)
    added, removed = print_diff(old, maps)

    ini_changed = bool(added or removed or not os.path.isfile(args.maps_ini))
    if ini_changed and not args.dry_run:
        os.makedirs(os.path.dirname(args.maps_ini) or ".", exist_ok=True)
        if os.path.isfile(args.maps_ini):
            backup(args.maps_ini)
        with open(args.maps_ini, "w") as fh:
            fh.write(render_ini(maps))
        print("wrote %d maps to %s" % (len(maps), args.maps_ini))
        print("reload on next map change (maps.ini is read at plugin_init)")

    if args.mapcycle:
        cycle_maps = args.mapcycle_maps if args.mapcycle_maps is not None else added
        mapcycle_append(args.mapcycle, cycle_maps, args.dry_run)
        if not args.dry_run:
            print("nextmap.amxx rereads mapcycle on the next map change")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
