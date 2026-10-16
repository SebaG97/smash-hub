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
};
