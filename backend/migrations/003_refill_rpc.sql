-- 003_refill_rpc.sql
-- admin.py calls rpc("fulfill_refill_request", {p_refill_id, p_new_status}) but this
-- function did not exist in production. It updates the request and adds the stock in ONE
-- transaction, and can never add the same refill to stock twice.

create or replace function public.fulfill_refill_request(p_refill_id uuid, p_new_status text)
returns public.refill_requests
language plpgsql security definer set search_path = public as $$
declare
  v     public.refill_requests;
  v_new text := lower(trim(coalesce(p_new_status, '')));
begin
  if v_new = '' then raise exception 'bad_status'; end if;

  select * into v from public.refill_requests where id = p_refill_id for update;
  if not found then raise exception 'refill_not_found'; end if;

  -- already fulfilled: repeating "fulfilled" is a no-op, anything else is refused
  -- (the stock was already added and must not be silently reversed here)
  if v.status = 'fulfilled' then
    if v_new = 'fulfilled' then return v; end if;
    raise exception 'already_fulfilled';
  end if;

  if v_new = 'fulfilled' and v.product_id is not null then
    update public.products
       set stock_quantity = stock_quantity + greatest(coalesce(v.requested_qty, 0), 0)
     where id = v.product_id;
  end if;

  update public.refill_requests set status = v_new
   where id = p_refill_id returning * into v;
  return v;
end $$;

revoke all on function public.fulfill_refill_request(uuid, text) from public, anon, authenticated;
grant execute on function public.fulfill_refill_request(uuid, text) to service_role;
