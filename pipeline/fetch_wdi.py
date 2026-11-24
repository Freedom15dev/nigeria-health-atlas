"""World Bank WDI, Nigeria, national health-spending indicators.

  SH.XPD.OOPC.CH.ZS  Out-of-pocket expenditure (% of current health expenditure)
  SH.XPD.CHEX.PC.CD  Current health expenditure per capita (current US$)
  SH.XPD.GHED.CH.ZS  Domestic general government health expenditure (% of current health expenditure)
  PA.NUS.FCRF        Official exchange rate (NGN per US$, period average): used by the centre model
National only: never spread across states (data trap 8).
"""
import requests

from common import save_raw_if_changed

INDICATORS = ["SH.XPD.OOPC.CH.ZS", "SH.XPD.CHEX.PC.CD", "SH.XPD.GHED.CH.ZS", "PA.NUS.FCRF"]
URL = "https://api.worldbank.org/v2/country/NGA/indicator/{}"


def main() -> None:
    out = {}
    try:
        for ind in INDICATORS:
            r = requests.get(URL.format(ind), params={"format": "json", "per_page": 100}, timeout=60)
            r.raise_for_status()
            js = r.json()
            if len(js) < 2 or js[1] is None:
                raise ValueError(f"no data returned for {ind}")
            out[ind] = sorted(
                [{"year": d["date"], "value": d["value"], "indicator": d["indicator"]["value"]} for d in js[1]],
                key=lambda d: d["year"],
            )
    except Exception as e:
        print(f"  World Bank API unavailable ({e}); using the latest saved snapshot")
        return
    save_raw_if_changed("wdi_nga", out, out)


if __name__ == "__main__":
    main()
