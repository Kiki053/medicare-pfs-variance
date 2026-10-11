-- With every GPCI at 1.000, the computed payment must equal CMS's own
-- total RVUs for that setting times the conversion factor. This checks
-- the formula against the totals printed in the file.

with national as (

    select *
    from {{ ref('fct_payment') }}
    where locality_key = 'US-00'

)

select
    n.payment_key,
    n.payment_amount,
    case n.setting when 'non_facility' then r.nonfac_total_rvu else r.fac_total_rvu end
        * n.conversion_factor as cms_total_times_cf
from national as n
inner join {{ ref('fct_rvu') }} as r using (rvu_key)
where abs(
    n.payment_amount
    - case n.setting when 'non_facility' then r.nonfac_total_rvu else r.fac_total_rvu end
      * n.conversion_factor
) > 0.011 * n.conversion_factor
