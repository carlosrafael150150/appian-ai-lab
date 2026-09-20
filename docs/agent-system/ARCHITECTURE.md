# Appian AI Lab - Architecture

## Purpose

Appian AI Lab is a persistent, model-independent platform for coordinating AI agents that work on software projects, with an initial specialization in Appian development.

The platform must preserve projects, conversations, knowledge, task history and execution history independently from any specific LLM, agent framework or compute provider.

## Core Architecture

Appian AI Lab separates four concerns:

### Work Plane

Manages the work being performed.

- Projects
- Repositories
- Workspaces
- Environments
- Tasks
- Conversations
- Messages
- Executions
- Artifacts
- Reviews

### Knowledge Plane

Maintains reusable and project-specific knowledge.

- Global Knowledge
- Project Knowledge
- Knowledge Items
- Knowledge Versions
- Knowledge Evidence
- Knowledge Proposals
- Project Snapshot

### Intelligence Plane

Provides reasoning and agent capabilities.

- Agents
- Models
- Skills
- Playbooks
- MCP Servers

### Control Plane

Coordinates and governs the platform.

- Compute
- Connections
- Secrets
- Policies
- Automations
- Usage
- Budgets
- Analytics
- API

## Separation of Agent, Model and Compute

These concepts are independent.

Agent:
Defines role, behavior, permissions, skills and tools.

Model:
The LLM used for reasoning.

Compute:
The infrastructure where a model is executed.

Example:

Appian Developer
    -> Qwen3-Coder
        -> RunPod RTX 5090

The model or compute resource may be changed without losing task history, project knowledge or conversations.

## Compute Architecture

Compute resources are shared resources and are not permanently bound to agents.

Multiple agents may use the same model endpoint.

Multiple compute resources may exist simultaneously.

The scheduler will eventually decide which available compute resource should execute a task.

Cloud GPU resources should be considered ephemeral.

The persistent state of Appian AI Lab must remain outside ephemeral compute resources.

## Persistent Platform

The Ubuntu Appian AI Lab machine hosts the persistent Control Plane.

Persistent data includes:

- Projects
- Git repositories
- Tasks
- Conversations
- Knowledge
- Skills
- Playbooks
- Configuration
- Execution history
- Usage information

External GPU infrastructure is used only when required.

## Context Architecture

Agent context is progressive rather than static.

The platform must not attempt to load all potentially relevant project knowledge, documentation, repository content or conversation history into the model at the beginning of a Task.

Each Execution starts with an Initial Context containing the minimum information required to begin reasoning, such as:

- system instructions
- agent policy
- Task objective
- relevant conversation state
- Project Snapshot
- relevant confirmed Project Knowledge
- assigned Workspace
- assigned Environment
- available Skills, Playbooks and tools

During execution, the Agent discovers additional context through tools.

This dynamically discovered information forms the Working Context of the Execution.

Examples include:

- project files
- Appian objects
- Appian documentation
- Project Knowledge
- Git changes
- tool results
- test results
- errors

The Agent should retrieve additional information when required rather than receiving all available information in advance.

## Agent Tool Architecture

Tools are divided by responsibility.

### Knowledge Tools

Knowledge Tools answer questions about what the Agent needs to know.

Initial sources include:

- Appian Documentation
- Project Knowledge

Future sources may include MCP servers and other knowledge providers.

### Workspace Tools

Workspace Tools answer questions about the current working state of a Task.

They operate against the Task's assigned Workspace and include capabilities such as:

- search workspace
- read workspace files
- inspect Git status
- inspect Git diff
- inspect the Task change set

The Agent must prefer the current Workspace over stale derived representations when determining the current state of files.

## Git

Git is the source of truth for project files and code history.

Agents must work through isolated workspaces and branches rather than directly modifying shared main branches.

## Appian Specialization

Appian AI Lab initially uses:

- Appian application repositories
- Appian documentation
- Appian-specific knowledge
- Appian development skills
- Appian deployment workflows
- Browser automation where necessary

The architecture must remain extensible to other technologies.
