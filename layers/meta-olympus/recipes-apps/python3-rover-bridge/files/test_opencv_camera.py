#!/usr/bin/env python3
# Version: v1.2
# RPi5/pisp cameras cannot be opened via cv2.VideoCapture + V4L2 directly.
# This script uses rpicam-still (single JPEG capture to stdout) which works
# reliably without pipe-buffering issues from rpicam-vid.
import cv2
import numpy as np
import subprocess
import os

FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

def capture_frame():
    """Capture one JPEG frame via rpicam-still, return BGR numpy array or None."""
    result = subprocess.run(
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
    frame = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return frame

def main():
    print("--- Test de Cámara CSI + OpenCV (RPi 5) ---")
    print("[INFO] Capturando frame con rpicam-still...")

    frame = capture_frame()

    if frame is None:
        print("[ERROR] No se pudo capturar el frame.")
        return

    raw_path   = "camera_test_raw.jpg"
    edges_path = "camera_test_edges.jpg"

    cv2.imwrite(raw_path, frame)
    print(f"[OK] Frame guardado en: {os.path.abspath(raw_path)}")

    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    cv2.imwrite(edges_path, edges)
    print("[OK] Detección de bordes (Canny) guardada.")
    print("Test finalizado.")

if __name__ == "__main__":
    main()
