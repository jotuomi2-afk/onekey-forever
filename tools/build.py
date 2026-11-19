#!/usr/bin/env python3
"""Build the release zip: dist/OneKeyForever-<version>.zip with one folder,
OneKeyDruid/, ready to unpack into Interface/AddOns.

    python3 tools/build.py            # tests + scan + zip
    python3 tools/build.py --no-test  # zip only (CI runs the tests itself)

The folder keeps the name OneKeyDruid so that players keep their settings
(SavedVariables OneKeyDruidDB) when they update.
"""
import hashlib, os, re, shutil, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "OneKeyDruid")
EXTRA = ["LICENSE", "README.md", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"]


def version():
    toc = open(os.path.join(ADDON, "OneKeyDruid.toc"), encoding="utf-8").read()
    return re.search(r"^## Version:\s*(\S+)", toc, re.M).group(1)


def main():
    if "--no-test" not in sys.argv:
        for cmd in (["tests/run_tests.py"], ["security/scan.py"]):
            r = subprocess.run([sys.executable, "-I"] + cmd, cwd=ROOT)
            if r.returncode:
                sys.exit("build stopped: %s failed" % cmd[0])
    v = version()
    dist = os.path.join(ROOT, "dist")
    stage = os.path.join(dist, "stage", "OneKeyDruid")
    shutil.rmtree(os.path.join(dist, "stage"), ignore_errors=True)
    os.makedirs(stage)
    for f in sorted(os.listdir(ADDON)):
        shutil.copy2(os.path.join(ADDON, f), stage)
    for f in EXTRA:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), stage)
    # the package itself must pass the scan (no stray files)
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "security", "scan.py"), stage])
    if r.returncode:
        sys.exit("build stopped: the staged package fails the scan")
    out = os.path.join(dist, "OneKeyForever-%s.zip" % v)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(stage)):
            # fixed timestamps: the same source gives the same zip
            info = zipfile.ZipInfo("OneKeyDruid/" + f, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, open(os.path.join(stage, f), "rb").read())
    shutil.rmtree(os.path.join(dist, "stage"))
    digest = hashlib.sha256(open(out, "rb").read()).hexdigest()
    open(out + ".sha256", "w").write("%s  %s\n" % (digest, os.path.basename(out)))
    print("built %s\nsha256 %s" % (os.path.relpath(out, ROOT), digest))


if __name__ == "__main__":
    main()
