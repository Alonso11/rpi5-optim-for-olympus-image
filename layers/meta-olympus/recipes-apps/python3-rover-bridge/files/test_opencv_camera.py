#!/usr/bin/env python3
# Version: v1.0
import cv2
import time
import os

def main():
    print("--- Test de Cámara CSI + OpenCV (RPi 5) ---")
    
    # 1. Intentar abrir la cámara con el backend de libcamera (V4L2)
    # En RPi 5 con libcamera, usualmente se usa el índice 0 para la cámara principal
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        print("[ERROR] No se pudo abrir la cámara. Verifica que 'libcamera-hello' funcione.")
        return

    # 2. Configurar resolución (ejemplo: 640x480 para rapidez)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("[OK] Cámara iniciada. Capturando un frame de prueba...")
    
    # Dejar que la cámara ajuste la exposición (un par de segundos)
    time.sleep(2)
    
    ret, frame = cap.read()
    
    if ret:
        # Guardar el frame original
        output_path = "camera_test_raw.jpg"
        cv2.imwrite(output_path, frame)
        print(f"[OK] Frame guardado en: {os.path.abspath(output_path)}")
        
        # Probar procesamiento básico (detección de bordes Canny)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        cv2.imwrite("camera_test_edges.jpg", edges)
        print("[OK] Detección de bordes (Canny) realizada y guardada.")
    else:
        print("[ERROR] No se pudo capturar el frame.")

    cap.release()
    print("Test finalizado.")

if __name__ == "__main__":
    main()
