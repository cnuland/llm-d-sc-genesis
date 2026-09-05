"""clfeval CLI — the same evaluation code from laptop to production.

    clfeval run      qualify a classifier against a suite
    clfeval compare  champion vs candidate, for CI regression
    clfeval observe  shadow mode against live traffic
    clfeval taxonomy enumerate folds and rank them BEFORE building anything
    clfeval suite    show / validate a suite document

Only the data, the environment and the promotion policy change between stages.
The evaluation logic does not, which is what makes a dev result and a production
result comparable at all.
"""
from .main import main
__all__ = ["main"]
