#!/usr/bin/env python3
import serial
import time
import sys

# Configuración del puerto USB (Arduino Mega vía regla Udev)
SERIAL_PORT = '/dev/arduino_mega'
BAUD_RATE = 115200

def send_command(ser, cmd):
    print(f"Enviando: {cmd}")
    ser.write(f"{cmd}\n".encode('utf-8'))

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Esperar a que el Arduino reinicie tras abrir el puerto
        print(f"Conectado a {SERIAL_PORT} a {BAUD_RATE} baudios.")
    except Exception as e:
        print(f"Error al abrir el puerto: {e}")
        sys.exit(1)

    print("\n--- Rover Remote Control Console ---")
    print("1: Mover 5 segundos (FWD:100)")
    print("2: Mover continuamente (FWD:100)")
    print("3: Parar (STOP)")
    print("q: Salir")

    while True:
        choice = input("\nSeleccione comando: ").lower()
        
        if choice == '1':
            send_command(ser, "F")
            print("Esperando 5 segundos...")
            time.sleep(5)
            send_command(ser, "S")
        elif choice == '2':
            send_command(ser, "F")
        elif choice == '3':
            send_command(ser, "S")
        elif choice == 'q':
            send_command(ser, "S")
            ser.close()
            break
        else:
            print("Comando no reconocido.")

if __name__ == "__main__":
    main()
