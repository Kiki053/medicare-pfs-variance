# Building the Power BI report

This builds a six-page report on the same star schema the write-up uses. It takes about an hour in Power BI Desktop on Windows. Everything here is public CMS data.

## 1. Get the data

Run the pipeline from the repository root (see the main README). The last step writes nine Parquet files to `powerbi/data`:

| File | Rows | What it is |
|---|---:|---|
| `dim_code.parquet` | 19,864 | One row per HCPCS code and modifier |
| `dim_locality.parquet` | 556 | GPCIs per Medicare locality per year |
| `dim_release.parquet` | 6 | Conversion factors per CMS release |
| `fct_rvu.parquet` | 92,200 | RVUs per code per year |
| `fct_payment.parquet` | 275,024 | Payment per code, year, focus locality, and setting |
| `mart_payment_variance.parquet` | 215,756 | Year-over-year change per code, split into causes |
| `mart_volume_weighted_change.parquet` | 55,273 | The same changes priced on 2024 Medicare volume |
| `mart_efficiency_adjustment.parquet` | 7,689 | CMS's 2026 efficiency adjustment list |
| `mart_local_comparison.parquet` | 68,756 | National, Tennessee, Rest of Georgia, and Atlanta payments side by side |

## 2. Load the tables

1. Open Power BI Desktop with a blank report. Before loading anything, go to **File > Options and settings > Options > Current file > Data Load** and clear **Autodetect new relationships after data is loaded**. Auto-detect would join the fact tables to each other on `hcpcs`, which breaks the model.
2. **Home > Transform data** to open Power Query. Then **Manage Parameters > New Parameter**: name it `DataFolder`, type **Text**, and set the current value to the full path of `powerbi\data\`, including the trailing backslash.
3. **New Source > Blank Query**, open **Advanced Editor**, and paste:

   ```m
   let
       Source = Parquet.Document(File.Contents(DataFolder & "dim_code.parquet"))
   in
       Source
   ```

   Rename the query `dim_code`. Duplicate it eight times, change the file name in each, and name each query after its file: `dim_locality`, `dim_release`, `fct_rvu`, `fct_payment`, `mart_payment_variance`, `mart_volume_weighted_change`, `mart_efficiency_adjustment`, `mart_local_comparison`.

4. Build a locality dimension. **New Source > Blank Query**, name it `Locality`, and paste:

   ```m
   let
       Source = dim_locality,
       Kept = Table.SelectColumns(Source, {"locality_key", "state", "locality_name", "focus_label", "is_focus"}),
       OnePerLocality = Table.Distinct(Kept, {"locality_key"}),
       Named = Table.AddColumn(OnePerLocality, "Locality", each
           if [focus_label] <> null then [focus_label] else Text.Proper([locality_name]) & " (" & [state] & ")",
           type text),
       WithSort = Table.AddColumn(Named, "Locality sort", each
           if [locality_key] = "US-00" then 1
           else if [locality_key] = "TN-35" then 2
           else if [locality_key] = "GA-99" then 3
           else if [locality_key] = "GA-01" then 4
           else 9,
           Int64.Type)
   in
       WithSort
   ```

5. **Close & Apply**.

## 3. Add the helper tables

In **Modeling > New table**, add each of these:

```dax
Year = SELECTCOLUMNS ( GENERATESERIES ( 2022, 2026, 1 ), "Year", [Value] )
```

```dax
Setting =
DATATABLE (
    "setting_key", STRING,
    "Setting", STRING,
    "Sort", INTEGER,
    {
        { "non_facility", "Office (non-facility)", 1 },
        { "facility", "Facility", 2 }
    }
)
```

```dax
Bridge step =
DATATABLE (
    "Step", STRING,
    "Sort", INTEGER,
    {
        { "Conversion factor", 1 },
        { "Work RVUs", 2 },
        { "Practice expense", 3 },
        { "Malpractice", 4 },
        { "Geographic index", 5 }
    }
)
```

Then make a home for the measures: **Home > Enter data**, leave the single column as is, name the table `Measures`, and load it.

Set the sort order of three label columns with **Column tools > Sort by column**: `Setting[Setting]` by `Setting[Sort]`, `Bridge step[Step]` by `Bridge step[Sort]`, and `Locality[Locality]` by `Locality[Locality sort]`.

## 4. Create the relationships

In Model view, create these relationships. All are one-to-many with a single filter direction, from the first table to the second.

| One side | Many side |
|---|---|
| `dim_code[code_key]` | `fct_rvu`, `fct_payment`, `mart_payment_variance`, `mart_volume_weighted_change`, `mart_efficiency_adjustment`, `mart_local_comparison` (each on `code_key`) |
| `Year[Year]` | `fct_rvu[calendar_year]`, `fct_payment[calendar_year]`, `mart_payment_variance[current_year]`, `mart_volume_weighted_change[current_year]`, `mart_local_comparison[calendar_year]`, `dim_locality[calendar_year]`, `dim_release[calendar_year]` |
| `Locality[locality_key]` | `fct_payment`, `mart_payment_variance`, `mart_volume_weighted_change`, `dim_locality` (each on `locality_key`) |
| `Setting[setting_key]` | `fct_payment`, `mart_payment_variance`, `mart_volume_weighted_change`, `mart_local_comparison` (each on `setting`) |

No fact table connects to another fact table, and `dim_release` and `dim_locality` hang off `Year` and `Locality` rather than the facts, so every filter has exactly one path. `Year` filters `mart_payment_variance` and `mart_volume_weighted_change` on the *current* year of each comparison: selecting 2026 shows the change from 2025 to 2026.

Power BI proposes **One to one** for `mart_efficiency_adjustment`, because both of its `code_key` columns are unique. Change that one to **Many to one** with a **Single** direction.

Hide the key columns on the many side so report authors pick fields from the dimensions.

## 5. Add the measures

Open **DAX query view**, paste all of [measures.dax](measures.dax), and choose **Update model with changes** above the `DEFINE` block. Then run the query: the result should show about +1.87% for National, +2.72% for Tennessee, and +2.96% for Rest of Georgia. Hide the placeholder column in `Measures`.

Set formats in **Measure tools**:

| Measures | Format |
|---|---|
| Conversion factor, Conversion factor, QP | Currency, 4 decimals |
| Payment, Payment, QP, Work/PE/MP amount, Prior payment, Current payment, Payment change, the five dollar effects, Tennessee/Rest of Georgia/Atlanta payment, Dalton minus Chattanooga | Currency, 2 decimals |
| Prior spend, Current spend, Spend change | Currency, 0 decimals, display units in millions |
| Every measure ending in `%` or `pts` | Percentage, 2 decimals |
| Services 2024, Services on adjusted codes, 2024, Adjusted codes | Whole number, thousands separator |
| Work GPCI, PE GPCI, MP GPCI | Decimal, 3 places |
| Bridge check | Decimal, 6 places |

## 6. Apply the theme

**View > Themes > Browse for themes** and choose [theme.json](theme.json). It uses the same blue, orange, and green as the write-up, blue for increases and red for decreases.

## 7. Build the pages

Each page answers one question. Put the question in the page title.

**Overview: how much did Medicare's rates move each year?**
- Line chart: `Year[Year]` on the x-axis, `Conversion factor` and `Conversion factor, QP` as values. The two lines match until 2026.
- Matrix: `Locality[Locality]` rows, `Year[Year]` columns (2023 to 2026), `Spend change %` values. Only National, Tennessee, and Rest of Georgia have volume, so the others drop out.
- Cards for 2026: `Conversion factor`, `Conversion factor change %`, and `Spend change %` for each of the three localities (visual-level filters).

**2026 bridge: what drove the change?**
- Slicer: `Locality[Locality]`, single select.
- Waterfall: `Bridge step[Step]` as the category, `Bridge effect, pts` as the value, filtered to 2026. Sort by category so the steps stay in order. Under **Sentiment colors**, set increase `#2A78D6`, decrease `#E34948`, and total `#898781`.
- Table: `Locality[Locality]` with `CF effect, pts`, `Work RVU effect, pts`, `PE RVU effect, pts`, `MP RVU effect, pts`, `GPCI effect, pts`, and `Spend change %`.

**Office vs facility: where did the money move?**
- Clustered bar: `Locality[Locality]` on the axis, `Setting[Setting]` as the legend, `Spend change %` as the value, filtered to 2026.
- Matrix: `Setting[Setting]` rows, `Locality[Locality]` columns, `PE RVU effect, pts` values. Practice expense carries most of the split.
- Table: `dim_code[code_key]`, `dim_code[description]`, `Setting[Setting]`, `Services 2024`, `Spend change`, filtered to National and 2026, sorted by `Spend change`. The biggest dollar movers sit at the top and bottom.

**Code explorer: what happened to one service?**
- Slicers: `dim_code[code_family]`, `dim_code[code_key]` (turn on search), `Setting[Setting]`.
- Line chart: `Year[Year]` on the x-axis, `Payment` as the value, `Locality[Locality]` as the legend, filtered to the four focus localities.
- Table: `Year[Year]`, `Prior payment`, `Current payment`, `CF effect`, `Work RVU effect`, `PE RVU effect`, `MP RVU effect`, `GPCI effect`, `Bridge check`.

**Dalton vs Chattanooga: what does the state line change?**
- Three line charts: `Year[Year]` on the x-axis and `Work GPCI`, `PE GPCI`, and `MP GPCI` as values, with `Locality[Locality]` as the legend, filtered to Tennessee and Rest of Georgia.
- Cards: `Median Dalton premium %` for 2026, one filtered to Facility and one to Office. They should read about 5.9% and 0.4%.
- Table: `dim_code[code_key]`, `dim_code[description]`, `Tennessee payment`, `Rest of Georgia payment`, `Dalton premium %`, filtered to 2026 and Facility, sorted by `Dalton minus Chattanooga`.

**Efficiency adjustment: who took the 2.5% cut?**
- Bar chart: `dim_code[code_family]` on the axis, `Services on adjusted codes, 2024` as the value.
- Table: `dim_code[code_key]`, `dim_code[description]`, `mart_efficiency_adjustment[cms_work_rvu_before]`, `mart_efficiency_adjustment[cms_work_rvu_after]`, `Services on adjusted codes, 2024`, sorted by services.

## 8. Check it against the write-up

| Check | Expected |
|---|---|
| Conversion factor, 2026 | $33.4009 ($33.5675 for QP) |
| Spend change %, 2026: National, Tennessee, Rest of Georgia | +1.87%, +2.72%, +2.96% |
| Spend change %, 2026, Office: National, Tennessee, Rest of Georgia | +6.59%, +7.45%, +7.23% |
| Spend change %, 2026, Facility: National, Tennessee, Rest of Georgia | −6.22%, −5.75%, −4.66% |
| MP GPCI 2026: Tennessee, Rest of Georgia | 0.537, 1.192 |
| Bridge check, any selection | 0 |

## 9. Save and share

Save the report locally. Don't commit the `.pbix`: it embeds the data, including CPT descriptors from `dim_code`, which the AMA license doesn't allow redistributing. For GitHub, add screenshots of each page to `docs/img` and link them from the README. If your Power BI Desktop offers the Power BI Project (`.pbip`) format, you can commit that instead, since this repository's `.gitignore` keeps its data cache out. The same goes for publishing: if you share the report on the web, remove `dim_code[description]` first or share screenshots instead.
