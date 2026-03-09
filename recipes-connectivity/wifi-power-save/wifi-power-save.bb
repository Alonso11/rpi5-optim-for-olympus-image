SUMMARY = "Activar ahorro de energia WiFi al arranque"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/files/common-licenses/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wifi-power-save.sh"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/init.d
    install -m 0755 wifi-power-save.sh ${D}${sysconfdir}/init.d/wifi-power-save
}

inherit update-rc.d

INITSCRIPT_NAME = "wifi-power-save"
INITSCRIPT_PARAMS = "defaults 99"
