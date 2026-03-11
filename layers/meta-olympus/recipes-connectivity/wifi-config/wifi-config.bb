SUMMARY = "Configuración automática de WiFi para Olympus Image"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wpa_supplicant-wlan0.conf"

S = "${WORKDIR}"

inherit systemd

# Aseguramos que wpa_supplicant esté presente
RDEPENDS:${PN} += "wpa-supplicant"

do_install() {
    # 1. Crear directorios de destino
    install -d ${D}${sysconfdir}/wpa_supplicant
    
    # 2. Instalar el archivo de configuración con permisos restringidos
    install -m 0600 ${WORKDIR}/wpa_supplicant-wlan0.conf ${D}${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf
}

# Habilitar el servicio systemd de wpa_supplicant para wlan0
SYSTEMD_SERVICE:${PN} = "wpa_supplicant@wlan0.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

FILES:${PN} += "${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf"
