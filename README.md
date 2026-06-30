# Analysverktyg

Internt Streamlit-verktyg för Härryda Djurklinik AB:s expansionsanalys.

## Syfte

Verktyget hjälper till att besvara frågan: var bör Härryda Djurklinik expandera?

Första versionen använder lokala CSV-filer för hundar, katter och hästar. SCB PxWeb och SCB Företagsregister är förberedda som platshållare men inga live-anrop görs ännu.

## Förväntade CSV-kolumner

Hundar:

```text
Län, Kommun, Registrerade_hundar_2025
```

Katter:

```text
Län, Kommun, Registrerade_katter_2025
```

Hästar:

```text
Län, Hästar_2016, Hästar_på_jordbruk_2016, Hästar_på_ridskolor_2016, Hästar_per_1000_invånare_2016
```

## Kör lokalt

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Exporter

Appen kan ladda ned:

- master municipality dataset som CSV
- top expansion candidates som CSV
- Excel-fil med flera flikar
- AI-vänlig Markdown-sammanfattning
- AI-vänlig JSON-context

## Projektstruktur

```text
app.py
src/
  import_animals.py
  analysis.py
  export.py
  validation.py
data/
  raw/
  processed/
output/
README.md
requirements.txt
```
