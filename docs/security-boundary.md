# SPM Agent Connector Security Boundary

SPM connectors are designed as a narrow agent-facing surface over the hosted SPM
platform.

## Included

- Temporal project memory recall.
- Context pack generation and verification.
- Context graph and boundary queries.
- Agent preflight and policy pack checks.
- Post-action reporting with tests, evidence and decisions.

## Excluded

- Billing and checkout.
- Customer portal sessions.
- Invoice payment.
- Tenant deletion or destructive administration.
- Raw secret return.
- Cross-project access without explicit project-scoped authorization.

## Operational Model

Agents authenticate with bearer tokens created or approved inside SPM. Tokens
should be scoped to one project and one operating mode. The SPM server applies
plan, quota, scope, permission and policy checks before serving tools.

The public connector package is not the SPM platform. It is a client-side
integration layer that points trusted agent clients at the hosted SPM MCP
endpoint.
