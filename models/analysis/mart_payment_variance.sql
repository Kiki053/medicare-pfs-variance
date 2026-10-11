-- Grain: one row per code x locality x setting x year, compared with the
-- year before. Splits each payment change into what drove it.
--
-- With P = CF x W and W = sum of (RVU x GPCI) over work, PE, and MP:
--   P1 - P0 = (CF1 - CF0) x W0                      conversion factor effect
--           + CF1 x sum(GPCI0 x (RVU1 - RVU0))      RVU effect (work, PE, MP)
--           + CF1 x sum(RVU1 x (GPCI1 - GPCI0))     geographic (GPCI) effect
-- The three effects add up to the total change exactly; no residual.

with payment as (

    select * from {{ ref('fct_payment') }}

),

pairs as (

    select
        cur.code_key,
        cur.hcpcs,
        cur.modifier,
        cur.locality_key,
        cur.setting,
        prev.calendar_year      as prior_year,
        cur.calendar_year       as current_year,
        prev.payment_amount     as prior_payment,
        cur.payment_amount      as current_payment,
        prev.conversion_factor  as cf0,
        cur.conversion_factor   as cf1,
        prev.work_rvu           as work0,
        cur.work_rvu            as work1,
        prev.pe_rvu             as pe0,
        cur.pe_rvu              as pe1,
        prev.mp_rvu             as mp0,
        cur.mp_rvu              as mp1,
        prev.pw_gpci            as gw0,
        cur.pw_gpci             as gw1,
        prev.pe_gpci            as gp0,
        cur.pe_gpci             as gp1,
        prev.mp_gpci            as gm0,
        cur.mp_gpci             as gm1
    from payment as cur
    inner join payment as prev
        on prev.code_key = cur.code_key
       and prev.locality_key = cur.locality_key
       and prev.setting = cur.setting
       and prev.calendar_year = cur.calendar_year - 1

)

select
    code_key || '-' || locality_key || '-' || setting || '-' || current_year as variance_key,
    code_key,
    hcpcs,
    modifier,
    locality_key,
    setting,
    prior_year,
    current_year,
    prior_payment,
    current_payment,
    current_payment - prior_payment                                         as payment_change,
    case when prior_payment > 0
         then (current_payment - prior_payment) / prior_payment end         as payment_change_pct,
    (cf1 - cf0) * (work0 * gw0 + pe0 * gp0 + mp0 * gm0)                     as cf_effect,
    cf1 * gw0 * (work1 - work0)                                             as work_rvu_effect,
    cf1 * gp0 * (pe1 - pe0)                                                 as pe_rvu_effect,
    cf1 * gm0 * (mp1 - mp0)                                                 as mp_rvu_effect,
    cf1 * (work1 * (gw1 - gw0) + pe1 * (gp1 - gp0) + mp1 * (gm1 - gm0))     as gpci_effect,
    work0                                                                   as prior_work_rvu,
    work1                                                                   as current_work_rvu,
    pe0                                                                     as prior_pe_rvu,
    pe1                                                                     as current_pe_rvu,
    mp0                                                                     as prior_mp_rvu,
    mp1                                                                     as current_mp_rvu,
    cf0                                                                     as prior_conversion_factor,
    cf1                                                                     as current_conversion_factor
from pairs
