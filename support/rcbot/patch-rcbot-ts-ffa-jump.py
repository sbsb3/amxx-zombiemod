#!/usr/bin/env python3
"""Patch RCBot 1.51b13_mm so IsEnemy honors this server's team modes.

CBot::IsEnemy for The Specialists:

    if (map is not tm_*) {
        assume enemy
        if (m_bTeamPlay == 0)
            return true;          // FFA: every living client is an enemy
    }
    // else strcmp setinfo "model"  (same model = teammate)

RCBot only sets m_bTeamPlay on tm_* maps. It never reads mp_teamplay.
ts_* / mecklenburg / etc. therefore always take the FFA path once that
`je` is restored, so Team DM and Zombie Mod teammates shoot each other.

The shipped Linux .so NOP'd the `je`, so bots always used the model check.
`apply` used to restore a blind FFA jump (everyone is an enemy on ts_*).
That is correct for Deathmatch (empty mp_teamlist) and wrong for TDM/ZM.

This `apply` restores FFA only when mp_teamlist is empty (the plugin's DM
signal) and falls through to the model strcmp when the list is set
("Blue;Red" in TDM and Zombie Mod).

    empty mp_teamlist  -> FFA, everyone is an enemy
    non-empty list     -> same setinfo "model" = teammate

The codecave overwrites BotClient_TS_PTakeDam::execute, a debug stub that
this release .so never registers.

Usage:
    patch-rcbot-ts-ffa-jump.py apply  [rcbot_mm.so]
    patch-rcbot-ts-ffa-jump.py check  [rcbot_mm.so]
    patch-rcbot-ts-ffa-jump.py revert [rcbot_mm.so]

Default path: /home/tsserver/serverfiles/rcbot/dlls/rcbot_mm.so
Restart the server after apply/revert; changelevel does not reload the .so.
"""

from __future__ import print_function

import os
import struct
import sys

# File offset == VA on this ELF (.text sh_addr == sh_offset).
OFFSET = 0x1CCA2
CAVE = 0x47510
MODEL_CMP = 0x1CCA8
FFA_RET = 0x1CE21

# Six NOPs that replaced `je CBot::IsEnemy+0x971` (return true, %dl already 1).
ORIGINAL = bytes([0x90, 0x90, 0x90, 0x90, 0x90, 0x90])
# Blind FFA: je 0x1ce21 ; rel32 = 0x1ce21 - 0x1cca8 = 0x179
FFA_ONLY = bytes([0x0F, 0x84, 0x79, 0x01, 0x00, 0x00])
# Bytes immediately before the site (cmpb $0, offsetof(CBotGlobals, m_bTeamPlay)).
PREFIX = bytes([0x80, 0xB8, 0xED, 0x03, 0x00, 0x00, 0x00])
# Bytes immediately after (start of the model-compare block).
SUFFIX = bytes([0x8B, 0xBB, 0xB0, 0xFE, 0xFF, 0xFF])

# Original BotClient_TS_PTakeDam::execute (debug ALERT stub).
CAVE_ORIGINAL = bytes.fromhex(
    "5383ec08e8000000005b81c3e7ba0600"
    "837c2414007424837c2418ff741d8b83"
    "b0feffff83ec088d8bccc3fdff516a01"
    "ff90f400000083c4185bc383c4085bc3"
)

DEFAULT_SO = "/home/tsserver/serverfiles/rcbot/dlls/rcbot_mm.so"
SYMBOL = "CBot::IsEnemy(edict_s*)"
SITE = "0x1cca2 (IsEnemy+0x7f2)"


def _die(msg, code=1):
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(code)


def _rel32(src, dest):
    return struct.pack("<i", dest - (src + 5))


def _smart_site():
    # jmp cave; nop  (fills the original 6-byte je)
    return b"\xE9" + _rel32(OFFSET, CAVE) + b"\x90"


def _smart_cave():
    # ebx is still CBot::IsEnemy's GOT. dl is already 1 (assume enemy).
    # pfnCVarGetString("mp_teamlist"): empty -> FFA, else model compare.
    parts = []
    parts.append(b"\x8B\x83\xB0\xFE\xFF\xFF")  # mov eax, [ebx-0x150]  enginefuncs
    parts.append(b"\x8D\x8B\x36\xD7\xFD\xFF")  # lea ecx, [ebx-0x228ca] "mp_teamlist"
    parts.append(b"\x89\x0C\x24")  # mov [esp], ecx
    parts.append(b"\xFF\x90\xE8\x00\x00\x00")  # call [eax+0xe8] pfnCVarGetString
    parts.append(b"\x85\xC0")  # test eax, eax
    parts.append(b"\x74\x0A")  # jz ffa  (+10 to the FFA jmp)
    parts.append(b"\x80\x38\x00")  # cmp byte [eax], 0
    parts.append(b"\x74\x05")  # jz ffa  (+5 to the FFA jmp)
    team_jmp = len(b"".join(parts))
    parts.append(b"\xE9" + _rel32(CAVE + team_jmp, MODEL_CMP))
    ffa_jmp = len(b"".join(parts))
    parts.append(b"\xE9" + _rel32(CAVE + ffa_jmp, FFA_RET))
    cave = b"".join(parts)
    if len(cave) > len(CAVE_ORIGINAL):
        _die("codecave is %d bytes, stub is only %d" % (len(cave), len(CAVE_ORIGINAL)))
    return cave + CAVE_ORIGINAL[len(cave) :]


def _read_blob(path, offset, size):
    with open(path, "rb") as fh:
        fh.seek(offset)
        return fh.read(size)


def _write_blob(path, offset, data):
    with open(path, "r+b") as fh:
        fh.seek(offset)
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _read_site(path):
    size = os.path.getsize(path)
    need = max(OFFSET + 6 + len(SUFFIX), CAVE + len(CAVE_ORIGINAL))
    if size < need:
        _die("%s is too small (%d bytes) to be rcbot_mm.so 1.51b13" % (path, size))
    prefix = _read_blob(path, OFFSET - len(PREFIX), len(PREFIX))
    site = _read_blob(path, OFFSET, 6)
    suffix = _read_blob(path, OFFSET + 6, len(SUFFIX))
    if prefix != PREFIX or suffix != SUFFIX:
        _die(
            "%s does not match RCBot 1.51b13_mm at %s "
            "(prefix=%s suffix=%s)"
            % (path, SITE, prefix.hex(), suffix.hex())
        )
    return site


def _state(path):
    site = _read_site(path)
    cave = _read_blob(path, CAVE, len(CAVE_ORIGINAL))
    if site == _smart_site() and cave == _smart_cave():
        return "smart"
    if site == FFA_ONLY and cave == CAVE_ORIGINAL:
        return "ffa"
    if site == ORIGINAL and cave == CAVE_ORIGINAL:
        return "stock"
    return "unknown:%s:%s" % (site.hex(), cave[:16].hex())


def check(path):
    state = _state(path)
    if state == "smart":
        print(
            "patched:   %s at %s (%s) — FFA only when mp_teamlist is empty"
            % (path, SITE, SYMBOL)
        )
        return 0
    if state == "ffa":
        print(
            "ffa-only:  %s at %s (blind FFA on ts_* — TDM/ZM teammates shoot each other)"
            % (path, SITE)
        )
        return 3
    if state == "stock":
        print("unpatched: %s at %s (six NOPs, bots ignore mp_teamplay 0)" % (path, SITE))
        return 2
    _die("%s has unexpected bytes at %s (%s)" % (path, SITE, state))


def apply(path):
    state = _state(path)
    if state == "smart":
        print("already patched: %s" % path)
        return 0
    if state not in ("stock", "ffa"):
        _die("%s has unexpected bytes at %s (%s)" % (path, SITE, state))
    _write_blob(path, CAVE, _smart_cave())
    _write_blob(path, OFFSET, _smart_site())
    print(
        "patched %s: IsEnemy FFA now follows mp_teamlist "
        "(empty = everyone is an enemy, set = same model is a teammate)" % path
    )
    print("restart the dedicated server to load the new .so")
    return 0


def revert(path):
    state = _state(path)
    if state == "stock":
        print("already unpatched: %s" % path)
        return 0
    if state not in ("smart", "ffa"):
        _die("%s has unexpected bytes at %s (%s)" % (path, SITE, state))
    _write_blob(path, OFFSET, ORIGINAL)
    _write_blob(path, CAVE, CAVE_ORIGINAL)
    print("reverted %s to stock six-NOP IsEnemy FFA site" % path)
    print("restart the dedicated server to load the new .so")
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv[1:] else 2
    cmd = argv[1]
    path = argv[2] if len(argv) > 2 else DEFAULT_SO
    if not os.path.isfile(path):
        _die("not a file: %s" % path)
    if cmd == "apply":
        return apply(path)
    if cmd == "check":
        return check(path)
    if cmd == "revert":
        return revert(path)
    _die("unknown command %r (use apply, check, or revert)" % cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
