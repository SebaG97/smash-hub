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
};
export type Event = {
  id: string;
  tournament_id: string;
  name: string;
  game: string;
  team_size: number;
  entrant_count: number;
  status: string | null;
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
export type Player = { id: string; tag: string };
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
  aliases: string[];
  history: Page<History>;
  scopes: Scope[];
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
