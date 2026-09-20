# Appian AI Lab - Execution Model

## Purpose

The Execution Model defines how persistent Tasks become concrete units of work performed by Agents.

A Task represents an objective.

An Execution represents one concrete period of work performed for that Task.

## Task and Execution

A Task may have multiple Executions throughout its lifecycle.

Examples include:

- initial implementation
- continuation after human feedback
- retry after failure
- review
- testing
- work performed by a different Agent

Execution history must remain associated with the Task.

## Single Active Execution

A Task may have only one active Execution at a time.

Therefore, only one Agent is operationally responsible for a Task at any given moment.

This avoids concurrent modification of the same Task Workspace and provides clear ownership of the current work.

## Parallelism

Parallel work is performed through separate Tasks or child Tasks.

Each parallel Task should normally have:

- its own Execution
- its own responsible Agent
- its own Workspace when modifications are possible
- its own Working Context

Task dependencies determine which Tasks may execute simultaneously.

## Agent Changes

A Task is not permanently bound to one Agent.

Different Executions of the same Task may use different Agents.

Example:

Task
- Execution 1: Appian Developer
- Execution 2: Appian Reviewer
- Execution 3: Appian Developer

Only one of these Executions may be active at a time.

## Resource Model

Agent, Model, Model Deployment and Compute are separate concepts.

### Agent

Defines the role, behavior, permissions, Skills and available tools.

### Model

Defines the logical LLM used for reasoning.

A Model is not tied to a specific endpoint or GPU.

### Compute

Defines an infrastructure resource capable of hosting model workloads.

Examples:

- RunPod RTX 5090
- RunPod H100
- local GPU

### Model Deployment

Represents a Model being served on a particular Compute resource.

A Model Deployment may define:

- Model
- Compute
- endpoint
- status
- deployment configuration
- concurrency limit

The same Model may have multiple Deployments.

Example:

Qwen3-Coder
- Qwen3-Coder @ RTX5090-A
- Qwen3-Coder @ RTX5090-B
- Qwen3-Coder @ H100-A

## Task Resource Configuration

A Task may specify:

- Agent
- Model
- optional preferred Compute

The preferred Compute is a scheduling preference.

It is not the actual Compute assignment.

When no preferred Compute is specified, the Scheduler may select any compatible available Model Deployment.

## Scheduler

The Scheduler is responsible for selecting execution capacity.

It considers:

- Task readiness
- Agent assignment
- Model assignment
- Task dependencies
- existing active Execution for the Task
- global concurrency limit
- Compute status
- Compute concurrency limit
- Model Deployment status
- Model Deployment concurrency limit
- optional preferred Compute

## Readiness

A Task is executable only when required conditions are satisfied.

Typical readiness checks include:

- Task is in an executable state
- Workspace exists
- Agent is assigned
- Model is assigned
- no active Execution already exists for the Task
- dependencies are complete
- global scheduler capacity is available
- a compatible online Model Deployment has available capacity

A Task may remain queued while resources are unavailable.

## Compute Selection

The Scheduler resolves the logical Model requested by the Task to a concrete Model Deployment.

Example:

Task
- Agent: Appian Analyst
- Model: Qwen3-Coder
- Preferred Compute: AUTO

Scheduler
- Deployment A: offline
- Deployment B: online and full
- Deployment C: online and available

Execution
- Model: Qwen3-Coder
- Deployment: C
- Compute: RunPod H100

## Execution Resource Snapshot

An Execution records the resources actually used.

This includes:

- Agent
- Model
- Model Deployment
- Compute

This information belongs to the Execution because infrastructure may change after the Task was created.

## Execution Lifecycle

Expected active lifecycle states include:

- preparing
- running
- waiting_for_user
- waiting_for_approval
- reviewing
- testing

Terminal states include:

- completed
- failed
- cancelled

## Execution Events

Important actions performed during an Execution should be recorded as Execution Events.

Examples:

- execution created
- context prepared
- model request
- Knowledge Tool call
- Workspace Tool call
- file modification
- Git operation
- test
- approval request
- error
- completion

## Context

Each Execution begins with Initial Context prepared by the Context Builder.

Additional information is discovered progressively through Knowledge Tools and Workspace Tools.

Dynamic context belongs to the Execution's Working Context.

## Principle

Tasks describe what should be achieved.

Agents describe who performs the work.

Models describe which reasoning model is requested.

Model Deployments describe where a Model is currently served.

Compute describes available infrastructure.

The Scheduler connects these concepts when an Execution begins.
