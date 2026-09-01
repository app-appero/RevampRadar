import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "discovery" / "data" / "_comuni_raw.json"
DST = ROOT / "app" / "discovery" / "data" / "italy_geo.json"

PREFERRED = [
    "Valle d'Aosta/Vallée d'Aoste",
    "Piemonte",
    "Liguria",
    "Lombardia",
    "Trentino-Alto Adige/Südtirol",
    "Veneto",
    "Friuli-Venezia Giulia",
    "Emilia-Romagna",
    "Toscana",
    "Umbria",
    "Marche",
    "Lazio",
    "Abruzzo",
    "Molise",
    "Campania",
    "Puglia",
    "Basilicata",
    "Calabria",
    "Sicilia",
    "Sardegna",
]


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    tree: dict[str, dict[str, set[str]]] = {}
    for item in raw:
        region = item["regione"]["nome"]
        province = item["provincia"]["nome"]
        city = item["nome"]
        tree.setdefault(region, {}).setdefault(province, set()).add(city)
    actual = list(tree)
    ordered: list[str] = []
    used: set[str] = set()
    for want in PREFERRED:
        prefix = want.split("/")[0]
        for key in actual:
            if key == want or key.startswith(prefix):
                if key not in used:
                    ordered.append(key)
                    used.add(key)
                    break
    ordered.extend(key for key in sorted(actual) if key not in used)
    payload = []
    for region in ordered:
        provinces = [
            {"name": name, "cities": sorted(cities, key=str.casefold)}
            for name, cities in sorted(tree[region].items(), key=lambda item: item[0].casefold())
        ]
        payload.append({"name": region, "provinces": provinces})
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(
        json.dumps({"regions": payload}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    SRC.unlink()
    print(f"wrote {DST} ({DST.stat().st_size} bytes, {len(payload)} regions)")


if __name__ == "__main__":
    main()
