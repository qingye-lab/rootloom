def slugify(value: str) -> str:
    return "-".join(value.strip().casefold().split())
