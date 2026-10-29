"""Build the one-click Windows app: dist/GreenLCC/GreenLCC.exe (+ dist/GreenLCC_Windows.zip to share).

Run:  pip install -r requirements-build.txt
      python scripts/build_exe.py

The exe bundles Python, the libraries and the app files, so the person running it needs nothing installed.
Double-click GreenLCC.exe: a console window opens, the app starts on a free local port and the browser opens.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEP = ";" if sys.platform == "win32" else ":"
DATA = ["app.py", "pages", "core", "data", "sample_quotes", ".streamlit"]
COLLECT_ALL = ["streamlit", "plotly", "pdfplumber", "pdfminer", "reportlab", "openpyxl", "numpy_financial", "pydantic"]
METADATA = ["streamlit", "plotly", "pydantic", "numpy", "pandas"]
HIDDEN = ["core." + p.stem for p in (ROOT / "core").glob("*.py") if p.stem != "__init__"] + [
    "scipy.optimize", "scipy._lib.array_api_compat.numpy.fft", "scipy.special._special_ufuncs"]


def main() -> None:
    cmd = [sys.executable, "-m", "PyInstaller", str(ROOT / "launcher.py"), "--name", "GreenLCC", "--onedir", "--noconfirm",
           "--clean", "--console", "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build")]
    for d in DATA:  # a file goes to the bundle root ("."), a folder keeps its name
        cmd += ["--add-data", f"{ROOT / d}{SEP}{'.' if (ROOT / d).is_file() else d}"]
    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]
    for pkg in METADATA:
        cmd += ["--copy-metadata", pkg]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]
    subprocess.run(cmd, check=True, cwd=ROOT)
    out = ROOT / "dist" / "GreenLCC"
    (out / "HOW TO RUN.txt").write_text(
        "Double-click GreenLCC.exe.\n"
        "A black window opens and your browser shows the app after a few seconds (first start can take ~20 s).\n"
        "Keep the black window open while you use the app; close it to stop.\n"
        "If the browser does not open, go to the address printed in the window (e.g. http://localhost:8501).\n",
        encoding="utf-8")
    zip_base = ROOT / "dist" / "GreenLCC_Windows"
    shutil.make_archive(str(zip_base), "zip", out.parent, out.name)
    print("built", out / "GreenLCC.exe", "and", zip_base.with_suffix(".zip"))


if __name__ == "__main__":
    main()
