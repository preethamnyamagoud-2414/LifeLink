# LifeLink Database Migrations

This directory tracks the relational database evolution of LifeLink.

## Executing Migrations

To apply the initial schema migration to your local MySQL database:

```powershell
mysql -u root -p lifelink_db < migrations/001_initial_schema.sql
```

## Migration Index

- `001_initial_schema.sql`: Core tables (`users`, `donors`, `blood_requests`, `request_responses`, `contact_messages`, `audit_logs`).
