"""Business actions the agent can take. Each tool validates its input, works through the
database, and raises ToolError with a message the agent can relay to the technician.

Tools never commit: the caller owns the transaction, so a multi-step action either fully
happens or not at all."""
