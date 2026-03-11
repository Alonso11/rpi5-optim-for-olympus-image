use std::io::{BufRead, BufReader, Write};
use std::time::Duration;
use anyhow::{Context, Result};
use serialport;

fn main() -> Result<()> {
    // 1. Configurar UART (Arduino via Regla Udev = /dev/arduino_mega)
    let port_name = "/dev/arduino_mega";
    let baud_rate = 115_200;

    println!("Iniciando Rover High-Level Controller en {}...", port_name);

    let mut port = serialport::new(port_name, baud_rate)
        .timeout(Duration::from_millis(100))
        .open()
        .context(format!("No se pudo abrir el puerto {}", port_name))?;

    let mut reader = BufReader::new(port.try_clone()?);
    let mut buffer = String::new();

    // 2. Enviar saludo inicial (Handshake)
    println!("Enviando handshake al Arduino Mega...");
    port.write_all(b"HELO:RPi5\n")?;

    // 3. Loop principal (Estrategia: Reactiva)
    loop {
        // A. Intentar leer telemetría o respuestas del Arduino
        if reader.read_line(&mut buffer).is_ok() {
            if !buffer.is_empty() {
                println!("[Arduino -> RPi]: {}", buffer.trim());
                buffer.clear();
            }
        }

        // B. Simular el envío de comandos (ej: cada 2 seg)
        // Aquí podrías integrar un servidor web o una IA más adelante
        println!("Ordenando al rover: AVANZAR...");
        port.write_all(b"MOVE:FWD:100\n")?;
        
        std::thread::sleep(Duration::from_secs(2));

        println!("Ordenando al rover: DETENER...");
        port.write_all(b"MOVE:STP:0\n")?;
        
        std::thread::sleep(Duration::from_secs(1));
    }
}
