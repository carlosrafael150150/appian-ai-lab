# Appian AI Lab - Knowledge Model

## Principle

Knowledge belongs to Appian AI Lab, not to a particular LLM.

Changing models or compute infrastructure must not cause accumulated knowledge to be lost.

## Global Knowledge

Reusable knowledge that is not specific to one Project.

Examples:

- Appian Documentation
- Appian technical patterns
- General coding practices

## Project Knowledge

Knowledge describing a specific Project.

Examples:

- Functional behavior
- Business rules
- Architecture
- Roles
- Processes
- Integrations
- Conventions
- Constraints
- Known issues
- Decisions
- Lessons learned

## Knowledge Provenance

Knowledge must preserve its origin.

Possible origins include:

- Human
- Repository
- Documentation
- Task
- Agent inference
- MCP
- External system

## Knowledge States

Knowledge must distinguish between certainty levels and lifecycle states.

Examples:

- Observed
- Inferred
- Proposed
- Confirmed
- Rejected
- Superseded

An agent inference must not automatically become confirmed Project Knowledge.

## Evidence

Inferred or discovered knowledge should reference evidence whenever possible.

Examples:

- Git file
- Appian object
- Process Model
- Expression Rule
- Task
- Human confirmation
- Documentation page

## Knowledge Proposals

Tasks may produce Knowledge Proposals.

A proposal may:

- create new knowledge
- modify existing knowledge
- supersede existing knowledge
- identify a contradiction

Proposals may require human review before becoming current knowledge.

## Evolution

Knowledge must preserve history.

When new knowledge replaces existing knowledge, the previous version should normally become Superseded rather than being deleted.

## Current Project Snapshot

Each Project may maintain a derived snapshot representing the current understanding of the Project.

The snapshot may include:

- Purpose
- Functional model
- Architecture
- Business rules
- Current decisions
- Integrations
- Constraints
- Known issues
- Roadmap

The Project Snapshot is derived information.

It is not the primary source of truth.

## Existing Projects

A Project may be created with little or no initial functional knowledge.

A Knowledge Discovery Task may analyze repositories and other available sources to propose an initial functional and technical baseline.

Discovered information must distinguish observations from inferences.

## Current vs Desired Behavior

Project Knowledge should be capable of distinguishing:

- current behavior
- desired behavior
- confirmed functional rule

Existing implementation must not automatically be interpreted as intended functional behavior.
