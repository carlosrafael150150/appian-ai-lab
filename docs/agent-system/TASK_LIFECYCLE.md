# Appian AI Lab - Task Lifecycle

## Definition

A Task represents a persistent objective.

A Task is not equivalent to one prompt or one model execution.

## Creation

A Task may be created:

- manually
- from an external system
- by an automation
- as a child of another Task
- through agent-proposed decomposition

## Task Hierarchy

Large Tasks may contain child Tasks.

Hierarchy represents decomposition of an objective.

## Dependencies

Dependencies represent execution constraints.

Hierarchy and dependency are independent concepts.

Two child Tasks may execute in parallel if no dependency prevents it.

## Conversation

A Task normally maintains an ongoing Conversation.

Follow-up instructions and corrections remain in the same Task unless they represent a genuinely different objective.

## Planning

Complex Tasks may be decomposed into child Tasks.

If an external system already provides an appropriate hierarchy, the existing hierarchy should normally be respected.

## Execution Concurrency

A Task may have only one active Execution at a time.

Parallel work should be represented as separate Tasks or child Tasks with independent Executions.

This preserves clear Agent ownership and prevents concurrent modification of the same Task Workspace.

## Queue

A Task may exist without an assigned Agent or Model.

A Task may also remain queued when no compatible Model Deployment has available Compute capacity.

Compute is assigned when an Execution is scheduled rather than being permanently assigned to the Task.

Such a Task remains queued until the necessary execution resources are available.

## Context Assembly

Before execution, the platform should assemble relevant context from:

- system architecture
- agent policy
- Task objective
- Task conversation
- Project Snapshot
- relevant Project Knowledge
- relevant Global Knowledge
- workspace
- environment
- skills
- playbooks
- MCP capabilities

Only relevant context should be supplied to the model.

## Execution

The selected Agent performs work using the assigned Model and Compute resource.

Executions produce traceable events.

## Human Interaction

A Task may enter a waiting state when clarification or approval is required.

Human corrections continue in the existing Conversation.

## Completion

Before completion, the platform should record:

- result
- artifacts
- Git changes
- tests
- errors
- usage
- relevant knowledge proposals

## Knowledge Extraction

Task completion may trigger analysis for new Project or Global Knowledge.

Knowledge should not be silently promoted to confirmed knowledge unless policy allows it.

## Task Statuses

Expected lifecycle states include:

- queued
- planning
- running
- waiting_for_user
- waiting_for_approval
- reviewing
- testing
- completed
- failed
- cancelled
