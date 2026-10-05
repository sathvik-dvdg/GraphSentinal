# ============================================================================
#  CELL B -- retrain, evaluate, package.     Paste into Colab and run.
#
#  Needs a GPU runtime (Runtime > Change runtime type > T4 GPU).
#  It refuses to start unless Cell A's verdict is clean.
#
#  IF COLAB DISCONNECTS: run this same cell again. Finished stages are skipped;
#  it continues, it does not restart. When it ends, one zip downloads and is
#  also saved on Drive. Send that zip back -- nothing else is needed.
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
result_zip = colab_runner.cell_b()
