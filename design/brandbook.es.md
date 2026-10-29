# Brandbook completo

## 1. Concepto

**Estilo:** Autómata de latón · compacto. **Qué es esta variante:** el mismo Primum —planetario de mesa, papel marfil y tinta, ébano y latón— pero «mecanizado»: esquinas a 90° (0–2 px), filetes de 1 px en lugar de sombras difusas y densidad de banco de trabajo en escritorio (controles de 32–36 px, pistas de 44 px, insignias de 20 px). Nombre, logotipo, color, tipografías, iconos y voz se heredan; cambian la forma y el ritmo. **Idea central: «la misma esfera, mecanizada».**

**Nombre: Primum.** El *Primum Mobile* es la esfera exterior que, en la cosmología medieval, pone en movimiento a todas las demás: el papel exacto de la placa central, que coordina sin actuar. Latín neutro de dos sílabas, igual en castellano, catalán e inglés; se lee bien en `Primum-7F3A` y `primum.local`. El símbolo no tiene letras, así que el sistema sobrevive a otro nombre (en la lámina se prueba con *Animatica* y *Concentus*).

**Personalidad:** Preciso · Sobrio · Técnico · Fiable.

**Cuándo elegirla frente a Primum:** cuando el uso principal es el editor de escritorio con muchas pistas y placas (museos, escape rooms, teatro, belenes grandes, equipos con varias instalaciones) y se valora ver más a la vez. Primum «redondo» sigue siendo la mejor opción si la prioridad es el primer contacto de personas no técnicas. En táctil (web local en el móvil, kiosco) las dos variantes miden lo mismo: mínimo 44 px, transporte de 64 px y pánico de 72 px.

**A quién atrae más:** técnicos de museo, escape rooms y teatro que pasan horas en el editor; makers y educadores de secundaria o FP; equipos del nivel Pro/Equipos.

**Riesgos:**
- *Más seco y técnico, menos amable para no técnicos.* Contención: la bienvenida y los asistentes usan la densidad táctil (48 px) también en escritorio; el latón, Fraunces y las órbitas se mantienen.
- *La densidad puede romper lo táctil.* Regla dura: en móvil y kiosco nada baja de 44 px y el foco vuelve a 3 px.
- *Esquinas rectas que se confundan con una herramienta genérica de ingeniería.* La identidad se apoya en el latón, la esfera graduada y el perfil de leva de los bloques.
- *Pistas en oscuro al límite* (9,8 normal, 4,6 deuteranopía): patrón y número obligatorios.

**Autoevaluación (1–5):** legibilidad en móvil **4** · adecuación a no técnicos **3** · distinción frente a Home Assistant / Node-RED / xLights / Arduino **4** · modo oscuro **5** · facilidad de implementación **5**.

## 2. Logotipo

**Símbolo.** Un planetario reducido a tres piezas: la esfera exterior (anillo grueso, el *Primum Mobile*), el eje que sale del pivote central y el astro de latón, separado del anillo por un hueco de aire. La órbita interior fina es el detalle que solo aparece a partir de 24 px. El eje apunta siempre arriba a la derecha (hacia las 1:30): es la «hora» de la marca y no se gira.

**Logotipo.** Símbolo + «Primum» en Fraunces 500, eje óptico alto (`opsz` 144), sin «wonky» (`WONK 0`, `SOFT 0`), interletraje −2 %. El punto de la «i» es el astro de latón. Para producción se vectoriza el texto (la lámina usa la fuente en vivo).

**Versiones**
- Principal horizontal: tinta `brand.primary` + latón `brand.secondary` sobre `surface.base` o `surface.raised`.
- Negativo: en oscuro la tinta pasa a `text.primary` (marfil) y el latón a `brand.primary` (latón pulido).
- Monocromo a una tinta (`neutral.950` sobre blanco) y monocromo negativo (`neutral.0` sobre `neutral.950`): el astro y el eje pasan a la misma tinta; el hueco de aire mantiene la lectura.
- Vertical (símbolo encima) para etiqueta, caja y pegatina.

**Tamaño mínimo:** logotipo 96 px de ancho (22 mm impreso); símbolo 16 px. **Versión de 16 px redibujada**: sin eje ni órbita interior; anillo de 2 px, pivote de Ø 4 px y astro de Ø 4,6 px con 1 px de aire.

**Icono de la app:** cuadrado casi recto (esquinas del 7 %, en vez del 22 % de Primum) `neutral.950` (ébano), anillo marfil `neutral.100`, astro latón. De 1024 a 180 px añade la graduación de esfera (60 marcas finas en latón); 64 px solo el símbolo; 32 y 16 px usan el dibujo de 16 px. El icono es igual en claro y oscuro. Favicon = dibujo de 16 px sin fondo.

**Zona de respeto:** x = diámetro del astro de latón, en los cuatro lados. En la etiqueta adhesiva puede bajar a ½ x.

**Usos incorrectos:** deformar; recolorear en rojo o en cualquier color de estado; añadir engranajes, remaches o adornos steampunk; recomponer el nombre en otra tipografía, cursiva o subrayado; sombras, relieves o latón «metalizado» con degradado; girar el símbolo.

## 3. Color

**Decisión de primario.** `brand.primary` es la **acción principal**. En claro es la tinta azul-negra de los planos (`#1C2333`); en oscuro es el latón pulido (`#D9B45E`) sobre ébano. `brand.secondary` es el latón de línea (órbitas, graduaciones, anillo de foco, astro del símbolo) y `brand.accent` el nogal de la caja del autómata (ilustración, embalaje). Así el amarillo-ocre nunca se usa para comunicar estado y `semantic.warning` puede ser un naranja claro de leer.

### Marca

| Token | HEX claro | HEX oscuro | Uso | Contraste sobre `surface.base` (claro / oscuro) |
|---|---|---|---|---|
| `brand.primary` | `#1C2333` | `#D9B45E` | Botón principal, transporte, selección | 13.81 / 9.53 · texto `text.inverse` 14.80 / 9.44 |
| `brand.secondary` | `#87661C` | `#B08E45` | Línea de latón, órbitas, foco (no texto) | 4.68 / 6.09 |
| `brand.accent` | `#6B4A33` | `#C49C78` | Nogal: ilustración y embalaje (uso escaso) | 6.97 / 7.50 |

### Neutros, superficies y texto

Neutros cálidos, iguales en ambos temas: `0 #FFFFFF` · `50 #FBF8F1` · `100 #F5F0E5` · `200 #E8E0CF` · `300 #D3C9B4` · `400 #AEA38C` · `500 #867C68` · `600 #665E4F` · `700 #4B463C` · `800 #332F29` · `900 #211E1A` · `950 #13110E`.

| Token | HEX claro | HEX oscuro | Uso | Contraste de `text.primary` (claro / oscuro) |
|---|---|---|---|---|
| `surface.base` | `#F5F0E5` | `#14110E` | Papel marfil / ébano | 13.81 / 15.74 |
| `surface.raised` | `#FFFCF6` | `#201C18` | Tarjetas, paneles | 15.33 / 14.16 |
| `surface.overlay` | `#FFFFFF` | `#2A2520` | Diálogos, menús | 15.70 / 12.69 |
| `text.primary` | `#1C2333` | `#F2EADB` | Texto | — |
| `text.secondary` | `#5B5648` | `#B7AC97` | Texto secundario | 6.44 / 8.39 sobre base |
| `text.inverse` | `#FBF8F1` | `#16120E` | Texto sobre `brand.primary` y `semantic.danger` | 14.80 / 9.44 sobre primario |

Regla: el texto de cuerpo es `color.text.primary` sobre `color.surface.base`; los metadatos, `color.text.secondary`; las líneas divisorias, `text.primary` al 13 % (no hay token de borde: se mezcla en CSS con `color-mix`).

### Semánticos reservados (solo estados; siempre color + icono + palabra)

| Token | HEX claro | HEX oscuro | Icono · palabra | Icono sobre base (cl / os) | Etiqueta en relleno (cl / os) |
|---|---|---|---|---|---|
| `semantic.danger` | `#C8102E` | `#FF5257` | Octógono con barra · «Pánico», «Peligro» | 5.18 / 5.91 | 5.55 / 5.85 |
| `semantic.warning` | `#B34D00` | `#F4923F` | Triángulo «!» · «Aviso» | 4.64 / 8.09 | 4.98 / 8.01 |
| `semantic.success` | `#2E7A35` | `#5CC46A` | Círculo con marca · «Conectado» | 4.68 / 8.56 | 5.01 / 8.48 |
| `semantic.running` | `#1D5FCC` | `#6AA6FF` | Play con anillo que avanza · «Reproduciendo» | 5.19 / 7.62 | 5.56 / 7.55 |
| `semantic.offline` | `#6A6F78` | `#9AA1AC` | Órbita cerrada · «Modo local», «Sin conexión» | 4.44 / 7.23 | 4.76 / 7.16 |
| `semantic.safe` | `#0E6E7E` | `#4FC1CF` | Escudo con barra · «Estado seguro» | 5.20 / 8.83 | 5.58 / 8.75 |
| `semantic.proposal` | `#7B3FB8` | `#B98CF0` | Destello · «Propuesta» + borde discontinuo | 5.69 / 7.23 | 6.10 / 7.16 |

`offline` es gris y sereno: el modo local es lo normal. `running` se anima con un giro a saltos de 30° (`steps(12)`, como un escape de reloj) y se detiene con `prefers-reduced-motion`. La pareja más cercana entre semánticos es offline–safe (8,7 en claro): se separan por icono y palabra.

### Pistas del editor: 12 esmaltes

Cada pista lleva **color + número + patrón en el talón del bloque + icono del elemento**; así se distinguen con cualquier daltonismo y en blanco y negro. Texto del bloque: `neutral.0` o `neutral.950`, el de mayor contraste.

| Token | Nombre · patrón | HEX claro | HEX oscuro | Texto del bloque (cl / os) |
|---|---|---|---|---|
| `track.1` | Índigo · rayado / | `#595FA0` | `#666ACC` | 0 → 5.88 / 0 → 4.67 |
| `track.2` | Pino · rayado \ | `#006448` | `#51A29B` | 0 → 7.20 / 950 → 6.27 |
| `track.3` | Granate · vertical | `#701140` | `#B0576B` | 0 → 11.39 / 0 → 4.75 |
| `track.4` | Bronce · horizontal | `#725603` | `#A8A65C` | 0 → 6.89 / 950 → 7.43 |
| `track.5` | Violeta · puntos | `#542B89` | `#907BA7` | 0 → 10.08 / 950 → 5.01 |
| `track.6` | Petróleo · cuadrícula | `#154668` | `#A1CBC5` | 0 → 9.96 / 950 → 10.65 |
| `track.7` | Ciruela · aspa | `#974381` | `#DF8DC9` | 0 → 6.11 / 950 → 7.89 |
| `track.8` | Turquesa · ajedrez | `#32889D` | `#56E5FF` | 950 → 4.62 / 950 → 12.61 |
| `track.9` | Salvia · rayado grueso | `#5F9A57` | `#D7E5B7` | 950 → 5.61 / 950 → 14.16 |
| `track.10` | Arcilla · puntos finos | `#C87E81` | `#F6B696` | 950 → 6.06 / 950 → 10.81 |
| `track.11` | Lavanda · macizo | `#8F88C3` | `#B3B2E8` | 950 → 5.81 / 950 → 9.38 |
| `track.12` | Ocre · hueco | `#A77902` | `#D1CC5C` | 950 → 4.83 / 950 → 11.22 |

Distinción (OKLab ×100, de `contrast.md`): claro — normal 12,2 · protan 5,7 · deutan 5,6 · tritan 5,6; oscuro — normal 9,8 · protan 6,3 · deutan 4,6 · tritan 4,9. Pista más cercana a `danger`: 14,5 (claro) y 14,9 (oscuro). `check.py`: **PASS, 0 avisos**. Todas las pistas tienen ≥ 3:1 sobre `surface.raised`, pero los bloques llevan además un borde un 30 % más oscuro.

## 4. Tipografía

| Familia | Token | Uso | Pesos | Licencia |
|---|---|---|---|---|
| **Fraunces** (Undercase Type) | `font.family.display` | Títulos, nombre de secuencia, cifras grandes de la esfera, logotipo | 400–600, eje `opsz` 9–144 automático, `WONK 0`, `SOFT 0` | SIL OFL 1.1 |
| **Instrument Sans** | `font.family.ui` | Toda la interfaz: botones, campos, menús, avisos, cuerpo | 400, 500, 600, 700 | SIL OFL 1.1 |
| **DM Mono** | `font.family.mono` | Pines, tiempos, Wi-Fi, direcciones, PIN, regla de tiempo | 400, 500 | SIL OFL 1.1 |

Pilas de reserva: Fraunces → Iowan Old Style, Palatino, Georgia; Instrument Sans → Helvetica Neue, Arial, system-ui; DM Mono → SF Mono, Menlo, Consolas.

**Escala (apretada arriba):** `xs` 12/1.4 (mono, regla, insignias de escritorio) · `sm` 14/1.4 (**texto denso de escritorio**: botones, campos, listas) · `md` 16/1.45 (cuerpo y todo lo táctil; mínimo en móvil) · `lg` 18/1.35 (subtítulos; umbral del serif) · `xl` 22/1.2 (título de diálogo, display 500) · `2xl` 28/1.1 (título de sección) · `3xl` 40/1.05 (título de pantalla). Interlineado general 1,42 en vez de 1,5.

**Reglas:** cuerpo en `font.family.ui` a `font.size.md`, `color.text.primary` sobre `color.surface.base`. Tiempos en mono con cifras tabulares. Mayúsculas espaciadas (+6 %) solo en etiquetas mono y en «PÁNICO». Nunca Fraunces en botones ni campos ni por debajo de 18 px.

**Sin Internet:** las tres familias se descargan una vez (woff2, subconjunto latín + latín extendido para catalán: à, è, ò, ï, ü, ç, l·l) y se empaquetan dentro de la app de escritorio y del sistema de archivos de la placa central; la web local las sirve desde `primum.local/fonts/` con `@font-face` y `font-display: swap`. Fraunces se incluye como fuente variable (ejes `opsz` y `wght`). Total aproximado: 250 KB.

## 5. Iconografía

Dibujo de relojero en versión recta, sobre retícula de 24 px con 2 px de aire y círculo guía de 20 px. **Trazo 1,5 px**, **remates rectos (butt) y uniones a inglete**, esquinas de rectángulo de 0,5 px, sin rellenos grandes. Los arcos y círculos se mantienen: son órbitas, no esquinas. Firma del estilo: **un único «pivote» macizo por icono** (Ø 2–3,5 px), el punto donde gira o actúa la pieza. Los iconos de estado usan trazo 1,6–2 px para leerse a 16 px. Color `color.text.primary`; en estado, el semántico correspondiente y siempre con palabra. Tamaños: 16 (densos), 20 (botones), 24 (listas), 32 (kiosco).

Juego completo (23): **placas** — centro (órbita con tres astros), nodo Wi-Fi (placa con antena), satélite por cable (placa con cable y conector); **elementos** — tira LED, bombilla/relé, motor, servo, sensor de presencia, pulsador, sensor de distancia, temperatura, altavoz, foco móvil DMX; **acciones** — reproducir, pausa, parar, pánico (octógono con barra), probar (pulso cuadrado), desplegar; **conexiones** — Wi-Fi, cable USB, radio de largo alcance, bus por cable. Más los de estado (triángulo, verificación, play con anillo, órbita cerrada, escudo, destello). Todos son originales: ni espirales tipo Espressif, ni ∞, ni hojas.

## 6. Ilustración y fotografía

**Ilustración:** lámina técnica de relojería. Piezas separadas y rotuladas, trazo 1,25 px en `text.primary`, superficies en `surface.raised`; **la conexión que importa** (el pin y el cable de señal) en latón y más gruesa; rótulos en DM Mono con línea guía acabada en pivote; órbitas de fondo punteadas para indicar el alcance de la placa. Los cables se dibujan como curvas suaves y paralelas, nunca cruzadas. Se usa en asistentes, documentación y estados vacíos.

**Fotografía:** luz lateral suave sobre fondo marfil o madera clara, una pieza protagonista y algo que dé escala (una mano, una figura del belén). En montaje real: fondo oscuro, solo la placa iluminada y su LED de estado visible. **Nunca:** marañas de cables, protoboards caóticas, soldador humeante, primeros planos de chips con marcas de fabricante, latón envejecido o engranajes decorativos.

## 7. Componentes de interfaz

**Radios:** `radius.sm` 0 (bloques, chips, avisos), `radius.md` 2 px (botones, campos, insignias, tarjetas), `radius.lg` 3 px (paneles grandes, modales, marco del móvil). `radius.full` solo para puntos de estado, interruptores y el astro del logotipo. **Sombras:** secas; `shadow.sm` es un filete de 1 px bajo el elemento, `shadow.md` un contorno de 1 px más un escalón de 2 px, `shadow.lg` (solo modales y ventanas) añade una sombra corta. Movimiento más rápido: `motion.fast` 100 ms, `motion.base` 180 ms, `motion.slow` 320 ms.

**Densidad.** La escala `space` no cambia (contrato común); cambia qué paso usa cada componente:

| Elemento | Escritorio compacto | Táctil (móvil, kiosco) |
|---|---|---|
| Botón | 32 px pequeño · 36 px normal | 48 px · transporte 64 · pánico 72 |
| Padding de botón | `space.2` × `space.3` | `space.3` × `space.4` |
| Campo de formulario | 36 px | 48 px |
| Fila de lista | 36–40 px | 48–52 px |
| Pista de la línea de tiempo | 44 px (bloque de 32) | — (solo escritorio) |
| Insignia de estado | 20 px, texto `font.size.xs` | 24 px, texto 13 px |
| Padding de tarjeta | `space.3` | `space.4` |
| Separaciones | `space.2` / `space.3` | `space.3` / `space.4` |
| Texto denso | `font.size.sm` | `font.size.md` |
| Anillo de foco | 2 px a 2 px (≥ 4,6:1) | 3 px a 3 px |

En CSS: un contenedor `.touch` (web local, kiosco, asistentes de bienvenida) sube todo a la columna táctil.

- **Botones.** Rectángulo de `radius.md`, 36 px (32 pequeño). *Principal:* `brand.primary` + `text.inverse` con bisel de latón (anillo interior de 1 px a 2 px del borde). *Secundario:* `surface.raised` con filete de 1 px `text.primary`. *Terciario:* texto subrayado en latón. *Pánico:* `semantic.danger` + `text.inverse`, icono + «PÁNICO» y **chaflán octogonal** (8 px en escritorio, 14–18 px en táctil). Se mantiene: en un sistema de esquinas rectas, un corte a 45° es la forma más reconocible y no es un radio. Nunca se deshabilita. Deshabilitado: sin relleno, borde discontinuo, texto al 45 %. Textos largos: dos líneas, el botón crece.
- **Tarjeta de elemento.** Padding `space.3`, `radius.md`, sin sombra (filete de 1 px). Icono de 32 px en anillo del color de su pista con su número; nombre en `sm` 600, tipo y placa en `xs`; dato vivo y pin en mono; insignia y «Probar» de 32 px.
- **Bloque de secuencia.** 32 px de alto, `radius.sm` (0), talón de 6 px con el patrón de la pista y **perfil de leva** al 15 %. Seleccionado: contorno de 1,5 px y tiradores cuadrados. Propuesta: borde discontinuo `semantic.proposal` + destello. Silenciado: color al 22 % y borde discontinuo.
- **Regla CUANDO · SI · HACER.** Pivotes de 32 px (redondos: son ejes, no botones; en táctil 44 px) unidos por un eje de latón; filas de 44 px.
- **Insignias.** 20 px, `radius.md`, filete de 1 px + fondo al 10 %; relleno solo para el estado global.
- **Aviso.** Filete completo de 1 px (2 px en peligro) del color de estado, fondo al 7 %, icono en cuadrado de 28 px.
- **Campo.** 36 px, `radius.md`, filete de 1 px; etiqueta de 13 px encima; error con filete de 2 px `danger` + icono + frase.
- **Propuesta de la IA.** Tarjeta de borde discontinuo `semantic.proposal`, insignia «Propuesta», vista previa y Aceptar/Descartar de 32 px. Aceptada: borde continuo y color de su pista.

**Primum vs Primum compacto** (en la lámina, lado a lado): botón 48 → 36 px, insignia 28 → 20 px, tarjeta con padding 16 → 12 px, bloque 44 → 32 px. Entre un 25 y un 35 % menos de alto por componente.

## 8. Pantallas de ejemplo

- **Editor de escritorio (1152 × 720), compacto:** barra superior de 40 px con estado de placas, «Modo local», Desplegar y Pánico separado por un divisor; carril de 44 px; regla de 30 px graduada como un anillo de minutos; 5 pistas holgadas de 44 px; cursor con cabeza romboidal de latón en 0:12; **lista de placas** de 36 px debajo de las pistas (lo que en Primum no cabía); inspector con simulador, curva de leva y la propuesta de la IA; transporte de 48 px.
- **Control móvil (390 × 844, claro y oscuro), densidad táctil:** esfera con un segundo por marca, arco azul de «en ejecución» y la aguja como cursor; Reproducir y Pausa de 64 px; lista de placas con estado en palabra; pánico de 72 px anclado abajo.
- **Asistente «Añadir elemento»:** pasos como astros sobre un eje; tipo, nombre, placa, pin con mapa de pines (GPIO 18 sugerido en latón, GPIO 4 ocupado) y avisos de pin y de alimentación.
- **Kiosco 800 × 480:** siempre en oscuro; esfera, controles y placas en tres columnas; pánico abajo a la derecha.
- **Web pública:** titular en Fraunces, planetario con los elementos en órbita, tres bloques (Secuencias, Automatizaciones, Seguro y local) y pie en ébano.
- **Etiqueta 50 × 30 mm a una tinta:** logotipo, «Placa central», Wi-Fi `Primum-7F3A`, clave `belen-luz-2026`, `primum.local`, PIN `4821` y QR real de conexión Wi-Fi de 16 mm. Textos a 6–7 pt. Caja en cartón negro mate con órbitas en latón y pegatina redonda.

## 9. Voz y tono

**Principios.** Habla como un relojero amable: preciso y sin prisa. Dice qué pasa, por qué y qué hacer, en ese orden. Frases cortas, verbos concretos, nada de jerga si hay palabra común («placa», no «nodo MCU»). La seguridad nunca se suaviza ni se adorna. Un toque de asombro solo en bienvenidas y logros, nunca en errores. Los nombres técnicos se escriben en mono y tal cual.

| Mensaje | Castellano | Català | English |
|---|---|---|---|
| Bienvenida | Bienvenido a Primum. Conecta tu primera placa y demos vida a tu belén. | Benvingut a Primum. Connecta la primera placa i donem vida al teu pessebre. | Welcome to Primum. Connect your first board and let's bring your nativity scene to life. |
| Error de pin | Este pin ya lo usa la tira LED. Te sugerimos GPIO 18, que está libre. | Aquest pin ja l'utilitza la tira LED. Et suggerim el GPIO 18, que és lliure. | This pin is already used by the LED strip. Try GPIO 18 — it's free. |
| Alerta del motor | El motor ha superado su tiempo máximo y se ha detenido. Revisa que nada lo bloquee antes de rearmarlo. | El motor ha superat el temps màxim i s'ha aturat. Comprova que res no el bloquegi abans de rearmar-lo. | The motor exceeded its maximum run time and has stopped. Check nothing is blocking it before re-arming. |
| Despliegue confirmado | Listo: «Anunciación» ya está en las 3 placas. | Fet: «Anunciació» ja és a les 3 plaques. | Done: “Annunciation” is now on all 3 boards. |

## 10. Design tokens

Archivos: `tokens/primum.json` y `tokens/primum.css`. Las variables CSS siguen el patrón `--<grupo>-<sub>-<clave>` (`color.semantic.danger` → `--color-semantic-danger`). El tema se elige con `data-theme="light|dark"` en `<html>` o, si no se fija, con la preferencia del sistema. Láminas visuales: **PrimumIdentidad** y **PrimumInterfaz**.

### JSON

```json
{
  "meta": {
    "style": "Autómata de latón · compacto",
    "name": "Primum",
    "slug": "e2b-compacto"
  },
  "font": {
    "family": {
      "ui": "\"Instrument Sans\", \"Helvetica Neue\", Helvetica, Arial, system-ui, sans-serif",
      "display": "\"Fraunces\", \"Iowan Old Style\", \"Palatino Linotype\", \"TeX Gyre Pagella\", Palatino, Georgia, serif",
      "mono": "\"DM Mono\", \"SFMono-Regular\", Menlo, Consolas, \"DejaVu Sans Mono\", monospace"
    },
    "size": {
      "xs": "12px",
      "sm": "14px",
      "md": "16px",
      "lg": "18px",
      "xl": "22px",
      "2xl": "28px",
      "3xl": "40px"
    }
  },
  "radius": {
    "sm": "0px",
    "md": "2px",
    "lg": "3px",
    "full": "9999px"
  },
  "space": {
    "1": "4px",
    "2": "8px",
    "3": "12px",
    "4": "16px",
    "5": "20px",
    "6": "24px",
    "7": "32px",
    "8": "40px",
    "9": "48px",
    "10": "64px",
    "11": "80px",
    "12": "96px"
  },
  "motion": {
    "fast": "100ms",
    "base": "180ms",
    "slow": "320ms"
  },
  "themes": {
    "light": {
      "color": {
        "brand": {
          "primary": "#1c2333",
          "secondary": "#87661c",
          "accent": "#6b4a33"
        },
        "neutral": {
          "0": "#ffffff",
          "50": "#fbf8f1",
          "100": "#f5f0e5",
          "200": "#e8e0cf",
          "300": "#d3c9b4",
          "400": "#aea38c",
          "500": "#867c68",
          "600": "#665e4f",
          "700": "#4b463c",
          "800": "#332f29",
          "900": "#211e1a",
          "950": "#13110e"
        },
        "semantic": {
          "danger": "#c8102e",
          "warning": "#b34d00",
          "success": "#2e7a35",
          "running": "#1d5fcc",
          "offline": "#6a6f78",
          "safe": "#0e6e7e",
          "proposal": "#7b3fb8"
        },
        "track": {
          "1": "#595fa0",
          "2": "#006448",
          "3": "#701140",
          "4": "#725603",
          "5": "#542b89",
          "6": "#154668",
          "7": "#974381",
          "8": "#32889d",
          "9": "#5f9a57",
          "10": "#c87e81",
          "11": "#8f88c3",
          "12": "#a77902"
        },
        "surface": {
          "base": "#f5f0e5",
          "raised": "#fffcf6",
          "overlay": "#ffffff"
        },
        "text": {
          "primary": "#1c2333",
          "secondary": "#5b5648",
          "inverse": "#fbf8f1"
        }
      },
      "shadow": {
        "sm": "0 1px 0 rgba(28,35,51,0.10)",
        "md": "0 0 0 1px rgba(28,35,51,0.10), 0 2px 0 rgba(28,35,51,0.08)",
        "lg": "0 0 0 1px rgba(28,35,51,0.14), 0 8px 0 -4px rgba(28,35,51,0.10), 0 16px 32px rgba(28,35,51,0.12)"
      }
    },
    "dark": {
      "color": {
        "brand": {
          "primary": "#d9b45e",
          "secondary": "#b08e45",
          "accent": "#c49c78"
        },
        "neutral": {
          "0": "#ffffff",
          "50": "#fbf8f1",
          "100": "#f5f0e5",
          "200": "#e8e0cf",
          "300": "#d3c9b4",
          "400": "#aea38c",
          "500": "#867c68",
          "600": "#665e4f",
          "700": "#4b463c",
          "800": "#332f29",
          "900": "#211e1a",
          "950": "#13110e"
        },
        "semantic": {
          "danger": "#ff5257",
          "warning": "#f4923f",
          "success": "#5cc46a",
          "running": "#6aa6ff",
          "offline": "#9aa1ac",
          "safe": "#4fc1cf",
          "proposal": "#b98cf0"
        },
        "track": {
          "1": "#666acc",
          "2": "#51a29b",
          "3": "#b0576b",
          "4": "#a8a65c",
          "5": "#907ba7",
          "6": "#a1cbc5",
          "7": "#df8dc9",
          "8": "#56e5ff",
          "9": "#d7e5b7",
          "10": "#f6b696",
          "11": "#b3b2e8",
          "12": "#d1cc5c"
        },
        "surface": {
          "base": "#14110e",
          "raised": "#201c18",
          "overlay": "#2a2520"
        },
        "text": {
          "primary": "#f2eadb",
          "secondary": "#b7ac97",
          "inverse": "#16120e"
        }
      },
      "shadow": {
        "sm": "0 1px 0 rgba(0,0,0,0.6)",
        "md": "0 0 0 1px rgba(242,234,219,0.08), 0 2px 0 rgba(0,0,0,0.5)",
        "lg": "0 0 0 1px rgba(242,234,219,0.10), 0 16px 32px rgba(0,0,0,0.55)"
      }
    }
  }
}
```

### CSS

```css
/* Primum — estilo «Autómata de latón · compacto». Generado desde tokens.json. */
:root {
  --font-family-ui: "Instrument Sans", "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif;
  --font-family-display: "Fraunces", "Iowan Old Style", "Palatino Linotype", "TeX Gyre Pagella", Palatino, Georgia, serif;
  --font-family-mono: "DM Mono", "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  --font-size-xs: 12px;
  --font-size-sm: 14px;
  --font-size-md: 16px;
  --font-size-lg: 18px;
  --font-size-xl: 22px;
  --font-size-2xl: 28px;
  --font-size-3xl: 40px;
  --radius-sm: 0px;
  --radius-md: 2px;
  --radius-lg: 3px;
  --radius-full: 9999px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;
  --space-10: 64px;
  --space-11: 80px;
  --space-12: 96px;
  --motion-fast: 100ms;
  --motion-base: 180ms;
  --motion-slow: 320ms;
}
:root,
[data-theme="light"] {
  --color-brand-primary: #1c2333;
  --color-brand-secondary: #87661c;
  --color-brand-accent: #6b4a33;
  --color-neutral-0: #ffffff;
  --color-neutral-50: #fbf8f1;
  --color-neutral-100: #f5f0e5;
  --color-neutral-200: #e8e0cf;
  --color-neutral-300: #d3c9b4;
  --color-neutral-400: #aea38c;
  --color-neutral-500: #867c68;
  --color-neutral-600: #665e4f;
  --color-neutral-700: #4b463c;
  --color-neutral-800: #332f29;
  --color-neutral-900: #211e1a;
  --color-neutral-950: #13110e;
  --color-semantic-danger: #c8102e;
  --color-semantic-warning: #b34d00;
  --color-semantic-success: #2e7a35;
  --color-semantic-running: #1d5fcc;
  --color-semantic-offline: #6a6f78;
  --color-semantic-safe: #0e6e7e;
  --color-semantic-proposal: #7b3fb8;
  --color-track-1: #595fa0;
  --color-track-2: #006448;
  --color-track-3: #701140;
  --color-track-4: #725603;
  --color-track-5: #542b89;
  --color-track-6: #154668;
  --color-track-7: #974381;
  --color-track-8: #32889d;
  --color-track-9: #5f9a57;
  --color-track-10: #c87e81;
  --color-track-11: #8f88c3;
  --color-track-12: #a77902;
  --color-surface-base: #f5f0e5;
  --color-surface-raised: #fffcf6;
  --color-surface-overlay: #ffffff;
  --color-text-primary: #1c2333;
  --color-text-secondary: #5b5648;
  --color-text-inverse: #fbf8f1;
  --shadow-sm: 0 1px 0 rgba(28,35,51,0.10);
  --shadow-md: 0 0 0 1px rgba(28,35,51,0.10), 0 2px 0 rgba(28,35,51,0.08);
  --shadow-lg: 0 0 0 1px rgba(28,35,51,0.14), 0 8px 0 -4px rgba(28,35,51,0.10), 0 16px 32px rgba(28,35,51,0.12);
}
[data-theme="dark"] {
  --color-brand-primary: #d9b45e;
  --color-brand-secondary: #b08e45;
  --color-brand-accent: #c49c78;
  --color-neutral-0: #ffffff;
  --color-neutral-50: #fbf8f1;
  --color-neutral-100: #f5f0e5;
  --color-neutral-200: #e8e0cf;
  --color-neutral-300: #d3c9b4;
  --color-neutral-400: #aea38c;
  --color-neutral-500: #867c68;
  --color-neutral-600: #665e4f;
  --color-neutral-700: #4b463c;
  --color-neutral-800: #332f29;
  --color-neutral-900: #211e1a;
  --color-neutral-950: #13110e;
  --color-semantic-danger: #ff5257;
  --color-semantic-warning: #f4923f;
  --color-semantic-success: #5cc46a;
  --color-semantic-running: #6aa6ff;
  --color-semantic-offline: #9aa1ac;
  --color-semantic-safe: #4fc1cf;
  --color-semantic-proposal: #b98cf0;
  --color-track-1: #666acc;
  --color-track-2: #51a29b;
  --color-track-3: #b0576b;
  --color-track-4: #a8a65c;
  --color-track-5: #907ba7;
  --color-track-6: #a1cbc5;
  --color-track-7: #df8dc9;
  --color-track-8: #56e5ff;
  --color-track-9: #d7e5b7;
  --color-track-10: #f6b696;
  --color-track-11: #b3b2e8;
  --color-track-12: #d1cc5c;
  --color-surface-base: #14110e;
  --color-surface-raised: #201c18;
  --color-surface-overlay: #2a2520;
  --color-text-primary: #f2eadb;
  --color-text-secondary: #b7ac97;
  --color-text-inverse: #16120e;
  --shadow-sm: 0 1px 0 rgba(0,0,0,0.6);
  --shadow-md: 0 0 0 1px rgba(242,234,219,0.08), 0 2px 0 rgba(0,0,0,0.5);
  --shadow-lg: 0 0 0 1px rgba(242,234,219,0.10), 0 16px 32px rgba(0,0,0,0.55);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-brand-primary: #d9b45e;
    --color-brand-secondary: #b08e45;
    --color-brand-accent: #c49c78;
    --color-neutral-0: #ffffff;
    --color-neutral-50: #fbf8f1;
    --color-neutral-100: #f5f0e5;
    --color-neutral-200: #e8e0cf;
    --color-neutral-300: #d3c9b4;
    --color-neutral-400: #aea38c;
    --color-neutral-500: #867c68;
    --color-neutral-600: #665e4f;
    --color-neutral-700: #4b463c;
    --color-neutral-800: #332f29;
    --color-neutral-900: #211e1a;
    --color-neutral-950: #13110e;
    --color-semantic-danger: #ff5257;
    --color-semantic-warning: #f4923f;
    --color-semantic-success: #5cc46a;
    --color-semantic-running: #6aa6ff;
    --color-semantic-offline: #9aa1ac;
    --color-semantic-safe: #4fc1cf;
    --color-semantic-proposal: #b98cf0;
    --color-track-1: #666acc;
    --color-track-2: #51a29b;
    --color-track-3: #b0576b;
    --color-track-4: #a8a65c;
    --color-track-5: #907ba7;
    --color-track-6: #a1cbc5;
    --color-track-7: #df8dc9;
    --color-track-8: #56e5ff;
    --color-track-9: #d7e5b7;
    --color-track-10: #f6b696;
    --color-track-11: #b3b2e8;
    --color-track-12: #d1cc5c;
    --color-surface-base: #14110e;
    --color-surface-raised: #201c18;
    --color-surface-overlay: #2a2520;
    --color-text-primary: #f2eadb;
    --color-text-secondary: #b7ac97;
    --color-text-inverse: #16120e;
    --shadow-sm: 0 1px 0 rgba(0,0,0,0.6);
    --shadow-md: 0 0 0 1px rgba(242,234,219,0.08), 0 2px 0 rgba(0,0,0,0.5);
    --shadow-lg: 0 0 0 1px rgba(242,234,219,0.10), 0 16px 32px rgba(0,0,0,0.55);
  }
}
```
