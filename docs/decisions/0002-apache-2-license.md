# 0002. Apache-2.0 license

- Status: Accepted
- Date: 2026-10-28

## Context
Primum is open source with possible paid tiers later (cloud services, Pro modules). The
license must encourage adoption and contributions.

## Decision
The `primum` repository is licensed under **Apache-2.0**.

## Alternatives considered
- **MIT**: equally permissive but without the explicit patent grant.
- **AGPL-3.0**: protects against closed hosted forks, but some companies avoid it, and paid
  features are planned to live in the cloud or in separate modules anyway.

## Consequences
- Anyone may use, modify and redistribute the code, including in closed products, keeping
  the notices.
- Paid features cannot rely on hiding code in this repository: they belong in the cloud or in
  separate repositories.
- While the author is the only copyright holder the license of future versions can change;
  once others contribute, that requires their agreement (or a CLA).
- Dependencies must have licenses compatible with Apache-2.0.
