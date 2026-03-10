SUMMARY = "Rover High-Level Controller (HLC) en Rust para RPi5"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Incluimos el código local
SRC_URI = "file://rover-hlc/"

S = "${WORKDIR}/rover-hlc"

inherit cargo

# Asegurar que se instale el binario en /usr/bin de la RPi5
do_install:append() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/target/${CARGO_TARGET_SUBDIR}/rover-hlc ${D}${bindir}/rover-hlc
}
