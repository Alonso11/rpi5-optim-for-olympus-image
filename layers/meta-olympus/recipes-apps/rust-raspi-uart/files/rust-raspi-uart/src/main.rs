use std::io::{self, Write};
use std::time::Duration;
use serialport;

fn main() {
    let port_name = "/dev/arduino_mega";
    let baud_rate = 9600;

    let mut port = serialport::new(port_name, baud_rate)
        .timeout(Duration::from_millis(10))
        .open()
        .expect("Fallo al abrir el puerto serial");

    let output = b"OLYMPUS_HELLO_ARDUINO\n";
    
    loop {
        match port.write_all(output) {
            Ok(_) => println!("Mensaje enviado al Arduino Mega via UART"),
            Err(ref e) if e.kind() == io::ErrorKind::TimedOut => (),
            Err(e) => eprintln!("{:?}", e),
        }
        std::thread::sleep(Duration::from_secs(5));
    }
}
