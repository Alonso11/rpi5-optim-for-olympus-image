# Load one overlay per CSI port so either camera can be connected without
# changing config.txt. libcamera detects which sensor is physically present.
#   CAM0 (right connector) = CSI1 / 1f00110000 / i2c@88000
#   CAM1 (left connector)  = CSI0 / 1f00128000 / i2c@80000
# camera_auto_detect=0: generic modules have no EEPROM; explicit overlays required.
# RPI_EXTRA_CONFIG must be set here (rpi-config scope), not in the image recipe.
RPI_EXTRA_CONFIG += "${@'dtoverlay=imx219,cam0\ndtoverlay=ov5647,cam1'}"

# meta-raspberrypi appends camera_auto_detect=1 via its own RPI_EXTRA_CONFIG
# after ours, overriding our setting. We strip all occurrences in do_install
# and append camera_auto_detect=0 last so it is the definitive value.
do_install:append() {
    config_file=$(find ${D} -name "config.txt" 2>/dev/null | head -n 1)
    if [ -n "$config_file" ]; then
        sed -i '/camera_auto_detect/d' "$config_file"
        echo "camera_auto_detect=0" >> "$config_file"
    fi
}
