# ============================================================================
#  CELL A -- the timestamp audit.            Paste into Colab and run. ~2-5 min.
#
#  Before this: upload graphsentinel_colab_bundle.zip anywhere in your Drive.
#  It needs no GPU and changes nothing. It writes a verdict that Cell B reads;
#  Cell B refuses to start unless that verdict says "clean".
# ============================================================================
import glob, os, shutil, sys, zipfile
from google.colab import drive

drive.mount("/content/drive", force_remount=False)
_z = sorted(glob.glob("/content/drive/MyDrive/**/graphsentinel_colab_bundle.zip",
                      recursive=True), key=os.path.getmtime)
assert _z, "Upload graphsentinel_colab_bundle.zip to your Drive first."
print("bundle:", _z[-1])
shutil.rmtree("/content/gs_bundle", ignore_errors=True)
zipfile.ZipFile(_z[-1]).extractall("/content/gs_bundle")
for _m in [m for m in sys.modules
           if m.split(".")[0] in ("graphsentinel", "colab_runner", "timestamp_audit")]:
    del sys.modules[_m]                      # never run a stale copy of the code
sys.path[:0] = ["/content/gs_bundle/ML/colab"]

import colab_runner
verdict = colab_runner.cell_a()
