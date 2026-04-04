#!/usr/bin/env python3
"""
debug_view.py — Visor local del stream de visión via SSH pipe.

Corre en el PC. Lee frames JPEG de stdin (escritos por debug_vision.py en el RPi5)
y los muestra en una ventana con cv2.imshow.

Protocolo de pipe:
  [4 bytes big-endian: longitud JPEG] [N bytes JPEG]

Uso:
  ssh pi@rpi5 "python3 /opt/olympus/debug_vision.py --mode seg" | python3 debug_view.py

Presionar 'q' o cerrar la ventana para salir.

Dependencias PC: opencv-python
  pip install opencv-python
"""

import struct
import sys


def read_exact(stream, n: int) -> bytes:
    """Lee exactamente n bytes de stream. Retorna bytes vacío si EOF."""
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return b""
        buf += chunk
    return buf


def main():
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("[ERROR] OpenCV no encontrado. Instalar con: pip install opencv-python")
        sys.exit(1)

    stdin = sys.stdin.buffer
    window = "Olympus Vision Debug (q para salir)"
    frame_count = 0

    print("[debug_view] Esperando frames... (Ctrl+C o 'q' para salir)")

    while True:
        # Leer cabecera de 4 bytes
        header = read_exact(stdin, 4)
        if not header:
            print("[debug_view] Stream terminado (EOF).")
            break

        length = struct.unpack(">I", header)[0]
        if length == 0 or length > 10_000_000:
            print(f"[debug_view] Longitud inválida: {length}, abortando.")
            break

        # Leer JPEG
        data = read_exact(stdin, length)
        if not data:
            print("[debug_view] Stream cortado leyendo frame, EOF.")
            break

        # Decodificar y mostrar
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            print(f"[debug_view] frame={frame_count} — fallo al decodificar JPEG, saltando.")
            frame_count += 1
            continue

        frame_count += 1
        try:
            cv2.imshow(window, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[debug_view] Saliendo por tecla 'q'.")
                break
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                print("[debug_view] Ventana cerrada.")
                break
        except cv2.error as e:
            print(f"[debug_view] Sin soporte de display: {e}")
            print("[debug_view] Instalar opencv-python (no headless): pip install opencv-python")
            break

    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass
    print(f"[debug_view] Total frames recibidos: {frame_count}")


if __name__ == "__main__":
    main()
