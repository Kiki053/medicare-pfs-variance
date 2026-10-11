# Modeling decisions

Every number in this project depends on a few choices about which CMS files to trust, which codes count, and how to split a change into its causes. Here they are, with the reasoning, so anyone can disagree with a specific choice rather than with the whole result.

## Which releases

**One release per year, the one in force for most of the year.** CMS posts several versions of the relative value file each year (A for January, then B, C, and D quarterly corrections). I use the January release for 2022, 2023, 2025, and 2026, because it's the fee schedule as it took effect.

**2024 uses the revised January release (RVU24AR), not the original (RVU24A).** The Consolidated Appropriations Act, 2024 raised the conversion factor from $32.7442 to $33.2875 for services from March 9 through December 31, 2024. CMS reissued the January file with the new rate. Since that rate applied to about 81% of the year, it's the better picture of 2024. Both releases are loaded; `dim_release.is_primary` marks the one used, and the original stays available for comparison.

**The RVU24AR file's header says it was released 03/11/2023.** That's a typo in CMS's file (it was posted in 2024). The loader ignores the header date and takes the year from the release itself.

## Which conversion factor in 2026

**2026 uses the conversion factor for clinicians who aren't qualifying APM participants ($33.4009).** Starting in 2026, CMS publishes two rates: $33.5675 for qualifying participants in advanced alternative payment models and $33.4009 for everyone else. Most clinicians billing Medicare aren't qualifying participants, so the non-qualifying rate is the default. `fct_payment.payment_amount_qp` carries the qualifying rate too.

CMS publishes separate 2026 RVU files for the two groups. The qualifying file lists only priced codes, and for every code in both files the RVUs match; only the conversion factor differs. The loader keeps both and tags rows with `cf_track` (`single` before 2026, then `non_qp` and `qp`).

## Which codes are priced

**Only payable status codes: A, R, and T.** A is active, R is restricted coverage, and T is paid only when no other service is billed that day. Codes with other statuses aren't paid from the fee schedule (for example, J for anesthesia, which uses its own conversion factor, or B for bundled services).

**Settings CMS marks "NA" aren't priced.** Some codes have no facility or no non-facility rate (CMS's NA indicator). Those code-setting pairs are left out rather than priced at zero.

**Drugs are left out of the volume-weighted totals.** Part B drugs are paid at average sales price, not from the fee schedule. The utilization file flags them, and they're dropped.

## Geography

**Four focus localities.** National (`US-00`, every GPCI at 1.000), Tennessee (`TN-35`, a single statewide locality that includes Chattanooga), Rest of Georgia (`GA-99`, which includes Dalton in Whitfield County), and Atlanta (`GA-01`) as an in-state contrast. They're set in `dbt_project.yml` as `focus_localities`, so adding one is a one-line change.

**The work GPCI is the one with the 1.000 floor.** Congress has kept a floor of 1.000 on the work GPCI, and that's the value Medicare pays with. For 2026, CMS also published the index before the floor; it's kept as `pw_gpci_no_floor` but not used for payment.

**Georgia's statewide volume is priced at Rest of Georgia rates.** The utilization file reports Georgia's services statewide, not by locality, so there's no way to split Atlanta's share out. Pricing all of it at Rest of Georgia rates means the Georgia figures describe Dalton's locality applied to Georgia's mix of services. It's an approximation, and the write-up says so.

**GPCI locality numbers are normalized to two digits.** CMS's GPCI files write some localities as "1" and the RVU files as "01". Staging pads them so they join.

## Volume weighting

**A fixed basket: 2024 Medicare volume, priced at every year's rates.** Holding volume fixed means every change in a weighted total comes from the fee schedule, not from changes in what was billed. 2024 is the latest year in the utilization file, and it's from Original Medicare Part B only.

**Only codes with one price per setting are in the weighted totals.** Codes with PC/TC indicator 1, mostly imaging and diagnostic tests, are billed either whole or in professional (modifier 26) and technical (modifier TC) pieces, each priced separately. Indicator 6 codes are billed with modifier 26. The utilization file reports services by code without the modifier, so for those codes there's no way to tell which piece was billed, and they're left out of the weighted totals. Every other indicator has a single price at the base code and stays in. The basket covers about 84 to 86% of 2024 allowed dollars for services paid from the fee schedule, depending on the geography. Every code, including the split ones, is still priced in `fct_payment`.

## Splitting a change into its causes

**The variance bridge is a sequential decomposition, conversion factor first.** With payment P = CF × W, where W is the sum of RVU × GPCI across work, practice expense, and malpractice:

```
P₁ − P₀ = (CF₁ − CF₀) × W₀                       conversion factor effect
        + CF₁ × Σ GPCI₀ × (RVU₁ − RVU₀)          RVU effects (work, PE, MP)
        + CF₁ × Σ RVU₁ × (GPCI₁ − GPCI₀)         geographic effect
```

The parts add up to the total exactly, with no residual, and `assert_variance_bridge_reconciles` checks that on every row. The order matters a little: a different order would assign the small cross terms differently. Conversion factor first answers the most common question ("what did the new rate alone do to last year's payment?"), and the cross terms are small next to the effects.

**The 2026 efficiency adjustment is part of the work RVU effect.** CMS applied the −2.5% to work RVUs in the 2026 file itself, so it shows up as a work RVU change. `mart_efficiency_adjustment` keeps CMS's list of affected codes, with before and after values, to size it separately.

**CMS's efficiency list rounds differently from the RVU file.** For 404 codes, the "after" work RVU on the efficiency list differs from the 2026 RVU file by 0.01. The RVU file is what Medicare pays with, so payments use it; the list is used only to flag which codes were adjusted.

## Cleaning the files

**CMS's multi-row headers are rebuilt from the rows themselves.** The RVU files spread each column name over several rows, and the layout shifts from year to year (2026 added a pricing indicator column). The loader finds the row whose first cell is "HCPCS", combines it with the rows above, and maps the combined names to stable column names. A year with a new column fails loudly rather than shifting data into the wrong field.

**Footer rows are filtered.** Some files end with note rows that land in the HCPCS column (one reads `\26`). Staging keeps only five-character codes.

**Everything lands as text and is typed in dbt.** The loader doesn't guess types, so a malformed value shows up as a null in staging and fails a test there, where it's easy to trace.
