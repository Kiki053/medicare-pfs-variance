-- Codes CMS exempted from the CY 2026 efficiency adjustment.

select distinct upper(trim(hcpcs)) as hcpcs
from {{ source('landing', 'efficiency_exclusions_2026') }}
where trim(hcpcs) <> ''
