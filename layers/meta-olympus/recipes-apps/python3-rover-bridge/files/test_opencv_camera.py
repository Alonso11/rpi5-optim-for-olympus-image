#!/usr/bin/env python3
# Version: v1.1
# RPi5/pisp cameras cannot be opened via cv2.VideoCapture + V4L2 directly.
# This script uses rpicam-vid (MJPEG over stdout) to capture a test frame.
import cv2
import numpy as np
import subprocess
import os

FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

def read_one_frame(proc):
    buf = b""
    while True:
        chunk = proc.stdout.read(4096)
        if not chunk:
            return None
        buf += chunk
        start = buf.find(b"\xff\xd8")
        end   = buf.find(b"\xff\xd9", start + 2 if start != -1 else 0)
        if start != -1 and end != -1:
            jpg = buf[start:end + 2]
            frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            return frame

def main():
    print("--- Test de Cámara CSI + OpenCV (RPi 5) ---")

    cmd = [
        "rpicam-vid",
        "--codec", "mjpeg",
        "--output", "-",
        "--width",  str(FRAME_WIDTH),
        "--height", str(FRAME_HEIGHT),
        "--framerate", "10",
        "--timeout", "3000",
        "--nopreview",
    ]

    print("[INFO] Iniciando rpicam-vid (3s)...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    frame = read_one_frame(proc)
    proc.terminate()
    proc.wait()

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
