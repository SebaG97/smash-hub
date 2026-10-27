/**
 * Local stock icons in /public/characters (cleaned SVGs, see docs/design.md).
 * start.gg names map to the game's file names; a few use internal names.
 */
const ALIASES: Record<string, string> = {
  "Banjo-Kazooie": "banjo_and_kazooie",
  Hero: "dq_hero",
  Incineroar: "gaogaen",
  "Mii Brawler": "mii_fighter",
  "Mii Gunner": "mii_fighter",
  "Mii Swordfighter": "mii_fighter",
  "Min Min": "minmin",
  "Piranha Plant": "packun_flower",
  "Pyra & Mythra": "homura",
  "R.O.B.": "rob",
  Rosalina: "rosalina_and_luma",
  "Simon Belmont": "simon",
};

const AVAILABLE = new Set([
  "banjo_and_kazooie",
  "bayonetta",
  "bowser",
  "bowser_jr",
  "byleth",
  "captain_falcon",
  "chrom",
  "cloud",
  "corrin",
  "daisy",
  "dark_pit",
  "dark_samus",
  "diddy_kong",
  "donkey_kong",
  "dq_hero",
  "dr_mario",
  "duck_hunt",
  "falco",
  "fox",
  "ganondorf",
  "gaogaen",
  "greninja",
  "homura",
  "ice_climbers",
  "ike",
  "inkling",
  "isabelle",
  "jigglypuff",
  "joker",
  "kazuya",
  "ken",
  "king_dedede",
  "king_k_rool",
  "kirby",
  "link",
  "little_mac",
  "lucario",
  "lucas",
  "lucina",
  "luigi",
  "mario",
  "marth",
  "mega_man",
  "meta_knight",
  "mewtwo",
  "mii_fighter",
  "minmin",
  "mr_game_and_watch",
  "ness",
  "olimar",
  "pac_man",
  "packun_flower",
  "palutena",
  "peach",
  "pichu",
  "pikachu",
  "pit",
  "pokemon_trainer",
  "richter",
  "ridley",
  "rob",
  "robin",
  "rosalina_and_luma",
  "roy",
  "ryu",
  "samus",
  "sephiroth",
  "sheik",
  "shulk",
  "simon",
  "snake",
  "sonic",
  "sora",
  "steve",
  "terry",
  "toon_link",
  "villager",
  "wario",
  "wii_fit_trainer",
  "wolf",
  "yoshi",
  "young_link",
  "zelda",
  "zero_suit_samus",
]);

function key(name: string) {
  return (
    ALIASES[name] ??
    name
      .toLowerCase()
      .replace(/&/g, "and")
      .replace(/\./g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
  );
}

/** Path of the local icon, or null (for example "Random Character"). */
export function characterIcon(name: string): string | null {
  const k = key(name);
  return AVAILABLE.has(k) ? `/characters/${k}.svg` : null;
}
