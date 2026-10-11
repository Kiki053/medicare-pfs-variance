-- Grain: one row per geography x code x setting x year-over-year change.
--
-- Prices a fixed basket, 2024 Medicare service counts, at each year's rates,
-- so the dollar change comes only from the fee schedule, not from volume.
-- Georgia's state counts are priced at Rest of Georgia rates (Dalton's
-- locality); Atlanta's share of Georgia volume makes that an approximation.
--
-- Scope: codes with one price per setting. PC/TC indicator 1 codes are billed
-- in professional (-26) and technical (-TC) pieces, and indicator 6 codes are
-- billed with -26. The utilization file doesn't split services by modifier,
-- so for those codes there's no way to tell which piece was billed, and they
-- are left out. Every other indicator has a single price at the base code.

with volume as (

    select
        geography,
        hcpcs,
        setting,
        services,
        services * avg_allowed_amount as allowed_2024
    from {{ ref('stg_utilization_2024') }}
    where not is_drug

),

geo_locality as (

    select * from (values
        ('US', 'US-00'),
        ('TN', 'TN-35'),
        ('GA', 'GA-99')
    ) as t(geography, locality_key)

),

eligible as (

    select distinct hcpcs, calendar_year
    from {{ ref('fct_rvu') }}
    where modifier = '' and pctc_indicator not in ('1', '6')

),

variance as (

    select v.*
    from {{ ref('mart_payment_variance') }} as v
    inner join eligible as e
        on e.hcpcs = v.hcpcs
       and e.calendar_year = v.current_year
    where v.modifier = ''

)

select
    g.geography || '-' || v.code_key || '-' || v.setting || '-' || v.current_year as volume_change_key,
    g.geography,
    v.locality_key,
    v.code_key,
    v.hcpcs,
    v.setting,
    v.prior_year,
    v.current_year,
    u.services                                      as services_2024,
    u.allowed_2024,
    u.services * v.prior_payment                    as prior_spend,
    u.services * v.current_payment                  as current_spend,
    u.services * v.payment_change                   as spend_change,
    u.services * v.cf_effect                        as cf_effect,
    u.services * v.work_rvu_effect                  as work_rvu_effect,
    u.services * v.pe_rvu_effect                    as pe_rvu_effect,
    u.services * v.mp_rvu_effect                    as mp_rvu_effect,
    u.services * v.gpci_effect                      as gpci_effect
from volume as u
inner join geo_locality as g using (geography)
inner join variance as v
    on v.hcpcs = u.hcpcs
   and v.setting = u.setting
   and v.locality_key = g.locality_key
