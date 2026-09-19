# Appian AI Lab - Domain Model

## Project

A Project represents a software product, application or initiative.

A Project may contain multiple repositories, tasks, environments and knowledge items.

A Project is not equivalent to a Git repository.

## Repository

A Git repository associated with a Project.

Git contains the authoritative history of project files.

## Workspace

An isolated working copy used by an agent or task.

A Workspace normally corresponds to a Git branch and filesystem location.

Agents should not perform independent tasks in the same writable workspace.

## Environment

Represents external runtime capabilities available to a task.

Examples:

- Appian DEV
- Appian INT
- Browser environment
- Database
- MCP servers
- External APIs

Workspace describes files.

Environment describes systems the task can interact with.

## Task

A persistent work objective.

A Task is not a prompt.

A Task may remain active across many messages, executions, agents and models.

Tasks may have parent/child relationships.

Tasks may also have dependencies independent from their hierarchy.

Tasks may contain references to external systems such as Jira.

## Conversation

A persistent discussion associated with a Task.

Corrections and follow-up instructions normally continue within the same Task conversation.

## Message

An individual contribution to a Conversation.

Messages may originate from users, agents, system components or tools.

## Execution

A concrete attempt to perform work for a Task.

A single user message may result in multiple tool calls and actions within one Execution.

## Execution Event

A traceable action occurring during an Execution.

Examples include:

- LLM call
- file read
- file modification
- Git operation
- MCP call
- browser action
- test
- error

## Artifact

A persistent result produced during a Task.

Examples:

- Git diff
- Appian package
- report
- screenshot
- test result

## Review

A decision point requiring approval, rejection or requested changes.

## Agent

Defines a working role and its behavior.

Examples:

- Appian Developer
- Appian Analyst
- Appian Reviewer
- Testing Agent
- Knowledge Agent

An Agent is not an LLM.

## Model

An LLM used by an Agent.

Models are interchangeable.

## Compute

Infrastructure capable of serving or executing a Model.

Examples:

- RunPod RTX 5090
- H100
- local GPU
- external model API

## Skill

A reusable capability.

Example:

Appian SAIL development.

## Playbook

A defined procedure.

Example:

Deploy PQRDSF to INT.

Skills describe capabilities.

Playbooks describe procedures.

## MCP Server

A capability or context provider exposed through Model Context Protocol.

## Connection

Configuration describing an external system.

Credentials must not be stored directly in the Connection.

## Secret

A protected credential referenced indirectly by other resources.

## Policy

A rule governing what an Agent may perform automatically, what requires approval and what is prohibited.

## Automation

A scheduled or event-driven action.

## Usage

Recorded resource consumption associated with models, compute, tasks and projects.

## Budget

A limit applied to resource consumption.
