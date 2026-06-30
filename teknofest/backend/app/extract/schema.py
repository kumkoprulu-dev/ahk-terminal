"""Katılım bankacılığı ürün/kampanya bilgi-çıkarım şeması.

Tasarım ilkesi: HER çıkarılan değer bir `Field` nesnesidir; değerin yanında
o değeri destekleyen KAYNAK ALINTI ve güven puanı taşınır. Böylece sonuç
"izlenebilir" olur — bir kâr payı oranı uydurulmuşsa kaynağı olmadığından
yakalanır (grounding). Bu, halüsinasyonsuzluk garantisinin temelidir.
"""
from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UrunTipi(str, Enum):
    katilma_hesabi = "katilma_hesabi"      # Katılma hesabı (vadeli)
    altin_hesabi = "altin_hesabi"          # Altın katılma hesabı
    doviz_katilma = "doviz_katilma"        # Döviz katılma hesabı
    finansman = "finansman"                # Bireysel/konut/taşıt finansmanı
    kart_kampanya = "kart_kampanya"        # Kart / harcama kampanyası
    katilim_sigorta = "katilim_sigorta"    # Tekafül / katılım sigortası
    diger = "diger"


class Grounded(BaseModel, Generic[T]):
    """Bir alanın değeri + kaynak kanıtı."""
    value: T | None = None
    source_quote: str | None = Field(
        default=None, description="Değeri destekleyen birebir kaynak cümle/ibare"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def grounded(self) -> bool:
        return self.value is not None and bool(self.source_quote)


class KatilimUrunu(BaseModel):
    """Tek bir katılım bankacılığı ürünü/kampanyası — yapılandırılmış kayıt."""

    banka: str
    urun_adi: str
    urun_tipi: UrunTipi = UrunTipi.diger

    # Sayısal/temel alanlar — hepsi grounding'li
    kar_payi_orani: Grounded[float] = Field(default_factory=Grounded)   # yıllık %, brüt
    kar_payi_orani_net: Grounded[float] = Field(default_factory=Grounded)
    # Katılım bankacılığına özgü: kâr PAYLAŞIM oranı (ör. "90-10" = %90 müşteri).
    # Faizsizlikte getiri sabit % değil; paylaşım oranı asıl üründür.
    paylasim_orani: Grounded[str] = Field(default_factory=Grounded)
    vade_gun: Grounded[int] = Field(default_factory=Grounded)           # gün cinsinden
    para_birimi: Grounded[str] = Field(default_factory=Grounded)        # TRY/USD/EUR/XAU
    min_tutar: Grounded[float] = Field(default_factory=Grounded)
    max_tutar: Grounded[float] = Field(default_factory=Grounded)

    avantajlar: list[str] = Field(default_factory=list)
    kosullar: list[str] = Field(default_factory=list)

    kampanya: bool = False
    kampanya_baslangic: Grounded[str] = Field(default_factory=Grounded)  # ISO tarih
    kampanya_bitis: Grounded[str] = Field(default_factory=Grounded)

    kaynak_url: str | None = None
    cekildigi_tarih: str | None = None  # ISO

    def grounded_field_count(self) -> int:
        return sum(
            1
            for f in (
                self.kar_payi_orani,
                self.kar_payi_orani_net,
                self.vade_gun,
                self.para_birimi,
                self.min_tutar,
                self.max_tutar,
                self.kampanya_baslangic,
                self.kampanya_bitis,
            )
            if f.grounded
        )

    def to_flat(self) -> dict:
        """Karşılaştırma/dashboard için düz sözlük."""
        return {
            "banka": self.banka,
            "urun_adi": self.urun_adi,
            "urun_tipi": self.urun_tipi.value,
            "kar_payi_orani": self.kar_payi_orani.value,
            "kar_payi_orani_net": self.kar_payi_orani_net.value,
            "paylasim_orani": self.paylasim_orani.value,
            "vade_gun": self.vade_gun.value,
            "para_birimi": self.para_birimi.value,
            "min_tutar": self.min_tutar.value,
            "max_tutar": self.max_tutar.value,
            "avantajlar": self.avantajlar,
            "kosullar": self.kosullar,
            "kampanya": self.kampanya,
            "kampanya_bitis": self.kampanya_bitis.value,
            "kaynak_url": self.kaynak_url,
            "guven": round(self._mean_conf(), 3),
        }

    def _mean_conf(self) -> float:
        confs = [
            f.confidence
            for f in (self.kar_payi_orani, self.vade_gun, self.para_birimi, self.min_tutar)
            if f.value is not None
        ]
        return sum(confs) / len(confs) if confs else 0.0


class ExtractionResult(BaseModel):
    urunler: list[KatilimUrunu] = Field(default_factory=list)
    provider: str = "mock"
    warnings: list[str] = Field(default_factory=list)
