#!/usr/bin/env python3
# Version: v1.0
import rover_bridge
import time
import sys

def main():
    print("--- Test de Sensor Ultrasónico (RPi 5 + Rust Bridge) ---")
    
    # 1. Inicializar el Rover (necesita el puerto serie del Arduino)
    try:
        # Usamos /dev/arduino_mega o un puerto ficticio para la prueba si no está conectado
        rover = rover_bridge.Rover("/dev/arduino_mega", 115200)
        print("[OK] Conexión con el puente de Rust establecida.")
    except Exception as e:
        print(f"[ERROR] No se pudo inicializar el bridge: {e}")
        sys.exit(1)

    # 2. Configurar pines del HC-SR04 (Usa números GPIO físicos/BCM)
    # Cambia estos números según tu cableado físico
    TRIGGER_PIN = 23 
    ECHO_PIN = 24
    
    try:
        res = rover.setup_ultrasonic(TRIGGER_PIN, ECHO_PIN)
        print(f"[OK] {res}")
    except Exception as e:
        print(f"[ERROR] Error al configurar GPIO: {e}")
        sys.exit(1)

    print(f"\nIniciando mediciones en pines Trig={TRIGGER_PIN}, Echo={ECHO_PIN}...")
    print("Presiona Ctrl+C para detener.\n")

    try:
        while True:
            # Medir distancia a través del bridge de Rust
            distancia = rover.get_ultrasonic_distance()
            
            if distancia is not None:
                print(f"Distancia: {distancia:6.2f} mm", end='\r')
            else:
                print("Fuera de rango o sin eco...       ", end='\r')
            
            time.sleep(0.1) # 10Hz es suficiente para evitar interferencias
            
    except KeyboardInterrupt:
        print("\n\nTest finalizado por el usuario.")

if __name__ == "__main__":
    main()
