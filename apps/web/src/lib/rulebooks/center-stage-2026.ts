import { list, notes, p, type Rulebook } from "./types";

/**
 * Reglamento Oficial de Center Stage 2026, v1.0 (revisado el 1 de noviembre de 2026).
 * Transcribed word for word from public/reglamentos/center-stage-2026-v1.0.pdf,
 * typos included: do not edit the text here without a new version of the PDF.
 */
export const centerStage2026: Rulebook = {
  id: "center-stage-2026",
  title: "Reglamento Oficial de Center Stage 2026",
  version: "1.0",
  revised: "2026-11-01",
  pdf: "/reglamentos/center-stage-2026-v1.0.pdf",
  filename: "Center Stage Reglamento v1.0.pdf",
  pages: 15,
  tournaments: ["center-stage-2026-1"],
  chapters: [
    {
      number: "1",
      title: "Glosario",
      id: "glosario",
      blocks: [
        {
          kind: "terms",
          items: [
            [
              "Dobles",
              "Formato donde los Jugadores compiten en grupos de dos únicos jugadores, llamados Equipos.",
            ],
            ["Jugador", "Cualquier persona que participa en el Torneo."],
            [
              "Juego o Partida",
              "Una única competición entre dos o más Jugadores de Super Smash Bros. Ultimate.",
            ],
            [
              "Local o Sede",
              "el centro de videojuegos y Esports EON - PLAY THE FUTURE",
            ],
            [
              "Mejor-de-X",
              "Significa que un Set se compone de X número de Juegos, y el Jugador que gana la mayoría de los Juegos es declarado el ganador. Una vez que un Jugador gana el número de Juegos requeridos para alcanzar la mayoría estipulada, ese Jugador será declarado ganador del Set y los Juegos que no hayan sido jugados hasta ese momento no serán jugados. Por ejemplo, en un Set del Mejor-De-Tres, una vez que un Jugador gana 2 Juegos, ese Jugador será inmediatamente declarado el ganador del Set.",
            ],
            [
              "Organizadores, Staff o TO’s",
              "Cualquier entidad encargada de proveer premios y cualquier otra persona o entidad involucrada en implementar, producir o administrar el Torneo, parcialmente o no.",
            ],
            [
              "Set o Encuentro",
              "Competición del torneo entre dos o más Jugadores que comprende múltiples Juegos.",
            ],
            [
              "Singles",
              "Formato donde los Jugadores compiten individualmente.",
            ],
            [
              "Torneo",
              "Evento de competición de Singles o Dobles de Super Smash Bros. Ultimate.",
            ],
          ],
        },
      ],
    },
    {
      number: "2",
      title: "Reglas del Evento",
      id: "reglas-del-evento",
      sections: [
        {
          number: "2.1",
          title: "Código de Conducta",
          blocks: [
            p(
              "Se espera que todos los Jugadores gocen de buena actitud deportiva y mantengan el respeto tanto para ellos como para los Organizadores y espectadores. Se espera que los Jugadores jueguen en sus mayores capacidades durante la totalidad del Torneo y así mismo muestren deportividad, honestidad y juego justo. Comportamientos que son inapropiados y violaciones del Código de Conducta incluyen, pero no se limitan a:",
            ),
            list(
              "Interferir con operaciones del Torneo;",
              "Actuar de forma antideportiva o disruptiva o con el objetivo de molestar, abusar, amenazar o acosar a cualquier otra persona;",
              "Participar en Amaño de Partidos, (véase, un acuerdo donde dos o más Jugadores deciden el resultado de un Juego o Set);",
              "Trampas de cualquier manera, en cualquier forma;",
              "Ralentizar o alentar el Juego o manipular el Juego de cualquier otra forma, conocida o no;",
              "Nombres de Jugador o aliases ofensivos, vulgares u obscenos;",
              "Sexismo, racismo o cualquier otra forma de prejuicio, discriminación o intolerancia;",
              "Participar en actos de violencia o cualquier actividad que sea juzgada por los Organizadores como inmoral, vergonzosa, carente de ética o contraria a las normas comunes de decencia;",
              "Participar en actos que son ilegales en la jurisdicción del Gobierno de la República del Paraguay.",
              "Ofrecer cualquier regalo, recompensa o trato preferencial a un Jugador u Organizador por asistencia con la intención de proveer una ventaja competitiva al mismo Jugador o a cualquier otro o con la intención de imponer una desventaja competitiva a cualquier oponente;",
              "Llevar puestas prendas o vestimentas o emplear cualquier tipo de lenguaje que resulte obsceno, soez, vulgar, insultante, amenazante, abusivo, calumnioso, difamatorio o que resulte de otro modo ofensivo o inaceptable, o que promueva o invite al odio o a conductas discriminatorias;",
              "Realizar cualquier acción o llevar a cabo cualquier gesto dirigido a un oponente, Organizador o espectador, o incitar a otras personas a hacerlo, que resulte insultante, burlesco, disruptivo o antideportivo;",
              "Tocar o interferir con las consolas, televisiones, luces, cámaras u otros elementos de producción del Torneo sin permiso o supervisión de un Organizador.",
              "Participar de cualquier otro tipo de comportamiento o conducta establecida como inapropiada por la discreción de los Organizadores o;",
              "Violar estas reglas de cualquier otra forma.",
            ),
          ],
        },
        {
          number: "2.2",
          title: "Aviso de filmación",
          blocks: [
            p(
              "Cualquier persona que entre al local consiente ser fotografiada, filmada y/o grabada de cualquier otra forma. La entrada al local constituye este consentimiento de fotografía, filmación y/o grabación y autorizan el uso de su imagen, apariencia, voz y nombre en cualquier medio y de forma indefinida, para cualquier fin relacionado con el evento Center Stage.",
            ),
          ],
        },
        {
          number: "2.3",
          title: "Menores",
          blocks: [
            p(
              "Si el Jugador está por debajo de la mayoría de edad de su país de procedencia (un “menor”), dicho Jugador menor debe estar acompañado en todo momento de su padre o tutor legal para registrarse y participar o asistir al Torneo. Todo lo que refiera al “Jugador” deberá incluir al padre o tutor legal del Jugador menor. Center Stage no se hace responsable de la debida supervisión de un Jugador o asistente menor de edad y dicha responsabilidad permanecerá en todo momento en poder del padre o tutor legal.",
            ),
          ],
        },
        {
          number: "2.4",
          title: "Conducta del Evento",
          blocks: [
            list(
              "Todos los asistentes deben estar registrados como Jugador, espectador, o bien haber sido invitado o autorizado por los Organizadores para entrar al local. Todos los asistentes deben mantener su identificador visible en todo momento.",
              "Se prohíbe el ingreso y la posesión de drogas o armas o el ingreso de alcohol externo al evento.",
              "El uso de cigarrillos, o cualquier equivalente electrónico (Como vapes o pods) Solo será permitido en áreas designadas fuera del edificio.",
              "Todos los asistentes son responsables de sus pertenencias. Entrando al local usted acepta que lo que sea que traiga es únicamente su responsabilidad. El staff de Center Stage, el local de EON, y cualquier patrocinador no asumen responsabilidad alguna por artículos perdidos, dañados o destruidos como consecuencia de su permanencia en el lugar. Los objetos proporcionados por otras personas con explícito permiso de los Organizadores, por otro lado, son y serán considerados equipamiento del Torneo.",
              "Los asistentes no deben sabotear, manipular o intentar remover cualquier equipamiento del local.",
              "Los Organizadores se reservan el derecho de negar la entrada al local de cualquier Jugador o espectador sospechoso de haber cometido un crimen o haber actuado de manera que sea perjudicial para la integridad del evento.",
              "Cualquier problema que pueda surgir fuera de estos términos serán llevados de manera individual y juzgados por los Organizadores.",
              "La violación de cualquiera de estas reglas podrá resultar en el desalojo del evento a la discreción del staff de Center Stage.",
            ),
          ],
        },
      ],
    },
    {
      number: "3",
      title: "Reglas del Torneo",
      id: "reglas-del-torneo",
      blocks: [
        p(
          "Las reglas de Center Stage están sujetas a cambio. Actualizaciones de las reglas serán incluidas en este documento siempre que hayan sido publicadas antes del fin de periodo de registro.",
        ),
      ],
      sections: [
        {
          number: "3.1",
          title: "Formato",
          blocks: [
            p(
              "Todos los Jugadores serán seedeados en grupos de doble eliminación. Los Jugadores avanzarán ya sea por el lado de winners o por el lado de losers. Los jugadores que avancen por el lado de losers empezarán en losers de la siguiente ronda. En Grand Finals, el Jugador que haya avanzado desde losers debe ganar dos (2) sets para que se le conceda el primer puesto del Torneo.",
            ),
          ],
        },
        {
          number: "3.2",
          title: "Duración de los Sets",
          blocks: [
            p(
              "Todos los sets se jugarán al Mejor-de-Cinco. Lo que significa que los Jugadores deben ganar tres juegos antes de llevarse la victoria del Set. Esto aplica tanto para Singles como para Dobles.",
            ),
          ],
        },
        {
          number: "3.3",
          title: "Versión del Juego",
          blocks: [
            p(
              "El Torneo usará cualquier actualización (incluyendo personajes) del juego que haya sido públicamente distribuida en Sudamérica para las 16:00 hs. Del 21 de octubre del 2026. El idioma del juego debe ser inglés. En caso de que un determinado personaje o escenario escogido por los Jugadores no esté disponible en el setup utilizado, cualquiera podrá solicitar ser transferido a una consola distinta.",
            ),
          ],
        },
        {
          number: "3.4",
          title: "Configuraciones del Juego",
          blocks: [
            list(
              "Stocks: 3",
              "Timer: 7:00",
              "Handicap: Off",
              "Team Attack: On",
              "Launch Rate: 1.0x",
              "Items: Off and None",
              "FS Meter: Off",
              "Damage Handicap: Off",
              "Custom Balance: Off",
              "Spirits: Off",
              "Pause: Off",
              "Stage Selection: Loser’s Pick",
              "Stage Hazards: Off",
              "Stage Morph: Off",
              "Underdog Boost: Off",
              "Score Display: Off",
              "Show Damage: Yes",
            ),
          ],
        },
        {
          number: "3.5",
          title: "Opciones",
          blocks: [
            list(
              "Radar: Small",
              "Echo Fighters: Separate",
              "Custom Balance: Off",
              "Los Mii Fighters están permitidos con cualquier combinación de ataques especiales.",
            ),
          ],
        },
        {
          number: "3.6",
          title: "Acuerdo Mutuo (o Gentleman)",
          blocks: [
            p(
              "Los Jugadores pueden escoger cualquier escenario legal si ambos están de acuerdo. Los Jugadores podrán también ignorar las cláusulas de elección de escenarios si ambos están de acuerdo. Los jugadores no pueden jugar en escenarios ilegales o cambiar la duración de la partida.",
            ),
          ],
        },
        {
          number: "3.7",
          title: "Doble Elección Ciega de Personaje",
          blocks: [
            p(
              "Cualquier Jugador con consentimiento de su oponente puede solicitar que una doble elección ciega ocurra. En esta situación, un reportador, referi o cualquier otro Organizador será comunicado, en secreto, de la elección de ambos Jugadores para el primer Juego. Ambos Jugadores elegirán entonces su personaje para el primer Juego con el reportador validando las elecciones de personaje. Cualquier Jugador que declare un Luchador Mii debe también declarar los movimientos especiales del mismo del mismo a la vez.",
            ),
          ],
        },
        {
          number: "3.8",
          title: "Pausar",
          blocks: [
            p(
              "Si un Jugador, intencional o accidentalmente, pausa el Juego presionando el botón de Start, o más (+), o desconectando su control o el de su oponente, el Jugador que pausó perderá una stock. Si una desconexión accidental ocurre mientras el Jugador desconectado está en la plataforma de respawneo, el Jugador no tiene por qué entregar la stock. La penalización podrá ser incrementada a la pérdida de múltiples stocks o la pérdida de un Juego, o se podrá ignorar la cláusula de la plataforma de respawneo a discreción del Organizador.",
            ),
          ],
        },
        {
          number: "3.9",
          title: "Reinicios",
          blocks: [
            p(
              "Los Organizadores podrán aprobar el reinicio de un Juego debido a circunstancias excepcionales, como un corte de energía.",
            ),
          ],
        },
        {
          number: "3.10",
          title: "Muerte Súbita",
          blocks: [
            p(
              "Si un Juego llega a Muerte Súbita, la muerte súbita del juego será ignorada. El ganador será determinado por la cantidad de stocks y porcentaje en el momento en que el Juego termina. Cuando el reloj llega a 0:00, el Jugador o Equipo con la mayor cantidad de stocks (sumadas en el caso de los Equipos) es el ganador. Si ambos Jugadores o Equipos están empatados en stocks, el Jugador o Equipo con la menor cantidad de porcentaje (sumados en caso de los Equipos) es el ganador. En el caso de un empate de porcentaje, o un Juego en el cual ambos Jugadores o Equipos pierden su última stock simultáneamente, un desempate de una sola stock será jugado con un tiempo límite igual a 2:30 minutos.",
            ),
          ],
        },
        {
          number: "3.11",
          title: "Stocks Compartidas",
          blocks: [
            p("Tomar la stock de un compañero está permitido en Dobles."),
          ],
        },
        {
          number: "3.12",
          title: "Clausula de “Grab and Go”",
          blocks: [
            p(
              "En dobles, los Jugadores no podrán cambiar de control con su compañero.",
            ),
          ],
        },
        {
          number: "3.13",
          title: "Clausula del Compañero Perdido",
          blocks: [
            p(
              "Si el compañero de un Jugador no se presenta para una partida, el Jugador no podrá reemplazar a su compañero con una CPU. El mencionado no jugará sin un compañero.",
            ),
          ],
        },
        {
          number: "3.14",
          title: "Reemplazo o sustitución de Jugador",
          blocks: [
            p(
              "Serás inmediatamente descalificado del torneo sin reembolsos si se te encuentra utilizando una o más tags alternativas y/u ocultas tu identidad para manipular la bracket o el seeding. Esto incluye jugar bajo el tag de otro Jugador, incluso si el Jugador registrado no puede llegar al evento por cualquier motivo, con o sin su permiso. Los Organizadores no están obligados a aprobar cualquier cambio acerca de las sustituciones de Jugadores.",
            ),
          ],
        },
        {
          number: "3.15",
          title: "Cláusula de Daltonismo",
          blocks: [
            p(
              "Los Jugadores podrán solicitarle a su oponente cambiar colores para acomodar condiciones de daltonismo o si su color es indistinguible del color del Equipo enemigo o el fondo del escenario. La solicitud debe ser realizada antes de que el Juego empiece.",
            ),
          ],
        },
        {
          number: "3.16",
          title: "Calentamientos",
          blocks: [
            p(
              "Calentamientos y pruebas de controles no deben exceder los 30 primeros segundos del cronómetro del Juego. Violar esta regla podrá resultar en una derrota automática a la discreción de los Organizadores.",
            ),
          ],
        },
        {
          number: "3.17",
          title: "Coaching",
          blocks: [
            p(
              "El coaching, definido como brindar o recibir consejos o información de/a otra persona durante un Set o entre Sets de Grand Finals, está permitido durante 30 segundos entre Juegos y durante 60 segundos entre Sets de Grand Finals. Cada Jugador podrá tener un coach designado que será comunicado a los Organizadores, un solo coach por torneo. No está permitido el coaching remoto ni recibir ayuda de Inteligencias Artificiales. Únicamente se admitirá la lectura de notas personales.",
            ),
          ],
        },
        {
          number: "3.18",
          title: "Tardanza",
          blocks: [
            p(
              "Cualquiera que no se presente a jugar su Set para los 5 minutos pasado el inicio indicado, sin previa comunicación al staff del Torneo, será sujeto a una descalificación total del evento. El cronómetro específico para DQ’s está sujeto a la discreción de los Organizadores antes del inicio del evento.",
            ),
          ],
        },
        {
          number: "3.19",
          title: "Amaño de Partidos (Colusión)",
          blocks: [
            p(
              "Jugadores sospechosos de amañar partidas serán inmediatamente descalificados del Torneo. Esto incluye perder una Partida a propósito, dividir un premio, o cometer cualquier otra forma de manipulación de la bracket. El Organizador se reserva el derecho de denegar pagos o premios de victoria a cualquier Jugador sospechoso de realizar amaños.",
            ),
          ],
        },
        {
          number: "3.20",
          title: "Malinterpretación o Mala configuración",
          blocks: [
            p(
              "Si un Juego fue realizado bajo configuraciones incorrectas según las especificadas en el reglamento que podrían haber afectado el resultado del Juego, un Jugador podrá solicitar al Organizador que dicho Juego vuelva a jugarse. La decisión final está sujeta a la discreción del Organizador. Esto debe ser hecho inmediatamente después del Juego en cuestión; luego de que el siguiente Juego haya empezado, el Juego anterior no podrá ser rejugado sin importar si las reglas fueron colocadas correctamente. Esto aplica para el resto del reglamento tras el final de un set a discreción de los Organizadores.",
            ),
          ],
        },
        {
          number: "3.21",
          title: "Retraso entre Juegos",
          blocks: [
            p(
              "La máxima cantidad de tiempo para elegir un escenario después de una derrota son sesenta (60) segundos. Los Jugadores tendrán hasta un máximo de dos minutos entre sets de grand finals antes de empezar el primer Juego del segundo Set.",
            ),
            p(
              "Cualquier cosa más allá de esto estará sujeto a las reglas de retraso y podrán resultar en la pérdida de un Juego a discreción del Organizador.",
            ),
          ],
        },
        {
          number: "3.22",
          title: "Uso de audífonos",
          blocks: [
            p(
              "Si un setup de torneo no tiene audio, o si el audio disponible no se oye por ruido externo, cualquier Jugador podrá llamar a un miembro del Staff y solicitar usar audífonos para escuchar al sonido del juego. De ser así, los Jugadores deberán proveer sus propios audífonos y proveer un splitter de audio para que su oponente tenga igual acceso al sonido del juego.",
            ),
            p(
              "Si un setup de torneo ya tiene audio utilizable, un Jugador no podrá conectar sus propios audífonos a menos que puedan proveer un splitter de audio y un par de altavoces para su oponente. Si estos altavoces no alcanzan los niveles de volumen de los originales, el Jugador no utilizará sus audífonos para oír el sonido del juego. Este reglamento no aplica para audífonos utilizados para música u otra forma de sonido que no incluya el del Juego.",
            ),
          ],
        },
        {
          number: "3.23",
          title: "Reglas de Escenarios y Procedimientos",
          id: "escenarios",
          index: true,
          sections: [
            {
              number: "3.23.1",
              title: "Lista de escenarios",
              blocks: [
                p("Escenarios iniciales o Starters"),
                list(
                  "Battlefield*",
                  "Hollow Bastion",
                  "Small Battlefield",
                  "Town and City",
                  "Pokemon Stadium 2",
                ),
                p("Escenarios posteriores o Counterpicks"),
                list(
                  "Smashville",
                  "Final Destination**",
                  "Kalos Pokemon League",
                ),
                notes(
                  "* Los jugadores deben jugar en la versión estándar de Battlefield",
                  "** Cuando Final Destination sea elegido, cualquier jugador podrá usar la forma Omega de Battlefield por motivos visuales, a menos que Steve haya sido seleccionado para ese Juego en particular, por el impacto del minado de Steve. Si Steve es utilizado, la forma Omega debe ser Wuhu Island.",
                  "*** Si una forma ilegal de Battlefield o Final Destination/Omega es seleccionada, cualquier jugador tiene derecho a solicitar que el Juego sea reiniciado antes de que una interacción tome lugar (Por ejemplo, que un Jugador haya recibido daño). De no ser así, el Juego tendrá que jugarse. Si un Jugador solicita el reinicio del Juego, el mismo será reiniciado en la versión estándar de Battlefield o una versión legal de Final Destination u Omega.",
                ),
              ],
            },
            {
              number: "3.23.2",
              title: "Baneo de escenarios: Juego 1",
              blocks: [
                p(
                  "Los Jugadores jugarán al Piedra, Papel o Tijeras en formato del mejor-de-uno, y el ganador empezará baneando escenarios primero. Los escenarios se banean en un orden de 1-2-1. Es decir, el ganador del Piedra, Papel, o Tijeras baneará un escenario inicial, seguido por dos baneos del Jugador contrario y un baneo final del primer Jugador. Cualquier Jugador puede solicitar hacer una Doble Elección Ciega de Personaje (Ver sección 3.7).",
                ),
              ],
            },
            {
              number: "3.23.3",
              title: "Baneo de Escenarios: Juego 2 en adelante",
              blocks: [
                p(
                  "Después de cada Juego, el ganador del Juego anterior dirá primero qué personaje usará. El perdedor del anterior Juego entonces dirá qué personaje usará él. El ganador del Juego anterior baneará hasta tres escenarios de la lista de Iniciales y/o Posteriores. Estos baneos no persisten a lo largo del resto del set. El perdedor del anterior Juego elegirá entonces uno de los escenarios restantes.",
                ),
              ],
            },
            {
              number: "3.23.4",
              title: "Cláusula de Escenarios para Steve",
              blocks: [
                p(
                  "Si un Jugador ha elegido a Steve y su oponente no lo ha hecho, el anterior procedimiento de baneos de escenario es ignorado y el Jugador o Equipo que no haya elegido a Steve elegirá/n cualquier escenario legal, ignorando los baneos*. Si ambos Jugadores o Equipos eligen a Steve, esta regla no aplica.",
                ),
                notes(
                  "*Si un jugador o Equipo elige a Steve para el Juego 1, debe/n ignorar la Doble Elección Ciega de Personaje y anunciar que usará/n a Steve, ya que no puede/n elegir o banear escenarios.",
                ),
              ],
            },
          ],
        },
        {
          number: "3.24",
          title: "Reglas Adicionales",
          id: "reglas-adicionales",
          index: true,
          sections: [
            {
              number: "3.24.1",
              title: "Regla Contra Retrasos (o Stalling)",
              blocks: [
                p(
                  "Cualquier Jugador que utilice el mismo movimiento especial más de cinco (5) veces sin regresar al escenario (Borde no incluido) está retrasando y podrá ser sujeto a perder el Juego. Esta regla solo se aplica en actos tomados debajo del escenario o más allá del mismo.",
                ),
                p(
                  "Esta regla se aplicará con una revisión de la repetición para evitar que el Juego sea indebidamente detenido o retrasado. Un jugador podrá llamar a un Organizador después de que el Juego haya concluido.",
                ),
                p(
                  "Personajes usando movimientos especiales repetidamente más de cinco veces con clara intención de volver al escenario (por ejemplo: R.O.B utilizando Up B múltiples veces), para continuar el Juego intentando interactuar con el otro Jugador (por ejemplo: al hacer edge-guarding), o usando movimientos que no afectan al momentum (por ejemplo: usar el Neutral B de Fox mientras cae) no serán penalizados por esta regla.",
                ),
              ],
            },
            {
              number: "3.24.2",
              title: "Planking (Técnica de Steve)",
              blocks: [
                p(
                  "Utilizar el Planking fuera del escenario con Steve está prohibido y resultará se dará el Juego perdido automáticamente por utilizarlo. El “Planking” es definido como crear bloques debajo del escenario y/o minar recursos fuera del escenario. Minar hasta dos recursos por un misinput (es decir, hacerlo por error) no será castigado. Esta distinción es hecha en caso de que un Jugador de Steve podría equivocarse y minar mientras intenta impedir la recuperación de un oponente. Abusar de esto para minar repetidamente dos recursos fuera del escenario resultará en la pérdida de una stock o del Juego a discreción del Organizador.",
                ),
                p(
                  "Colocar bloques bajo el escenario para bloquear o hacer edgeguarding está permitido.",
                ),
              ],
            },
            {
              number: "3.24.3",
              title: "MLG/PMLG (Técnica de Steve)",
              blocks: [
                p(
                  "Las técnicas de Steve “MLG” y “PMLG” no serán usadas de ninguna manera durante una Partida de Torneo. Si un Jugador sospecha que su oponente ha usado MLG o PMLG, podrán guardar la repetición y pedir una revisión a un Organizador. En caso de confirmarse el Jugador recibirá la penalización de perder un Juego, o perder el Set por múltiples ofensas durante el mismo.",
                ),
              ],
              sections: [
                {
                  number: "3.24.3.1",
                  title: "MLG",
                  blocks: [
                    p(
                      "Se define como utilizar un doble salto y luego un aéreo para incrementar el knockback verticalmente después de recibir un golpe para evitar morir por las blastzones horizontales y cancelar el momentum del knockback.",
                    ),
                  ],
                },
                {
                  number: "3.24.3.2",
                  title: "PMLG",
                  blocks: [
                    p(
                      "Se define como usar un Bloque Fantasma para negar el knockback fuera del estado de tumble.",
                    ),
                  ],
                },
              ],
            },
            {
              number: "3.24.4",
              title: "Elecciones de Música Dentro del Juego",
              blocks: [
                p(
                  "La música del Juego 1 debe ser aleatoria a menos que ambos Jugadores acuerden una canción o permitan a un Jugador elegir.",
                ),
                p(
                  "Desde el Juego 2 en adelante, la música no puede ser escogida por el Jugador que ganó el Juego anterior*.",
                ),
                p(
                  "Las siguientes canciones no serán elegidas en ninguna circunstancia**:",
                ),
                list(
                  "25m",
                  "All Retro Medleys",
                  "Deluge Dirge",
                  "Electroplankton",
                  "Environmental Noises",
                  "Freakyworms Your Creations, Alive!",
                  "Gamer",
                  "Pac-Man",
                  "Rhythm Boxing",
                  "Ring a Ding (Debido al copy-right)",
                ),
                notes(
                  "* Un Jugador oyendo su propia música mediante audífonos u otra forma no podrá elegir la música del Juego. En tal caso, el Jugador usando el audio del Juego podrá optar por elegir la música en cada Juego.",
                  "** Si ambos Jugadores aceptan, cualquiera de las canciones antes mencionadas podrá ser usadas fuera de Partidas en Stream.",
                  "*** Los Organizadores se reservan el derecho de juzgar, incluyendo, pero no limitándose a la solicitud de un Jugador, si un Jugador está eligiendo canciones para incomodar o molestar a su oponente incluyendo canciones que no se encuentren en la lista anterior. En caso de ser descubierto un intento de evitar o abusar la regla de Elecciones de Música Dentro del Juego podrán ser penalizados con un Juego perdido a discreción del Organizador.",
                ),
              ],
            },
            {
              number: "3.24.5",
              title: "Reglamento para los Controles",
              blocks: [
                p(
                  "El control recomendado es un control de Gamecube alámbrico. Funciones turbo, macros, y modificaciones de hardware (con excepción de modificaciones exteriores, como notches y cambios cosméticos) están prohibidas. Las excepciones incluyen modificaciones contra Snapback y PODE fixes. Controles estilo box están permitidos siempre que se hayan actualizado a la última versión de firmware del productor. Los Organizadores del Torneo tienen el derecho de inspeccionar cualquier control en cualquier momento y determinar su legalidad.",
                ),
              ],
            },
          ],
        },
        {
          number: "3.25",
          title: "Reglas Finales",
          id: "reglas-finales",
          index: true,
          blocks: [
            p(
              "Si cualquier situación inesperada tiene lugar, el juicio del staff del torneo es ley. Estas reglas podrán ser alteradas entre fases de un torneo en los mejores intereses del evento.",
            ),
          ],
        },
      ],
    },
    {
      // The document's index calls it chapter 5; its heading says 4. The heading wins.
      number: "4",
      title: "Indemnización",
      id: "indemnizacion",
      blocks: [
        p(
          "Por la presente, todos los asistentes aceptan indemnizar y eximir de responsabilidad al personal de Center Stage y a los organizadores del torneo frente a cualquier reclamación, acción o procedimiento de terceros, de cualquier naturaleza, así como frente a cualquier daño, responsabilidad, coste o gasto —incluidos los honorarios y gastos razonables de asesoría jurídica externa— que se derive o guarde relación con el incumplimiento, por parte del asistente, de cualquiera de las garantías, declaraciones, compromisos, obligaciones o acuerdos establecidos en estas normas.",
        ),
      ],
    },
  ],
};
