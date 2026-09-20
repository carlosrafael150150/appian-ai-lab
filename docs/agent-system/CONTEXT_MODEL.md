# Appian AI Lab - Context Model

## Purpose

The Context Model defines how information is supplied to Agents during execution.

Context is not equivalent to Knowledge.

Knowledge is durable information maintained by the platform.

Context is the subset of information available to an Agent at a particular moment.

## Initial Context

Each Execution begins with an Initial Context.

It should contain only the information reasonably required to begin working.

Possible components include:

- platform instructions
- Agent Policy
- Task definition
- relevant Conversation state
- Project Snapshot
- relevant confirmed Project Knowledge
- Workspace identity
- Environment identity
- available Skills
- available Playbooks
- available tools

Initial Context should remain compact.

## Working Context

Working Context contains information discovered while the Agent performs the Task.

Examples:

- Appian objects discovered in the Workspace
- files read by the Agent
- Appian documentation retrieved through Knowledge Tools
- Project Knowledge retrieved during research
- Git status
- Git diff
- errors
- test results
- MCP responses
- external system responses

Working Context evolves throughout an Execution.

## Progressive Context Discovery

Agents should not attempt to predict every piece of information that may be required before execution begins.

Instead:

Task
-> Initial Context
-> Reason
-> Identify missing information
-> Retrieve information through tools
-> Add relevant result to Working Context
-> Reason again
-> Act

This loop may repeat many times within the same Task.

## Working Memory

Long-running Executions may discover more information than can reasonably remain in the model context.

The platform may maintain Working Memory representing the currently relevant information.

Working Memory may contain summaries, references and selected source material.

Working Memory is temporary execution state.

It must not automatically become permanent Project Knowledge.

## Context Traceability

The platform should eventually preserve enough information to reconstruct what context influenced an Execution.

This may include references to:

- Project Snapshot version
- Knowledge Items and versions
- Appian documentation pages
- Workspace files
- Conversation messages
- tool results

This supports auditing, debugging and model comparison.

## Knowledge Tools

Knowledge Tools provide information that helps the Agent understand how something works or what is known.

Initial tools include:

- search_appian_docs
- search_project_knowledge

## Workspace Tools

Workspace Tools expose the current operational state of the assigned Task Workspace.

Initial tools include:

- search_workspace
- read_workspace_file
- workspace_status
- workspace_diff
- workspace_changeset

Workspace Tools operate on the current filesystem rather than a persistent repository graph.

## Source Selection

Agents should prefer the most authoritative source appropriate to the question.

Examples:

How does an Appian function work?
-> Appian Documentation

What is the confirmed functional behavior of this Project?
-> Project Knowledge

What files and Appian objects currently exist in this Task?
-> Workspace

What has this Task changed?
-> Workspace Change Set

What happened earlier in this Task?
-> Conversation and Execution history

## Principle

Do not send everything to the model.

Give the Agent enough context to begin, and give it tools to discover the rest.
