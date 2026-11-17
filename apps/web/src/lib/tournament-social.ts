/**
 * Social media images of a tournament (SH-SOCIAL-01): the data the API returns
 * (GET /insights/tournaments/{id}/social), the list of images and when each one has
 * something to show. Shared by the image route and the organizers' panel.
 */

export type Ref = {
  id: string;
  tag: string | null;
  seed?: number | null;
  prefix?: string | null;
  mains?: { character: string; costume?: number }[];
};

export type GameReport = {
  winner: string | null;
  loser: string | null;
  won: boolean | null;
};

export type SocialSet = {
  winner: Ref;
  loser: Ref;
  score: string | null;
  round: string | null;
  factor: number;
  comeback: boolean;
  games: GameReport[];
};

export type Performer = Ref & {
  seed: number;
  placement: number;
  tiers: number;
};

export type Newcomer = Ref & { placement: number; days?: number };

export type ImpactRow = {
  player_id: string;
  gamer_tag: string;
  place: number;
  previous: number | null;
  change: number | null;
  mains?: { character: string; costume?: number }[];
};

export type Social = {
  tournament: {
    id: string;
    name: string;
    slug: string;
    starts_at: string | null;
    city: string | null;
  };
  summary: {
    event_id: string;
    event: string | null;
    main: boolean;
    entrants: number | null;
    top: (Ref & { placement: number; seed: number | null })[];
  };
  champion: Ref | null;
  champion_path: {
    opponent: Ref;
    won: boolean;
    score: string | null;
    round: string | null;
    losers: boolean;
    factor: number;
  }[];
  grand_final: SocialSet[];
  upsets: SocialSet[];
  over: Performer[];
  under: Performer[];
  close_sets: SocialSet[];
  numbers: {
    entrants: number | null;
    sets: number;
    games: number;
    full_length: number;
    sweeps: number;
    comebacks: number;
    upsets: number;
    biggest_upset: number;
    characters: number;
    top_character: string | null;
  };
  characters: {
    games: number;
    coverage: number | null;
    items: {
      character: string;
      games: number;
      share: number;
      win_rate: number;
      players: number;
    }[];
  };
  newcomers: {
    debuts: Newcomer[];
    debut_count: number;
    returns: Newcomer[];
  };
  rivalries: {
    a: Ref;
    b: Ref;
    before: [number, number];
    here: SocialSet[];
    after: [number, number];
  }[];
  ranking: {
    slug: string;
    name: string;
    up: ImpactRow[];
    down: ImpactRow[];
    entered: ImpactRow[];
  } | null;
  achievements: {
    id: string;
    name: string;
    description: string;
    rarity: string;
    rarity_name: string;
    players: { id: string; tag: string }[];
  }[];
  prode: {
    name: string;
    participants: number;
    champion: string | null;
    champion_hits: number;
    ranking: {
      rank: number;
      name: string;
      points: number;
      exact_hits: number;
      hits: number;
    }[];
  } | null;
};

export const FORMATS = {
  portrait: { label: "Vertical 1080×1350 (feed)", width: 1080, height: 1350 },
  square: { label: "Cuadrada 1080×1080", width: 1080, height: 1080 },
  story: { label: "Historia 1080×1920", width: 1080, height: 1920 },
  wide: { label: "Horizontal 1920×1080", width: 1920, height: 1080 },
} as const;
export type Format = keyof typeof FORMATS;

export function isFormat(value: string | null): value is Format {
  return value !== null && value in FORMATS;
}

/** Fewer games than this and the characters image says too little. */
const MIN_CHARACTER_GAMES = 10;

export const CARDS = [
  {
    key: "podio",
    title: "Top 8",
    hint: "Podio con renders y del 4.º al 8.º.",
    has: (d: Social) => d.summary.top.length >= 3,
  },
  {
    key: "campeon",
    title: "Camino del campeón",
    hint: "Cada set del campeón hasta el título.",
    has: (d: Social) => d.champion_path.length > 0,
  },
  {
    key: "final",
    title: "Gran final",
    hint: "Marcador y personajes de cada game.",
    has: (d: Social) => d.grand_final.length > 0,
  },
  {
    key: "sorpresas",
    title: "Sorpresas",
    hint: "Las victorias más inesperadas según el seed.",
    has: (d: Social) => d.upsets.length > 0,
  },
  {
    key: "seeds",
    title: "Por encima de su seed",
    hint: "Quiénes terminaron mejor de lo esperado.",
    has: (d: Social) => d.over.length > 0,
  },
  {
    key: "peleados",
    title: "Sets más peleados",
    hint: "Los que llegaron al último game.",
    has: (d: Social) => d.close_sets.length > 0,
  },
  {
    key: "numeros",
    title: "El torneo en números",
    hint: "Jugadores, sets, games, barridas, remontadas…",
    has: (d: Social) => d.numbers.sets > 0,
  },
  {
    key: "personajes",
    title: "Personajes del torneo",
    hint: "Los más usados y cuánto ganaron (si se cargaron en start.gg).",
    has: (d: Social) => d.characters.games >= MIN_CHARACTER_GAMES,
  },
  {
    key: "debutantes",
    title: "Debutantes y regresos",
    hint: "Primer torneo y los que volvieron tras 6 meses o más.",
    has: (d: Social) =>
      d.newcomers.debuts.length + d.newcomers.returns.length > 0,
  },
  {
    key: "ranking",
    title: "Impacto en el ranking",
    hint: "Quién subió, quién entró y quién bajó en el ranking oficial.",
    has: (d: Social) =>
      Boolean(
        d.ranking &&
        d.ranking.up.length + d.ranking.entered.length + d.ranking.down.length,
      ),
  },
  {
    key: "logros",
    title: "Logros desbloqueados",
    hint: "Logros que se ganaron en este torneo.",
    has: (d: Social) => d.achievements.length > 0,
  },
  {
    key: "prode",
    title: "Resultados del Prode",
    hint: "Tabla final del Prode liquidado.",
    has: (d: Social) => Boolean(d.prode?.ranking.length),
  },
  {
    key: "rivalidad",
    title: "Cara a cara",
    hint: "Rivales con historia que se cruzaron en el torneo.",
    has: (d: Social) => d.rivalries.length > 0,
  },
] as const;

export type CardKey = (typeof CARDS)[number]["key"];

export function cardOf(key: string) {
  return CARDS.find((c) => c.key === key) ?? null;
}

/** Why an image cannot be made, in words for organizers. */
export const MISSING: Record<CardKey, string> = {
  podio: "Faltan resultados del top.",
  campeon: "No hay sets del campeón.",
  final: "start.gg no marca ninguna ronda como gran final.",
  sorpresas: "No hubo sorpresas (o el seeding se marcó como no confiable).",
  seeds: "Nadie terminó por encima de su seed.",
  peleados: "Ningún set llegó al último game, o no hay marcadores.",
  numeros: "No hay sets cargados.",
  personajes: "No se cargaron suficientes personajes en start.gg.",
  debutantes: "Nadie debutó ni volvió después de meses.",
  ranking:
    "El torneo no cuenta para el ranking oficial publicado, o no movió a nadie.",
  logros: "No se ganaron logros en este torneo (o falta recalcularlos).",
  prode: "El torneo no tiene un Prode liquidado.",
  rivalidad: "No se cruzaron jugadores con historial entre ellos.",
};
