-- Grain: one row per code x setting x year, with the payment in each focus
-- locality side by side. The question it answers: for the same service,
-- how much does Medicare pay in Chattanooga vs Dalton vs Atlanta?

with payment as (

    select code_key, hcpcs, modifier, calendar_year, setting, locality_key, payment_amount
    from {{ ref('fct_payment') }}

)

select
    code_key || '-' || setting || '-' || calendar_year              as comparison_key,
    code_key,
    hcpcs,
    modifier,
    calendar_year,
    setting,
    max(case when locality_key = 'US-00' then payment_amount end)  as national_payment,
    max(case when locality_key = 'TN-35' then payment_amount end)  as tennessee_payment,
    max(case when locality_key = 'GA-99' then payment_amount end)  as rest_of_georgia_payment,
    max(case when locality_key = 'GA-01' then payment_amount end)  as atlanta_payment,
    max(case when locality_key = 'GA-99' then payment_amount end)
      - max(case when locality_key = 'TN-35' then payment_amount end) as dalton_minus_chattanooga
from payment
group by code_key, hcpcs, modifier, calendar_year, setting
