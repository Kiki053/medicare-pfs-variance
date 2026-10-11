-- One typed row per HCPCS code x modifier x release x conversion factor track.

with source as (

    select * from {{ source('landing', 'pprrvu') }}

),

typed as (

    select
        release_id,
        cast(calendar_year as integer)                          as calendar_year,
        cf_track,
        upper(trim(hcpcs))                                      as hcpcs,
        -- '' means "no modifier" so the code-modifier key is never null
        upper(coalesce(trim(modifier), ''))                     as modifier,
        trim(description)                                       as description,
        nullif(trim(status_code), '')                           as status_code,
        nullif(trim(not_used_for_medicare_payment), '')         as not_used_for_medicare_payment,
        try_cast(nullif(work_rvu, '') as double)                as work_rvu,
        try_cast(nullif(nonfac_pe_rvu, '') as double)           as nonfac_pe_rvu,
        try_cast(nullif(fac_pe_rvu, '') as double)              as fac_pe_rvu,
        try_cast(nullif(mp_rvu, '') as double)                  as mp_rvu,
        try_cast(nullif(nonfac_total_rvu, '') as double)        as nonfac_total_rvu,
        try_cast(nullif(fac_total_rvu, '') as double)           as fac_total_rvu,
        nonfac_na_indicator = 'NA'                              as is_nonfac_na,
        fac_na_indicator = 'NA'                                 as is_fac_na,
        nullif(trim(pctc_indicator), '')                        as pctc_indicator,
        nullif(trim(global_days), '')                           as global_days,
        nullif(trim(multiple_procedure_indicator), '')          as multiple_procedure_indicator,
        nullif(trim(pricing_indicator), '')                     as pricing_indicator,
        try_cast(nullif(conversion_factor, '') as double)       as conversion_factor,
        nullif(trim(diagnostic_imaging_family), '')             as diagnostic_imaging_family,
        released_on
    from source

)

select *
from typed
-- the older files end with a stray footer row; real codes are 5 characters
where regexp_full_match(hcpcs, '[0-9A-Z]{5}')
