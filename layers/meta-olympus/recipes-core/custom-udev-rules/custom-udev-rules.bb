SUMMARY = "Reglas Udev personalizadas para Arduino Mega"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://99-arduino.rules"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/udev/rules.d
    install -m 0644 ${WORKDIR}/99-arduino.rules ${D}${sysconfdir}/udev/rules.d/99-arduino.rules
}

FILES:${PN} += "${sysconfdir}/udev/rules.d/99-arduino.rules"
