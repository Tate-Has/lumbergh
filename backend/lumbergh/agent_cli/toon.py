"""Minimal TOON renderer for lb's stdout (applied only at the output boundary)."""


def _cell(value) -> str:
    if value is None:
        value = ""
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if s == "" or any(c in s for c in ' ,:"\n'):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def render_collection(name: str, rows: list[dict], fields: list[str]) -> str:
    header = f"{name}[{len(rows)}]{{{','.join(fields)}}}:"
    body = ["  " + ",".join(_cell(row.get(f)) for f in fields) for row in rows]
    return "\n".join([header, *body])


def render_object(pairs) -> str:
    return "\n".join(f"{k}: {_cell(v)}" for k, v in pairs)


def render_block(key: str, text: str) -> str:
    body = "\n".join("  " + line for line in text.split("\n"))
    return f"{key}: |\n{body}"
