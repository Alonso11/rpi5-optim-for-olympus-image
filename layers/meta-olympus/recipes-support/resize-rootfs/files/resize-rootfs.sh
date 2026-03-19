#!/bin/sh
# Version: v1.1
# --- OLYMPUS: AUTO-RESIZE ROOTFS SCRIPT ---
# Este script expande la particion root al 100% de la SD.
# Usa un flag file para ejecutarse solo una vez.

DONE_FLAG="/var/lib/misc/resize-rootfs.done"

# Guard: si ya se expandio, salir sin hacer nada
if [ -f "$DONE_FLAG" ]; then
    echo "Particion ya expandida previamente. Omitiendo."
    exit 0
fi

ROOT_PART=$(mount | grep ' / ' | cut -d' ' -f1)
ROOT_DEV=$(echo $ROOT_PART | sed 's/p[0-9]//')
PART_NUM=$(echo $ROOT_PART | sed 's/.*p//')

echo "Expandiendo particion $ROOT_PART en disco $ROOT_DEV (Particion $PART_NUM)..."

# 1. Expandir la particion en la tabla de particiones (usando parted)
parted $ROOT_DEV --script "resizepart $PART_NUM 100%"

# 2. Informar al kernel del cambio
partprobe $ROOT_DEV

# 3. Expandir el sistema de archivos online (ext4)
resize2fs $ROOT_PART

# 4. Crear flag para evitar re-ejecucion en proximos arranques
mkdir -p $(dirname $DONE_FLAG)
touch $DONE_FLAG

echo "Expansion completada con exito."
