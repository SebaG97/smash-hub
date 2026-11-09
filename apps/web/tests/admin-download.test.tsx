import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AdminDownload } from "../src/components/admin-download";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

it("fetches the image with the organizer's key and saves it", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  const fetch = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(new Response(new Blob([url, String(init?.method)]))),
  );
  vi.stubGlobal("fetch", fetch);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => undefined);
  render(
    <AdminDownload
      endpoint="/og/seeding/cs/pools"
      filename="cs-pools.png"
      label="Descargar pools (horizontal)"
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /Descargar pools/ }));
  await vi.waitFor(() => expect(click).toHaveBeenCalled());
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/og/seeding/cs/pools");
  expect(init?.method).toBe("POST");
  expect((init?.headers as Record<string, string>).Authorization).toBe(
    "Bearer secret-key",
  );
});

it("is not offered to readers", () => {
  const { container } = render(
    <AdminDownload endpoint="/x" filename="x.png" label="Descargar" />,
  );
  expect(container).toBeEmptyDOMElement();
});
