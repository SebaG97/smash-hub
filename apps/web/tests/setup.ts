import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { setMe } from "../src/lib/session";

// Nobody signed in unless a test says otherwise, so no test pays an /auth/me request.
beforeEach(() => {
  setMe({
    user: null,
    legacy_admin_key: false,
  });
});
