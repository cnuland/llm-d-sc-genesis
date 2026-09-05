"""clfeval — classifier qualification framework for llm-d-sc.

Not an eval library. A qualification system: it answers whether a classifier
revision is trustworthy enough for THIS taxonomy, THIS workload, THIS traffic,
THIS runtime and THIS environment, and produces the evidence that proves it.

Five evaluation planes, one contract, one report, from laptop to production.
"""
from .specs import ClassifierTaskSpec, DatasetSpec, Gate, AbstentionPolicy
from .adapters import (ClassifierAdapter, HuggingFaceAdapter, LlmDScAdapter,
                       CallableAdapter, majority_class_baseline)
from .runner import qualify, load_rows, PLANES
from .reports import QualificationReport
from .sinks import MlflowLedger
from .controls import DEFAULT_CONTROLS, Status
from .traffic import ShadowRun, ShadowConfig
__all__ = ["ClassifierTaskSpec","DatasetSpec","Gate","AbstentionPolicy",
           "ClassifierAdapter","HuggingFaceAdapter","LlmDScAdapter",
           "CallableAdapter","majority_class_baseline","qualify","load_rows",
           "PLANES","QualificationReport","MlflowLedger","DEFAULT_CONTROLS",
           "Status","ShadowRun","ShadowConfig"]
