# Load overlays for both supported CSI cameras so either can be connected.
# Each dtoverlay must be on its own line in config.txt — RPI_EXTRA_CONFIG uses
# += which joins with spaces, so we embed newlines via a Python expression.
# camera_auto_detect=0: generic modules (no EEPROM) are not auto-detected;
# explicit dtoverlays are required.
# RPI_EXTRA_CONFIG must be set here (rpi-config scope), not in the image recipe.
RPI_EXTRA_CONFIG += "${@'dtoverlay=imx219\ndtoverlay=ov5647'}"

# meta-raspberrypi appends camera_auto_detect=1 via its own RPI_EXTRA_CONFIG
# after ours, overriding our setting. We strip all occurrences in do_install
# and append camera_auto_detect=0 last so it is the definitive value.
do_install:append() {
    sed -i '/camera_auto_detect/d' ${D}${BOOTFILES_DIR}/config.txt
    echo "camera_auto_detect=0" >> ${D}${BOOTFILES_DIR}/config.txt
}
