#!/usr/bin/env python3
import rover_bridge  # Este es el módulo compilado en Rust con PyO3
import time
import sys

def main():
    print("Probando el Puente Rust-Python (Olympus Bridge)...")
    
    # 1. Instanciar la clase Rover definida en Rust
    # (/dev/ttyACM0 es el Arduino Mega vía USB)
    try:
        rover = rover_bridge.Rover("/dev/ttyACM0", 115200)
        print("Instancia de Rover creada en Rust correctamente.")
    except Exception as e:
        print(f"Error al crear el objeto Rover: {e}")
        sys.exit(1)

    # 2. Controlar el Rover usando el método en Rust
    try:
        print("\nMoviendo motor (Rust gestiona el puerto serie)...")
        res = rover.send_command("F")
        print(f"Respuesta de Rust: {res}")
        
        time.sleep(3)
        
        print("\nDeteniendo motor...")
        res = rover.send_command("S")
        print(f"Respuesta de Rust: {res}")
        
    except Exception as e:
        print(f"Error durante la comunicación: {e}")

if __name__ == "__main__":
    main()
