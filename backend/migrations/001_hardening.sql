-- 001_hardening.sql  --  RUN ON A STAGING SUPABASE PROJECT FIRST.
--
-- BEFORE RUNNING, check for duplicates that would block the unique indexes:
--   select order_reference, count(*) from orders group by 1 having count(*) > 1;
--   select checkout_request_id, count(*) from orders
--     where checkout_request_id <> '' group by 1 having count(*) > 1;
--
-- AFTER RUNNING: the FastAPI backend MUST use the service-role key.
-- RLS below denies anon/authenticated by default; service_role bypasses it.

begin;

-- ---------------------------------------------------------------- orders
create sequence if not exists public.orders_order_no_seq;

alter table public.orders
  add column if not exists order_no bigint,
  add column if not exists sold_by_staff_id uuid references public.staff_users(id),
  add column if not exists delivery_fee numeric not null default 0,
  add column if not exists stock_released boolean not null default false,
  add column if not exists paid_at timestamptz;

update public.orders set order_no = nextval('public.orders_order_no_seq') where order_no is null;
alter table public.orders alter column order_no set default nextval('public.orders_order_no_seq');

create unique index if not exists orders_order_no_key on public.orders(order_no);
create unique index if not exists orders_order_reference_key
  on public.orders(order_reference) where order_reference is not null;
create unique index if not exists orders_checkout_request_id_key
  on public.orders(checkout_request_id) where checkout_request_id is not null and checkout_request_id <> '';
-- real M-Pesa receipts are 10 alphanumerics; legacy junk like 'MPESA_PAID' is excluded
create unique index if not exists orders_receipt_number_key
  on public.orders(receipt_number) where receipt_number ~ '^[A-Z0-9]{10}$';

alter table public.products
  add constraint products_stock_nonneg check (stock_quantity >= 0) not valid;

-- ------------------------------------------------------- supporting tables
create table if not exists public.delivery_zones (
  name   text primary key,
  fee    numeric not null check (fee >= 0),
  active boolean not null default true
);
-- insert into public.delivery_zones(name, fee) values ('Nairobi CBD', 200), ...;

alter table public.staff_users
  add column if not exists pin_hash text,
  add column if not exists pin_failed_attempts int not null default 0,
  add column if not exists pin_locked_until timestamptz;
-- Set pin_hash with bcrypt, then DROP the plaintext pin_code column.

create table if not exists public.whatsapp_staff_sessions (
  id uuid primary key default gen_random_uuid(),
  staff_id uuid not null references public.staff_users(id) on delete cascade,
  phone text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create index if not exists wa_sessions_lookup on public.whatsapp_staff_sessions(staff_id, phone, expires_at);

create table if not exists public.processed_webhook_messages (
  msg_id text primary key,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------- functions
-- Server computes prices, delivery fee and stock. Everything is one transaction:
-- any exception rolls back the order, the items and the stock changes together.
create or replace function public.create_order(
  p_customer_id uuid, p_phone text, p_fulfillment text, p_location text,
  p_delivery_address text, p_payment_method text, p_channel text,
  p_sold_by uuid, p_items jsonb
) returns public.orders
language plpgsql security definer set search_path = public as $$
declare
  v_order public.orders;
  v_item jsonb;
  v_prod public.products;
  v_qty int;
  v_subtotal numeric := 0;
  v_fee numeric := 0;
  v_id uuid := gen_random_uuid();
  v_no bigint := nextval('public.orders_order_no_seq');
begin
  if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
    raise exception 'empty_cart';
  end if;

  if lower(p_fulfillment) like 'deliver%' then
    select fee into v_fee from public.delivery_zones where name = p_location and active;
    if v_fee is null then raise exception 'unknown_delivery_zone'; end if;
  end if;

  insert into public.orders(
    id, order_no, order_reference, customer_id, customer_phone, phone,
    fulfillment, location, delivery_address, payment_method, channel,
    sold_by_staff_id, status, payment_status, delivery_fee, items, total, total_amount)
  values (
    v_id, v_no, 'AYU-' || lpad(v_no::text, 6, '0'), p_customer_id, p_phone, p_phone,
    p_fulfillment, p_location, coalesce(p_delivery_address, ''), p_payment_method, p_channel,
    p_sold_by,
    case when p_payment_method ilike '%m-pesa%' or p_payment_method ilike '%mpesa%'
         then 'Pending PIN' else 'Processing' end,
    'pending', v_fee, '[]'::jsonb, 0, 0);

  for v_item in select * from jsonb_array_elements(p_items) loop
    v_qty := (v_item->>'qty')::int;
    if v_qty is null or v_qty < 1 or v_qty > 100 then raise exception 'bad_qty'; end if;

    update public.products
       set stock_quantity = stock_quantity - v_qty
     where id = (v_item->>'id')::uuid and stock_quantity >= v_qty
    returning * into v_prod;
    if not found then raise exception 'out_of_stock:%', v_item->>'id'; end if;

    insert into public.order_items(order_id, product_id, quantity, unit_price)
    values (v_id, v_prod.id, v_qty, v_prod.price);
    v_subtotal := v_subtotal + v_prod.price * v_qty;
  end loop;

  update public.orders o
     set total = v_subtotal + v_fee,
         total_amount = v_subtotal + v_fee,
         items = (select jsonb_agg(jsonb_build_object(
                    'id', oi.product_id, 'name', p.name,
                    'price', oi.unit_price, 'qty', oi.quantity))
                  from public.order_items oi join public.products p on p.id = oi.product_id
                  where oi.order_id = v_id)
   where o.id = v_id
  returning * into v_order;

  return v_order;
end $$;

-- Cancel an unpaid order and put the stock back (safe to call twice).
create or replace function public.release_order_stock(p_order_id uuid, p_new_status text)
returns void language plpgsql security definer set search_path = public as $$
declare v_ok boolean;
begin
  update public.orders
     set stock_released = true, status = p_new_status, payment_status = 'failed'
   where id = p_order_id and stock_released = false and payment_status = 'pending'
  returning true into v_ok;

  if v_ok then
    update public.products p
       set stock_quantity = p.stock_quantity + s.q
      from (select product_id, sum(quantity) as q
              from public.order_items where order_id = p_order_id group by product_id) s
     where p.id = s.product_id;
  end if;
end $$;

-- Idempotent: calling it again for an already-paid order changes nothing.
-- p_amount / p_receipt may be null (e.g. confirmed via STK Query, which has neither).
create or replace function public.mark_order_paid(
  p_checkout_id text, p_receipt text default null, p_amount numeric default null
) returns public.orders
language plpgsql security definer set search_path = public as $$
declare v_order public.orders;
begin
  select * into v_order from public.orders where checkout_request_id = p_checkout_id for update;
  if not found then return null; end if;
  if v_order.payment_status = 'paid' then return v_order; end if;
  if p_amount is not null and p_amount < v_order.total_amount then
    raise exception 'amount_mismatch';
  end if;

  update public.orders
     set payment_status = 'paid',
         status = case when v_order.stock_released then 'Paid - Needs Review' else 'Paid' end,
         receipt_number = coalesce(p_receipt, receipt_number),
         mpesa_receipt = coalesce(p_receipt, mpesa_receipt),
         paid_at = now()
   where id = v_order.id
  returning * into v_order;
  return v_order;
end $$;

-- Day boundaries in Nairobi time, paid orders only.
create or replace function public.daily_sales_report(
  p_day date default (now() at time zone 'Africa/Nairobi')::date
) returns table(seller text, channel text, orders_count bigint, total numeric)
language sql stable security definer set search_path = public as $$
  select coalesce(s.name, o.sold_by_phone, 'Online customers'),
         o.channel, count(*), sum(o.total_amount)
    from public.orders o
    left join public.staff_users s on s.id = o.sold_by_staff_id
   where o.payment_status = 'paid'
     and (o.paid_at at time zone 'Africa/Nairobi')::date = p_day
   group by 1, 2
   order by 4 desc;
$$;

-- Money/stock functions must NOT be callable through the public API.
revoke all on function public.create_order(uuid,text,text,text,text,text,text,uuid,jsonb) from public, anon, authenticated;
revoke all on function public.release_order_stock(uuid,text) from public, anon, authenticated;
revoke all on function public.mark_order_paid(text,text,numeric) from public, anon, authenticated;
revoke all on function public.daily_sales_report(date) from public, anon, authenticated;
grant execute on function public.create_order(uuid,text,text,text,text,text,text,uuid,jsonb) to service_role;
grant execute on function public.release_order_stock(uuid,text) to service_role;
grant execute on function public.mark_order_paid(text,text,numeric) to service_role;
grant execute on function public.daily_sales_report(date) to service_role;

-- ------------------------------------------------------------ RLS (deny by default)
do $$
declare t text;
begin
  foreach t in array array[
    'stores','leads','conversations','users','products','orders','order_items',
    'stock_wishlist','mpesa_transactions','employees','suppliers','staff_users',
    'refill_requests','payment_overrides','customers','reviews','delivery_zones',
    'whatsapp_staff_sessions','processed_webhook_messages']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

revoke all on public.users, public.staff_users, public.mpesa_transactions,
              public.payment_overrides, public.whatsapp_staff_sessions
  from anon, authenticated;

create or replace function public.is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from public.staff_users
                 where auth_user_id = auth.uid() and is_active and active);
$$;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from public.staff_users
                 where auth_user_id = auth.uid() and is_active and active and role in ('admin','owner'));
$$;

-- Vue admin dashboard (signed-in staff only)
create policy staff_leads_all on public.leads
  for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy staff_products_read on public.products
  for select to authenticated using (public.is_staff());
create policy admin_products_write on public.products
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Customers see/edit only their own profile row
create policy customers_self_read on public.customers
  for select to authenticated using (id = auth.uid());
create policy customers_self_update on public.customers
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- Public catalog WITHOUT buying_price / supplier fields
create or replace view public.products_public as
  select id, name, description, category, price, stock_quantity, image_url, part_number, created_at
    from public.products;
grant select on public.products_public to anon, authenticated;

commit;
