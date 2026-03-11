SUMMARY = "Auto-resize RootFS for Raspberry Pi"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://resize-rootfs.sh \
           file://resize-rootfs.service"

S = "${WORKDIR}"

inherit systemd

# Herramientas necesarias para la expansion
RDEPENDS:${PN} += "parted e2fsprogs-resize2fs"

do_install() {
    # 1. Instalar el script en /usr/bin
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/resize-rootfs.sh ${D}${bindir}/resize-rootfs.sh

    # 2. Instalar el servicio de systemd
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/resize-rootfs.service ${D}${systemd_system_unitdir}/resize-rootfs.service
}

# Habilitar el servicio systemd
SYSTEMD_SERVICE:${PN} = "resize-rootfs.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

FILES:${PN} += "${bindir}/resize-rootfs.sh"
