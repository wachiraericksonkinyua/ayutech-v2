-- Supabase schema required by the order, POS, payment and WhatsApp endpoints.
-- Apply to a staging project first. This migration expects existing public.orders
-- and public.products tables, as used by the current application.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Staff PIN authentication and WhatsApp sessions.
ALTER TABLE public.staff_users
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS pin_hash TEXT,
  ADD COLUMN IF NOT EXISTS pin_failed_attempts INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS pin_locked_until TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_staff_users_phone_active
  ON public.staff_users (phone) WHERE active = TRUE;

CREATE TABLE IF NOT EXISTS public.whatsapp_staff_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  staff_id UUID NOT NULL REFERENCES public.staff_users(id) ON DELETE CASCADE,
  phone TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_staff_sessions_active
  ON public.whatsapp_staff_sessions (staff_id, phone, expires_at DESC);

CREATE TABLE IF NOT EXISTS public.processed_webhook_messages (
  msg_id TEXT PRIMARY KEY,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- These fields are added without changing the existing orders/products ID type.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS order_reference TEXT,
  ADD COLUMN IF NOT EXISTS customer_id UUID,
  ADD COLUMN IF NOT EXISTS customer_phone TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS fulfillment TEXT NOT NULL DEFAULT 'pickup',
  ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS delivery_address TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS payment_method TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS payment_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total NUMERIC(12, 2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'Pending',
  ADD COLUMN IF NOT EXISTS stock_released BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS items JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'app',
  ADD COLUMN IF NOT EXISTS sold_by_staff_id TEXT,
  ADD COLUMN IF NOT EXISTS sold_by_name TEXT,
  ADD COLUMN IF NOT EXISTS checkout_request_id TEXT,
  ADD COLUMN IF NOT EXISTS receipt_number TEXT,
  ADD COLUMN IF NOT EXISTS mpesa_receipt TEXT,
  ADD COLUMN IF NOT EXISTS payment_reference TEXT,
  ADD COLUMN IF NOT EXISTS payment_notes TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE public.orders
   SET total_amount = total
 WHERE total_amount = 0 AND total > 0;
UPDATE public.orders
   SET payment_status = 'paid'
 WHERE payment_status = 'pending'
   AND lower(COALESCE(status, '')) IN ('paid', 'fulfilled');
UPDATE public.orders
   SET customer_phone = phone
 WHERE COALESCE(customer_phone, '') = '' AND COALESCE(phone, '') <> '';

ALTER TABLE public.orders ALTER COLUMN customer_id DROP NOT NULL;
CREATE SEQUENCE IF NOT EXISTS public.order_reference_seq;
UPDATE public.orders SET order_reference = NULL
 WHERE order_reference IS NOT NULL AND btrim(order_reference) = '';
SELECT setval(
  'public.order_reference_seq',
  COALESCE(MAX((substring(order_reference FROM '^AYU-([0-9]+)$'))::BIGINT), 0) + 1,
  FALSE
)
FROM public.orders;
UPDATE public.orders
   SET order_reference = 'AYU-' || lpad(nextval('public.order_reference_seq')::TEXT, 6, '0')
 WHERE order_reference IS NULL;
SELECT setval(
  'public.order_reference_seq',
  COALESCE(MAX((substring(order_reference FROM '^AYU-([0-9]+)$'))::BIGINT), 0) + 1,
  FALSE
)
FROM public.orders;

CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_order_reference_unique
  ON public.orders (order_reference) WHERE order_reference IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_checkout_request_unique
  ON public.orders (checkout_request_id) WHERE checkout_request_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_mpesa_receipt_unique
  ON public.orders (mpesa_receipt) WHERE mpesa_receipt IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_customer_created
  ON public.orders (customer_id, created_at DESC);

-- Product IDs are stored as text here so this table works with either UUID or
-- integer product primary keys used by existing AyuTech deployments.
CREATE TABLE IF NOT EXISTS public.order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL,
  product_name TEXT NOT NULL,
  part_number TEXT NOT NULL DEFAULT '',
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
  line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON public.order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON public.order_items (product_id);

CREATE TABLE IF NOT EXISTS public.delivery_zones (
  name TEXT PRIMARY KEY,
  fee NUMERIC(12, 2) NOT NULL CHECK (fee >= 0),
  active BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO public.delivery_zones (name, fee) VALUES
  ('CBD & Industrial Area (KES 200)', 200),
  ('Near Suburbs: Westlands/Kilimani (KES 300)', 300),
  ('Outskirts: Rongai/Ruaka/Kitengela (KES 450)', 450),
  ('Upcountry Parcel / Courier (KES 600)', 600)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.mpesa_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_request_id TEXT,
  checkout_request_id TEXT NOT NULL UNIQUE,
  result_code INTEGER,
  result_desc TEXT,
  mpesa_receipt TEXT,
  amount NUMERIC(12, 2),
  phone_number TEXT,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.payment_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id),
  staff_id UUID,
  staff_name TEXT NOT NULL,
  payment_method TEXT NOT NULL,
  reference TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  paid_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.refill_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id TEXT,
  product_name TEXT NOT NULL,
  requested_qty INTEGER NOT NULL CHECK (requested_qty > 0),
  requested_by_name TEXT NOT NULL,
  supplier_name TEXT NOT NULL DEFAULT 'Direct Importer',
  supplier_phone TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending_approval',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.create_order(
  p_customer_id UUID,
  p_phone TEXT,
  p_fulfillment TEXT,
  p_location TEXT,
  p_delivery_address TEXT,
  p_payment_method TEXT,
  p_channel TEXT,
  p_sold_by TEXT,
  p_items JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_order_id UUID := gen_random_uuid();
  v_reference TEXT;
  v_item JSONB;
  v_qty INTEGER;
  v_product_id TEXT;
  v_name TEXT;
  v_part_number TEXT;
  v_price NUMERIC(12, 2);
  v_line_total NUMERIC(12, 2);
  v_total NUMERIC(12, 2) := 0;
  v_delivery_fee NUMERIC(12, 2) := 0;
  v_items JSONB := '[]'::jsonb;
  v_order public.orders%ROWTYPE;
BEGIN
  IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' THEN
    RAISE EXCEPTION 'empty_cart';
  END IF;
  IF jsonb_array_length(p_items) < 1 OR jsonb_array_length(p_items) > 30 THEN
    RAISE EXCEPTION 'empty_cart';
  END IF;
  IF p_fulfillment NOT IN ('pickup', 'delivery') THEN
    RAISE EXCEPTION 'invalid_fulfillment';
  END IF;
  IF p_fulfillment = 'delivery' THEN
    SELECT fee INTO v_delivery_fee FROM public.delivery_zones
      WHERE name = p_location AND active = TRUE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'unknown_delivery_zone';
    END IF;
  END IF;

  FOR v_item IN SELECT value FROM jsonb_array_elements(p_items)
  LOOP
    IF COALESCE(v_item->>'id', '') = ''
       OR COALESCE(v_item->>'qty', '') !~ '^[0-9]+$' THEN
      RAISE EXCEPTION 'bad_qty';
    END IF;
    v_qty := (v_item->>'qty')::INTEGER;
    IF v_qty < 1 OR v_qty > 1000 THEN
      RAISE EXCEPTION 'bad_qty';
    END IF;
    v_product_id := v_item->>'id';

    UPDATE public.products
       SET stock_quantity = stock_quantity - v_qty
     WHERE id::text = v_product_id
       AND stock_quantity >= v_qty
     RETURNING name, COALESCE(part_number, ''), price
          INTO v_name, v_part_number, v_price;
    IF NOT FOUND THEN
      IF EXISTS (SELECT 1 FROM public.products WHERE id::text = v_product_id) THEN
        RAISE EXCEPTION 'out_of_stock';
      END IF;
      RAISE EXCEPTION 'unknown_product';
    END IF;
    IF v_price IS NULL OR v_price < 0 THEN
      RAISE EXCEPTION 'invalid_product_price';
    END IF;

    v_line_total := v_price * v_qty;
    v_total := v_total + v_line_total;
    v_items := v_items || jsonb_build_array(jsonb_build_object(
      'id', v_product_id,
      'name', v_name,
      'part_number', v_part_number,
      'price', v_price,
      'qty', v_qty
    ));
  END LOOP;

  v_total := round(v_total + v_delivery_fee);
  v_reference := 'AYU-' || lpad(nextval('public.order_reference_seq')::TEXT, 6, '0');

  INSERT INTO public.orders (
    id, order_reference, customer_id, customer_phone, phone, fulfillment,
    location, delivery_address, payment_method, payment_status, total_amount,
    total, status, stock_released, items, channel, sold_by_staff_id,
    checkout_request_id, created_at
  ) VALUES (
    v_order_id, v_reference, p_customer_id, p_phone, p_phone, p_fulfillment,
    COALESCE(p_location, ''), COALESCE(p_delivery_address, ''), p_payment_method,
    'pending', v_total, v_total, 'Pending', FALSE, v_items,
    COALESCE(NULLIF(p_channel, ''), 'app'), p_sold_by, NULL, now()
  )
  RETURNING * INTO v_order;

  FOR v_item IN SELECT value FROM jsonb_array_elements(v_items)
  LOOP
    INSERT INTO public.order_items (
      order_id, product_id, product_name, part_number, quantity, unit_price, line_total
    ) VALUES (
      v_order_id, v_item->>'id', v_item->>'name', COALESCE(v_item->>'part_number', ''),
      (v_item->>'qty')::INTEGER, (v_item->>'price')::NUMERIC,
      (v_item->>'price')::NUMERIC * (v_item->>'qty')::INTEGER
    );
  END LOOP;

  RETURN to_jsonb(v_order);
END;
$$;

CREATE OR REPLACE FUNCTION public.release_order_stock(
  p_order_id UUID,
  p_new_status TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_order public.orders%ROWTYPE;
  v_item RECORD;
BEGIN
  SELECT * INTO v_order FROM public.orders WHERE id = p_order_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'order_not_found';
  END IF;
  IF v_order.payment_status = 'paid' OR v_order.stock_released THEN
    RETURN to_jsonb(v_order);
  END IF;

  FOR v_item IN
    SELECT product_id, quantity FROM public.order_items WHERE order_id = p_order_id
  LOOP
    UPDATE public.products
       SET stock_quantity = stock_quantity + v_item.quantity
     WHERE id::text = v_item.product_id;
  END LOOP;

  UPDATE public.orders
     SET stock_released = TRUE,
         status = p_new_status,
         payment_status = CASE WHEN payment_status = 'pending' THEN 'failed' ELSE payment_status END
   WHERE id = p_order_id
   RETURNING * INTO v_order;
  RETURN to_jsonb(v_order);
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_order_paid(
  p_checkout_id TEXT,
  p_receipt TEXT DEFAULT NULL,
  p_amount NUMERIC DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_order public.orders%ROWTYPE;
BEGIN
  SELECT * INTO v_order FROM public.orders
    WHERE checkout_request_id = p_checkout_id FOR UPDATE;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;
  IF v_order.payment_status = 'paid' THEN
    RETURN to_jsonb(v_order);
  END IF;
  IF v_order.payment_status <> 'pending' OR v_order.stock_released THEN
    RAISE EXCEPTION 'order_not_payable';
  END IF;
  IF p_amount IS NOT NULL AND abs(p_amount - v_order.total_amount) > 0.01 THEN
    RAISE EXCEPTION 'amount_mismatch';
  END IF;

  UPDATE public.orders
     SET payment_status = 'paid',
         status = 'Paid',
         receipt_number = COALESCE(NULLIF(p_receipt, ''), receipt_number),
         mpesa_receipt = COALESCE(NULLIF(p_receipt, ''), mpesa_receipt)
   WHERE id = v_order.id
   RETURNING * INTO v_order;
  RETURN to_jsonb(v_order);
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_order_paid_manual(
  p_order_id UUID,
  p_method TEXT,
  p_reference TEXT,
  p_staff_id UUID,
  p_staff_name TEXT,
  p_notes TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_order public.orders%ROWTYPE;
BEGIN
  SELECT * INTO v_order FROM public.orders WHERE id = p_order_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'order_not_payable';
  END IF;
  IF v_order.payment_status = 'paid' THEN
    IF v_order.payment_method = p_method
       AND COALESCE(v_order.payment_reference, '') = COALESCE(NULLIF(p_reference, ''), '') THEN
      RETURN to_jsonb(v_order);
    END IF;
    RAISE EXCEPTION 'order_not_payable';
  END IF;
  IF v_order.payment_status <> 'pending' OR v_order.stock_released THEN
    RAISE EXCEPTION 'order_not_payable';
  END IF;

  UPDATE public.orders
     SET payment_status = 'paid',
         status = CASE WHEN channel = 'pos' THEN 'Fulfilled' ELSE 'Paid' END,
         payment_method = p_method,
         payment_reference = NULLIF(p_reference, ''),
         payment_notes = COALESCE(p_notes, ''),
         receipt_number = COALESCE(NULLIF(p_reference, ''), receipt_number)
   WHERE id = p_order_id
   RETURNING * INTO v_order;

  INSERT INTO public.payment_audit (
    order_id, staff_id, staff_name, payment_method, reference, notes
  ) VALUES (
    p_order_id, p_staff_id, COALESCE(p_staff_name, 'Staff'), p_method,
    COALESCE(p_reference, ''), COALESCE(p_notes, '')
  );
  RETURN to_jsonb(v_order);
END;
$$;

CREATE OR REPLACE FUNCTION public.daily_sales_report(p_day DATE DEFAULT CURRENT_DATE)
RETURNS TABLE(seller TEXT, channel TEXT, orders_count BIGINT, total NUMERIC)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT COALESCE(s.name, 'Customer') AS seller,
         o.channel,
         count(*) AS orders_count,
         COALESCE(sum(o.total_amount), 0) AS total
    FROM public.orders o
    LEFT JOIN public.staff_users s ON s.id::text = o.sold_by_staff_id
   WHERE o.payment_status = 'paid'
     AND o.created_at::date = p_day
   GROUP BY COALESCE(s.name, 'Customer'), o.channel
   ORDER BY seller, channel
$$;

CREATE OR REPLACE FUNCTION public.fulfill_refill_request(
  p_refill_id UUID,
  p_new_status TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_refill public.refill_requests%ROWTYPE;
  v_result public.refill_requests%ROWTYPE;
BEGIN
  IF p_new_status NOT IN ('pending_approval', 'approved', 'fulfilled', 'rejected', 'cancelled') THEN
    RAISE EXCEPTION 'invalid_refill_status';
  END IF;
  SELECT * INTO v_refill FROM public.refill_requests WHERE id = p_refill_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'refill_not_found';
  END IF;
  IF v_refill.status = 'fulfilled' AND p_new_status <> 'fulfilled' THEN
    RAISE EXCEPTION 'refill_already_fulfilled';
  END IF;

  IF p_new_status = 'fulfilled' AND v_refill.status <> 'fulfilled'
     AND v_refill.product_id IS NOT NULL THEN
    UPDATE public.products
       SET stock_quantity = stock_quantity + v_refill.requested_qty
     WHERE id::text = v_refill.product_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'refill_product_not_found';
    END IF;
  END IF;
  UPDATE public.refill_requests
     SET status = p_new_status, updated_at = now()
   WHERE id = p_refill_id
   RETURNING * INTO v_result;
  RETURN to_jsonb(v_result);
END;
$$;

REVOKE ALL ON FUNCTION public.create_order(UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_order_stock(UUID, TEXT) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.mark_order_paid(TEXT, TEXT, NUMERIC) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.mark_order_paid_manual(UUID, TEXT, TEXT, UUID, TEXT, TEXT) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.daily_sales_report(DATE) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fulfill_refill_request(UUID, TEXT) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.create_order(UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION public.release_order_stock(UUID, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_order_paid(TEXT, TEXT, NUMERIC) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_order_paid_manual(UUID, TEXT, TEXT, UUID, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.daily_sales_report(DATE) TO service_role;
GRANT EXECUTE ON FUNCTION public.fulfill_refill_request(UUID, TEXT) TO service_role;
