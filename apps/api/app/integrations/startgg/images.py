"""Tournament logo and banner from start.gg (hosted there; the hub only keeps the links)."""

KINDS = ("profile", "banner")


def tournament_images(images):
    """start.gg `images` -> {"profile": url, "banner": url}, with only what exists."""
    found = {}
    for image in images or []:
        kind, url = image.get("type"), image.get("url")
        if kind in KINDS and kind not in found and str(url or "").startswith("https://"):
            found[kind] = url
    return found
