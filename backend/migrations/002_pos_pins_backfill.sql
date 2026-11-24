-- 002_pos_pins_backfill.sql
-- Run each SECTION separately (select it, then Run). Back up first:
--   create table if not exists public.orders_backup_20261124 as select * from public.orders;
--   alter table public.orders_backup_20261124 enable row level security;
--   create table if not exists public.staff_backup_20261124 as select * from public.staff_users;
--   alter table public.staff_backup_20261124 enable row level security;

-- ===================================================== SECTION A (safe, run now)
-- Audited cash / manual payment for POS and counter sales.
create or replace function public.mark_order_paid_manual(
  p_order_id uuid, p_method text, p_reference text,
  p_staff_id uuid, p_staff_name text, p_notes text
) returns public.orders
language plpgsql security definer set search_path = public as $$
declare v public.orders;
begin
  update public.orders
     set payment_status = 'paid', status = 'Fulfilled', paid_at = now(),
         payment_mode = p_method, payment_reference = coalesce(p_reference, ''),
         verified_by_user_id = p_staff_id::text, verified_by_name = p_staff_name,
         verification_notes = coalesce(p_notes, '')
   where id = p_order_id and payment_status = 'pending' and stock_released = false
  returning * into v;
  if v.id is null then raise exception 'order_not_payable'; end if;

  insert into public.payment_overrides(
    order_id, order_reference, payment_method, payment_reference, amount,
    customer_phone, verified_by_user_id, verified_by_name, notes)
  values (v.id::text, v.order_reference, p_method, coalesce(p_reference, ''), v.total_amount,
          v.customer_phone, p_staff_id::text, p_staff_name, coalesce(p_notes, ''));
  return v;
end $$;

revoke all on function public.mark_order_paid_manual(uuid,text,text,uuid,text,text) from public, anon, authenticated;
grant execute on function public.mark_order_paid_manual(uuid,text,text,uuid,text,text) to service_role;

-- ===================================================== SECTION B (run BEFORE deploying new pin_login)
-- Turn the plaintext PINs into bcrypt hashes (pgcrypto, compatible with passlib/bcrypt).
-- The OLD code keeps working because pin_code is left untouched for now.
create extension if not exists pgcrypto with schema extensions;

update public.staff_users
   set pin_hash = extensions.crypt(pin_code, extensions.gen_salt('bf', 10))
 where pin_code is not null and pin_code <> '' and pin_hash is null;

-- ===================================================== SECTION C (backfill, run after you reviewed the list)
-- Cutoff protects orders created by the still-running old backend today.
-- Everything old that CLAIMS to be paid but has no verifiable proof becomes
-- 'unverified' so it stays OUT of sales reports until you confirm it.
begin;

update public.orders set payment_status = 'unverified'
 where created_at < date '2026-11-24'
   and (lower(payment_status) = 'paid' or status in ('Paid','Fulfilled'));

-- tiny amounts are obviously your own test payments
update public.orders set payment_status = 'test'
 where created_at < date '2026-11-24'
   and payment_status = 'unverified' and total_amount < 100;

-- contradictory: failed payment that someone flipped to Paid by typing a receipt
update public.orders set payment_status = 'failed'
 where created_at < date '2026-11-24' and status = 'Payment Failed';

-- abandoned checkouts and old cancelled rows
update public.orders set status = 'Cancelled', payment_status = 'failed'
 where created_at < date '2026-11-24'
   and payment_status = 'pending'
   and status in ('Pending PIN','pending','pending_payment','Pending Review','Cancelled');

-- the old code never reserved stock, so the new release function must never restore any
update public.orders set stock_released = true where created_at < date '2026-11-24';

commit;

-- AFTER you check an old order against the M-Pesa statement, promote it, e.g.:
--   update public.orders set payment_status = 'paid', paid_at = created_at
--    where order_reference = 'AYU-xxxx';

-- ===================================================== SECTION D (only AFTER new pin_login is live and tested)
-- update public.staff_users set pin_code = null;
-- alter table public.staff_users drop column pin_code;   -- when nothing reads it any more
