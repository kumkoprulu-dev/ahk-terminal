"""Kombinatoryal gösterge araması — tekli → ikili → üçlü, sepet (BIST+kripto) üzerinde.

Kullanım:
  python scripts/run_combo_search.py singles          # tüm göstergeler tek tek
  python scripts/run_combo_search.py pairs  A B C ...  # verilen hayatta-kalanların ikilileri
  python scripts/run_combo_search.py triples A B C ... # verilen hayatta-kalanların üçlüleri
Argümansız pairs/triples: tekli taramanın top-N'i otomatik hayatta-kalan seçilir.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import combo_search as cs  # noqa: E402
from app.data import service  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402

try:
    from app.data import okx_provider  # noqa: E402
except Exception:
    okx_provider = None

BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]


def load_basket(interval="1d"):
    basket = {}
    for s in BIST:
        try:
            basket[s] = service.get_ohlcv(s, interval, "5y")
        except Exception as e:
            print(f"  {s}: veri HATA {str(e)[:40]}")
    if okx_provider is not None:
        for s in CRYPTO:
            try:
                basket[s.replace("-USDT-SWAP", "")] = okx_provider.get_ohlcv(s, interval, bars=1000)
            except Exception as e:
                print(f"  {s}: veri HATA {str(e)[:40]}")
    ok = {k: v for k, v in basket.items() if v is not None and len(v) > 200}
    print(f"Sepet: {len(ok)} sembol yüklendi ({', '.join(ok)})")
    return ok


def show(title, ranked, top=25):
    print(f"\n{'='*84}\n {title}\n{'='*84}")
    print(f"  {'#':>3}  {'kombo':<30}{'skor':>7}{'Sharpe':>8}{'getiri%':>9}{'işlem':>7}{'DD%':>7}{'kâr%':>6}{'>B&H%':>7}")
    for i, d in enumerate(ranked[:top], 1):
        name = "+".join(d["names"])
        print(f"  {i:>3}  {name:<30}{d['score']:>7}{d['sharpe']:>8}{d['ret']:>9}"
              f"{d['trades']:>7}{d['dd']:>7}{d['prof_pct']:>6}{d['beat_bh']:>7}")


def save(stage: str, ranked: list, basket: dict) -> None:
    """Sıralama sonuçlarını kalıcı veritabanına yaz (rank'lı)."""
    rows = [dict(d, _rank=i) for i, d in enumerate(ranked, 1)]
    db = get_results_store()
    run_id = db.record("run_combo_search", f"combo_{stage}", rows,
                       label=f"{stage} — sepet {len(basket)} sembol",
                       params={"stage": stage, "basket": sorted(basket)})
    print(f"\n  [DB] {len(rows)} sonuç kaydedildi → results.sqlite (run #{run_id})")


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "singles"
    survivors = sys.argv[2:]
    basket = load_basket()

    if stage == "singles":
        ranked = cs.rank_singles(basket)
        show(f"TEKLİ — {len(ranked)} gösterge (sepet {len(basket)} sembol, in-sample triage)", ranked, top=99)
        keep = [d["names"][0] for d in ranked if d["score"] > 0][:14]
        print(f"\n  >>> Hayatta kalanlar (skor>0, top14): {' '.join(keep)}")
        save(stage, ranked, basket)

    elif stage == "pairs":
        if not survivors:
            survivors = [d["names"][0] for d in cs.rank_singles(basket) if d["score"] > 0][:14]
        print(f"İkili taban ({len(survivors)}): {' '.join(survivors)}")
        ranked = cs.rank_pairs(survivors, basket, cross_cat_only=True)
        show(f"İKİLİ — kategoriler-arası ({len(ranked)} çift)", ranked, top=30)
        save(stage, ranked, basket)

    elif stage == "triples":
        if not survivors:
            survivors = [d["names"][0] for d in cs.rank_singles(basket) if d["score"] > 0][:12]
        print(f"Üçlü taban ({len(survivors)}): {' '.join(survivors)}")
        ranked = cs.rank_triples(survivors, basket, distinct_cat=True)
        show(f"ÜÇLÜ — çok-kategorili ({len(ranked)} kombo)", ranked, top=30)
        save(stage, ranked, basket)


if __name__ == "__main__":
    main()
