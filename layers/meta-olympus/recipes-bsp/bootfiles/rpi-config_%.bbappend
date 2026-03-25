# IMX219 third-party camera (no EEPROM): requires explicit dtoverlay.
# RPI_EXTRA_CONFIG must be set here (rpi-config scope), not in the image recipe.
RPI_EXTRA_CONFIG += "dtoverlay=imx219"
