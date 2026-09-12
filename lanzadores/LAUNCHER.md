# Arrancar KAIZEN con doble clic

Para abrir el panel de KAIZEN **sin tocar la terminal**: doble clic en **`KAIZEN.lnk`**
(el icono del enso con el bambú).

## Dos modos

| Launcher | Modo | Qué hace |
|---|---|---|
| `Kaizen.cmd` (`KAIZEN.lnk`) | **Simulación** (`SOE_SIM=1`) | Sin red ni coste. Prospección/redacción devuelven ejemplos. Para mirar la interfaz. |
| `Kaizen-REAL.cmd` | **REAL** | Prospección y redacción usan **Claude de verdad** y la web (consume API, cuesta dinero). Necesita `ANTHROPIC_API_KEY` en `.env`. |

En el panel, el modo se ve en `http://127.0.0.1:8000/health` → `"sim": true/false`.

> En modo REAL, escribe una orden de prospección para ver algo real, p. ej.:
> `busca tiendas gourmet en Alicante`. Verás coste real en la tarjeta de Finanzas
> y fichas nuevas en `diario/`.

> Si la ventana negra parece "congelarse": en Windows, **hacer clic dentro** de una
> consola la pone en modo selección y **pausa** el servidor. Pulsa `Esc` o `Enter`
> dentro de ella para reanudarlo, y evita clicar ahí.

## Qué hace al arrancar
1. Comprueba que Python está instalado.
2. La **primera vez** crea un entorno virtual en `.venv/` e instala las dependencias.
3. Arranca el servidor en `http://127.0.0.1:8000` (modo simulación, sin coste de API).
4. Abre ese enlace en tu **navegador predeterminado** a los pocos segundos.
5. Deja una ventana negra con los logs del servidor (para ver errores en tiempo real).

## Primer arranque vs siguientes
- **Primera vez:** tarda **varios minutos** (crea el venv y descarga las dependencias). Es normal.
- **Siguientes:** **instantáneo** — reutiliza el venv y salta la instalación.

## Mover el acceso directo al escritorio o al menú inicio
- **Al escritorio:** clic derecho en `KAIZEN.lnk` → *Cortar* → pégalo en el Escritorio.
  (O arrástralo con el ratón desde la carpeta del proyecto al Escritorio.)
- **Al menú inicio:** copia `KAIZEN.lnk` en
  `%AppData%\Microsoft\Windows\Start Menu\Programs\`
  (pega esa ruta en la barra del Explorador y suelta ahí el acceso directo).
- El acceso directo guarda la ruta del proyecto; si **mueves la carpeta KAIZEN**, recréalo
  (ver más abajo).

## Cómo parar el servidor
Cierra la ventana negra de logs, o pulsa **Ctrl+C** dentro de ella. El servidor se detiene limpio.

## Si Python no está instalado
La ventana te lo dirá y se quedará abierta. Descarga Python desde **https://python.org**,
y durante la instalación marca **"Add Python to PATH"**. Luego vuelve a hacer doble clic.

## Notas
- `Kaizen.cmd` es el launcher real (lo que ejecuta el acceso directo). `kaizen.bat` es otra cosa:
  la CLI antigua de Kaizen v1.
- Todo vive en el `.venv/` del proyecto: **cero dependencias globales**.
- Para recrear el acceso directo (p. ej. si moviste la carpeta), desde PowerShell en la raíz
  del repositorio (`Kaizen.cmd` y `Kaizen.ico` viven en `lanzadores/`, no en la raíz):
  ```powershell
  $r=$PWD.Path; $w=New-Object -ComObject WScript.Shell; $l=$w.CreateShortcut("$r\KAIZEN.lnk")
  $l.TargetPath="$r\lanzadores\Kaizen.cmd"; $l.WorkingDirectory=$r; $l.IconLocation="$r\lanzadores\Kaizen.ico"; $l.Save()
  ```
  Si ya tenías `KAIZEN.lnk` creado antes de esta reorganización, sigue apuntando a la ruta
  antigua (`$r\Kaizen.cmd`, que ya no existe) — recréalo con el comando de arriba.
