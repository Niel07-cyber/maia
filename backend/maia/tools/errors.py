"""Errors that tools raise on purpose, meant to be read by the agent."""


class ToolError(Exception):
    """A request the tool refused, with a plain-language reason (unknown part, not enough
    stock, and so on). Anything else that goes wrong is a bug, not a ToolError."""
