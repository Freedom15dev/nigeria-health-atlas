"""NDHS 2024 state-level indicators from the DHS Program API.

Indicator IDs were looked up with the /indicators endpoint (not guessed):
  AH_HINS_M_ANY  Any health insurance [Men]
  AH_HINS_W_NON  No health insurance [Women]  (the API has no "any" indicator for women)
  HC_WIXQ_P_4TH  Population in the fourth wealth quintile
  HC_WIXQ_P_HGH  Population in the highest wealth quintile
  RH_PAHC_W_DIS  Problems in accessing health care: distance to health facility [Women]
  RH_PAHC_W_MON  Problems in accessing health care: getting money for treatment [Women]
"""
import requests

from common import save_raw_if_changed

SURVEY = "NG2024DHS"
INDICATORS = [
    "AH_HINS_M_ANY", "AH_HINS_W_NON",
    "HC_WIXQ_P_4TH", "HC_WIXQ_P_HGH",
    "RH_PAHC_W_DIS", "RH_PAHC_W_MON",
]
URL = "https://api.dhsprogram.com/rest/dhs/data"
FIELDS = ("SurveyId,IndicatorId,Indicator,CharacteristicLabel,LevelRank,Value,Precision,"
          "DenominatorWeighted,DenominatorUnweighted,CILow,CIHigh,IsPreferred")


def main() -> None:
    params = {
        "surveyIds": SURVEY, "indicatorIds": ",".join(INDICATORS),
        "breakdown": "subnational", "returnFields": FIELDS, "perpage": 5000, "f": "json",
    }
    try:
        r = requests.get(URL, params=params, timeout=120)
        r.raise_for_status()
        data = r.json()["Data"]
    except Exception as e:  # keep the pipeline usable offline
        print(f"  DHS API unavailable ({e}); using the latest saved snapshot")
        return
    data = sorted(data, key=lambda d: (d["IndicatorId"], d["CharacteristicLabel"]))
    save_raw_if_changed(f"dhs_{SURVEY}_state", {"url": URL, "params": params, "Data": data}, data)


if __name__ == "__main__":
    main()
