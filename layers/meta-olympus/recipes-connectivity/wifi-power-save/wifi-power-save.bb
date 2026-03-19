# Version: v1.0
SUMMARY = "Activar ahorro de energia WiFi al arranque (systemd)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/files/common-licenses/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wifi-power-save.sh \
           file://wifi-power-save.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "wifi-power-save.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/wifi-power-save.sh ${D}${bindir}/wifi-power-save.sh

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/wifi-power-save.service ${D}${systemd_system_unitdir}/wifi-power-save.service
}

FILES:${PN} += "${bindir}/wifi-power-save.sh"
