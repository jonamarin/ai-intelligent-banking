"""Typed tool implementations (get_customer, create_dispute, freeze_card, ...).

Read tools (read_tools.py) execute directly — low action-risk. Action tools
(action_tools.py) return a ToolProposal only; nothing they touch is ever
written to the database — see base.py's module docstring for why. The LLM
never gets raw database access — only these tools.
"""
