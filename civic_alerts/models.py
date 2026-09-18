"""Structure commune a toutes les sources d'annonces."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Listing:
    source: str
    listing_id: str
    title: str
    url: str
    price: int | None = None
    year: int | None = None
    odometer_km: int | None = None
    transmission: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def key(self) -> str:
        """Identifiant stable inter-execution, utilise pour la deduplication."""
        return f"{self.source}:{self.listing_id}"

    def to_dict(self) -> dict:
        return asdict(self)

    def human_price(self) -> str:
        return f"{self.price:,} $".replace(",", " ") if self.price is not None else "prix n/d"

    def human_odometer(self) -> str:
        if self.odometer_km is None:
            return "km n/d"
        return f"{self.odometer_km:,} km".replace(",", " ")
