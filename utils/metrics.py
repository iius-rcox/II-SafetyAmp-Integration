from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from typing import List, Optional


def _get_existing(name: str):
    try:
        return REGISTRY._names_to_collectors[name]
    except KeyError:
        return None


def get_or_create_counter(name: str, description: str, labelnames: Optional[List[str]] = None) -> Counter:
    existing = _get_existing(name)
    if isinstance(existing, Counter):
        return existing
    if existing is not None:
        # Different type already registered; raise for clarity
        raise ValueError(f"A collector named '{name}' is already registered with a different type")
    return Counter(name, description, labelnames=labelnames or [])


essentially_label_list_type = List[str]

def get_or_create_gauge(name: str, description: str, labelnames: Optional[List[str]] = None) -> Gauge:
    existing = _get_existing(name)
    if isinstance(existing, Gauge):
        return existing
    if existing is not None:
        raise ValueError(f"A collector named '{name}' is already registered with a different type")
    return Gauge(name, description, labelnames=labelnames or [])


def get_or_create_histogram(name: str, description: str, labelnames: Optional[List[str]] = None, buckets: Optional[List[float]] = None) -> Histogram:
    existing = _get_existing(name)
    if isinstance(existing, Histogram):
        return existing
    if existing is not None:
        raise ValueError(f"A collector named '{name}' is already registered with a different type")
    if buckets is not None:
        return Histogram(name, description, labelnames=labelnames or [], buckets=buckets)
    return Histogram(name, description, labelnames=labelnames or [])
