export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
export type Tournament = {
  id: string;
  name: string;
  starts_at: string | null;
  ends_at: string | null;
  status: string | null;
  games: string[];
  participant_count: number;
  entrant_count: number;
  source: string | null;
  location: { city?: string; country_code?: string } | null;
  images?: { profile?: string; banner?: string } | null;
  counts_for_ranking?: boolean;
  seeding_reliable?: boolean;
};
export type Event = {
  id: string;
  tournament_id: string;
  name: string;
  game: string;
  team_size: number;
  entrant_count: number;
  status: string | null;
  /** Mission 20: main bracket (ranking, titles) or secondary; null for team events. */
  main?: boolean | null;
  main_set?: boolean;
};
export type Entrant = {
  id: string;
  name: string;
  seed: number | null;
  placement: number | null;
  members: { player_id: string; tag: string }[];
};
export type Match = {
  id: string;
  status: string;
  resolution:
    | "unresolved"
    | "played"
    | "dq"
    | "bye"
    | "placeholder"
    | "conditional_unused";
  classification_reason: string;
  stats_eligible: boolean;
  ranking_eligible: boolean;
  round_label: string | null;
  sides: {
    entrant_id: string | null;
    name: string | null;
    score: number | null;
    is_winner: boolean;
  }[];
};
export type Main = {
  costume?: number;
  character: string;
  icon?: string | null;
  games: number;
  share: number;
};
export type Player = {
  id: string;
  tag: string;
  mains?: Main[];
  /** Approved team or prefix (Mission 22). */
  prefix?: string | null;
};
export type History = {
  tournament_id: string;
  tournament_name: string;
  event_id: string;
  event_name: string;
  tag: string;
  entrant_name: string;
  placement: number | null;
};
export type PlayerDetail = Player & {
  /** Key of their team page when the prefix is a team. */
  team?: string | null;
  aliases: string[];
  history: Page<History>;
  scopes: Scope[];
  ranking?: { slug: string; name: string; place: number } | null;
  best_results?: {
    placement: number;
    entrants: number | null;
    tournament_id: string;
    tournament_name: string;
    starts_at: string | null;
    event_name?: string | null;
    main?: boolean;
  }[];
};

export type Scope = {
  game_id: string;
  game_name: string;
  mode: "singles" | "doubles";
};
export type Statistics = {
  player: Player;
  sets_played: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  tournaments_played: number;
  tournaments_registered: number;
  first_set_at: string | null;
  last_set_at: string | null;
  best_final_placement: number | null;
  latest_tournament?: { id: string; name: string } | null;
  unique_opponents: number;
};
export type CompetitiveMatch = {
  id: string;
  tournament_id: string;
  tournament_name: string;
  event_id: string;
  event_name: string;
  completed_at: string | null;
  opponents: Player[];
  result: "W" | "L";
  score: number | null;
  opponent_score: number | null;
  round_label: string | null;
  stats_eligible: true;
  source: string | null;
  source_url: string | null;
};
export type FrequentOpponent = {
  opponent: Player;
  sets_played: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  last_encounter_at: string | null;
};
export type HeadToHead = {
  player_a: Player;
  player_b: Player;
  encounters: number;
  wins_a: number;
  wins_b: number;
  win_rate_a: number | null;
  win_rate_b: number | null;
  first_encounter_at: string | null;
  last_encounter_at: string | null;
  history: Page<CompetitiveMatch>;
};

export type SeedingProjectSummary = {
  slug: string;
  name: string;
  kind: "seeding" | "ranking";
  country_code: string | null;
  startgg_event_slug?: string | null;
  event_date: string;
  window_start: string;
  published?: boolean;
};
export type SeedingOverride = {
  player_id: string;
  seed: number;
  reason: string;
  actor: string;
  updated_at: string | null;
};
export type SeedingRow = {
  seed: number;
  seed_algorithm: number;
  player_id: string;
  gamer_tag: string;
  rating: number | null;
  rd: number | null;
  conservative: number | null;
  placement_score: number | null;
  best_placements: {
    placement: number;
    entrants: number;
    tournament: string;
    date: string;
    score: number;
  }[];
  wins: number;
  losses: number;
  sets: number;
  offline_sets: number;
  events: number;
  offline_events: number;
  last_event: string | null;
  main_circuit: string | null;
  circuits: Record<string, number>;
  confidence: string;
  combined: number | null;
  rank_conservative: number | null;
  rank_placement: number | null;
  merged_sets: number;
  elo: number | null;
  bradley_terry: number | null;
  points: number | null;
  win_rate: number | null;
  wilson: number | null;
  eligible: boolean;
  scores: Record<string, number | null>;
  ranks: Record<string, number>;
  reasons_by_method?: Record<string, string[]>;
  mains?: Main[];
  flags: string[];
  reasons: string[];
  override: SeedingOverride | null;
};
export type PublicSeedingView = {
  slug: string;
  name: string;
  kind: "seeding" | "ranking";
  country_code: string | null;
  published: boolean;
  public: true;
  method: string;
  method_label: string;
  startgg_event_slug: string | null;
  event_date: string;
  window_start: string;
  data_cutoff: string | null;
  run: {
    window_start: string;
    window_end: string;
    set_count: number;
    event_count: number;
    parameters: { min_sets: number };
  } | null;
  seeds: {
    seed: number;
    gamer_tag: string;
    prefix?: string | null;
    mains?: Main[];
    wins?: number;
    losses?: number;
    sets?: number;
    last_event?: string | null;
    score?: number | null;
    reasons?: string[];
  }[];
};
export type SeedingMethod = { id: string; label: string; description: string };
export type SeedingView = {
  slug: string;
  name: string;
  kind: "seeding" | "ranking";
  country_code: string | null;
  published: boolean;
  public?: false;
  method: string | null;
  methods: SeedingMethod[];
  startgg_event_slug: string | null;
  event_date: string;
  window_start: string;
  data_cutoff: string | null;
  refresh: {
    status: "IDLE" | "RUNNING" | "FAILED";
    started_at: string | null;
    progress: { step: string; done: number; total: number | null } | null;
    error: string | null;
  };
  dataset: {
    entrants: number;
    sets: number;
    counted_sets: number;
    events: number;
    offline_events: number;
    classifications: Record<string, number>;
  };
  merges: {
    from_player_id: string;
    to_player_id: string;
    tag: string | null;
  }[];
  duplicates: {
    player_id: string;
    kept_player_id: string;
    tag: string | null;
  }[];
  excluded_tournaments?: string[];
  merge_candidates?: {
    source: string;
    source_tag: string;
    target: string;
    target_tag: string;
    sets: number;
    counted_sets: number;
  }[];
  run: {
    id: string;
    created_at: string;
    actor: string;
    algorithm_version: string;
    parameters: Record<string, number>;
    window_start: string;
    window_end: string;
    data_cutoff: string | null;
    set_count: number;
    event_count: number;
    offline_event_count: number;
    player_count: number;
  } | null;
  seeds: SeedingRow[];
};
