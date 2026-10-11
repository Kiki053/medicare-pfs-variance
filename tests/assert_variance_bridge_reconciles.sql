-- The conversion factor, RVU, and GPCI effects must add up to the total
-- payment change. Any row returned here fails the test.

select
    variance_key,
    payment_change,
    cf_effect + work_rvu_effect + pe_rvu_effect + mp_rvu_effect + gpci_effect as sum_of_effects
from {{ ref('mart_payment_variance') }}
where abs(
    payment_change
    - (cf_effect + work_rvu_effect + pe_rvu_effect + mp_rvu_effect + gpci_effect)
) > 0.0001
