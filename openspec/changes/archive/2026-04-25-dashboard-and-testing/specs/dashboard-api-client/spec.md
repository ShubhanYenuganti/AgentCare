## ADDED Requirements

### Requirement: Typed API client layer
The dashboard SHALL include a typed API client at `src/api/client.ts` built on RTK Query with all FastAPI endpoints typed from `src/types/index.ts`.

#### Scenario: Patient list endpoint typed
- **WHEN** a component calls the `useGetPatientsQuery` hook
- **THEN** it receives typed data matching the enriched patient list response shape

### Requirement: Polling hooks
Polling hooks SHALL be available for `GET /actions` (polling interval 10s while action feed is mounted) and `GET /actions/{id}/chat-history` (polling interval 3s while chat panel is open).

#### Scenario: Action feed auto-refreshes
- **WHEN** the Action Feed view is mounted
- **THEN** actions are re-fetched every 10 seconds without requiring a manual refresh

### Requirement: Shared type definitions
`src/types/index.ts` SHALL export TypeScript interfaces for all API response shapes: `Patient`, `LifeGraph`, `Action`, `ChatMessage`, `Caregiver`, `OrgProfile`, `SchedulingOption`.

#### Scenario: Types exported
- **WHEN** a component imports from `src/types/index.ts`
- **THEN** all listed interfaces are available with no TypeScript errors
