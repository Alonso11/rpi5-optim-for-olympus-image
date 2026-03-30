#!/usr/bin/env python3
"""
Olympus HLC — Post-flash smoke test
Version: v1.0

Verifica que la imagen Yocto está correctamente instalada en la RPi5
SIN necesidad de Arduino conectado.

Ejecutar desde la máquina local:
    ssh root@<RPi5-IP> python3 /usr/bin/test_smoke.py

O directamente en la RPi5:
    python3 /usr/bin/test_smoke.py

Salida: PASS / FAIL por cada check. Exit code 0 = todo OK.
"""

import importlib
import os
import subprocess
import sys
import time

PASS  = "\033[32mPASS\033[0m"
FAIL  = "\033[31mFAIL\033[0m"
WARN  = "\033[33mWARN\033[0m"
SKIP  = "\033[90mSKIP\033[0m"

results = []

def check(name, ok, detail=""):
    tag = PASS if ok else FAIL
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
    "/usr/bin/olympus_controller.py":              "controlador HLC principal",
    "/etc/olympus/olympus_controller.yaml":        "configuración operacional",
    "/usr/share/olympus/models/yolov8n.onnx":      "modelo bbox (referencia)",
    "/usr/share/olympus/models/yolov8n-seg.onnx":  "modelo segmentación (GNC-REQ-002)",
    "/usr/lib/python3.12/site-packages/rover_bridge.so": "extensión Rust PyO3",
}

for path, desc in FILES.items():
    check(f"{path}", os.path.exists(path), desc)

# ─── 2. Versión del controlador ───────────────────────────────────────────────

section("2. Versión del controlador")

EXPECTED_VERSION = "v2.3"
try:
    with open("/usr/bin/olympus_controller.py") as f:
        for line in f:
            if line.startswith("# Version:"):
                version = line.split(":", 1)[1].strip()
                check("olympus_controller.py versión", version == EXPECTED_VERSION,
                      f"encontrado={version} esperado={EXPECTED_VERSION}")
                break
except OSError as e:
    check("olympus_controller.py versión", False, str(e))

# ─── 3. Parámetros YAML presentes ─────────────────────────────────────────────

section("3. Parámetros YAML")

YAML_KEYS = [
    "ping_interval_s", "tlm_warn_s", "tlm_retreat_s", "tlm_stb_s",
    "retreat_dist_mm", "slip_stall_frames",
    "batt_warn_mv", "batt_critical_mv",
    "temp_warn_c", "temp_crit_c",
    "storage_min_mb", "tlm_interval_warn_s",
    "exp_speed_l", "exp_speed_r",
    "vision_mode", "seg_model_path", "seg_conf_min", "seg_zone_min", "seg_roi_top",
]

try:
    with open("/etc/olympus/olympus_controller.yaml") as f:
        yaml_content = f.read()
    for key in YAML_KEYS:
        check(f"  yaml: {key}", key in yaml_content)
except OSError as e:
    check("YAML accesible", False, str(e))

# ─── 4. Imports Python ────────────────────────────────────────────────────────

section("4. Imports Python")

try:
    import yaml
    check("python3-pyyaml", True, f"versión {getattr(yaml, '__version__', 'ok')}")
except ImportError as e:
    check("python3-pyyaml", False, str(e))

try:
    import cv2
    has_dnn = hasattr(cv2, "dnn") and hasattr(cv2.dnn, "readNetFromONNX")
    check("python3-opencv", True, f"versión {cv2.__version__}")
    check("cv2.dnn.readNetFromONNX", has_dnn)
except ImportError as e:
    check("python3-opencv", False, str(e))

try:
    import numpy
    check("python3-numpy", True, f"versión {numpy.__version__}")
except ImportError as e:
    check("python3-numpy", False, str(e))

try:
    import rover_bridge
    check("rover_bridge.so", True, "importado correctamente")
except ImportError as e:
    check("rover_bridge.so", False, str(e))

# ─── 5. Sintaxis del controlador ─────────────────────────────────────────────

section("5. Sintaxis del controlador")

ret = subprocess.run(
    [sys.executable, "-m", "py_compile", "/usr/bin/olympus_controller.py"],
    capture_output=True,
)
check("py_compile olympus_controller.py", ret.returncode == 0,
      ret.stderr.decode().strip() if ret.returncode != 0 else "OK")

# ─── 6. Dry-run del controlador (sin Arduino) ─────────────────────────────────

section("6. Dry-run del controlador (10 s, sin Arduino)")

proc = subprocess.Popen(
    [sys.executable, "/usr/bin/olympus_controller.py",
     "--mode", "manual", "--dry-run"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

time.sleep(3)

# Enviar algunos comandos MSM y verificar respuestas
output_lines = []
commands = ["ping\n", "exp 40 40\n", "stb\n", "q\n"]
for cmd in commands:
    proc.stdin.write(cmd)
    proc.stdin.flush()
    time.sleep(0.3)

try:
    out, _ = proc.communicate(timeout=5)
    output_lines = out.splitlines()
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    output_lines = out.splitlines()

check("dry-run arranca sin error", proc.returncode in (0, None),
      f"exit={proc.returncode}")
check("dry-run recibe PONG",   any("PONG"    in l for l in output_lines))
check("dry-run recibe ACK:EXP", any("ACK:EXP" in l for l in output_lines))
check("dry-run recibe ACK:STB", any("ACK:STB" in l for l in output_lines))
check("dry-run emite TLM",      any("TLM"     in l for l in output_lines))
check("dry-run logea SafeMode o normal",
      any(kw in l for l in output_lines
          for kw in ("SAFE MODE", "NORMAL", "INFO", "WARN")))

# ─── 7. Modelos ONNX cargables ────────────────────────────────────────────────

section("7. Modelos ONNX (carga cv2.dnn)")

for model_name, path in [
    ("yolov8n.onnx",     "/usr/share/olympus/models/yolov8n.onnx"),
    ("yolov8n-seg.onnx", "/usr/share/olympus/models/yolov8n-seg.onnx"),
]:
    if not os.path.exists(path):
        check(f"  {model_name} cargable", False, "archivo no encontrado")
        continue
    try:
        import cv2
        net = cv2.dnn.readNetFromONNX(path)
        n_layers = len(net.getLayerNames())
        check(f"  {model_name} cargable", n_layers > 0, f"{n_layers} capas")
    except Exception as e:
        check(f"  {model_name} cargable", False, str(e))

# ─── Resumen ──────────────────────────────────────────────────────────────────

section("Resumen")
passed = sum(results)
total  = len(results)
print(f"\n  {passed}/{total} checks pasados\n")

if passed == total:
    print(f"  ✓ Imagen lista para operación\n")
    sys.exit(0)
else:
    failed = total - passed
    print(f"  ✗ {failed} check(s) fallaron — revisar antes de flashear\n")
    sys.exit(1)
