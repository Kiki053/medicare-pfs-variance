-- Grain: one row per HCPCS code x modifier x year x locality x setting.
--
-- Medicare's formula:
--   payment = (work RVU x work GPCI + PE RVU x PE GPCI + MP RVU x MP GPCI) x CF
-- PE RVU depends on the setting: non-facility (an office) or facility
-- (a hospital or ASC, where the facility is paid separately for its costs).
-- Only payable status codes, and only settings CMS doesn't mark "NA".

with rvu as (

    select * from {{ ref('fct_rvu') }}
    where is_payable

),

releases as (

    select calendar_year, conversion_factor, conversion_factor_qp
    from {{ ref('dim_release') }}
    where is_primary

),

localities as (

    select * from {{ ref('dim_locality') }}
    where is_focus

),

settings as (

    select 'non_facility' as setting
    union all
    select 'facility'

),

by_setting as (

    select
        r.*,
        s.setting,
        case s.setting when 'non_facility' then r.nonfac_pe_rvu else r.fac_pe_rvu end as pe_rvu,
        case s.setting when 'non_facility' then r.is_nonfac_na else r.is_fac_na end    as is_na
    from rvu as r
    cross join settings as s

),

priced as (

    select
        b.code_key,
        b.rvu_key,
        b.hcpcs,
        b.modifier,
        b.calendar_year,
        l.locality_key,
        l.locality_year_key,
        b.setting,
        b.work_rvu,
        b.pe_rvu,
        b.mp_rvu,
        l.pw_gpci,
        l.pe_gpci,
        l.mp_gpci,
        rel.conversion_factor,
        rel.conversion_factor_qp,
        b.is_qp_eligible,
        b.work_rvu * l.pw_gpci + b.pe_rvu * l.pe_gpci + b.mp_rvu * l.mp_gpci as gpci_adjusted_rvus
    from by_setting as b
    inner join releases as rel using (calendar_year)
    inner join localities as l on l.calendar_year = b.calendar_year
    where not b.is_na

)

select
    code_key || '-' || locality_key || '-' || setting || '-' || calendar_year as payment_key,
    code_key,
    rvu_key,
    hcpcs,
    modifier,
    calendar_year,
    locality_key,
    locality_year_key,
    setting,
    work_rvu,
    pe_rvu,
    mp_rvu,
    pw_gpci,
    pe_gpci,
    mp_gpci,
    conversion_factor,
    gpci_adjusted_rvus,
    round(work_rvu * pw_gpci * conversion_factor, 6)                       as work_amount,
    round(pe_rvu * pe_gpci * conversion_factor, 6)                         as pe_amount,
    round(mp_rvu * mp_gpci * conversion_factor, 6)                         as mp_amount,
    round(gpci_adjusted_rvus * conversion_factor, 6)                       as payment_amount,
    round(
        gpci_adjusted_rvus
        * case when is_qp_eligible then conversion_factor_qp else conversion_factor end,
        6
    )                                                                       as payment_amount_qp
from priced
