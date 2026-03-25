#!/usr/bin/env python3
# Version: v0.1
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
import sys
import time
import rover_bridge

# ─── Constants ───────────────────────────────────────────────────────────────

PING_INTERVAL_S   = 1.0    # Max seconds between commands before sending PING
FRAME_WIDTH       = 640
FRAME_HEIGHT      = 480
VISION_CONF_MIN   = 0.5    # Minimum detection confidence to act on
VISION_AREA_MIN   = 0.05   # Min bbox area as fraction of frame to act on

# Frame zones for avoidance decision (fractions of FRAME_WIDTH)
ZONE_LEFT_END     = 0.33   # 0–33%  → obstacle left  → AVD:R
ZONE_RIGHT_START  = 0.67   # 67–100% → obstacle right → AVD:L
# Center zone (33–67%) → RET

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


# ─── Main loop ───────────────────────────────────────────────────────────────

def run(rover, source, mode):
    print(f"\n[Controller] Starting in {mode.upper()} mode. Ctrl+C to stop.\n")
    last_cmd_time = 0.0

    try:
        while True:
            cmd = source.next_command()

            # Vision mode: camera error → safe stop
            if cmd is None and mode == "vision":
                print("[Controller] Camera error — sending STB")
                cmd = "STB"

            if cmd is not None:
                try:
                    response = rover.send_command(cmd)
                    print(f"  {cmd:<16} → {response}")
                    last_cmd_time = time.monotonic()
                except TimeoutError as e:
                    print(f"  [TIMEOUT] {e}")
                except Exception as e:
                    print(f"  [ERROR] {e}")

            # Keepalive: PING if no command sent in the last PING_INTERVAL_S
            if time.monotonic() - last_cmd_time >= PING_INTERVAL_S:
                try:
                    response = rover.send_command("PING")
                    print(f"  {'PING':<16} → {response}")
                    last_cmd_time = time.monotonic()
                except Exception as e:
                    print(f"  [PING ERROR] {e}")

            # In vision mode sleep briefly between frames
            if mode == "vision":
                time.sleep(0.05)  # ~20 Hz max loop rate

    except (KeyboardInterrupt, SystemExit):
        print("\n[Controller] Stopping — sending STB...")
        try:
            rover.send_command("STB")
        except Exception:
            pass


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
    args = parser.parse_args()

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
        run(rover, source, args.mode)
    finally:
        if isinstance(source, VisionSource):
            source.release()


if __name__ == "__main__":
    main()
