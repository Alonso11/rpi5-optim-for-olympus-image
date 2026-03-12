#!/usr/bin/env python3
import rover_bridge  # Este es el módulo compilado en Rust con PyO3
import time
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Olympus Bridge Debug Tool')
    parser.add_argument('--port', type=str, default='/dev/arduino_mega', help='Puerto serie (ej: /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    args = parser.parse_args()

    print(f"Probando el Puente Rust-Python (Olympus Bridge) en {args.port}...")
    
    # 1. Instanciar la clase Rover definida en Rust
    try:
        rover = rover_bridge.Rover(args.port, args.baud)
        print("Instancia de Rover creada en Rust correctamente.")
        print("Esperando 2 segundos para inicialización (DTR reset)...")
        time.sleep(2)
    except Exception as e:
        print(f"Error al crear el objeto Rover: {e}")
        print("Sugerencia: Prueba con --port /dev/ttyUSB0 o verifica permisos (sudo).")
        sys.exit(1)

    print("\n--- Control Manual del Rover (Rust Bridge) ---")
    print("Comandos comunes: F (Avanzar), B (Retroceder), L (Izquierda), R (Derecha), S (Parar)")
    print("O intenta el protocolo largo: MOVE:FWD:100")
    print("Escribe 'q' para salir.")

    while True:
        cmd = input("\nIngrese comando: ").strip()
        
        if cmd.lower() == 'q':
            print("Saliendo...")
            break
        
        if not cmd:
            continue

        try:
            print(f"Enviando '{cmd}' via Rust...")
            res = rover.send_command(cmd)
            print(f"Respuesta de Rust: {res}")
        except Exception as e:
            print(f"Error durante la comunicación: {e}")

if __name__ == "__main__":
    main()
