import re


def parse_duration(text: str) -> float:
    """'1h30m' -> 5400.0 ; supports d, h, m, s ; a bare number means seconds."""
    if re.fullmatch(r"\d+(\.\d+)?", text.strip()):
        return float(text)
    total = 0.0
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)([dhms])", text):
        total += float(num) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
    if not total:
        raise ValueError(f"bad duration: {text!r}")
    return total


def batched(iterable, size: int):
    """Yield lists of at most `size` items."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
