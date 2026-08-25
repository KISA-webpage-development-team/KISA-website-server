-- Demo data for validating the KISA Flask API against Supabase.
-- Intended for a scratch Supabase project before importing real AWS RDS data.

BEGIN;

INSERT INTO users (
    email,
    fullname,
    bornyear,
    bornmonth,
    borndate,
    major,
    gradyear,
    linkedin
)
VALUES
    (:'admin_email', :'admin_fullname', 2003, 1, 1, 'KISA Admin', 2027, NULL),
    ('supabase-demo-student@umich.edu', 'Supabase Demo Student', 2004, 5, 14, 'Computer Science', 2028, NULL)
ON CONFLICT (email) DO UPDATE SET
    fullname = EXCLUDED.fullname,
    bornyear = EXCLUDED.bornyear,
    bornmonth = EXCLUDED.bornmonth,
    borndate = EXCLUDED.borndate,
    major = EXCLUDED.major,
    gradyear = EXCLUDED.gradyear,
    linkedin = EXCLUDED.linkedin;

INSERT INTO admins (email)
VALUES (:'admin_email')
ON CONFLICT (email) DO NOTHING;

DELETE FROM posts
WHERE title IN (
    'Supabase demo announcement',
    'Supabase demo community post'
);

INSERT INTO posts (
    type,
    email,
    title,
    text,
    isannouncement,
    fullname,
    readcount,
    anonymous
)
VALUES
    (
        'announcement',
        :'admin_email',
        'Supabase demo announcement',
        'This seeded post confirms the Supabase-backed bulletin board can read announcement data.',
        true,
        :'admin_fullname',
        0,
        false
    ),
    (
        'community',
        'supabase-demo-student@umich.edu',
        'Supabase demo community post',
        'This seeded post confirms normal user content can be loaded from Supabase.',
        false,
        'Supabase Demo Student',
        0,
        false
    );

DELETE FROM pocha
WHERE title = 'Supabase Demo Pocha';

WITH demo_pocha AS (
    INSERT INTO pocha (
        startdate,
        enddate,
        title,
        description
    )
    VALUES (
        '2026-01-01T00:00:00Z',
        '2026-12-31T23:59:59Z',
        'Supabase Demo Pocha',
        'Seeded pocha used to validate menu, cart, order, and dashboard flows on Supabase.'
    )
    RETURNING pochaid
),
menu_rows AS (
    INSERT INTO menu (
        namekor,
        nameeng,
        category,
        price,
        stock,
        isimmediateprep,
        parentpochaid,
        agecheckrequired
    )
    SELECT
        seed.namekor,
        seed.nameeng,
        seed.category,
        seed.price,
        seed.stock,
        seed.isimmediateprep,
        demo_pocha.pochaid,
        seed.agecheckrequired
    FROM demo_pocha
    CROSS JOIN (
        VALUES
            ('김밥', 'Kimbap', 'food', 5.00, 25, false, false),
            ('떡볶이', 'Tteokbokki', 'food', 7.00, 20, false, false),
            ('콜라', 'Cola', 'drink', 2.00, 40, true, false)
    ) AS seed(namekor, nameeng, category, price, stock, isimmediateprep, agecheckrequired)
    RETURNING menuid, nameeng, parentpochaid
),
paid_order AS (
    INSERT INTO "order" (
        email,
        parentpochaid,
        ispaid
    )
    SELECT 'supabase-demo-student@umich.edu', pochaid, true
    FROM demo_pocha
    RETURNING orderid
),
cart_order AS (
    INSERT INTO "order" (
        email,
        parentpochaid,
        ispaid
    )
    SELECT :'admin_email', pochaid, false
    FROM demo_pocha
    RETURNING orderid
)
INSERT INTO orderitem (
    status,
    quantity,
    parentorderid,
    menuid
)
SELECT 'pending', 2, paid_order.orderid, menu_rows.menuid
FROM paid_order
JOIN menu_rows ON menu_rows.nameeng = 'Kimbap'
UNION ALL
SELECT 'ready', 1, paid_order.orderid, menu_rows.menuid
FROM paid_order
JOIN menu_rows ON menu_rows.nameeng = 'Cola'
UNION ALL
SELECT 'pending', 1, cart_order.orderid, menu_rows.menuid
FROM cart_order
JOIN menu_rows ON menu_rows.nameeng = 'Tteokbokki';

COMMIT;
