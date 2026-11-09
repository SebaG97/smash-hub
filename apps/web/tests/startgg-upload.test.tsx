import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  StartggUpload,
  type UploadPlan,
} from "../src/components/startgg-upload";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const plan: UploadPlan = {
  enabled: true,
  phase: { id: "77", name: "Pools (BO3)" },
  confirm_text: "center-stage-2026",
  changes: [{ tag: "Zio", before: 5, after: 4 }],
  unchanged: 85,
  not_seeded: [],
  not_on_startgg: [],
  digest: "abcdef0123456789",
};

function signIn() {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
}

it("writes only after reviewing and typing the slug", async () => {
  signIn();
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const body =
        init?.method === "POST"
          ? { status: "pushed", changed: 1, verified: true, wrong: [] }
          : plan;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
  render(<StartggUpload slug="center-stage-2026" />);
  fireEvent.click(
    screen.getByRole("button", { name: "Revisar cambios para subir" }),
  );
  expect(await screen.findByText("Zio")).toBeInTheDocument();
  const upload = screen.getByRole("button", { name: "Subir a start.gg" });
  expect(upload).toBeDisabled();
  const typed = screen.getByLabelText("Texto de confirmación");
  expect(typed).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(typed, { target: { value: "center" } });
  expect(upload).toBeDisabled();
  fireEvent.change(typed, { target: { value: "center-stage-2026" } });
  expect(upload).toBeEnabled();
  expect(calls.some((c) => c.init?.method === "POST")).toBe(false);
  fireEvent.click(upload);
  expect(
    await screen.findByText(/se verificó leyendo start.gg/),
  ).toBeInTheDocument();
  const post = calls.find((c) => c.init?.method === "POST")!;
  expect(JSON.parse(String(post.init?.body))).toEqual({
    digest: plan.digest,
    confirm: "center-stage-2026",
  });
});

it("explains when the server has uploads switched off", async () => {
  signIn();
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...plan, enabled: false })),
      ),
    ),
  );
  render(<StartggUpload slug="center-stage-2026" />);
  fireEvent.click(
    screen.getByRole("button", { name: "Revisar cambios para subir" }),
  );
  expect(
    await screen.findByText(/está apagado en el servidor/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Subir a start.gg" })).toBeNull();
});
