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
