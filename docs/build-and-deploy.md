# Build y Deploy de la Imagen Olympus

## Requisitos

- VM Linux con al menos 100 GB de disco y 8 GB RAM
- Git, Python 3, build-essential instalados
- Cuenta GCP con `gcloud` configurado (para deploy remoto)
- `bmaptool` instalado en la máquina local (para flashear SD)

---

## 1. Preparar el entorno

Clona el repositorio y ejecuta el script de configuración:

```bash
git clone https://github.com/Alonso11/olympus-hlc-rpi5.git
cd olympus-hlc-rpi5
./scripts/setup-env.sh
```

El script clona automáticamente todas las capas externas necesarias:
- poky (scarthgap)
- meta-raspberrypi
- meta-openembedded

---

## 2. Inicializar el entorno de Yocto

```bash
source layers/poky/oe-init-build-env build
```

Esto configura las variables de entorno y sitúa el shell en el directorio `build/`.

---

## 3. Compilar la imagen completa

```bash
bitbake olympus-image
```

La primera compilación puede tardar varias horas dependiendo del hardware.
Las compilaciones sucesivas usan sstate-cache y son mucho más rápidas.

La imagen generada se encuentra en:
```
build/tmp/deploy/images/raspberrypi5/
```

### Compilar una receta individual (para pruebas)

```bash
bitbake python3-rover-bridge
bitbake resize-rootfs
bitbake wifi-power-save
```

---

## 4. Descargar la imagen desde la VM (GCP)

Desde tu máquina local, ejecuta el script de deploy:

```bash
~/deploy-olympus-image.sh
# Descarga en ./olympus-image/ por defecto

# O especifica destino:
~/deploy-olympus-image.sh ~/Downloads/olympus
```

El script usa `gcloud compute scp` para transferir los archivos `.wic.bz2`
desde la VM `instance-20260309-151629` (zona `us-central1-a`).

---

## 5. Flashear la imagen en la microSD

Conecta la microSD a tu máquina local (aparece como `/dev/sdb`).

```bash
sudo ~/flash-olympus-image.sh
# Con defaults: imagen en ./olympus-image, destino /dev/sdb

# O especifica rutas:
sudo ~/flash-olympus-image.sh ~/Downloads/olympus /dev/sdb
```

El script:
1. Verifica que el dispositivo existe
2. Pide confirmación antes de borrar
3. Desmonta las particiones automáticamente
4. Usa `bmaptool` si está disponible (más rápido), o `dd` como fallback

> **Instalar bmaptool:**
> ```bash
> sudo apt install bmap-tools -y
> ```

---

## 6. Primer arranque en la RPi5

1. Inserta la microSD en la RPi5
2. Conecta el Arduino Mega por USB
3. Enciende la RPi5
4. En el primer arranque, `resize-rootfs.service` expande la partición root
   automáticamente (solo ocurre una vez, controlado por flag en `/var/lib/misc/resize-rootfs.done`)
5. Conéctate por SSH:
   ```bash
   ssh root@<IP_RPi5>
   # Sin contraseña (debug-tweaks habilitado)
   ```

---

## Referencia de archivos de configuración

| Archivo | Descripción |
|---------|-------------|
| `build/conf/local.conf` | MACHINE, RPI_EXTRA_CONFIG, powersave |
| `build/conf/bblayers.conf` | Stack de capas activas |
| `scripts/setup-env.sh` | Clona capas externas |
| `layers/meta-olympus/` | Capa personalizada (prioridad 10) |

---

## Branches del repositorio

| Branch | Descripción |
|--------|-------------|
| `main` | Base estable inicial — comunicación UART básica |
| `layer-rover-control` | Branch activo — HLC completo (MSM, visión, YAML config) |
| `sensor-integration` | Legacy — HC-SR04 en GPIO RPi5 (superado por `layer-rover-control`) |
| `csi-camera` | Legacy — soporte cámara CSI inicial (superado por `layer-rover-control`) |
