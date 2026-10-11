-- 2024 Medicare service counts for the nation, Georgia, and Tennessee.

with source as (

    select * from {{ source('landing', 'utilization_geo_2024') }}

)

select
    case
        when rndrng_prvdr_geo_desc = 'National' then 'US'
        when rndrng_prvdr_geo_desc = 'Georgia' then 'GA'
        when rndrng_prvdr_geo_desc = 'Tennessee' then 'TN'
    end                                                 as geography,
    upper(trim(hcpcs_cd))                               as hcpcs,
    trim(hcpcs_desc)                                    as hcpcs_description,
    hcpcs_drug_ind = 'Y'                                as is_drug,
    case place_of_srvc
        when 'F' then 'facility'
        when 'O' then 'non_facility'
    end                                                 as setting,
    cast(tot_rndrng_prvdrs as bigint)                   as rendering_providers,
    cast(tot_benes as bigint)                           as beneficiaries,
    cast(tot_srvcs as double)                           as services,
    cast(avg_mdcr_alowd_amt as double)                  as avg_allowed_amount,
    cast(avg_mdcr_pymt_amt as double)                   as avg_medicare_payment
from source
where rndrng_prvdr_geo_desc in ('National', 'Georgia', 'Tennessee')
