# RFQ Intelligence — Production Demo

RFQ Intelligence is deployed as a live HTTPS API on Azure Container Apps.

The demo allows reviewers to exercise the production service without installing Python, Docker, PostgreSQL, or the repository locally.

## API access

Base URL:

```text
https://<RFQ-CONTAINER-APP-FQDN>
```

Health endpoint:

```http
GET /health
```

RFQ processing endpoint:

```http
POST /rfq/process
```

The processing endpoint requires an API key:

```http
X-API-Key: <DEMO-API-KEY>
```

The demo API key is provided separately and should not be committed to the repository.

> The service may scale to zero when inactive. The first request after a period of inactivity can therefore take slightly longer while the application starts.

---

## 1. Check service health

```bash
curl -i \
  "https://<RFQ-CONTAINER-APP-FQDN>/health"
```

Expected result:

```text
HTTP 200
```

---

## 2. Exact product — automated quotation

This request contains a known customer and an exact catalog SKU.

```bash
curl -sS \
  -X POST \
  "https://<RFQ-CONTAINER-APP-FQDN>/rfq/process" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <DEMO-API-KEY>" \
  -d '{
    "sender_email": "<KNOWN-DEMO-CUSTOMER-EMAIL>",
    "email_text": "Bonjour, merci de nous chiffrer 10 VAN-BR-050."
  }' | python3 -m json.tool
```

Expected high-level result:

```json
{
  "status": "READY_FOR_QUOTE"
}
```

The system should:

- identify the customer;
- extract the requested product and quantity;
- match `VAN-BR-050` against the trusted catalog;
- apply deterministic pricing and customer rules;
- return a quotation subtotal.

The language model does not generate the product price or customer discount.

---

## 3. Ambiguous product — human review

```bash
curl -sS \
  -X POST \
  "https://<RFQ-CONTAINER-APP-FQDN>/rfq/process" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <DEMO-API-KEY>" \
  -d '{
    "sender_email": "<KNOWN-DEMO-CUSTOMER-EMAIL>",
    "email_text": "Bonjour, pouvez-vous nous chiffrer 10 raccords ?"
  }' | python3 -m json.tool
```

Expected high-level result:

```json
{
  "status": "REVIEW_REQUIRED"
}
```

The system should not arbitrarily select a catalog product when the request is insufficiently specific.

---

## 4. Unknown product — human review

```bash
curl -sS \
  -X POST \
  "https://<RFQ-CONTAINER-APP-FQDN>/rfq/process" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <DEMO-API-KEY>" \
  -d '{
    "sender_email": "<KNOWN-DEMO-CUSTOMER-EMAIL>",
    "email_text": "Bonjour, merci de nous chiffrer 5 XYZ-999."
  }' | python3 -m json.tool
```

Expected high-level result:

```json
{
  "status": "REVIEW_REQUIRED"
}
```

An unknown reference must not be converted into the nearest available catalog product.

---

## Expected behaviour summary

| Scenario | Expected result |
|---|---|
| Known customer + exact product | `READY_FOR_QUOTE` |
| Ambiguous product description | `REVIEW_REQUIRED` |
| Unknown product reference | `REVIEW_REQUIRED` |
| Missing or invalid API key | HTTP `401` |
| Temporary AI dependency failure | HTTP `503` |
| Temporary database failure | HTTP `503` |

---

## Architecture note

RFQ Intelligence deliberately separates probabilistic language understanding from deterministic business authority.

> **The LLM understands the language; the software keeps the business authority.**

The language model assists with structured extraction.

The application remains authoritative for:

- product catalog identity;
- product matching safety boundaries;
- stock;
- pricing;
- customer discounts;
- quotation calculations;
- automation eligibility.

Uncertain cases are explicitly routed to human review rather than forcing an automated answer.

---

## Production environment

The demo runs on:

- Docker;
- Azure Container Apps;
- Azure Container Registry;
- PostgreSQL Flexible Server;
- SQLAlchemy;
- Alembic migrations;
- GitHub Actions CI/CD;
- Azure OIDC;
- Azure Monitor and Log Analytics.

Production releases use immutable Git commit SHA container images.

Database migrations run before application deployment, and the service has been validated through controlled database-failure, revision-rollback, and database-restore exercises.

---

## Demo data

The service uses fictional industrial catalog and customer data.

Please do not submit confidential, personal, or production business information through the public demo endpoint.