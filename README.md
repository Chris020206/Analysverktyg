# Analysverktyg

Internt Streamlit-verktyg för Härryda Djurklinik AB:s expansionsanalys.

## Syfte

Verktyget hjälper till att besvara frågan: var bör Härryda Djurklinik expandera?

Första versionen använder lokala CSV-filer för hundar, katter och hästar. SCB PxWeb används för folkmängd när användaren hämtar data i appen. Övriga SCB-fält och SCB Företagsregister är fortfarande platshållare.

## Förenklad SCB-strategi

Appen ska i normal användning bara hämta nödvändiga råvariabler och beräkna resten internt.

Aktiva eller planerade råvariabler:

- `Folkmangd` från SCB PxWeb
- `Yta_km2` från SCB PxWeb när stabil tabell finns, eller från uppladdad GeoJSON om tillgängligt
- veterinärföretag från Företagsregistret senare

Indikatorer som beräknas internt:

- `Befolkningstathet = Folkmangd / Yta_km2`
- `Hundar_per_1000_inv`
- `Katter_per_1000_inv`
- `Smadjur_per_1000_inv`
- `Veterinarforetag_per_10000_smadjur`
- `Smadjur_per_veterinarforetag`

Inkomst, hushåll och boendeform används inte i aktiv scoring just nu. Eventuella placeholder-kolumner kan finnas kvar i exporter, men modellen ska inte förlita sig på dem.

## Preliminär scoringmodell

`Expansion_score` är en tidig beslutsstödsindikator, inte en slutlig rekommendation. Den normaliserar tillgängliga komponenter till 0-100 och viktar dem så här:

- Smådjursefterfrågan (`Smadjur_score`): 30 %
- Veterinär konkurrens/kapacitet (`Konkurrens_score`): 25 %
- Folkmängd (`Folkmangd_score`): 15 %
- Befolkningstäthet (`Befolkningstathet_score`): 15 %
- Djurägandeintensitet (`Djurtagande_score`): 15 %

Om SCB- eller konkurrensdata saknas beräknas poängen bara från de komponenter som finns och vikterna normaliseras om. Modellen fabricerar inga värden.

## GeoJSON för karta

Den interaktiva kartan kräver att en svensk kommun-GeoJSON laddas upp i sidopanelen. GeoJSON-filen ska innehålla polygoner för kommuner och ett egenskapsfält med kommunnamn, till exempel `Kommun`, `Kommunnamn`, `name` eller `NAMN`.

Första implementationen matchar masterdata mot GeoJSON på kommunnamn. Om kommunnamn inte matchar visar appen en varning med vilka kommuner i masterdata som saknar geografisk matchning. Kommunkodsmatchning är förberedd som nästa naturliga steg, men används inte ännu.

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
  mapping.py
  validation.py
data/
  raw/
  processed/
output/
README.md
requirements.txt
```
