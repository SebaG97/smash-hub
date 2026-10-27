"use client";

import { Resource } from "./competition-browser";
import { PlayerOfMonthCard, type PlayerOfMonth } from "./insights";

/** Home: the player of the month, when there is enough recent activity. */
export function HomeSpotlight() {
  return (
    <Resource<{
      player_of_month: PlayerOfMonth | null;
    }>
      path="insights/records"
      optional
    >
      {(d) =>
        d.player_of_month ? <PlayerOfMonthCard p={d.player_of_month} /> : null
      }
    </Resource>
  );
}
