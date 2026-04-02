#!/usr/bin/env python3
"""
Olympus HLC — Post-flash smoke test
Version: v1.1

Verifica que la imagen Yocto está correctamente instalada en la RPi5
SIN necesidad de Arduino conectado.

Ejecutar desde la máquina local:
    ssh root@<RPi5-IP> python3 /usr/bin/test_smoke.py

O directamente en la RPi5:
    python3 /usr/bin/test_smoke.py

Salida: PASS / FAIL por cada check. Exit code 0 = todo OK.
"""

import os
import subprocess
import sys
import time

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = []


def check(name, ok, detail=""):
    tag  = PASS if ok else FAIL
    line = f"  [{tag}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append(ok)
    return ok


def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─── 1. Archivos instalados ───────────────────────────────────────────────────

section("1. Archivos instalados")

FILES = {
    "/usr/bin/olympus_controller.py":                    "controlador legacy v2.4",
    "/usr/lib/python3.12/site-packages/olympus_hlc/__init__.py": "paquete olympus_hlc v3.0",
    "/usr/lib/python3.12/site-packages/olympus_hlc/engine.py":   "HlcEngine",
    "/usr/lib/python3.12/site-packages/olympus_hlc/sources/gcs.py": "GCSSource",
    "/etc/olympus/olympus_controller.yaml":              "configuración operacional",
    "/usr/share/olympus/models/yolov8n.onnx":            "modelo bbox (referencia)",
    "/usr/share/olympus/models/yolov8n-seg.onnx":        "modelo segmentación (GNC-REQ-002)",
    "/usr/lib/python3.12/site-packages/rover_bridge.so": "extensión Rust PyO3",
}

for path, desc in FILES.items():
    check(path, os.path.exists(path), desc)


# ─── 2. Versiones ────────────────────────────────────────────────────────────

section("2. Versiones")

# Legacy controller
try:
    with open("/usr/bin/olympus_controller.py") as f:
        for line in f:
            if line.startswith("# Version:"):
                version = line.split(":", 1)[1].strip()
                check("olympus_controller.py version", version == "v2.4",
                      f"encontrado={version} esperado=v2.4")
                break
except OSError as e:
    check("olympus_controller.py version", False, str(e))

# Nuevo paquete
try:
    with open("/usr/lib/python3.12/site-packages/olympus_hlc/__init__.py") as f:
        content = f.read()
    check("olympus_hlc version", "v3.0" in content, content.strip())
except OSError as e:
    check("olympus_hlc version", False, str(e))


# ─── 3. Parámetros YAML ──────────────────────────────────────────────────────

section("3. Parámetros YAML")

YAML_KEYS = [
    "ping_interval_s", "tlm_warn_s", "tlm_retreat_s", "tlm_stb_s",
    "retreat_dist_mm", "slip_stall_frames",
    "batt_warn_mv", "batt_critical_mv",
    "temp_warn_c", "temp_crit_c",
    "storage_min_mb", "tlm_interval_warn_s",
    "exp_speed_l", "exp_speed_r",
    "vision_mode", "seg_model_path",
    "gcs_listen_port", "csp_enabled",
]

try:
    with open("/etc/olympus/olympus_controller.yaml") as f:
        yaml_content = f.read()
    for key in YAML_KEYS:
        check(f"  yaml: {key}", key in yaml_content)
except OSError as e:
    check("YAML accesible", False, str(e))


# ─── 4. Imports Python ───────────────────────────────────────────────────────

section("4. Imports Python")

for mod, label in [
    ("yaml",         "python3-pyyaml"),
    ("cv2",          "python3-opencv"),
    ("numpy",        "python3-numpy"),
    ("rover_bridge", "rover_bridge.so"),
]:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "ok")
        check(label, True, ver)
    except ImportError as e:
        check(label, False, str(e))

# cv2.dnn separado (puede importar pero sin DNN)
try:
    import cv2
    has_dnn = hasattr(cv2, "dnn") and hasattr(cv2.dnn, "readNetFromONNX")
    check("cv2.dnn.readNetFromONNX", has_dnn)
except ImportError:
    pass

# Paquete olympus_hlc importable
try:
    import importlib
    hlc = importlib.import_module("olympus_hlc.engine")
    check("olympus_hlc.engine importable", hasattr(hlc, "HlcEngine"))
    src = importlib.import_module("olympus_hlc.sources.gcs")
    check("olympus_hlc.sources.gcs importable", hasattr(src, "GCSSource"))
except Exception as e:
    check("olympus_hlc importable", False, str(e))


# ─── 5. Sintaxis ─────────────────────────────────────────────────────────────

section("5. Sintaxis de los módulos instalados")

for path in [
    "/usr/bin/olympus_controller.py",
    "/usr/lib/python3.12/site-packages/olympus_hlc/engine.py",
    "/usr/lib/python3.12/site-packages/olympus_hlc/monitors.py",
    "/usr/lib/python3.12/site-packages/olympus_hlc/sources/gcs.py",
]:
    ret = subprocess.run(
        [sys.executable, "-m", "py_compile", path],
        capture_output=True,
    )
    check(f"  py_compile {os.path.basename(path)}",
          ret.returncode == 0,
          ret.stderr.decode().strip() if ret.returncode != 0 else "OK")


# ─── 6. Dry-run olympus_hlc (sin Arduino) ────────────────────────────────────

section("6. Dry-run olympus_hlc --mode manual (sin Arduino)")

proc = subprocess.Popen(
    [sys.executable, "-m", "olympus_hlc",
     "--mode", "manual", "--dry-run", "--log-path", "/tmp/smoke_hlc.log"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

time.sleep(2)
for cmd in ["ping\n", "exp 40 40\n", "stb\n", "q\n"]:
    try:
        proc.stdin.write(cmd)
        proc.stdin.flush()
    except BrokenPipeError:
        break
    time.sleep(0.2)

try:
    out, _ = proc.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()

lines = out.splitlines()
check("olympus_hlc arranca",        proc.returncode in (0, 1, None))
check("olympus_hlc responde PING",  any("pong"    in l for l in lines))
check("olympus_hlc recibe ACK:EXP", any("ACK:EXP" in l for l in lines))
check("olympus_hlc recibe ACK:STB", any("ACK:STB" in l for l in lines))
check("olympus_hlc emite TLM",      any("TLM"     in l for l in lines))
check("olympus_hlc log creado",     os.path.exists("/tmp/smoke_hlc.log"))


# ─── 7. Dry-run olympus_controller.py legacy (sin Arduino) ───────────────────

section("7. Dry-run olympus_controller.py legacy (sin Arduino)")

proc2 = subprocess.Popen(
    [sys.executable, "/usr/bin/olympus_controller.py",
     "--mode", "manual", "--dry-run"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

time.sleep(2)
for cmd in ["ping\n", "q\n"]:
    try:
        proc2.stdin.write(cmd)
        proc2.stdin.flush()
    except BrokenPipeError:
        break
    time.sleep(0.2)

try:
    out2, _ = proc2.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc2.kill()
    out2, _ = proc2.communicate()

lines2 = out2.splitlines()
check("legacy arranca",         proc2.returncode in (0, 1, None))
check("legacy responde PING",   any("pong" in l for l in lines2))


# ─── 8. Modelos ONNX cargables ───────────────────────────────────────────────

section("8. Modelos ONNX (cv2.dnn)")

for name, path in [
    ("yolov8n.onnx",     "/usr/share/olympus/models/yolov8n.onnx"),
    ("yolov8n-seg.onnx", "/usr/share/olympus/models/yolov8n-seg.onnx"),
]:
    if not os.path.exists(path):
        check(f"  {name}", False, "archivo no encontrado")
        continue
    try:
        import cv2
        net = cv2.dnn.readNetFromONNX(path)
        n   = len(net.getLayerNames())
        check(f"  {name}", n > 0, f"{n} capas")
    except Exception as e:
        check(f"  {name}", False, str(e))


# ─── Resumen ─────────────────────────────────────────────────────────────────

section("Resumen")
passed = sum(results)
total  = len(results)
print(f"\n  {passed}/{total} checks pasados\n")

if passed == total:
    print("  ✓ Imagen lista para operar\n")
    sys.exit(0)
else:
    print(f"  ✗ {total - passed} check(s) fallaron — revisar antes de usar\n")
    sys.exit(1)
