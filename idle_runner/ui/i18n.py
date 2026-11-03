"""The window's texts in English and Spanish. The code writes English and passes it through `t`; SPANISH maps each
English text to its Spanish version: neutral Spanish with "tú", and the game's own Spanish words for what the game
shows (its settings are "Ajustes", so Idle Runner's own Settings page is "Configuración"). A text missing here
shows in English. The logs and event names stay in English: only what the window shows changes.
"""
import os
import sys

_language = "en"


def system_language() -> str:
    """"es" when the system's language is Spanish, else "en"."""
    if sys.platform == "win32":
        import ctypes
        return "es" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0A else "en"
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):  # the order gettext reads them in
        value = os.environ.get(name)
        if value:
            return "es" if value.lower().startswith("es") else "en"
    return "en"


def set_language(code: str) -> None:
    """Use `code` ("en", "es", or "auto" for the system's language) for every `t` from now on."""
    global _language
    _language = system_language() if code == "auto" else code


def node_name(name: str) -> str:
    """An Ascension Tree node's name (tree_nodes.NODES, in English) as the game shows it in the window's language."""
    return NODES_ES.get(name, name) if _language == "es" else name


def t(text: str, **values: object) -> str:
    """`text` in the window's language, with `values` filled into its {fields}."""
    if _language == "es":
        text = SPANISH.get(text, text)
    return text.format(**values) if values else text


SPANISH: dict[str, str] = {
    # --- app.py: pages, sidebar, dashboard ---
    "Dashboard": "Panel",
    "Settings": "Configuración",
    "Tree order": "Orden del árbol",
    "Activity": "Actividad",
    "Help": "Ayuda",
    "Everything": "Todo",
    "Purchases": "Compras",
    "Ascensions": "Ascensiones",
    "Minigames": "Minijuegos",
    "Problems": "Problemas",
    "Support Idle Runner": "Apoya Idle Runner",
    "Version {version}": "Versión {version}",
    "Version {version} is available": "La versión {version} está disponible",
    "Stopped": "Detenido",
    "Start": "Iniciar",
    "Stop": "Detener",
    "Stopping…": "Deteniendo…",
    "Restart": "Reiniciar",
    "Settings changed. Restart the bot to use them.": "La configuración cambió. Reinicia el bot para usarla.",
    "This run": "Esta sesión",
    "Running for": "Tiempo jugando",
    "Upgrades": "Mejoras",
    "Equipment": "Equipamiento",
    "Last bonus": "Último bonus",
    "Tree nodes": "Nodos del árbol",
    "Silver boxes": "Cajas plateadas",
    "Latest": "Últimos eventos",
    "Something went wrong?": "¿Algo salió mal?",
    "Mark problem": "Marcar problema",
    "(no description)": "(sin descripción)",
    "Marked: {text} (saved in {folder})": "Marcado: {text} (guardado en {folder})",
    "Bot output": "Salida del bot",
    "Statistics": "Estadísticas",
    "Open logs folder": "Abrir la carpeta de logs",
    "Nothing yet. Press Start on the Dashboard.": "Nada todavía. Pulsa Iniciar en el Panel.",
    "Nothing yet.": "Nada todavía.",
    "Looking for Idle Slayer…": "Buscando Idle Slayer…",
    "Idle Slayer isn't running": "Idle Slayer no está abierto",
    "Idle Slayer's window is {width}×{height}: set it to 1280×720, windowed":
        "La ventana de Idle Slayer mide {width}×{height}: ponla en 1280×720, en ventana",
    "Idle Slayer found, 1280×720": "Idle Slayer encontrado, 1280×720",
    "Paused": "En pausa",
    "{reason}. Click the game to resume.": "{reason}. Haz clic en el juego para seguir.",
    "Waiting for the game": "Esperando el juego",
    "Its window closed. The bot looks for it every 2 seconds.":
        "Su ventana se cerró. El bot la busca cada 2 segundos.",
    "Running": "Jugando",
    "Playing while the game is in front. Click another window to pause it.":
        "Juega mientras el juego está al frente. Haz clic en otra ventana para pausarlo.",
    "The bot stopped (exit code {code}).": "El bot se detuvo (código de salida {code}).",
    "Press Start, then click the game.": "Pulsa Iniciar y haz clic en el juego.",
    "The bot checks the game's settings in a few seconds, while the game is in front.":
        "El bot revisa los ajustes del juego en unos segundos, mientras el juego esté al frente.",
    "The bot checks the game's settings at the next Start.":
        "El bot revisa los ajustes del juego en el próximo inicio.",
    "Stop the bot and quit?": "¿Detener el bot y salir?",
    "Set up the game": "Prepara el juego",
    "Safety": "Seguridad",
    "Links": "Enlaces",
    "Project page on GitHub": "Página del proyecto en GitHub",
    "Report a problem": "Reportar un problema",
    "All versions": "Todas las versiones",
    # The Help page (app.SETUP and app.SAFETY).
    """Before you start, in Idle Slayer:
•  Windowed, 1280×720, in English or Spanish.
•  Keys: jump = Up arrow, boost = Right arrow.
•  Custom cursor off, portal dialogue off, scientific notation off.
•  Rounded bulk on, hide locked quest rewards on.
•  Don't buy the Vertical Magnet.
At the first Start of each day the bot reads these settings (then presses Cancel) and lists any wrong
one under Problems. Settings, "Check game settings now" reads them again.

The bot only plays while the game window is in front. Click another window to pause it, click the game to
resume.""": """Antes de empezar, en Idle Slayer:
•  En ventana, 1280×720, en español o en inglés.
•  Teclas: salto = flecha arriba, impulso = flecha derecha.
•  En Ajustes: "Desactivar el cursor personalizado" activado; "Confirmar diálogo al activar el portal" y
    "Usar notación científica" desactivados.
•  "Compra masiva redondeada" y "Ocultar recompensas de Misiones Bloqueadas" activados.
•  No compres el Imán Vertical para Cajas Aleatorias.
En el primer inicio de cada día el bot lee estos ajustes (y después pulsa Cancelar) y muestra en Problemas
los que estén mal. En Configuración, "Revisar los ajustes del juego ahora" los lee otra vez.

El bot solo juega mientras la ventana del juego está al frente. Haz clic en otra ventana para pausarlo y en el
juego para seguir.""",
    """What the bot will never do:
•  Read or change the game's memory, files or network. It only looks at the window and presses keys.
•  Spend jewels. It presses Buy in the tree only when the game shows enough Slayer Points.
•  Ultra Ascend.
Tree buying stays off until you turn it on. Ascending is on: at a +20% CpS bonus, at the latest every
30 minutes (Settings, Ascension).""": """Lo que el bot nunca hace:
•  Leer o cambiar la memoria, los archivos o la red del juego. Solo mira la ventana y pulsa teclas.
•  Gastar gemas. En el árbol pulsa Comprar solo cuando el juego muestra que alcanzan los Puntos de Asesino.
•  Ultra Ascender.
La compra en el árbol está desactivada hasta que la actives. Ascender está activado: con un +20 %
de bonus de MpS, o cada 30 minutos como máximo (Configuración, Ascensión).""",
    # --- settings_page.py ---
    "The bot checks Idle Slayer's own settings at the first Start of each day.":
        "El bot revisa los ajustes de Idle Slayer en el primer inicio de cada día.",
    "Check game settings now": "Revisar los ajustes del juego ahora",
    "Buy now": "Comprar ahora",
    "The bot buys at its next check, in a few seconds.": "El bot compra en su próximo chequeo, en unos segundos.",
    "Start the bot first: it buys while it runs.": "Primero inicia el bot: compra mientras está en marcha.",
    "{problem}. These are the defaults; changing a setting saves them over {file}.":
        "{problem}. Estos son los valores por defecto; al cambiar uno se guardan sobre {file}.",
    "“{label}” must be a number, not {value}": "“{label}” tiene que ser un número, no {value}",
    "{file} changed outside this window. Replace those changes with the settings shown here?\n\n"
    "(No: close the window and open it again to see them.)":
        "{file} cambió fuera de esta ventana. ¿Reemplazar esos cambios con la configuración que se ve aquí?\n\n"
        "(No: cierra la ventana y vuelve a abrirla para verla.)",
    # config.check_ranges, before ui.fields.friendly puts the labels in
    "jump_interval_ms must be 0-300": "jump_interval_ms tiene que estar entre 0 y 300",
    "circle_portals_count must be 1-9": "circle_portals_count tiene que estar entre 1 y 9",
    "auto_buy_minutes and auto_ascend_minutes must be > 0":
        "auto_buy_minutes y auto_ascend_minutes tienen que ser mayores que 0",
    "ascend_bonus_sample_minutes must be >= 0": "ascend_bonus_sample_minutes no puede ser negativo",
    "auto_ascend_percent must be >= 0": "auto_ascend_percent no puede ser negativo",
    "post_ascend_first_buy_seconds must be >= 0": "post_ascend_first_buy_seconds no puede ser negativo",
    "color_tolerance must be 0-255": "color_tolerance tiene que estar entre 0 y 255",
    "log_level must be DEBUG, INFO or WARNING": "log_level tiene que ser DEBUG, INFO o WARNING",
    "blackbox_fps must be 0-30": "blackbox_fps tiene que estar entre 0 y 30",
    "blackbox_minutes must be > 0": "blackbox_minutes tiene que ser mayor que 0",
    "language must be auto, en or es": "language tiene que ser auto, en o es",
    # --- fields.py: cards, labels, help, warnings, units ---
    "Window": "Ventana",
    "Playing": "Juego",
    "Shopping": "Compras",
    "Ascension": "Ascensión",
    "Ascension Tree": "Árbol de Ascensión",
    "Minions": "Súbditos",
    "Crafting": "Fabricación",
    "Advanced": "Avanzado",
    "minutes": "minutos",
    "seconds": "segundos",
    "Language": "Idioma",
    "The window's language. It changes the next time you open Idle Runner.":
        "El idioma de esta ventana. Cambia la próxima vez que abras Idle Runner.",
    "System language": "Idioma del sistema",
    "Time between jumps": "Tiempo entre saltos",
    "How often the bot jumps and boosts.": "Cada cuánto salta el bot y usa el impulso.",
    "Travel through portals": "Viajar por los portales",
    "Takes the next zone whenever the portal is ready.": "Pasa a la zona siguiente cada vez que el portal está listo.",
    "First zone": "Primera zona",
    "Where the trip through the zones starts.": "Dónde empieza el recorrido por las zonas.",
    "Rage at Megahordes only with Soul Bonus": "Usar Furia en las Mega Hordas solo con Bonus de Almas",
    "Saves the rage for a Megahorde that gives more souls.": "Guarda la Furia para una Mega Horda que da más almas.",
    "Buy upgrades and equipment": "Comprar mejoras y equipamiento",
    "Opens the shop on a timer and buys everything affordable, except the Vertical Magnet and Electric Worms. "
    "Also claims quest rewards.":
        "Abre la tienda cada cierto tiempo y compra todo lo que alcance, salvo el Imán Vertical para Cajas "
        "Aleatorias y los Electric Worms. También reclama las recompensas de las misiones.",
    "Buy every": "Comprar cada",
    "First buy after ascending": "Primera compra después de ascender",
    "Then the wait doubles until it reaches the interval above. 0 waits the full interval.":
        "Después la espera se duplica hasta llegar al intervalo de arriba. Con 0 espera el intervalo completo.",
    "Ascend automatically": "Ascender automáticamente",
    "Ascending resets your run. It can't be undone. The bot never Ultra Ascends.":
        "Ascender reinicia tu partida y no se puede deshacer. El bot nunca usa Ultra Ascender.",
    "Ascend at this bonus": "Ascender con este bonus",
    "As soon as the Ascend button shows at least this \"+X% CpS bonus\". The wiki suggests about 20 % mid game "
    "and 10 % late. 0 ascends on the timer only.":
        "En cuanto el botón Ascender muestra al menos este \"+X% bonus de MpS\". La wiki sugiere un 20 % a mitad "
        "de partida y un 10 % al final. Con 0 asciende solo por tiempo.",
    "Or at the latest every": "O como máximo cada",
    "Check the bonus every": "Revisar el bonus cada",
    "Reads the Ascend button and logs the bonus. 0 never checks it, so ascending at a bonus is off too.":
        "Lee el botón Ascender y registra el bonus. Con 0 nunca lo revisa, así que tampoco asciende por bonus.",
    "Buy Ascension Tree nodes": "Comprar nodos del Árbol de Ascensión",
    "At start and after every ascension, in the order of the Tree order page.":
        "Al iniciar y después de cada ascensión, en el orden de la página Orden del árbol.",
    "Spends your Slayer Points.": "Gasta tus Puntos de Asesino.",
    "I have Work Benefits": "Tengo Beneficios de Trabajo",
    "The Divinity that makes missions 15% faster: the bot checks the minions back sooner.":
        "La Divinidad que hace las misiones un 15 % más rápidas: el bot busca antes a los súbditos.",
    "I have Improved Work Conditions": "Tengo Condiciones de Trabajo Mejoradas",
    "The Divinity that makes missions 20% faster.": "La Divinidad que hace las misiones un 20 % más rápidas.",
    "I have Greeks Blessing": "Tengo Greeks Blessing",
    "The Divinity that makes missions 25% faster.": "La Divinidad que hace las misiones un 25 % más rápidas.",
    "Skip bonus stages": "Saltear las Etapas Bonus",
    "Waits for them to end instead of playing.": "Espera a que terminen en vez de jugarlos.",
    "I don't have Lockpicking 100": "No tengo Abrir cerraduras 100",
    "The Divinity that makes Chest Hunt animations twice as fast: without it the bot waits longer at each chest.":
        "La Divinidad que hace el doble de rápidas las animaciones de la Cacería de Cofres: sin ella el bot espera "
        "más en cada cofre.",
    "I don't have the Reinforced Crystal Saver": "No tengo el Guardián de Cristal Reforzado",
    "Then the life saver opens right after the first chest, even with Perfect Chest Hunts on.":
        "Así el guardián se abre justo después del primer cofre, aunque las Cacerías de Cofres perfectas estén activadas.",
    "Go for Perfect Chest Hunts": "Buscar Cacerías de Cofres perfectas",
    "Riskier: ignores the life saver until a 2x shows. Turn the x2 x2 Dark Divinity off.":
        "Más arriesgado: ignora el guardián hasta que aparece un x2. Desactiva la Divinidad Oscura x2 x2.",
    "Craft a Souls Compass": "Fabricar una Souls Compass",
    "At a Megahorde with Soul Bonus.": "En una Mega Horda con Bonus de Almas.",
    "Craft a Rage Pill": "Fabricar una Rage Pill",
    "Craft the Dimensional Staff once": "Fabricar la Vara de la Dimensión Alternativa una vez",
    "At the first Megahorde after Start.": "En la primera Mega Horda después de Iniciar.",
    "Craft the Bidimensional Staff once": "Fabricar el Bidimensional Staff una vez",
    "Game window title": "Título de la ventana del juego",
    "Colour tolerance": "Tolerancia de color",
    "0 matches colours exactly, like the original.":
        "Con 0 los colores tienen que coincidir exactamente, como en el original.",
    "Logs folder": "Carpeta de logs",
    "Logs, screenshots and the black box.": "Logs, capturas y la caja negra.",
    "Log detail": "Detalle del log",
    "DEBUG also logs every pixel check.": "DEBUG también registra cada lectura de píxeles.",
    "Save screenshots": "Guardar capturas",
    "At minigames, timeouts and errors.": "En los minijuegos, las esperas agotadas y los errores.",
    "Black box frames per second": "Cuadros por segundo de la caja negra",
    "Keeps the last minutes of play to look at problems later. 0 turns it off.":
        "Guarda los últimos minutos de juego para revisar problemas después. Con 0 se desactiva.",
    "Black box keeps": "La caja negra guarda",
    "About 1.4 GB per hour at 4 frames per second.": "Unos 1,4 GB por hora a 4 cuadros por segundo.",
    # --- tree_page.py ---
    "Search": "Buscar",
    "Reset to recommended": "Volver al orden recomendado",
    "Bought by the bot, in this order": "Los compra el bot, en este orden",
    "Not bought by the bot": "No los compra el bot",
    "Node": "Nodo",
    "Cost (SP)": "Costo (SP)",
    "Status": "Estado",
    "Remove": "Quitar",
    "Add": "Agregar",
    "bought this run": "comprado en esta sesión",
    # --- activity.py: what the bot is doing (DOING) and the minigames (MINIGAMES) ---
    "Checking the game's settings": "Revisando los ajustes del juego",
    "Checking the Ascension Tree": "Revisando el Árbol de Ascensión",
    "Checking the minions": "Revisando los súbditos",
    "Buying upgrades and equipment": "Comprando mejoras y equipamiento",
    "Ascending": "Ascendiendo",
    "Claiming quests": "Reclamando misiones",
    "Reading the ascension bonus": "Leyendo el bonus de ascensión",
    "Taking a portal": "Entrando en un portal",
    "Playing Bonus Stage": "Jugando una Etapa Bonus",
    "Playing Chest Hunt": "Jugando una Cacería de Cofres",
    "Playing Knight boss fight": "Peleando contra el Knight",
    "Playing Victor boss fight": "Peleando contra Victor",
    "Playing Ascending Heights": "Jugando Ascending Heights",
    "Bonus Stage": "Etapa Bonus",
    "Chest Hunt": "Cacería de Cofres",
    "Knight boss fight": "Pelea contra el Knight",
    "Victor boss fight": "Pelea contra Victor",
    "Ascending Heights": "Ascending Heights",
    # --- activity.py: the activity feed ---
    "{count} upgrade": "{count} mejora",
    "{count} upgrades": "{count} mejoras",
    "{count} equipment": "{count} de equipamiento",
    "Bought {first}": "Compró {first}",
    "Bought {first} and {second}": "Compró {first} y {second}",
    "Ascended": "Ascendió",
    "Ascended (+{bonus}% bonus)": "Ascendió (+{bonus}% de bonus)",
    "Bonus: +{percent}%": "Bonus: +{percent}%",
    "Tree: bought {node}": "Árbol: compró {node}",
    "{minigame} started": "Empezó: {minigame}",
    "Silver Box collected": "Caja plateada recogida",
    "Quest claimed": "Misión reclamada",
    "Took 2 extra daily quests": "Tomó 2 Misiones Diarias extra",
    "A minion came back from its mission": "Un súbdito volvió de su misión",
    "Sent a minion ({cost} SP)": "Envió un súbdito ({cost} SP)",
    "Took the minions' Daily Bonus: 3 hours off every mission":
        "Tomó el Bonus Diario de los súbditos: 3 horas menos en cada misión",
    "Minions: not enough SP to send one ({cost} SP)": "Súbditos: no alcanzan los SP para enviar uno ({cost} SP)",
    "Game settings OK": "Ajustes del juego: todo bien",
    "Game settings: already checked today": "Ajustes del juego: ya revisados hoy",
    "Tree: next is {node}, not enough SP": "Árbol: sigue {node}, no alcanzan los SP",
    "Tree stopped at {node}: {reason}": "Árbol detenido en {node}: {reason}",
    "Bot started": "Bot iniciado",
    "Bot stopped": "Bot detenido",
    "Resumed": "Reanudado",
    "Game window found": "Ventana del juego encontrada",
    "Paused: {reason}": "En pausa: {reason}",
    "Game unavailable: {reason}": "Juego no disponible: {reason}",
    # Why the bot paused or stopped a routine (event reasons)
    "game not focused": "el juego no está al frente",
    "the game window is not focused": "la ventana del juego no está al frente",
    "the game window is minimized": "la ventana del juego está minimizada",
    "another window is over the game under the pointer": "otra ventana tapa el juego bajo el puntero",
    "not enough SP": "no alcanzan los SP",
    "no modal": "no se abrió su ventana",
    "layout not found": "no se encontró dónde quedó el árbol",
    "cost not read": "no se leyó el costo",
    "cost not readable": "costo ilegible",
    "no effect": "sin efecto",
    "shop not open": "la tienda no se abrió",
    "no Settings button": "no apareció el botón Ajustes",
    "dialog not shown": "no apareció el diálogo",
    "ascend button not found": "no se encontró el botón Ascender",
    "no dialog after the Ascend click": "no apareció el diálogo después de pulsar Ascender",
    "nothing to claim": "nada que reclamar",
    # The game's settings, in the game's own Spanish (game_settings.SETTINGS)
    "Use scientific notation": "Usar notación científica",
    "Disable custom cursor": "Desactivar el cursor personalizado",
    "Rounded bulk buy": "Compra masiva redondeada",
    "Hide locked Quest rewards": "Ocultar recompensas de Misiones Bloqueadas",
    "Confirm dialogue when activating the Portal": "Confirmar diálogo al activar el portal",
    # Problems (blackbox.ANOMALIES)
    "stuck": "Atascado",
    "Sync timeout": "Sincronización agotada",
    "tick_crash": "Error inesperado",
    "repeater_error": "Error del saltador",
    "Bot stopped after repeated errors": "Bot detenido tras varios errores seguidos",
    "Game window lost": "Se perdió la ventana del juego",
    "click_outside_window": "Clic fuera de la ventana del juego",
    "Shop click retried": "Clic en la tienda repetido",
    "Shop tab not shown": "No se mostró la pestaña de la tienda",
    "AutoUpgrade shop not open": "La tienda no se abrió para comprar",
    "Claim quests: shop not open": "Reclamar misiones: la tienda no se abrió",
    "Upgrade click had no effect": "El clic en una mejora no tuvo efecto",
    "Shopping stopped for a Random Box": "Compras pausadas por una Caja Aleatoria",
    "Ascend skipped": "No ascendió",
    "Coins reading timed out": "No se pudieron leer las monedas a tiempo",
    "Chesthunt saver not found": "No se encontró el Guardián de la Cacería de Cofres",
    "Life saver skipped: saver not found": "Guardián salteado: no se encontró",
    "Portal destination not found": "No se encontró el destino del portal",
    "Ascending Heights timed out after 4 minutes": "Ascending Heights se cortó a los 4 minutos",
    "Ascend bonus not shown": "No se mostró el bonus de ascensión",
    "Ascend bonus unreadable": "No se pudo leer el bonus de ascensión",
    "Tree not shown": "No se mostró el árbol",
    "Tree node not bought": "No se compró el nodo del árbol",
    "Tree jewel offer closed": "Árbol: se cerró una oferta de gemas",
    "Extra daily quests click had no effect": "El clic en las Misiones Diarias extra no tuvo efecto",
    "Minions SP not readable": "Súbditos: no se pudieron leer los SP",
    "Minions buttons unknown": "Súbditos: botones desconocidos",
    "Minion not claimed": "No se reclamó el súbdito",
    "Minions daily bonus click had no effect": "El clic en el Bonus Diario de los súbditos no tuvo efecto",
    "Game setting wrong": "Ajuste del juego incorrecto",
    "Game setting not found": "Ajuste del juego no encontrado",
    "Game settings not checked": "No se revisaron los ajustes del juego",
}


# Every Ascension Tree node's name in the game in Spanish, read from its modal (2026-10-28).
NODES_ES: dict[str, str] = {
    "Village Key": "Llave de la Aldea",
    "Idle Earrings I": "Aretes Inactivos I",
    "Idle Earrings II": "Aretes Inactivos II",
    "Blessing of Cronus": "Bendición de Cronos",
    "Portals": "Portales",
    "Green Ore": "Mineral Verde",
    "Pink Ore": "Mineral Rosa",
    "Soul Gem": "Gema de Alma",
    "Ancient Quests": "Misiones Ancestrales",
    "Hot Desert": "Desierto Caliente",
    "Portal Traveler": "Viajero del Portal",
    "Legendary Belt": "Cinturón legendario",
    "Sacred Book of Projectiles": "Libro Sagrado de Proyectiles",
    "Stability": "Estabilidad",
    "Triple Shot": "Disparo Triple",
    "Orange Ore": "Mineral Naranja",
    "Yellow Ore": "Mineral Amarillo",
    "Dangerous While Alone": "Peligroso estando solo",
    "Bullet Time": "Tiempo de bala",
    "Doesn't Matter to Me": "Para Mí No Es Importante",
    "Soul Slash": "Tirador de Almas",
    "Axe Edge": "Borde del hacha",
    "Minions": "Súbditos",
    "Money Laundering": "Lavado de Dinero",
    "Purple Ore": "Mineral Morado",
    "Cheap Darkness": "Oscuridad Barata",
    "Dagger Edge": "Borde de Daga",
    "Stocks Buyer": "Comprador de Acciones",
    "Every Day Counts": "Cada Día Cuenta",
    "Idle Earrings III": "Aretes Inactivos III",
    "Idle Earrings IV": "Aretes Inactivos IV",
    "Idle Earrings of Death": "Aretes de la Muerte Inactivos",
    "Bring Hell": "Traer el Infierno",
    "Mystic Valley": "Valle Místico",
    "Enchanted Arrows": "Flechas Encantadas",
    "Dark Wand": "Varita Oscura",
    "Dark Wizard": "Mago Oscuro",
    "Map": "Mapa",
    "Ethereal Wand": "Varita etérea",
    "Dual Randomness": "Doble Caja Aleatoria",
    "Coins In The Box": "Monedas en la Caja",
    "Royalties": "Regalías",
    "Lunar Idle Earrings": "Aretes Lunares Inactivos",
    "Solar Idle Earrings": "Aretes Solares Inactivos",
    "Book of Efficiency I": "Libro de Eficiencia I",
    "Silver Money Amulet": "Amuleto de Plata",
    "Golden Money Amulet": "Amuleto Dorado",
    "Soul Reaper II": "Segador de Almas II",
    "Soul Amulet": "Amuleto de Alma",
    "Rock And Stone": "Roca y Piedra",
    "Embrace The Fear": "Abrazar el Miedo",
    "Skeleton": "Esqueleto",
    "Safety First": "Seguridad Primero",
    "Chest Hunt Saver": "Guardián de la Cacería de Cofres",
    "Sword Edge II": "Filo de Espada II",
    "Shinies": "Brillantes",
    "Golden Invasion": "Invasión Dorada",
    "Saved": "Guardado",
    "Book of Efficiency II": "Libro de Eficiencia II",
    "Bonus Stage 2": "Etapa Bonus 2",
    "Doomed": "Condenado",
    "Permanent Supply Boxes": "Cajas de Suministros Permanentes",
    "King of The Sea": "Rey del Mar",
    "ASHPD": "ASHPD",
    "Wall Breaker": "Rompedor de pared",
    "Tornado of Souls": "Tornado de Almas",
    "Gemstone Rush": "Fiebre de Gemas",
    "Bag": "Bolsa",
    "Terra Idle Earrings": "Aretes de Tierra Inactivos",
    "Roll The Dice": "Tira los Dados",
    "Premium Time": "Tiempo Premium",
    "Knight Services": "Servicios de Caballero",
    "High Alchemy": "Alquimia Alta",
    "Blue Sparkle": "Chispa Azul",
    "Factory": "Fábrica",
    "Human After All": "Humano después de todo",
    "Protect": "Proteger",
    "Oblivion Idle Earrings": "Aretes del Olvido Inactivos",
    "Boost Blood": "Sangre con Impulso",
    "Augmented Boost Kill": "Acelerador de muertes aumentado",
    "Super Chest Souls": "Almas de Super Cofre",
    "Soul Silver": "Alma de Plata",
    "Muscle Memory": "Memoria Muscular",
    "Book of Efficiency III": "Libro de Eficiencia III",
    "Idle Earrings of Unity": "Aretes de la Unidad Inactivos",
    "Mega Horde": "Mega Horda",
    "Blessing of Kratos": "Bendición de Kratos",
    "Divinities": "Divinidades",
    "Critical Culling": "Tiro Crítico",
    "Bonus Rewards+": "Recompensas Extras +",
    "Mega Chest Souls": "Almas de Mega Cofres",
    "Book of Efficiency IV": "Libro de Eficiencia IV",
    "Inner Power": "Poder Interior",
    "3 Rows": "3 Filas",
    "Critical Training": "Entrenamiento Crítico",
    "Critical Practice": "Práctica Crítica",
    "Critical Study": "Estudio Crítico",
    "Perfect Prestige": "Prestigio perfecto",
    "Rage Mode": "Modo Furia",
    "Already Enraged": "Ya está enfurecido",
    "Outrage": "Enfado",
    "Fury": "Furia",
    "Gala's Bone": "Hueso de Gala",
    "Climbing Boots": "Botas de Escalada",
    "Book of Efficiency V": "Libro de Eficiencia V",
    "Giant Horde": "Horda de Gigantes",
    "Careful Slayer": "Asesino cuidadoso",
    "Master Chest Souls": "Almas de Cofres Maestros",
    "Advanced Cooking": "Cocina Avanzada",
    "Ramen": "Ramen",
    "Stew": "Estofado",
    "Bonus Sphere Control": "Control de Esferas de Bonificación",
    "Astral Slayer": "Asesino Astral",
    "Ultra Ascension": "Ultra Ascensión",
    "Magic Beetle Box": "Caja Mágica de Escarabajos",
    "Cheap Cooldown": "Enfriamiento Barato",
    "Boost Kill": "Muerte con Impulso",
    "Chemical X": "Sustancia X",
    "Unique Soul Vase": "Urna de Almas Única",
    "Mirror Force": "Fuerza del Espejo",
    "Silver Spirit": "Espíritu de Plata",
    "Shadow Essence": "Esencia de Sombra",
    "The Eye of Providence": "El Ojo de la Providencia",
    "Cyan Ore": "Mineral Cian",
    "Board The Platforms": "Sube a las plataformas",
    "Bad-Tempered": "De Mal Humor",
    "Monolith": "Monolito",
    "Rare Soul Vase": "Urna de Almas Rara",
    "Cleric's Staff": "Bastón de Clérigo",
    "Book of Efficiency VI": "Libro de Eficiencia VI",
    "Triple Silvers": "Plata Triple",
    "Uncontrolled Anger": "Ira Descontrolada",
    "Reincarnation": "Reencarnación",
    "Augmented Soul Gatherer": "Recolector de Almas Aumentado",
    "Permanent Slayer": "Asesino Permanente",
    "Generations": "Generaciones",
    "Stones of Time": "Piedras del Tiempo",
    "Souls Surge I": "Aumento de Almas I",
    "Endless Aggression": "Agresión Infinita",
    "Mining Jewels": "Joyas de Minería",
    "Soul Reaper": "Segador de Almas",
    "Souls Surge II": "Aumento de Almas II",
    "Bonus Stage 3": "Etapa Bonus 3",
    "Random Box Magnet": "Imán para Cajas Aleatorias",
    "True Idle Slayer": "Asesino Verdadero",
    "Sword Edge": "Filo de Espada",
    "Blue Ore": "Mineral Azul",
    "Red Ore": "Mineral Rojo",
    "Soul Gatherer Bundle": "Paquete de Recolector de Almas",
    "Gold Hammer": "Martillo de Oro",
    "Boost Coin": "Monedas con Impulso",
    "Wander's Path": "Camino de Wander",
    "Ancient Slayer": "Asesino Antiguo",
    "Slowmo Bonus": "Bonus de Lentitud",
    "The Chosen One": "El Elegido",
    "Special Random Box Magnet": "Imán para Cajas Aleatorias Especiales",
    "Golden Tooth": "Diente dorado",
    "Souls Bonus": "Bonus de Almas",
    "Reinvest": "Reinvertir",
    "Permanent Quests": "Misiones Permanentes",
    "Portal Dominum": "Portal Dominum",
}
