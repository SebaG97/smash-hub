import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { FlagPicker, flagEmoji } from "../src/components/flag-picker";
import type { SeedingRow } from "../src/lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const row = (seed: number, tag: string, extra: Partial<SeedingRow>) =>
  ({
    seed,
    player_id: String(seed * 100),
    gamer_tag: tag,
    main_circuit: "PY",
    country: "PY",
    country_chosen: false,
    ...extra,
  }) as SeedingRow;

const rows = [
  row(1, "Chag", { main_circuit: "MX", country: "MX" }),
  row(15, "Pocketo", { main_circuit: "ONLINE", country: null }),
];

it("lists players without a flag and saves the chosen one", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  const fetch = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify({ url, init }))),
  );
  vi.stubGlobal("fetch", fetch);
  const onChange = vi.fn();
  render(<FlagPicker rows={rows} onChange={onChange} />);
  expect(screen.queryByLabelText("Bandera de Chag")).toBeNull();
  expect(screen.getByText("juega online")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Bandera de Pocketo"), {
    target: { value: "PY" },
  });
  await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  const [url, init] = fetch.mock.calls[0];
  expect(url).toMatch(/\/seeding\/countries\/1500$/);
  expect(JSON.parse(String(init?.body))).toEqual({ country: "PY" });
  fireEvent.click(
    screen.getByRole("button", { name: /Cambiar la bandera de cualquiera/ }),
  );
  expect(screen.getByLabelText("Bandera de Chag")).toHaveTextContent(
    `${flagEmoji("MX")} MX (circuito)`,
  );
});

it("is not shown to readers", () => {
  const { container } = render(<FlagPicker rows={rows} onChange={vi.fn()} />);
  expect(container).toBeEmptyDOMElement();
});
