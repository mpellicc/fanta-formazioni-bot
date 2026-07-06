"""Shared PTB type aliases."""

from typing import Any

from telegram.ext import Application

# PTB's Application carries six type parameters; jobs and post_init callbacks receive it
# with slightly different (but compatible) parametrizations, so Any keeps signatures sane.
BotApp = Application[Any, Any, Any, Any, Any, Any]
