# OPERATIONS

This document outlines operations, startup, validation, and failure-handling procedures for the Synthetic Commercial Data Generator.

---

## 1. Startup Process

The generator container is executed as a batch utility using Docker Compose:

```bash
docker compose up synth-generator
```

On startup:
1. The container executes `python -m synth_data_creator.main`.
2. It parses environment variables and verifies the `DATABASE_URL`.
3. It initializes the database schema idempotently (dropping old tables if they exist to start fresh).
4. Progress is logged sequentially to stdout.

---

## 2. Validation Process

Before terminating with exit code 0, the service performs count verification checks. It queries the PostgreSQL database tables directly to confirm the numbers of records inserted:

```sql
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM raw_sales;
SELECT COUNT(*) FROM raw_payments;
SELECT COUNT(*) FROM raw_returns;
```

If the actual counts match the configured targets exactly, the container prints:
```text
Synthetic Dataset Generation Complete
```
And terminates with exit code `0`.

---

## 3. Failure Handling

If any exception occurs during schema setup, generation, bulk insertion, or verification:
- The error traceback is printed to stderr.
- The service terminates immediately with exit code `1`.
- The container halts.

Because the restart policy is explicitly set to `restart: "no"` in `docker-compose.yml`, the container will **not** enter an infinite restart loop upon failure, preserving host CPU resources.

---

## 4. Troubleshooting

### 4.1 Connection Failures (`Name or service not known`)
- **Symptoms**: Logs show `socket.gaierror: [Errno -2] Name or service not known`.
- **Cause**: The container is trying to connect to a host service (like a database container) using `host.docker.internal` on Linux, but the DNS resolver inside Docker cannot map the hostname.
- **Solution**: Ensure `docker-compose.yml` has the `extra_hosts` option set:
  ```yaml
  extra_hosts:
    - "host.docker.internal:host-gateway"
  ```

### 4.2 Port Allocation Conflicts
- **Symptoms**: `Bind for 0.0.0.0:5432 failed: port is already allocated`.
- **Cause**: A database container in your Compose configuration is trying to bind to host port `5432` which is already occupied by a local PostgreSQL service.
- **Solution**: Map the database service to an alternate host port (e.g., `5433:5432`):
  ```yaml
  ports:
    - "5433:5432"
  ```
