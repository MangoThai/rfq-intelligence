# RFQ Intelligence — Architecture

RFQ Intelligence is an AI-assisted backend service for processing industrial requests for quotation (RFQs).

The system converts unstructured customer emails into structured RFQ lines, matches requested items against a trusted product catalog, applies deterministic business rules and pricing logic, and decides whether a request can proceed automatically or requires human review.

V1 established and evaluated the core RFQ processing pipeline.

V2 extends that validated application with production-oriented concerns:

- containerization;
- PostgreSQL persistence;
- database migrations;
- API authentication;
- cloud deployment;
- CI/CD;
- secrets management;
- observability and alerting;
- failure handling;
- rollback;
- database recovery.

The fundamental architecture remains intentionally small.

The goal is not to maximize the number of frameworks or infrastructure components. The goal is to build a system whose decisions can be understood, tested, operated, and recovered.

---

## Table of contents

1. [Purpose](#1-purpose)
2. [High-level architecture](#2-high-level-architecture)
3. [Architectural principle: bounded LLM responsibility](#3-architectural-principle-bounded-llm-responsibility)
4. [Request lifecycle](#4-request-lifecycle)
5. [Extraction validation](#5-extraction-validation)
6. [Product matching](#6-product-matching)
7. [Deterministic business rules](#7-deterministic-business-rules)
8. [Pricing](#8-pricing)
9. [Global RFQ decision](#9-global-rfq-decision)
10. [Persistence architecture](#10-persistence-architecture)
11. [Failure semantics](#11-failure-semantics)
12. [Runtime and deployment architecture](#12-runtime-and-deployment-architecture)
13. [Database migrations](#13-database-migrations)
14. [Continuous delivery](#14-continuous-delivery)
15. [Authentication and secrets](#15-authentication-and-secrets)
16. [Observability](#16-observability)
17. [Recovery and rollback](#17-recovery-and-rollback)
18. [Evaluation architecture](#18-evaluation-architecture)
19. [Technology stack](#19-technology-stack)
20. [Known limitations and intentional non-goals](#20-known-limitations-and-intentional-non-goals)
21. [Design philosophy](#21-design-philosophy)

---

# 1. Purpose

RFQ Intelligence addresses a common B2B workflow:

> A customer sends an email requesting prices for industrial products, often using inconsistent references, approximate descriptions, quantities, units, and incomplete information.

The system assists with this workflow by:

1. extracting structured RFQ lines from the email;
2. matching requested products against a trusted catalog;
3. identifying the customer where possible;
4. applying deterministic business rules;
5. calculating quotation values from trusted data;
6. deciding whether the request can be prepared automatically;
7. explicitly routing uncertain cases to human review;
8. persisting processing results;
9. exposing the workflow through a secured API;
10. providing operational visibility when dependencies or deployments fail.

The system is designed around a strict distinction between:

- **language understanding**, where probabilistic models are useful;
- **business authority**, where deterministic application logic remains authoritative.

---

# 2. High-level architecture

RFQ Intelligence has two complementary architectural layers.

## 2.1 Application architecture

```text
Incoming RFQ email
        │
        ▼
FastAPI request validation
        │
        ▼
Customer identification
        │
        ▼
LLM structured extraction
        │
        ▼
Extraction validation
        │
        ▼
Product matching
        │
        ▼
Deterministic business rules
        │
        ▼
Pricing / quotation preparation
        │
        ▼
Global RFQ decision
        │
        ├──────────────► REVIEW_REQUIRED
        │
        └──────────────► READY_FOR_QUOTE
        │
        ▼
PostgreSQL persistence
        │
        ▼
HTTP response
```

## 2.2 Production architecture

```text
                         GitHub
                           │
                    Pull Request / main
                           │
                    GitHub Actions
                    ├── pytest
                    ├── Ruff
                    └── mypy
                           │
                     Azure OIDC
                           │
                           ▼
               Azure Container Registry
                  immutable SHA image
                           │
                           ▼
             Azure Container Apps Job
                 Alembic upgrade head
                           │
                           ▼
                Azure Container Apps
                   FastAPI container
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
        OpenAI API             PostgreSQL Flexible Server
                                           │
                                           ▼
                                      persisted RFQs

                    Azure Monitor
              ┌─────────┼──────────┐
              ▼         ▼          ▼
         app logs   HTTP logs    alerts
```

The application remains a single deployable service.

No microservice boundary currently provides enough value to justify additional operational complexity.

---

# 3. Architectural principle: bounded LLM responsibility

The central design principle of RFQ Intelligence is:

> **The LLM understands the language; the software keeps the business authority.**

The language model is intentionally limited to tasks where probabilistic interpretation is useful.

Typical LLM responsibility includes:

- identifying requested products from natural-language text;
- extracting quantities;
- extracting units;
- recognizing references provided by the customer;
- structuring ambiguous or incomplete wording;
- reporting extraction issues.

The LLM does **not** have authority over:

- catalog truth;
- stock;
- product prices;
- customer discounts;
- quotation calculations;
- business permissions;
- matching safety boundaries;
- final automation eligibility.

These values come from deterministic application code and trusted application data.

This boundary reduces the impact of hallucination and makes important decisions testable outside the model.

---

# 4. Request lifecycle

The main production endpoint is:

```text
POST /rfq/process
```

A request contains:

- the sender email;
- the raw RFQ email text.

The processing lifecycle is approximately:

```text
HTTP request
    │
    ▼
API-key authentication
    │
    ▼
Pydantic request validation
    │
    ▼
Request ID creation
    │
    ▼
Customer resolution
    │
    ▼
Structured LLM extraction
    │
    ▼
Extraction validation
    │
    ▼
Product matching
    │
    ▼
Business-rule evaluation
    │
    ▼
Pricing
    │
    ▼
RFQ-level decision
    │
    ▼
Persistence transaction
    │
    ▼
Structured HTTP response
```

The request ID follows the processing lifecycle and is returned to the caller through:

```text
X-Request-ID
```

This identifier is also included in relevant structured logs.

---

# 5. Extraction validation

LLM output is treated as untrusted structured input.

Successful model generation is therefore not sufficient for automation.

Extracted lines are validated before entering business logic.

Relevant checks include:

- presence of a usable product query;
- quantity validity;
- unit validity;
- consistency of extracted information;
- explicit extraction issues;
- unsupported or incomplete information.

Validation issues remain visible downstream rather than being silently corrected by the model.

The system prefers explicit uncertainty over fabricated certainty.

A syntactically valid LLM response can therefore still result in:

```text
REVIEW_REQUIRED
```

---

# 6. Product matching

Product matching converts an extracted customer request into a possible catalog product.

The matching strategy uses increasingly permissive evidence while preserving explicit abstention.

The main categories include:

- exact or normalized SKU matches;
- formatting-tolerant reference matches;
- constrained typo/fuzzy matching;
- description-based matching;
- ambiguous matches;
- unmatched products.

The matching layer can therefore produce outcomes equivalent to:

```text
MATCHED
AMBIGUOUS
NOT_FOUND
```

A product is not selected merely because it is the closest available catalog entry.

Where confidence or evidence is insufficient, the system routes the line to review.

This behaviour is deliberate.

A false positive product match is more dangerous than requesting human verification.

---

# 7. Deterministic business rules

Once a product has been identified, business logic becomes deterministic.

The application remains authoritative for information such as:

- stock availability;
- product sales unit;
- pack or quantity constraints;
- lead time;
- customer identity;
- customer discount;
- eligibility for automatic quotation;
- decision reason codes.

The model cannot override these rules.

This provides an important architectural property:

> identical trusted inputs produce identical business decisions.

Business rules can therefore be tested independently from the language model.

---

# 8. Pricing

Pricing is never generated by the LLM.

The quotation calculation uses trusted application data.

A typical line calculation follows the conceptual form:

```text
catalog unit price
        ×
requested quantity
        ↓
line subtotal
```

Customer-specific deterministic adjustments, such as an allowed discount, are applied through application logic.

The RFQ quotation subtotal is calculated from accepted line subtotals.

Python `Decimal` values are used for monetary calculations rather than binary floating-point arithmetic.

If information required for a safe quotation is missing or contradictory, the system does not invent a value.

The request is routed to:

```text
REVIEW_REQUIRED
```

---

# 9. Global RFQ decision

Line-level processing feeds an RFQ-level decision.

The two main terminal states are:

```text
READY_FOR_QUOTE
```

and:

```text
REVIEW_REQUIRED
```

`READY_FOR_QUOTE` means the system has sufficient trusted information to prepare the quotation automatically under the current business rules.

`REVIEW_REQUIRED` means human verification is necessary.

Reasons may include:

- ambiguous product matching;
- unknown product;
- invalid quantity;
- unsupported unit;
- missing required information;
- conflicting information;
- extraction issues;
- business-rule failure.

Human review is part of the architecture rather than an exception to it.

The automation objective is therefore not:

> automate every RFQ.

It is:

> automate RFQs for which the available evidence is sufficiently safe, while making uncertainty explicit everywhere else.

---

# 10. Persistence architecture

V2 introduces PostgreSQL persistence for RFQ processing history.

The main relationship is:

```text
rfq_requests
     │
     └──────── 1:N ──────── rfq_lines
```

## 10.1 `rfq_requests`

Request-level persistence includes information such as:

- internal identifier;
- request ID;
- customer ID;
- final RFQ status;
- decision reason codes;
- quotation subtotal;
- model identifier;
- model response identifier;
- model latency;
- estimated model cost;
- creation timestamp.

## 10.2 `rfq_lines`

Line-level persistence includes:

- RFQ foreign key;
- line number;
- original extracted product query;
- quantity;
- unit;
- extraction issues;
- matching status;
- matched SKU;
- decision status;
- decision reason codes;
- line subtotal.

## 10.3 Data minimization

The raw RFQ email body is deliberately **not persisted**.

This keeps the database focused on operationally useful structured information and reduces unnecessary storage of potentially sensitive customer content.

## 10.4 Transaction boundary

Persistence occurs inside a database transaction.

The parent RFQ and its lines are committed as one logical unit.

Database failures therefore do not leave an intentionally partially persisted RFQ result.

## 10.5 Connection strategy

SQLAlchemy 2 is used for database access with Psycopg 3.

For the current low-traffic workload, the application uses:

```text
NullPool
```

rather than retaining persistent database connections between requests.

Each database interaction therefore obtains a fresh connection.

This choice was introduced after controlled failure testing demonstrated that stale pooled network connections could cause excessively long waits after PostgreSQL interruption.

Connection creation is bounded with an explicit connection timeout.

For the current scale, the small additional connection overhead is preferred over more complex stale-connection management.

---

# 11. Failure semantics

RFQ Intelligence treats important dependency failures explicitly.

Failures must not be converted into apparently valid RFQ results.

## 11.1 AI dependency unavailable

Transient OpenAI API failures are translated into:

```text
HTTP 503
```

with a structured application error:

```text
AI_DEPENDENCY_UNAVAILABLE
```

The caller is informed that the extraction dependency is temporarily unavailable.

The system does not produce a guessed RFQ result.

## 11.2 Database unavailable

Database operational failures are translated into:

```text
HTTP 503
```

with:

```text
DATABASE_UNAVAILABLE
```

The database connection attempt is bounded so the HTTP request does not remain indefinitely blocked during an outage.

## 11.3 Authentication failure

Missing or invalid API credentials return:

```text
HTTP 401
```

with:

```text
INVALID_API_KEY
```

## 11.4 Application startup configuration

Required production configuration fails closed.

For example, the application does not silently start an unsecured RFQ processing endpoint if the required API key configuration is absent.

---

# 12. Runtime and deployment architecture

RFQ Intelligence is packaged as a Docker container.

The Docker build uses a multi-stage strategy.

The runtime image contains only the components required to operate the service and run its database migrations.

The container includes:

- the installed Python application;
- runtime dependencies;
- catalog/reference data;
- Alembic configuration;
- Alembic migrations.

The runtime container runs as a non-root user.

Secrets are not baked into the image.

Application data paths are configured through runtime configuration rather than assumptions about the source repository layout.

The production hosting platform is:

```text
Azure Container Apps
```

Azure Container Apps provides:

- HTTPS ingress;
- container revisions;
- secret references;
- managed deployment;
- log integration;
- revision traffic control;
- scale configuration.

The application currently uses a deliberately small resource profile because the goal is to operate a realistic service without introducing unnecessary infrastructure.

---

# 13. Database migrations

Database schema evolution is managed by:

```text
Alembic
```

The application does not create the production schema through:

```python
Base.metadata.create_all()
```

Production schema changes must instead be explicit migrations.

The deployment sequence is:

```text
new application image
        │
        ▼
Azure Container Apps migration job
        │
        ▼
alembic upgrade head
        │
        ├──── failure ────► deployment stops
        │
        ▼
application deployment
```

The migration job uses the **same immutable container image** as the application deployment.

This avoids a class of problems where migration code differs from the application version being released.

A failed migration prevents the application deployment from continuing.

---

# 14. Continuous delivery

GitHub Actions orchestrates validation and deployment.

The delivery pipeline performs the following high-level sequence:

```text
push / merge to main
        │
        ▼
quality checks
        │
        ├── pytest
        ├── Ruff lint
        ├── Ruff format check
        └── mypy
        │
        ▼
Azure authentication through OIDC
        │
        ▼
Docker build
        │
        ▼
Azure Container Registry
        │
        ▼
immutable SHA-tagged image
        │
        ▼
database migration job
        │
        ▼
Container Apps deployment
        │
        ▼
production smoke checks
```

Production images use a Git commit SHA tag:

```text
rfq-intelligence:sha-<git-commit>
```

This provides a direct relationship between:

- source code;
- CI/CD run;
- container image;
- deployed revision.

## 14.1 OIDC authentication

GitHub Actions authenticates to Azure through OpenID Connect federation.

Long-lived Azure client secrets are therefore not required in GitHub Actions.

The deployment identity is granted only the Azure permissions required by the release workflow.

---

# 15. Authentication and secrets

The main RFQ endpoint requires:

```text
X-API-Key
```

The health endpoint remains public:

```text
GET /health
```

The health endpoint is intended for infrastructure/liveness checks and does not expose RFQ business operations.

The API-key implementation uses constant-time comparison for provided credentials.

Required secrets include values such as:

- OpenAI API credentials;
- RFQ API credentials;
- PostgreSQL connection information.

Secrets are supplied through runtime configuration and Azure secret references.

They are not intended to appear in:

- Git history;
- Docker images;
- Dockerfiles;
- application logs;
- public documentation.

The API-key mechanism is intentionally simple.

It is appropriate for the current small internal or service-to-service deployment model.

It is not presented as a replacement for an enterprise identity platform in a future multi-user or public application.

---

# 16. Observability

Observability exists at both application and infrastructure levels.

## 16.1 Structured application logs

Application events are written as structured JSON to stdout.

This makes logs compatible with container-native log collection.

Relevant events include:

- RFQ processing status;
- dependency failures;
- authentication failures;
- model metadata;
- request correlation information.

The raw RFQ email body is not written to logs.

## 16.2 Request correlation

Each request receives a request ID.

The ID is:

- stored in request state;
- used in relevant application logs;
- returned as:

```text
X-Request-ID
```

This enables a caller-visible failure to be correlated with application logs.

## 16.3 Model observability

Where available, RFQ processing records information such as:

- model identifier;
- OpenAI response identifier;
- model latency;
- token/cost metadata.

These values are observational and do not influence deterministic business decisions.

## 16.4 Azure Monitor

Azure collects:

- Container Apps console logs;
- Container Apps HTTP logs.

Queries can therefore inspect:

- HTTP 5xx responses;
- processing events;
- dependency failures;
- request IDs;
- revision behaviour;
- latency information.

## 16.5 Alerting

Azure Monitor scheduled-query alerts monitor operational conditions including:

- HTTP 5xx responses;
- critical application dependency failures such as AI or database unavailability.

Alerts are connected to an Azure Action Group.

The objective is not comprehensive enterprise monitoring.

It is to ensure that important service failures can be detected without manually inspecting logs continuously.

---

# 17. Recovery and rollback

V2 includes controlled operational failure drills.

The purpose was to verify actual failure behaviour rather than assume that recovery mechanisms would work.

## 17.1 PostgreSQL outage

Azure PostgreSQL was deliberately stopped while the application remained deployed.

The validated behaviour was:

```text
PostgreSQL unavailable
        │
        ▼
bounded connection attempt
        │
        ▼
SQLAlchemy OperationalError
        │
        ▼
HTTP 503
DATABASE_UNAVAILABLE
        │
        ▼
structured logs / HTTP logs
        │
        ▼
Azure Monitor detection
```

After PostgreSQL returned to:

```text
Ready
```

the application successfully processed requests again without requiring a new application deployment.

This validated dependency recovery independently from release recovery.

## 17.2 Faulty application revision

A deliberately invalid Azure Container Apps revision was created by removing required runtime configuration.

This produced a startup failure.

Multiple-revision mode allowed the failure to be diagnosed without rebuilding the previously healthy application image.

The recovery process was:

```text
faulty revision
      │
      ▼
startup failure
      │
      ▼
revision/log inspection
      │
      ▼
traffic redirected
      │
      ▼
previous healthy revision
      │
      ▼
service restored
```

The broken revision could then be deactivated.

The operational principle is:

> during an incident, restore service first; investigate or correct the faulty release second.

## 17.3 PostgreSQL point-in-time restore

Database recovery was also tested independently.

Azure PostgreSQL point-in-time restore was used to create an isolated temporary server from the production database backup history.

The restored environment was verified to contain:

- persisted `rfq_requests`;
- persisted `rfq_lines`;
- the Alembic migration version.

The production database remained untouched during the restore exercise.

The temporary recovery server was deleted after verification.

This demonstrates that backup configuration was not merely enabled but that restored application data could actually be read.

---

# 18. Evaluation architecture

Evaluation remains separate from production runtime concerns.

The V1 evaluation strategy tests whether RFQ automation is sufficiently conservative.

The evaluation layers include:

## 18.1 Matching regression tests

Synthetic and curated cases exercise:

- exact references;
- formatting variations;
- typos;
- descriptions;
- ambiguous cases;
- unknown products.

The important safety distinction is not only whether a product can be matched.

The evaluation also checks whether the system automates cases that should have been sent to review.

## 18.2 Calibration cases

Calibration datasets are used to adjust automation boundaries while monitoring:

- matching correctness;
- automation coverage;
- unsafe automation.

The system intentionally accepts lower automation coverage when required to preserve safety.

## 18.3 End-to-end evaluation

End-to-end RFQ scenarios validate the complete decision path:

```text
email
  ↓
extraction
  ↓
matching
  ↓
business rules
  ↓
pricing
  ↓
READY_FOR_QUOTE / REVIEW_REQUIRED
```

These tests also collect model operational information such as latency, token usage and estimated cost.

## 18.4 Adversarial evaluation

Adversarial cases are used to exercise uncertain, contradictory and potentially unsafe requests.

The primary safety metric is:

```text
unsafe automation
```

rather than automation coverage alone.

Detailed current evaluation results are maintained separately in:

```text
docs/evaluation-results.md
```

This architecture document describes the evaluation strategy rather than duplicating benchmark results that may evolve independently.

---

# 19. Technology stack

## Application

- Python 3.13
- FastAPI
- Pydantic
- OpenAI API
- RapidFuzz
- Python `Decimal`

## Persistence

- PostgreSQL 17
- SQLAlchemy 2
- Psycopg 3
- Alembic

## Testing and quality

- pytest
- mypy
- Ruff
- pre-commit

## Containerization

- Docker
- multi-stage builds
- non-root runtime
- uv

## Cloud

- Azure Container Registry
- Azure Container Apps
- Azure Container Apps Jobs
- Azure Database for PostgreSQL Flexible Server
- Azure Monitor
- Log Analytics
- Azure Action Groups
- managed/federated Azure identities

## Delivery

- GitHub
- GitHub Actions
- Azure OIDC federation
- immutable SHA-tagged container images

---

# 20. Known limitations and intentional non-goals

RFQ Intelligence is intentionally narrow.

The project does not attempt to simulate the architecture of a large enterprise platform.

## 20.1 Current product limitations

The current scope primarily assumes:

- text-based RFQ input;
- French-language industrial requests;
- a small trusted product catalog;
- limited customer/contact data;
- one primary RFQ processing API;
- simple API-key authentication;
- no complex user interface.

The catalog and customer reference datasets remain application-managed files rather than a complete ERP integration.

The current system is therefore a representative production-style service, not a replacement for an industrial ERP or CRM.

## 20.2 Intentional infrastructure non-goals

The current architecture deliberately excludes:

- Kubernetes;
- microservices;
- Kafka;
- RabbitMQ;
- Redis;
- distributed task queues;
- complex frontend infrastructure;
- service mesh infrastructure.

None is currently required by the workload.

## 20.3 Intentional AI non-goals

The project also deliberately excludes:

- multi-agent orchestration;
- autonomous agents;
- MCP integration;
- RAG;
- vector databases;
- fine-tuning.

These technologies may be useful in other systems, but RFQ Intelligence currently has no demonstrated requirement that justifies them.

## 20.4 Infrastructure as code

The current V2 deployment was intentionally built and exercised directly against Azure resources to learn and validate the operational model.

Infrastructure-as-code would be a reasonable future step if:

- environments had to be recreated regularly;
- multiple environments were required;
- infrastructure changes became frequent;
- team collaboration required declarative infrastructure review.

It is not necessary merely to increase the project's technology count.

---

# 21. Design philosophy

RFQ Intelligence follows several engineering principles.

## 21.1 The problem chooses the technology

Technologies are introduced only when they solve a demonstrated problem.

V2 exists because V1 lacked production deployment and operational experience.

It does not exist to add unrelated frameworks.

## 21.2 Deterministic code owns invariants

The language model is not trusted with values that the software can know deterministically.

Examples include:

- prices;
- stock;
- discounts;
- calculations;
- product catalog truth;
- permissions;
- business decision thresholds.

## 21.3 Abstention is a feature

The system does not need to automate every request.

```text
REVIEW_REQUIRED
```

is a valid and desirable result when evidence is insufficient.

## 21.4 Fail explicitly

External dependency failures must remain failures.

The system should not convert:

```text
database unavailable
```

or:

```text
AI service unavailable
```

into apparently valid business output.

## 21.5 Prefer bounded systems

Network calls, database connections and external services should fail within controlled bounds rather than leaving requests indefinitely suspended.

## 21.6 Operability is part of software correctness

A system is not finished merely because its happy path works locally.

The V2 definition of correctness also includes the ability to:

- deploy reproducibly;
- migrate data safely;
- authenticate callers;
- inspect logs;
- correlate failures;
- detect incidents;
- recover dependencies;
- roll back faulty releases;
- restore persisted data.

## 21.7 Avoid speculative complexity

Architecture should grow from observed requirements.

The current system deliberately remains:

```text
one API
one container image
one relational database
one deployment pipeline
```

until evidence justifies something more complex.

---

# Final architecture summary

RFQ Intelligence combines probabilistic language understanding with deterministic business control.

V1 established that the RFQ workflow could be processed and evaluated safely.

V2 demonstrates that the same application can also be operated as a real service:

```text
unstructured RFQ
      │
      ▼
bounded LLM extraction
      │
      ▼
deterministic matching and business rules
      │
      ▼
safe RFQ decision
      │
      ▼
PostgreSQL persistence
      │
      ▼
secured FastAPI service
      │
      ▼
Docker
      │
      ▼
CI/CD + migrations
      │
      ▼
Azure Container Apps
      │
      ▼
logs / alerts / rollback / recovery
```

The architecture deliberately favors clarity, explicit failure semantics, human review and operational recoverability over unnecessary technical complexity.