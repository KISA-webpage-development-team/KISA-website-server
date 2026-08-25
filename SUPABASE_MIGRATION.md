# Supabase Migration Notes

## Current State

- Backend: Flask app in Elastic Beanstalk.
- Database: AWS RDS MySQL, selected by `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `FLASK_ENV`.
- Storage and notifications still use AWS separately:
  - S3/CloudFront for bulletin editor and pocha menu images.
  - SNS/APNS for pocha push notifications.
- Frontend talks to the Flask API through `NEXT_PUBLIC_BACKEND_URL`, so the first migration can keep the frontend API contract unchanged.

## Recommended First Cut

Move only the relational database from RDS MySQL to Supabase Postgres. Keep Flask as the API layer for now.

This preserves the current routes, JWT/session assumptions, sockets, Stripe flow, image handling, and notification flow while removing the expensive RDS database. Moving images from S3 to Supabase Storage can be a second phase after the DB cutover.

## New Environment Variables

```text
DATABASE_ENGINE=postgres
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

`SUPABASE_DB_URL` is also accepted as an alias for `DATABASE_URL`.

For local or old AWS behavior, leave `DATABASE_ENGINE` unset and the app will keep using MySQL.

## Schema

Use `queries/supabase_schema.sql` to create the scratch Supabase schema.

The schema intentionally uses lowercase Postgres identifiers because the existing Flask SQL does not quote most table/column names. `server.model.Cursor` maps returned lowercase keys back to the camelCase response shape expected by the frontend.

## Data Export

From the AWS RDS MySQL source, export these tables:

```text
users
admins
posts
comments
postlikes
commentlikes
pocha
menu
order
orderItem
notificationARNs
```

Suggested order for import:

```text
users -> admins -> posts -> comments -> postlikes/commentlikes -> pocha -> menu -> order -> orderItem -> notificationARNs
```

After importing identity columns, reset sequences in Supabase:

```sql
SELECT setval(pg_get_serial_sequence('posts', 'postid'), COALESCE((SELECT max(postid) FROM posts), 1));
SELECT setval(pg_get_serial_sequence('pocha', 'pochaid'), COALESCE((SELECT max(pochaid) FROM pocha), 1));
SELECT setval(pg_get_serial_sequence('menu', 'menuid'), COALESCE((SELECT max(menuid) FROM menu), 1));
SELECT setval(pg_get_serial_sequence('"order"', 'orderid'), COALESCE((SELECT max(orderid) FROM "order"), 1));
SELECT setval(pg_get_serial_sequence('orderitem', 'orderitemid'), COALESCE((SELECT max(orderitemid) FROM orderitem), 1));
```

## Verification Checklist

- Signup/login/admin check.
- Board list, announcement list, post detail, create/update/delete post.
- Comments, nested comments, likes.
- User profile, user posts, user comments.
- Pocha status, menu, previous pochas.
- Cart add/remove for immediate and non-immediate prep items.
- Stock reservation and payment success/failure.
- Dashboard order status changes and websocket events.
- S3 image upload/delete still works after DB switch.
- SNS notification registration and send still works after DB switch.

## Cutover Guardrail

Do not point production at Supabase until:

- RDS snapshot/export is complete.
- Scratch Supabase import passes the checklist.
- Supabase connection string uses pooled connection on port `6543` for the deployed Flask app.
- Rollback is simply changing `DATABASE_ENGINE` back to MySQL and restoring the old env values.
