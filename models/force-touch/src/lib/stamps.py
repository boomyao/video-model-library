"""Which rendered frames can be kept. Bookkeeping only: nothing in here changes a picture, so this file is not part of
what a shot's frames are signed with (and it runs without Blender, see the self-test at the bottom).

A folder of frames carries a stamp, _stamp.json:

    {"v": 2, "code": "...", "fps": 60, "dur": 6.0333, "start": 0.0, "n": 392, "opts": "--shot S001 --draft --camblur",
     "rel": {"0.01>": 5.075, "0.02@关机": 7.657, ...}}

  code   the project code the shot ran (its script, what it borrows from shots/, the modules of lib/ it loaded) and
         the options of the run
  rel    every narration moment the shot asked the clock for, in seconds since the shot's own start

The frames stay good while the code is the same and those moments are where they were, seen from the shot's start
(within TOL). A film that only got longer or shorter somewhere else moves a shot as a whole: its start changes, its
picture does not. A shot whose own lines were re-timed or re-worded is rendered again.

Stamps written before this file existed ({"sig", "start", "n"}) tied the frames to the absolute start time. They are
accepted once, while nothing has moved, and rewritten in the new form (see legacy_signature).
"""
import hashlib
import json
import os

TOL = 0.02          # seconds: a shot's start and end snap to frames on their own, so its moments wobble by a frame
HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY_KIT = os.path.join(HERE, "_legacy_shotkit.txt")     # shotkit.py as it was when the old stamps were written
NOT_PICTURE = ("lib/stamps.py",)                           # project files a frame does not depend on
SKIP_VALUE = ("--f0", "--f1", "--still", "--out", "--stamp-alts")     # options (with their value) that do not change a frame
SKIP_FLAG = ("--anchors-only", "--stamp-only", "--adopt")


def options(argv):
    """The part of a run's options that the frames depend on, as one string."""
    keep, skip = [], False
    for a in argv:
        if skip and not a.startswith("--"):
            skip = False
            continue
        skip = a in SKIP_VALUE
        if not skip and a not in SKIP_FLAG:
            keep.append(a)
    return " ".join(keep)


def _files(root, paths):
    here = os.path.realpath(root) + os.sep
    out = []
    for p in sorted({os.path.realpath(p) for p in paths if p and p.endswith(".py")}):
        rel = os.path.relpath(p, here)
        if os.path.exists(p) and p.startswith((here + "lib" + os.sep, here + "shots" + os.sep)) and rel not in NOT_PICTURE:
            out.append((rel, p))
    return out


def code_signature(root, paths, opts, version=1):
    h = hashlib.sha1(("v%d " % version).encode())
    for rel, p in _files(root, paths):
        h.update(rel.encode())
        h.update(open(p, "rb").read())
    h.update(opts.encode())
    return h.hexdigest()


def legacy_signature(root, paths, opts, start, n):
    """The signature of the old stamps, computed as the old shotkit.py computed it (its own bytes were part of it)."""
    if not os.path.exists(LEGACY_KIT):
        return None
    h = hashlib.sha1(("%.3f %d " % (start, n)).encode())
    for rel, p in _files(root, paths):
        h.update(rel.encode())
        h.update(open(LEGACY_KIT if rel == os.path.join("lib", "shotkit.py") else p, "rb").read())
    h.update(opts.encode())
    return h.hexdigest()


def make(code, fps, start, dur, n, opts, asked):
    return {"v": 2, "code": code, "fps": fps, "dur": round(dur, 4), "start": round(start, 4), "n": n, "opts": opts,
            "rel": {k: round(v - start, 4) for k, v in sorted(asked.items())}}


def check(stamp, code, fps, start, dur, n, resolve, legacy=None):
    """(fresh, why): are the frames this stamp belongs to still the frames the shot would render now?
    resolve(anchor) gives film seconds for a narration anchor and may raise when the words are gone."""
    if not stamp:
        return False, "no stamp"
    if stamp.get("v") != 2:
        same = abs(stamp.get("start", -1e9) - start) < 1e-3 and stamp.get("n") == n
        if same and legacy and stamp.get("sig") == legacy:
            return True, "old stamp, nothing has moved"
        return False, "old stamp: timing, code or options differ"
    if stamp.get("code") != code:
        return False, "code or options differ"
    if stamp.get("fps") != fps:
        return False, "frame rate differs"
    if abs(stamp.get("dur", -1e9) - dur) > TOL:
        return False, "the shot is %.3f s long, was %.3f" % (dur, stamp.get("dur", 0.0))
    for k, was in stamp.get("rel", {}).items():
        try:
            now = resolve(k) - start
        except Exception:
            return False, "narration anchor %s is gone" % k
        if abs(now - was) > TOL:
            return False, "%s is %.3f s into the shot, was %.3f" % (k, now, was)
    return True, "same code, same timing inside the shot"


def read(outdir):
    p = os.path.join(outdir, "_stamp.json")
    try:
        return json.load(open(p, encoding="utf8"))
    except (OSError, ValueError):
        return None


def write(outdir, stamp):
    json.dump(stamp, open(os.path.join(outdir, "_stamp.json"), "w", encoding="utf8"), ensure_ascii=False)


if __name__ == "__main__":
    asked = {"0.01>": 5.075, "0.02@关机": 7.657}
    st = make("abc", 60, 0.0, 6.0333, 392, "--shot S001 --draft", asked)
    ok = lambda s, **k: check(s, k.get("code", "abc"), k.get("fps", 60), k.get("start", 0.0), k.get("dur", 6.0333), 392,
                              k.get("resolve", lambda a: asked[a] + k.get("shift", 0.0)))[0]
    assert ok(st)
    assert ok(st, start=3.2167, shift=3.2167 + 0.008)                  # the film got longer before the shot
    assert ok(st, dur=6.05)                                             # the end snapped to the next frame
    assert not ok(st, shift=0.05)                                       # the lines moved inside the shot
    assert not ok(st, dur=6.2)
    assert not ok(st, code="abd")
    assert not ok(st, fps=30)
    assert not ok(st, resolve=lambda a: {}[a])                          # the words are gone
    assert not ok(None)
    old = {"sig": "s1", "start": 12.5, "n": 100}
    assert check(old, "abc", 30, 12.5, 2.8, 100, None, legacy="s1")[0]
    assert not check(old, "abc", 30, 12.6, 2.8, 100, None, legacy="s1")[0]
    assert not check(old, "abc", 30, 12.5, 2.8, 100, None, legacy="s2")[0]
    assert options(["--shot", "S1", "--f0", "3", "--draft", "--stamp-only", "--out", "x", "--camblur"]) == "--shot S1 --draft --camblur"
    print("stamps ok")
