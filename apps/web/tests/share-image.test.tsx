import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ShareImage } from "../src/components/share-image";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

beforeEach(() => {
  let n = 0;
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: () => `blob:${++n}`,
    revokeObjectURL: () => undefined,
  });
});
afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

const rows = Array.from({ length: 14 }, (_, i) => ({
  place: i + 1,
  tag: `P${i + 1}`,
  mains: [{ character: "Ryu", games: 1, share: 100, costume: 2 }],
}));

function file(name: string, type: string, size = 10) {
  return new File(["x".repeat(size)], name, { type });
}

it("readers only get the download link", () => {
  render(
    <ShareImage
      endpoint="/og/ranking/rk"
      filename="rk.png"
      label="Bajar"
      rows={rows}
    />,
  );
  expect(screen.getByRole("link", { name: "Bajar" })).toHaveAttribute(
    "href",
    "/og/ranking/rk",
  );
  expect(
    screen.queryByRole("button", { name: "Personalizar imagen" }),
  ).not.toBeInTheDocument();
});

it("organizers replace renders with their own pictures", async () => {
  saveAdmin({ key: "k", name: "Org" });
  const fetchMock = vi.fn(async () => ({
    ok: true,
    blob: async () => new Blob(["png"]),
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(
    <ShareImage
      endpoint="/og/ranking/rk"
      filename="rk.png"
      label="Bajar"
      rows={rows}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Personalizar imagen" }));
  // Only the 12 places the image shows.
  expect(screen.getAllByRole("listitem")).toHaveLength(12);
  expect(document.querySelector(".share-slots img")).toHaveAttribute(
    "src",
    "/renders/ryu/2?w=160",
  );

  fireEvent.change(screen.getByLabelText("Imagen para P2"), {
    target: { files: [file("notes.txt", "text/plain")] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("no es una imagen");
  fireEvent.change(screen.getByLabelText("Imagen para P2"), {
    target: { files: [file("big.jpg", "image/jpeg", 6 * 1024 * 1024)] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("más de 5 MB");

  fireEvent.change(screen.getByLabelText("Imagen para P1"), {
    target: { files: [file("foto.jpg", "image/jpeg")] },
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(document.querySelector(".share-slots img")).toHaveAttribute(
    "src",
    "blob:1",
  );
  expect(
    screen.getByRole("button", { name: "Usar el render" }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Generar imagen" }));
  expect(
    await screen.findByRole("link", { name: "Descargar imagen personalizada" }),
  ).toHaveAttribute("download", "rk.png");
  const [url, init] = fetchMock.mock.calls[0] as unknown as [
    string,
    RequestInit,
  ];
  expect(url).toBe("/og/ranking/rk");
  expect(init.method).toBe("POST");
  expect((init.headers as Record<string, string>).Authorization).toBe(
    "Bearer k",
  );
  const form = init.body as FormData;
  expect([...form.keys()]).toEqual(["image-0"]);
});

it("shows the server's explanation when generation fails", async () => {
  saveAdmin({ key: "k", name: "Org" });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      text: async () => "Necesitás la clave de organizador.",
    })),
  );
  render(
    <ShareImage
      endpoint="/og/ranking/rk"
      filename="rk.png"
      label="Bajar"
      rows={rows}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Personalizar imagen" }));
  fireEvent.click(screen.getByRole("button", { name: "Generar imagen" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Necesitás la clave de organizador.",
  );
});
