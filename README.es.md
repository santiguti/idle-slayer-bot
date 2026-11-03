<p align="center">
  <img src="docs/images/banner.svg" alt="Idle Runner, un bot de Idle Slayer" width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licencia MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <img alt="Linux y Windows" src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows-brightgreen">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776ab">
</p>

<p align="center"><a href="README.md">English</a> | <b>Español</b></p>

# Idle Runner

**Un bot de Idle Slayer para Linux y Windows.** Juega [Idle Slayer](https://store.steampowered.com/app/1353300/Idle_Slayer/) por ti. Salta, recoge cajas, compra mejoras, juega los minijuegos, asciende cuando conviene y gasta tus Puntos de Asesino en el Árbol de Ascensión.

Solo **mira la ventana del juego y pulsa teclas**, igual que lo harías tú. Nunca toca la memoria, los archivos ni las partidas guardadas del juego.

**[⬇️ Descargar para Linux o Windows](https://santiguti.github.io/idle-slayer-bot/es/)** (o baja los archivos desde [Releases](../../releases))

> [!NOTE]
> La ventana de Idle Runner sale en español si tu sistema está en español. Si no, elige **Español** en *Settings → Window → Language* y vuelve a abrirla. El juego puede estar en español o en inglés.

<p align="center">
  <img src="docs/images/es/ui-dashboard.png" alt="La ventana de Idle Runner: el bot está jugando, con las compras, las ascensiones y los últimos eventos de esta partida" width="80%">
</p>

<p align="center">
  <img src="docs/images/gameplay.png" alt="El bot corriendo por las colinas mientras aparece una caja plateada" width="49%">
  <img src="docs/images/shop.png" alt="La lista de mejoras de la tienda, que el bot lee para comprar" width="35%">
</p>

## ✨ Qué hace

| | |
|---|---|
| 🏃 **Corre** | Salta y usa el impulso sin parar, al ritmo que elijas. |
| 🎁 **Recoge** | Las cajas plateadas y naranjas, dos Misiones Diarias extra y el Bonus Diario de los súbditos cada día. Envía a tus súbditos a sus misiones. |
| 🛒 **Compra** | Mejoras y equipamiento cada pocos minutos, y reclama las recompensas de las misiones. Justo después de ascender compra en cuanto tienes 6 monedas, y después va espaciando las compras. |
| 🌀 **Viaja** | Entra en los portales y, si quieres, recorre las zonas una tras otra. |
| 😡 **Usa la Furia** | En las Mega Hordas, y si quieres solo con Bonus de Almas. |
| 🎮 **Juega los minijuegos** | Cacerías de Cofres, Etapas Bonus 2 y 3, Ascending Heights y la pelea contra Victor. |
| ⬆️ **Asciende** | En cuanto el **"+X% bonus de MpS"** del botón Ascender llega al 20 %, o cada 30 minutos como máximo. Puedes cambiar los dos valores o desactivarlo. |
| 🌳 **Gasta SP** | Opcional. Compra nodos del Árbol de Ascensión en tu orden, al iniciar y después de cada ascensión. *Nuevo, todavía en prueba.* |

## 🔒 Seguridad

- Solo lee píxeles de la ventana del juego y envía teclas y clics. Nunca lee ni cambia la memoria, los archivos ni el tráfico de red del juego.
- Nunca gasta gemas (cuestan dinero real): en el Árbol de Ascensión pulsa Comprar solo cuando el juego muestra que alcanzan los Puntos de Asesino, y cierra cualquier oferta que pida gemas.
- Nunca usa Ultra Ascender.
- La compra de nodos del árbol está desactivada hasta que la actives. Ascender viene activado (con un +20 % de bonus de MpS, o cada 30 minutos como máximo); desactívalo en la página Configuración si prefieres ascender tú.

## 📦 Instalación

En Linux necesitas la **versión de Steam de Idle Slayer para Linux**. Para Windows, mira *Windows* más abajo.

**1. Instálalo.** La forma más fácil: descarga `IdleRunner-…-linux-x64.tar.gz` desde [Releases](../../releases), descomprímelo y ejecuta `./install.sh` dentro de la carpeta `IdleRunner`. Eso agrega *Idle Runner* al menú de aplicaciones (no hace falta Python; Ubuntu 22.04 / Fedora 36 o más nuevo).

O, con Python 3.12 o más nuevo y [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/santiguti/idle-slayer-bot
idle-runner            # abre la ventana
```

O desde un clon, en un entorno virtual:

```bash
git clone https://github.com/santiguti/idle-slayer-bot.git
cd idle-slayer-bot
python3 -m venv .venv
.venv/bin/pip install -e .
```

**2. Prepara el juego:**
- En ventana, a **1280x720**, en **español** o en **inglés**.
- Teclas: salto = **flecha arriba**, impulso = **flecha derecha**.
- En Ajustes, *Desactivar el cursor personalizado* activado, y *Confirmar diálogo al activar el portal* y *Usar notación científica* desactivados.
- *Compra masiva redondeada* y *Ocultar recompensas de Misiones Bloqueadas* activados.
- No compres el **Imán Vertical para Cajas Aleatorias**.

En el primer inicio de cada día el bot abre los Ajustes del juego, lee estas opciones (solo las lee y después pulsa Cancelar) y muestra las que están mal en la página Actividad. Cuando todas están bien, no vuelve a mirarlas ese día; **Revisar los ajustes del juego ahora**, en la página Configuración, hace que las mire otra vez.

**3. Ábrelo:** `idle-runner` (o `.venv/bin/python -m idle_runner`) abre la ventana.

Pulsa **Iniciar** y haz clic en el juego. El bot solo juega mientras la ventana del juego está activa: cambia a otra ventana para pausarlo y vuelve a hacer clic en el juego para seguir. La ventana muestra:

- **Panel:** qué está haciendo el bot, si encontró el juego con el tamaño correcto, los números de esta partida y los últimos eventos.
- **Configuración:** cada opción explicada con palabras simples, guardada en cuanto la cambias.
- **Orden del árbol:** qué nodos del Árbol de Ascensión compra el bot y en qué orden. Arrástralos, agrega o quita nodos, o vuelve al orden recomendado.
- **Actividad:** todo lo que hizo el bot, filtrado por compras, ascensiones, minijuegos o problemas.
- **Ayuda:** la preparación del juego, lo que el bot nunca hace y enlaces.

La ventana sale en español o en inglés según el idioma de tu sistema; puedes cambiarlo en *Configuración → Ventana → Idioma*.

<details>
<summary>Windows</summary>

Descarga `IdleRunner-…-windows-x64.zip` desde [Releases](../../releases), descomprímelo donde quieras y haz doble clic en `IdleRunner.exe`. El exe no tiene firma de código, así que SmartScreen puede decir "Windows protegió su PC": elige **Más información → Ejecutar de todas formas**.

O ejecútalo desde el código en PowerShell (Python 3.12 o más nuevo):

```powershell
git clone https://github.com/santiguti/idle-slayer-bot.git
cd idle-slayer-bot
py -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\idle-runner
```

</details>

> [!WARNING]
> **El bot asciende solo desde el principio** (con un +20 % de bonus de MpS, o a los 30 minutos), y una ascensión no se puede deshacer: reinicia tu partida. Desactiva *Ascender automáticamente* en la página Configuración si prefieres hacerlo tú. La compra de nodos del árbol, que gasta tus SP, está desactivada hasta que la actives.

<details>
<summary>¿El juego arranca con la pantalla en negro?</summary>

Al runtime de Steam le falta una biblioteca que el juego necesita. En Steam, abre **Propiedades → Opciones de lanzamiento** de Idle Slayer y pega esto (ajusta la ruta a tu biblioteca de Steam):

```
"<steam library>/steamapps/common/Idle Slayer/Idle Slayer.x86_64" # %command%
```

Fíjate también en que el juego use X11/XWayland: `~/.config/unity3d/Pablo Leban/Idle Slayer/Player.log` tiene que decir `Selected window backend: x11`. No lo lances con `-force-wayland`.

</details>

<details>
<summary>¿KDE pide permiso de "control remoto"?</summary>

La primera vez que el bot pulsa una tecla, KDE Plasma en Wayland pregunta si lo permites. Acepta y vuelve a hacer clic en el juego.

</details>

## 🛡️ Hecho para jugar sin supervisión

| | |
|---|---|
| 👀 **Siempre atento** | Busca Mega Hordas, Cacerías de Cofres, misiones y cajas plateadas todo el tiempo, sin puntos ciegos. |
| 🎯 **Fácil de controlar** | Juega mientras el juego está activo. Cambia de ventana para pausarlo y vuelve para seguir. Sin atajos de teclado y sin robar el foco. **Comprar ahora** lo manda a la tienda en el momento. |
| 🛡️ **Ascensiones seguras** | Nunca hace clic en el botón **Ultra Ascender**: confirma en un lugar seguro, y solo cuando aparece el diálogo de confirmación. Nunca usa Ultra Ascender. |
| ♻️ **Preparado para la Ultra Ascensión** | Maneja el juego después de una Ultra Ascensión: una tienda sin la pestaña Misiones, sin la pestaña de súbditos y con un solo botón Ascender. |
| 🔧 **Nunca se traba** | Una pantalla que no aparece queda registrada con una captura y se saltea. Después de 5 errores seguidos se detiene de forma segura. |
| 📼 **Caja negra** | Guarda la última hora de juego. Pulsa **Marcar problema** y ese momento queda guardado para siempre. |
| 📐 **Control de la ventana** | Se pausa con un aviso mientras la ventana no mide 1280x720. |
| 🧪 **Tests automáticos** | Más de 400 tests, muchos con capturas reales del juego. |

<details>
<summary>Todos los detalles</summary>

- Foco = juega, alt-tab = pausa, Ctrl+C = detener. Cerrar la terminal o `kill` también lo detienen limpiamente, y las teclas pulsadas se sueltan (una tecla mantenida se suelta en cuanto el juego pierde el foco).
- El tamaño de la ventana se controla todo el tiempo (por ejemplo, si la ventana se maximiza).
- Un error inesperado queda registrado con su traceback y el bot sigue; se detiene después de 5 errores seguidos. Los bucles que podrían quedarse colgados se rinden después de un tiempo y registran un evento `stuck` con una captura.
- El saltador se pausa en cuanto empieza una rutina de menús.
- Los clics fuera de la ventana del juego se rechazan.
- **Tienda:** cada clic en una pestaña se verifica antes de comprar, así un clic pensado para una pestaña no cae en otra (por ejemplo, "Máx" en Equipamiento es "Compra todo lo disponible" en Mejoras). Si la tienda no se abre (por ejemplo, porque la pantalla de resultados de un minijuego todavía la tapa), lo vuelve a intentar 15 s después. La tienda se cierra solo mientras se ve, y el bot espera a que termine de cerrarse: un segundo clic mientras se cierra deja un panel vacío que bloquea todos los clics siguientes.
- **Misiones:** las filas azules de las Misiones de Evento se saltean mientras su botón es el gris de la recompensa, y se compran cuando se reclaman. Sin la pestaña Misiones (después de una Ultra Ascensión, hasta que se vuelven a desbloquear) no cobra, así nunca abre por error la tienda de gemas.
- **Caja Aleatoria:** si aparece una caja plateada o naranja mientras compra o reclama misiones, el bot se detiene, deja que el saltador la agarre y vuelve a comprar poco después.
- **Después de ascender:** el bot lee el contador de monedas y compra en cuanto muestra 6 (el primer nivel de la espada), ya sea una ascensión del bot o tuya. Después las compras empiezan a los `post_ascend_first_buy_seconds` (15 s por defecto) y la espera se duplica hasta llegar a `auto_buy_minutes`.
- **Ascender por %:** cada `ascend_bonus_sample_minutes` el bot abre la pestaña Ascensión y lee el "+X% bonus de MpS" del botón (SP que da la ascensión ÷ SP ganados hasta ahora). Con `auto_ascend_percent` puesto, asciende en la primera lectura que lo alcanza; `auto_ascend_minutes` queda como límite. Un bonus que no puede leer queda registrado con una captura, nunca se adivina.
- **Árbol de Ascensión:** con `auto_buy_tree`, el bot aleja el zoom del árbol al máximo (ahí cada nodo tiene un lugar fijo) y hace clic en los nodos en el orden de `tree_order` (ver Configuración). Los nodos comprados se saltean y se recuerdan entre inicios (en `state.json`, al lado de `config.toml`); cada corrida abre primero el último nodo recordado, sin comprar, y los olvida todos si una Ultra Ascensión reinició el árbol. Se detiene en el primer nodo que no puede comprar. Corre al iniciar, después de cada ascensión del bot y después de una tuya.
- **Súbditos:** al iniciar, después de cada corrida del árbol y cuando debería terminar una misión que empezó, el bot reclama a los súbditos que vuelven de sus misiones y envía a cada súbdito cuya misión cubren tus SP sin gastar. Sabe cuánto dura cada misión por su costo (la tabla de la wiki); marca en la página Configuración las Divinidades que aceleran las misiones (Beneficios de Trabajo, Condiciones de Trabajo Mejoradas, Greeks Blessing). Las misiones que no empezó las revisa cada hora. Primero lee el costo de la misión en el botón y tus SP en el encabezado, así el juego nunca llega a ofrecer gemas por la diferencia. Una vez por día, después de enviarlos, toma el Bonus Diario gratuito (3 horas menos en cada misión en curso) mientras algún súbdito está en misión.
- **Etapa Bonus 1** (mientras el nodo "Etapa Bonus 2" del árbol no está comprado) se saltea: el bot deja que se acabe su primera sección y lo cierra.
- Las fabricaciones de una sola vez (la Vara de la Dimensión Alternativa y la Bidimensional Staff) se hacen una vez por corrida. La rotación de portales vuelve a empezar desde `circle_portals_count`.
- Las marcas de sincronización de las Etapas Bonus que nunca aparecen quedan registradas como eventos `Sync timeout` con una captura.
- La pelea contra el Knight está desactivada.

</details>

## 🧠 Cómo funciona

```mermaid
flowchart LR
    A["📸 Mira la<br/>ventana del juego"] --> B{"🤔 ¿Qué hay en pantalla?"}
    B -->|nada especial| C["⬆️ Sigue saltando"]
    B -->|caja plateada, Mega Horda,<br/>portal, minijuego...| D["🖱️ Pulsa las teclas<br/>y hace los clics que harías tú"]
    C --> A
    D --> A
```

## ⚙️ Ajustes

Todos los ajustes están en la página Configuración de la ventana, con lo que hace cada uno. También puedes copiar `config.example.toml` a `config.toml` y editarlo; cada línea está explicada en el archivo (en inglés).

<p align="center">
  <img src="docs/images/es/ui-settings.png" alt="La página Configuración" width="49%">
  <img src="docs/images/es/ui-tree-order.png" alt="La página Orden del árbol" width="49%">
</p>

Para ascender por porcentaje, pon `ascend_bonus_sample_minutes` (cada cuánto se lee el bonus, por ejemplo 5) y `auto_ascend_percent`. Para cambiar qué nodos del árbol se compran y en qué orden, lístalos en `tree_order`, en la sección `[tree]` de `config.toml` (todos los nombres válidos están en [`idle_runner/tree_nodes.py`](idle_runner/tree_nodes.py)). Sin eso, el bot usa el orden recomendado.

---

<details>
<summary><b>🛠️ Para desarrolladores</b>: uso desde la terminal, logs, calibración y tests</summary>

### Preparación y tests
```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

### Desde una terminal
```bash
cp config.example.toml config.toml   # después edítalo
.venv/bin/python -m idle_runner run
```
El bot solo envía teclas y clics mientras la ventana de Idle Slayer está activa. Haz alt-tab para pausarlo y vuelve al juego para seguir. Detenlo con Ctrl+C en la terminal (o con Detener en la ventana). Guardar desde la ventana reescribe `config.toml` sin comentarios; `config.example.toml` los conserva.

### Calibración y depuración: `probe`
```bash
.venv/bin/python -m idle_runner probe                     # datos de la ventana, tiempos de captura, probe.png
.venv/bin/python -m idle_runner probe --find 830399       # ¿dónde está este color exacto?
.venv/bin/python -m idle_runner probe --pixel 640 360     # color de un píxel del área cliente
.venv/bin/python -m idle_runner probe --delay 3 --key Up  # prueba de teclas (activa el juego en 3 s)
```

Las coordenadas del código están en el marco del script original de AutoIt (la ventana incluida la barra de título de Windows); `Game` resta el desplazamiento (8, 31). Medido en la máquina de desarrollo (2026-10-21):
- Ventana: área cliente de 1280x720, desplazamiento del marco (8, 31), tolerancia de color necesaria: 0. Verificado con el píxel del botón del portal (AutoIt (1180, 166) es exactamente `0x830399`) y la grilla de las Chest Hunts.
- Tiempos de captura: 1 px 0,23 ms, cuadro completo 5,1 ms.

### Logs
- `logs/idle_runner.log`: legible, con milisegundos. Con `log_level = "DEBUG"` también registra cada búsqueda de píxeles.
- `logs/events.jsonl`: un objeto JSON por evento (`ts`, `event` y campos extra), para analizar. Las lecturas del bonus de ascensión son eventos `Ascend bonus` con un campo `percent`.
- `logs/frames/`: capturas PNG al empezar y terminar los minijuegos, en los tiempos de espera de seguridad (`stuck-*`), en los errores (`crash-*`), en los bonus de ascensión ilegibles y en los nodos del árbol que no se compraron.
- `.venv/bin/python -m idle_runner stats`: cantidad de eventos y duración de las rutinas.
- `logs/blackbox/`: la caja negra. Mientras el bot juega, un proceso aparte guarda la ventana del juego `blackbox_fps` veces por segundo (4 por defecto, unos 100 KB por cuadro) y conserva los últimos `blackbox_minutes` (60 por defecto, unos 1,4 GB).
- `logs/marks/<hora>-<motivo>/`: cuadros guardados para siempre, con un `note.txt`:
  - los guarda la propia caja negra alrededor de cada anomalía que registra el bot (desde un minuto antes hasta 30 s después; ver `ANOMALIES` en `idle_runner/blackbox.py`);
  - y también **Marcar problema** en la ventana, o `.venv/bin/python -m idle_runner mark "lo que viste"`: los últimos 5 minutos. Marca en cuanto notes algo.

  Los cuadros son enlaces duros, así que una marca no ocupa espacio extra hasta que la caja negra borra su copia. Borra las marcas viejas a mano.
- `.venv/bin/python -m idle_runner blackbox`: solo la caja negra, por ejemplo mientras juegas tú.
- Cada clic, paso de rueda y tecla mantenida que envía el bot está en `idle_runner.log` (no en la consola). Los toques del saltador solo aparecen con `log_level = "DEBUG"`.

</details>

## 💛 Apoyo

Idle Runner es gratis y lo va a seguir siendo. Si te ahorra unos cuantos clics y quieres agradecerlo, puedes [invitarme un café en Ko-fi](https://ko-fi.com/santiguti). Los reportes de errores y las ideas en [Issues](../../issues) ayudan igual.

## 🙏 Créditos

- Este proyecto empezó como una versión para Linux de [Idle Runner](https://github.com/Devil4ngle/Idle_Slayer_Script), el script de AutoIt para Windows de [Devil4ngle](https://github.com/Devil4ngle). Su lógica de detección, sus coordenadas y sus tiempos siguen siendo la base del bot.
- **Idle Slayer** es un juego de Pablo Leban. Este proyecto no está afiliado al juego ni a su desarrollador, ni cuenta con su aval. Úsalo bajo tu propio riesgo.

Publicado con la [licencia MIT](LICENSE).
