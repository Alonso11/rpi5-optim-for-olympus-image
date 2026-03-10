SUMMARY = "Aplicacion Rust para comunicacion UART con Arduino Mega"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://rust-raspi-uart/"

S = "${WORKDIR}/rust-raspi-uart"

inherit cargo

# Asegurar que se instalen las dependencias necesarias de C para serialport si fuera necesario
# serialport en Linux no suele necesitar dependencias externas extras más que libc.

# Forzamos la instalación del binario en /usr/bin
do_install:append() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/target/${CARGO_TARGET_SUBDIR}/rust-raspi-uart ${D}${bindir}/rust-raspi-uart
}
