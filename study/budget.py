"""Shared bounds for recipes, CLI fallback and the complete public run."""
import argparse

DEFAULT_SECONDS = 900
SETUP_SECONDS = 600
MAX_RUN_SECONDS = 3000


def validate_seconds(value):
    if type(value) is not int or not 30 <= value <= 3600:
        raise ValueError("seconds must be an integer in 30..3600")
    return value


def cli_seconds(value):
    try:
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
            raise ValueError("seconds must be an integer in 30..3600")
        return validate_seconds(int(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def recipe_seconds(recipe, fallback=DEFAULT_SECONDS):
    validate_seconds(fallback)
    if "seconds" in recipe and "budget_seconds" in recipe:
        raise ValueError("use budget_seconds or legacy seconds, not both")
    return validate_seconds(recipe.get("budget_seconds", recipe.get("seconds", fallback)))


def validate_run_budget(recipes, fallback=DEFAULT_SECONDS):
    validate_seconds(fallback)
    total = SETUP_SECONDS + sum(recipe_seconds(recipe, fallback) for recipe in recipes)
    if total > MAX_RUN_SECONDS:
        raise ValueError(f"total run budget {total}s exceeds {MAX_RUN_SECONDS}s including {SETUP_SECONDS}s setup")
    return total
