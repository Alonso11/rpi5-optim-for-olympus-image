#!/usr/bin/env python3
# Version: v1.3
# Olympus HLC — Main Controller
#
# Integrates the CSI camera (or manual operator input) with the Arduino MSM
# via rover_bridge. Two modes selectable at startup:
#
#   --mode vision   Camera + cv2.dnn (YOLOv8n ONNX) → MSM commands
#   --mode manual   Operator stdin → MSM commands
#
# In both modes the pipeline to the Arduino is identical:
#   source.next_command() → rover_bridge.send_command() → log response
#
# The Arduino watchdog fires ERR:WDOG → FAULT if no command arrives in ~2s.
# This loop sends PING every 1s when idle to keep the watchdog alive.
#
# Usage:
#   olympus_controller.py --mode manual
#   olympus_controller.py --mode vision --model /usr/share/olympus/models/yolov8n.onnx

import argparse
import dataclasses
import datetime
import enum
import logging
import logging.handlers
import os
import sys
import time
import rover_bridge

# ─── Constants ───────────────────────────────────────────────────────────────

PING_INTERVAL_S   = 1.0    # Max seconds between commands before sending PING
TLM_TIMEOUT_S     = 5.0    # Seconds without TLM → link loss → force STB (COMM-REQ-005)
CYCLE_WARN_MS     = 1500   # Umbral de advertencia de ciclo lento (RNF-001: ≤ 2000 ms)
CYCLE_LOG_PERIOD  = 50     # Cada cuántos ciclos loguear tiempo a DEBUG
RETREAT_DIST_MM   = 300    # Distancia táctica HLC para iniciar RET (> 200 mm del LLC)
MAX_WAYPOINTS     = 5      # Últimos N waypoints seguros a retener (SyRS-061)
BATT_WARN_MV      = 14000  # 3.5 V/celda × 4S Li-ion → advertir operador (EPS-REQ-001)
BATT_CRITICAL_MV  = 12800  # 3.2 V/celda × 4S Li-ion → forzar STB inmediato
FRAME_WIDTH       = 640
FRAME_HEIGHT      = 480
VISION_CONF_MIN   = 0.5    # Minimum detection confidence to act on
VISION_AREA_MIN   = 0.05   # Min bbox area as fraction of frame to act on

# Frame zones for avoidance decision (fractions of FRAME_WIDTH)
ZONE_LEFT_END     = 0.33   # 0–33%  → obstacle left  → AVD:R
ZONE_RIGHT_START  = 0.67   # 67–100% → obstacle right → AVD:L
# Center zone (33–67%) → RET

# ─── Telemetry Frame ─────────────────────────────────────────────────────────

@dataclasses.dataclass
class TlmFrame:
    """
    Frame de telemetría extendida emitido por el Arduino (~1 s).
    Formato: TLM:<SAF>:<STALL>:<TS>ms:<MV>mV:<MA>mA:<I0>:<I1>:<I2>:<I3>:<I4>:<I5>:<T>C:<B0>:<B1>:<B2>:<B3>:<B4>:<B5>C:<DIST>mm
    (Ref. ICD LLC §Frame de telemetría extendida, SyRS-030)
    """
    safety:     str        # "NORMAL" | "WARN" | "LIMIT" | "FAULT"
    stall_mask: int        # 6 bits: bit5=FR … bit0=RL
    tick_ms:    int        # ms desde boot del Arduino (contador monotónico)
    batt_mv:    int        # tensión batería en mV  (0 = sin lectura)
    batt_ma:    int        # corriente batería en mA con signo (0 = sin lectura)
    currents:   list       # [FR, FL, CR, CL, RR, RL] mA
    temp_c:     int        # temperatura ambiente °C
    batt_temps: list       # [B1a, B1b, B2a, B2b, B3a, B3b] °C
    dist_mm:    int        # distancia ToF en mm (0 = sin lectura)

    @staticmethod
    def parse(raw: str):
        """
        Parsea un frame TLM crudo (sin el \\n final).
        Retorna TlmFrame o None si el formato no es válido.

        Ejemplo:
          TLM:NORMAL:000000:12340ms:11800mV:2350mA:200:210:195:205:180:190:24C:25:25:26:26:25:25C:450mm
        """
        # Índices de los campos tras split(':'):
        # 0=TLM 1=SAF 2=STALL 3=TSms 4=MVmV 5=MAma
        # 6..11=I0-I5  12=TC  13..17=B0-B4  18=B5C  19=DISTmm
        try:
            parts = raw.split(":")
            if len(parts) != 20 or parts[0] != "TLM":
                return None

            safety     = parts[1]
            stall_mask = int(parts[2], 2)          # "000101" → int
            tick_ms    = int(parts[3].rstrip("ms"))
            batt_mv    = int(parts[4].rstrip("mV"))
            batt_ma    = int(parts[5].rstrip("mA"))
            currents   = [int(parts[i]) for i in range(6, 12)]
            temp_c     = int(parts[12].rstrip("C"))
            batt_temps = [int(parts[i]) for i in range(13, 18)] + \
                         [int(parts[18].rstrip("C"))]
            dist_mm    = int(parts[19].rstrip("mm"))

            return TlmFrame(
                safety=safety, stall_mask=stall_mask, tick_ms=tick_ms,
                batt_mv=batt_mv, batt_ma=batt_ma, currents=currents,
                temp_c=temp_c, batt_temps=batt_temps, dist_mm=dist_mm,
            )
        except (ValueError, IndexError):
            return None


# ─── Waypoint Tracker ────────────────────────────────────────────────────────

@dataclasses.dataclass
class Waypoint:
    """Instantánea de un punto seguro registrado durante exploración (SyRS-061)."""
    tick_ms: int          # timestamp Arduino en ms (contador monotónico del firmware)
    state:   object       # RoverState en el momento del registro
    dist_mm: int          # distancia frontal ToF en mm
    batt_mv: int          # tensión batería en mV


class WaypointTracker:
    """
    Registra los últimos MAX_WAYPOINTS puntos seguros visitados durante EXPLORE
    con safety NORMAL (SyRS-061). Detecta condiciones tácticas de retreat a nivel
    HLC antes de que el Arduino dispare el FAULT de emergencia.

    Capas de protección de distancia:
      LLC (hardware):  < 200 mm (HC-SR04) o < 150 mm (VL53L0X) → FAULT inmediato
      HLC (táctica):   < RETREAT_DIST_MM (300 mm)               → RET proactivo
    """

    def __init__(self, max_waypoints: int = MAX_WAYPOINTS,
                 retreat_dist_mm: int = RETREAT_DIST_MM):
        self._points: list        = []
        self._max: int            = max_waypoints
        self._retreat_dist: int   = retreat_dist_mm

    # ── registro ─────────────────────────────────────────────────────────────

    def record(self, tlm, msm_state) -> None:
        """
        Guarda un waypoint si el rover está en EXPLORE con safety NORMAL.
        Mantiene como máximo MAX_WAYPOINTS entradas (FIFO).
        """
        if getattr(msm_state, "value", None) != "EXP":
            return
        if tlm.safety != "NORMAL":
            return
        wp = Waypoint(
            tick_ms=tlm.tick_ms,
            state=msm_state,
            dist_mm=tlm.dist_mm,
            batt_mv=tlm.batt_mv,
        )
        self._points.append(wp)
        if len(self._points) > self._max:
            self._points.pop(0)

    # ── consulta ─────────────────────────────────────────────────────────────

    def last_safe(self):
        """Retorna el waypoint seguro más reciente, o None si no hay ninguno."""
        return self._points[-1] if self._points else None

    def count(self) -> int:
        return len(self._points)

    def should_retreat(self, tlm) -> bool:
        """
        True si la distancia frontal es menor que el umbral táctico HLC
        y hay una lectura válida (dist_mm > 0).
        Solo activo cuando dist_mm > 0 (0 = sin lectura del VL53L0X).
        """
        return tlm.dist_mm > 0 and tlm.dist_mm < self._retreat_dist


# ─── Energy Monitor ──────────────────────────────────────────────────────────

class EnergyLevel(enum.Enum):
    OK       = "OK"
    WARN     = "WARN"
    CRITICAL = "CRITICAL"


class EnergyMonitor:
    """
    Supervisa tensión de batería desde frames TLM (EPS-REQ-001, SyRS-017).
    Solo logea al cambiar de nivel para no saturar el log.

    Umbrales para batería 4S Li-ion:
      OK       : batt_mv ≥ BATT_WARN_MV
      WARN     : BATT_CRITICAL_MV ≤ batt_mv < BATT_WARN_MV
      CRITICAL : batt_mv < BATT_CRITICAL_MV  → forzar STB
    """

    def __init__(self,
                 warn_mv: int     = BATT_WARN_MV,
                 critical_mv: int = BATT_CRITICAL_MV):
        self._warn_mv:     int         = warn_mv
        self._critical_mv: int         = critical_mv
        self._level:       EnergyLevel = EnergyLevel.OK

    @property
    def level(self) -> EnergyLevel:
        return self._level

    def update(self, tlm) -> EnergyLevel:
        """
        Evalúa batt_mv del TLM y actualiza el nivel.
        Retorna el nivel resultante.
        batt_mv == 0 significa sin lectura — se ignora sin cambiar el nivel.
        """
        mv = tlm.batt_mv
        if mv == 0:
            return self._level

        if mv < self._critical_mv:
            new_level = EnergyLevel.CRITICAL
        elif mv < self._warn_mv:
            new_level = EnergyLevel.WARN
        else:
            new_level = EnergyLevel.OK

        self._level = new_level
        return self._level


# ─── Logger ──────────────────────────────────────────────────────────────────

class OlympusLogger:
    """
    Logger estructurado con timestamps ISO-8601 (SRS-061, CDH-REQ-002).
    Escribe a stdout y a LOG_PATH con rotación automática por tamaño.

    Política de rotación (CDH-REQ-002 — ~2 h de retención mínima):
      _MAX_BYTES    = 5 MB  → ~3–4 h de logs a ciclo 1 s
      _BACKUP_COUNT = 1     → hlc.log + hlc.log.1 ≈ 7–8 h en disco

    Si el archivo no es accesible, continúa solo con stdout sin abortar.
    """

    DEFAULT_LOG_PATH = "/var/log/olympus/hlc.log"
    _MAX_BYTES       = 5_000_000   # ~3–4 h de logs típicos
    _BACKUP_COUNT    = 1           # un fichero de respaldo → ~7–8 h total en disco

    def __init__(self, log_path: str = DEFAULT_LOG_PATH):
        self._handler = None
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self._handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self._MAX_BYTES,
                backupCount=self._BACKUP_COUNT,
                encoding="utf-8",
            )
            self._handler.setFormatter(logging.Formatter("%(message)s"))
        except OSError as e:
            print(f"[Logger] Warning: no se puede abrir {log_path}: {e} — solo stdout")

    # ── escritura interna ────────────────────────────────────────────────────

    def _write(self, level: str, component: str, msg: str) -> None:
        ts   = datetime.datetime.now().isoformat(timespec="milliseconds")
        line = f"[{ts}] [{level:<5}] [{component:<7}] {msg}"
        print(line)
        if self._handler:
            self._handler.emit(logging.makeLogRecord({"msg": line}))

    # ── API pública ──────────────────────────────────────────────────────────

    def info(self, component: str, msg: str) -> None:
        self._write("INFO", component, msg)

    def warn(self, component: str, msg: str) -> None:
        self._write("WARN", component, msg)

    def log_transition(self, from_state, to_state, reason: str,
                       warn: bool = False) -> None:
        """
        Auditoría de transición de estado MSM (SRS-061).
        Registra estado_origen, estado_destino, razón y timestamp.
        """
        level = "WARN" if warn else "INFO"
        self._write(level, "MSM",
                    f"{from_state.value} → {to_state.value}  [{reason}]")

    def log_cmd(self, cmd: str, kind: str, data) -> None:
        """Log del comando enviado y la respuesta recibida del Arduino."""
        resp = f"{data}" if data else kind.upper()
        self._write("INFO", "CMD", f"{cmd:<16} → {kind}:{resp}" if data
                    else f"{cmd:<16} → {kind}")

    def log_tlm(self, tlm) -> None:
        """Log compacto del frame TLM recibido (SyRS-030)."""
        self._write("INFO", "TLM",
                    f"{tlm.safety:<6} stall={tlm.stall_mask:06b} "
                    f"batt={tlm.batt_mv}mV/{tlm.batt_ma}mA "
                    f"dist={tlm.dist_mm}mm t={tlm.tick_ms}ms")

    def log_energy(self, level, batt_mv: int) -> None:
        """Log de cambio de nivel de energía (EPS-REQ-001)."""
        lvl_str = level.value if hasattr(level, 'value') else str(level)
        msg = f"batería {batt_mv} mV — nivel {lvl_str}"
        if lvl_str == "CRITICAL":
            self._write("ERROR", "EPS", msg)
        elif lvl_str == "WARN":
            self._write("WARN",  "EPS", msg)
        else:
            self._write("INFO",  "EPS", msg)

    def log_cycle(self, cycle_ms: float) -> None:
        """Log periódico de tiempo de ciclo para verificación de RNF-001."""
        self._write("DEBUG", "CYCLE", f"{cycle_ms:.1f} ms")

    def close(self) -> None:
        if self._handler:
            self._handler.close()
            self._handler = None


# ─── Rover State Machine ─────────────────────────────────────────────────────

class RoverState(enum.Enum):
    STANDBY = "STB"
    EXPLORE = "EXP"
    AVOID   = "AVD"
    RETREAT = "RET"
    FAULT   = "FLT"

    @staticmethod
    def from_ack(label: str):
        for s in RoverState:
            if s.value == label:
                return s
        return None


class RoverMSM:
    """
    Espejo local del estado MSM del Arduino (SyRS-060, SRS-061).

    Registra el estado actual y el tiempo de entrada para auditoría
    de transiciones. Solo hace transición al recibir un ACK confirmado
    del Arduino — nunca por inferencia del comando enviado.
    """

    def __init__(self):
        self._state:   RoverState = RoverState.STANDBY
        self._entered: float      = time.monotonic()

    @property
    def state(self) -> RoverState:
        return self._state

    def transition(self, new_state: RoverState) -> None:
        """Registra una transición confirmada por ACK del Arduino."""
        self._state   = new_state
        self._entered = time.monotonic()

    def time_in_state(self) -> float:
        """Segundos transcurridos en el estado actual."""
        return time.monotonic() - self._entered

    def blocks_command(self, cmd: str) -> bool:
        """
        True si el comando debe bloquearse en el estado actual.
        En FAULT solo RST y PING son válidos (ICD LLC §Tabla de estados).
        """
        if self._state == RoverState.FAULT:
            return cmd not in ("RST", "PING")
        return False


# ─── Command Sources ─────────────────────────────────────────────────────────

class ManualSource:
    """
    Reads MSM commands from stdin.
    Accepts shortcuts or full MSM protocol strings.

    Shortcuts:
      exp <l> <r>  →  EXP:<l>:<r>
      avl          →  AVD:L
      avr          →  AVD:R
      ret          →  RET
      stb          →  STB
      ping         →  PING
      rst          →  RST
      q            →  exit
    """

    def __init__(self):
        self._print_help()

    def _print_help(self):
        print("\n--- Olympus Controller — Manual Mode ---")
        print("Shortcuts: exp <l> <r> | avl | avr | ret | stb | ping | rst | q (quit)")
        print("Or type MSM commands directly: EXP:80:80 / AVD:L / RET / STB\n")

    def next_command(self):
        """
        Blocks until the operator enters a command.
        Returns the MSM command string, or None to skip this cycle.
        Raises SystemExit on 'q'.
        """
        try:
            raw = input("cmd> ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)

        if not raw:
            return None

        lower = raw.lower()

        if lower == "q":
            raise SystemExit(0)
        elif lower.startswith("exp "):
            parts = lower.split()
            if len(parts) == 3:
                return f"EXP:{parts[1]}:{parts[2]}"
            print("[!] Usage: exp <left_speed> <right_speed>  e.g. exp 80 80")
            return None
        elif lower == "avl":
            return "AVD:L"
        elif lower == "avr":
            return "AVD:R"
        elif lower == "ret":
            return "RET"
        elif lower == "stb":
            return "STB"
        elif lower == "ping":
            return "PING"
        elif lower == "rst":
            return "RST"
        else:
            # Pass through as-is (full MSM command)
            return raw.upper()


class VisionSource:
    """
    Reads frames from the CSI camera and decides MSM commands via cv2.dnn.
    Model: YOLOv8n exported to ONNX (opset 12).

    Frame capture uses rpicam-vid (MJPEG over stdout) instead of
    cv2.VideoCapture, because RPi5/pisp V4L2 nodes are raw CSI capture
    nodes that cannot be opened directly by OpenCV.

    Decision logic based on bounding box position in the frame:
      Left zone  (0–33%)   → AVD:R  (obstacle on left, turn right)
      Center zone (33–67%) → RET    (obstacle ahead, retreat)
      Right zone  (67–100%) → AVD:L  (obstacle on right, turn left)
      No detection          → EXP:60:60 (keep exploring)
    """

    def __init__(self, model_path):
        try:
            import cv2
            import numpy as np
            import subprocess
            self._cv2        = cv2
            self._np         = np
            self._subprocess = subprocess
        except ImportError:
            print("[ERROR] OpenCV not found. Install python3-opencv.")
            raise SystemExit(1)

        print(f"[Vision] Loading model: {model_path}")
        self._net = self._cv2.dnn.readNetFromONNX(model_path)
        print(f"[Vision] Model loaded — {len(self._net.getLayerNames())} layers")
        print("[Vision] Camera ready (rpicam-still per-frame capture).")

    def _capture_frame(self):
        """
        Capture one JPEG via rpicam-still --output -.
        Returns a BGR numpy array or None on error.
        rpicam-vid MJPEG stdout did not flush reliably on RPi5/pisp;
        rpicam-still is simpler and sufficient for ~1–2 Hz inference.
        """
        result = self._subprocess.run(
            [
                "rpicam-still",
                "--output", "-",
                "--width",  str(FRAME_WIDTH),
                "--height", str(FRAME_HEIGHT),
                "--timeout", "1000",
                "--nopreview",
                "--encoding", "jpg",
            ],
            capture_output=True,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        return self._cv2.imdecode(
            self._np.frombuffer(result.stdout, self._np.uint8),
            self._cv2.IMREAD_COLOR,
        )

    def next_command(self):
        """
        Captures a frame, runs inference, and returns an MSM command.
        Returns None on camera read error (caller will send STB).
        """
        frame = self._capture_frame()
        if frame is None:
            print("[Vision] Frame capture failed.")
            return None

        cmd = self._decide(frame)
        return cmd

    def _decide(self, frame):
        cv2 = self._cv2
        np  = self._np

        # Preprocess: resize to 640x640, normalize to [0,1]
        blob = cv2.dnn.blobFromImage(
            frame, 1 / 255.0, (640, 640), swapRB=True, crop=False
        )
        self._net.setInput(blob)
        output = self._net.forward()  # shape: (1, 84, 8400)

        # output[0] shape: (84, 8400) — 4 bbox coords + 80 class scores
        predictions = output[0].T     # → (8400, 84)
        frame_area  = FRAME_WIDTH * FRAME_HEIGHT

        best_area = 0.0
        best_cx   = None

        for pred in predictions:
            scores     = pred[4:]
            class_id   = int(np.argmax(scores))
            confidence = float(scores[class_id])

            if confidence < VISION_CONF_MIN:
                continue

            # bbox in [cx, cy, w, h] normalized to 640x640 input
            cx_norm, _cy_norm, w_norm, h_norm = pred[:4]
            cx = cx_norm / 640.0
            w  = w_norm  / 640.0
            h  = h_norm  / 640.0
            area_frac = w * h

            if area_frac < VISION_AREA_MIN:
                continue  # Too small / too far — ignore

            if area_frac > best_area:
                best_area = area_frac
                best_cx   = cx

        if best_cx is None:
            return "EXP:60:60"   # No obstacle — keep exploring

        if best_cx < ZONE_LEFT_END:
            return "AVD:R"       # Obstacle on left → turn right
        elif best_cx > ZONE_RIGHT_START:
            return "AVD:L"       # Obstacle on right → turn left
        else:
            return "RET"         # Obstacle center → retreat

    def release(self):
        pass  # No persistent process to clean up with rpicam-still


# ─── Response parser ─────────────────────────────────────────────────────────

# Kinds returned by parse_response():
#   "pong"        — PING keepalive reply
#   "ack"         — ACK:<STATE>  data = state string ("STB","EXP","AVD","RET","FLT")
#   "err_estop"   — ERR:ESTOP   rover is in FAULT, command rejected
#   "err_wdog"    — ERR:WDOG    watchdog fired, rover went to FAULT
#   "err_unknown" — ERR:UNKNOWN command not recognised by firmware
#   "unknown"     — unrecognised frame (data = raw string)

def parse_response(resp):
    if resp == "PONG":
        return ("pong", None)
    if resp.startswith("ACK:"):
        return ("ack", resp[4:])
    if resp == "ERR:ESTOP":
        return ("err_estop", None)
    if resp == "ERR:WDOG":
        return ("err_wdog", None)
    if resp == "ERR:UNKNOWN":
        return ("err_unknown", None)
    return ("unknown", resp)


# ─── Dry-run mock ────────────────────────────────────────────────────────────

class DryRunRover:
    """Simulates Arduino responses following the MSM protocol."""

    _CMD_TO_STATE = {
        "STB": "STB", "RET": "RET", "FLT": "FLT",
        "RST": "STB", "AVD:L": "AVD", "AVD:R": "AVD",
    }

    # Synthetic TLM emitted every ~1 s to avoid false link-loss warnings
    # during dry-run testing (recv_tlm returning None would trigger COMM-REQ-005
    # after TLM_TIMEOUT_S seconds, which is confusing when there is no real link).
    _TLM_INTERVAL_S = 1.0
    _TLM_TEMPLATE   = (
        "TLM:NORMAL:000000:{tick}ms:16000mV:500mA:"
        "100:100:100:100:100:100:25C:25:25:25:25:25:25C:1000mm"
    )

    def __init__(self):
        self._state        = "STB"
        self._tick_ms      = 0
        self._last_tlm_ts  = time.monotonic()

    def send_command(self, cmd):
        if cmd == "PING":
            return "PONG"
        if cmd.startswith("EXP:"):
            self._state = "EXP"
            return "ACK:EXP"
        new_state = self._CMD_TO_STATE.get(cmd)
        if new_state is not None:
            self._state = new_state
            return f"ACK:{new_state}"
        return "ERR:UNKNOWN"

    def recv_tlm(self):
        """
        Emits a synthetic TLM frame every _TLM_INTERVAL_S seconds so that
        the link-loss watchdog (TLM_TIMEOUT_S) does not fire during dry-run.
        Returns None between intervals, mimicking the async behaviour of the LLC.
        """
        now = time.monotonic()
        if now - self._last_tlm_ts >= self._TLM_INTERVAL_S:
            self._tick_ms     += int((now - self._last_tlm_ts) * 1000)
            self._last_tlm_ts  = now
            return self._TLM_TEMPLATE.format(tick=self._tick_ms)
        return None


# ─── Main loop ───────────────────────────────────────────────────────────────

def _send(rover, cmd, log=None):
    """
    Envía cmd, parsea respuesta, retorna (kind, data).
    Si se pasa log (OlympusLogger) registra el intercambio.
    Retorna ("timeout", None) o ("error", str) en caso de fallo.
    """
    try:
        raw = rover.send_command(cmd)
        kind, data = parse_response(raw)
        if log:
            log.log_cmd(cmd, kind, data)
        return kind, data
    except TimeoutError as e:
        if log:
            log.warn("CMD", f"{cmd:<16} → TIMEOUT: {e}")
        return "timeout", None
    except Exception as e:
        if log:
            log.warn("CMD", f"{cmd:<16} → ERROR: {e}")
        return "error", str(e)


def run(rover, source, mode, log_path=OlympusLogger.DEFAULT_LOG_PATH):
    log = OlympusLogger(log_path)
    log.info("CTRL", f"Starting in {mode.upper()} mode")

    last_cmd_time   = time.monotonic()
    last_tlm_time   = time.monotonic()
    tlm_loss_active = False
    msm             = RoverMSM()
    tracker         = WaypointTracker()
    energy          = EnergyMonitor()
    prev_energy     = EnergyLevel.OK
    cycle_count     = 0

    try:
        while True:
            cycle_start = time.monotonic()

            # Drenar TLM asíncrono pendiente antes de cualquier comando
            raw_tlm = rover.recv_tlm()
            tlm_override = None
            if raw_tlm:
                last_tlm_time = time.monotonic()
                if tlm_loss_active:
                    log.info("COMM", "TLM restablecido — enlace recuperado")
                    tlm_loss_active = False
                tlm = TlmFrame.parse(raw_tlm)
                if tlm:
                    log.log_tlm(tlm)
                    tracker.record(tlm, msm.state)

                    # Supervisión de energía — logea solo al cambiar de nivel
                    e_level = energy.update(tlm)
                    if e_level != prev_energy:
                        log.log_energy(e_level, tlm.batt_mv)
                        prev_energy = e_level

                    # Prioridad de override: CRITICAL > should_retreat
                    if e_level == EnergyLevel.CRITICAL:
                        log.warn("EPS", "batería crítica — forzando STB")
                        tlm_override = "STB"
                    elif tracker.should_retreat(tlm):
                        wp = tracker.last_safe()
                        wp_info = (f"last_safe tick={wp.tick_ms}ms dist={wp.dist_mm}mm"
                                   if wp else "no waypoint previo")
                        log.warn("NAV",
                                 f"obstáculo táctico a {tlm.dist_mm} mm "
                                 f"(< {RETREAT_DIST_MM} mm) — forzando RET "
                                 f"[{wp_info}]")
                        tlm_override = "RET"
            elif time.monotonic() - last_tlm_time > TLM_TIMEOUT_S:
                # Pérdida de enlace serie — forzar STB hasta recuperar TLM
                if not tlm_loss_active:
                    log.warn("COMM",
                             f"sin TLM por {TLM_TIMEOUT_S:.0f}+ s — "
                             f"forzando STB (COMM-REQ-005)")
                    tlm_loss_active = True
                tlm_override = "STB"

            cmd = tlm_override or source.next_command()

            # Vision mode: camera error → safe stop
            if cmd is None and mode == "vision":
                log.warn("CTRL", "Camera error — sending STB")
                cmd = "STB"

            if cmd is not None:
                if msm.blocks_command(cmd):
                    log.warn("CMD", f"{cmd:<16} → BLOCKED (rover in FAULT, send RST)")
                else:
                    kind, data = _send(rover, cmd, log)
                    last_cmd_time = time.monotonic()

                    if kind == "ack" and data is not None:
                        new_state = RoverState.from_ack(data)
                        if new_state is not None:
                            log.log_transition(msm.state, new_state, f"ACK:{data}")
                            msm.transition(new_state)
                    elif kind == "err_wdog":
                        log.log_transition(msm.state, RoverState.FAULT,
                                           "ERR:WDOG", warn=True)
                        msm.transition(RoverState.FAULT)
                        log.info("CTRL", "Auto-sending RST to recover from watchdog")
                        kind2, data2 = _send(rover, "RST", log)
                        if kind2 == "ack" and data2 is not None:
                            new_state = RoverState.from_ack(data2)
                            if new_state is not None:
                                log.log_transition(msm.state, new_state, "RST")
                                msm.transition(new_state)
                    elif kind == "err_estop":
                        log.log_transition(msm.state, RoverState.FAULT,
                                           "ERR:ESTOP", warn=True)
                        msm.transition(RoverState.FAULT)

            # Keepalive: PING if no command sent in the last PING_INTERVAL_S
            if time.monotonic() - last_cmd_time >= PING_INTERVAL_S:
                _send(rover, "PING", log)
                last_cmd_time = time.monotonic()

            # In vision mode sleep briefly between frames
            if mode == "vision":
                time.sleep(0.05)  # ~20 Hz max loop rate

            # Medición de ciclo (RNF-001: ≤ 2000 ms)
            cycle_ms = (time.monotonic() - cycle_start) * 1000
            cycle_count += 1
            if cycle_ms > CYCLE_WARN_MS:
                log.warn("CYCLE",
                         f"ciclo lento: {cycle_ms:.1f} ms "
                         f"(umbral {CYCLE_WARN_MS} ms, RNF-001)")
            elif cycle_count % CYCLE_LOG_PERIOD == 0:
                log.log_cycle(cycle_ms)

    except (KeyboardInterrupt, SystemExit):
        log.info("CTRL", "Stopping — sending STB")
        try:
            rover.send_command("STB")
        except Exception:
            pass
    finally:
        log.close()


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Olympus HLC Controller — vision or manual mode"
    )
    parser.add_argument(
        "--mode",
        choices=["vision", "manual"],
        required=True,
        help="Command source: 'vision' (camera+YOLOv8n) or 'manual' (stdin)"
    )
    parser.add_argument(
        "--model",
        default="/usr/share/olympus/models/yolov8n.onnx",
        help="Path to YOLOv8n ONNX model (vision mode only)"
    )
    parser.add_argument(
        "--port",
        default="/dev/arduino_mega",
        help="Serial port for Arduino (default: /dev/arduino_mega)"
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Arduino connection; print commands to stdout (testing without hardware)"
    )
    parser.add_argument(
        "--log-path",
        default=OlympusLogger.DEFAULT_LOG_PATH,
        help=f"Path for the HLC log file (default: {OlympusLogger.DEFAULT_LOG_PATH})"
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[Controller] DRY-RUN mode — Arduino not required.")
        rover = DryRunRover()
    else:
        print(f"[Controller] Connecting to Arduino on {args.port} @ {args.baud}...")
        try:
            rover = rover_bridge.Rover(args.port, args.baud)
            print("[Controller] Connected.")
        except Exception as e:
            print(f"[ERROR] Cannot open rover bridge: {e}")
            sys.exit(1)

    if args.mode == "manual":
        source = ManualSource()
    else:
        source = VisionSource(args.model)

    try:
        run(rover, source, args.mode, log_path=args.log_path)
    finally:
        if isinstance(source, VisionSource):
            source.release()


if __name__ == "__main__":
    main()
