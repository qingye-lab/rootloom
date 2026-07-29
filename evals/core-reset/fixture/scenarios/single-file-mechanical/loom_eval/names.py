def normalize_name(value: str) -> str:
    tmp = " ".join(value.strip().split())
    return tmp.casefold()
