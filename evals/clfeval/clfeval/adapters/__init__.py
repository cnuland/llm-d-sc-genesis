from .base import ClassifierAdapter
from .huggingface import HuggingFaceAdapter
from .callable_ import CallableAdapter, majority_class_baseline

def __getattr__(name):
    # grpc is an optional dependency; importing the package must not require it
    if name == "LlmDScAdapter":
        from .llmdsc import LlmDScAdapter as _A
        return _A
    raise AttributeError(name)

__all__ = ["ClassifierAdapter","HuggingFaceAdapter","LlmDScAdapter",
           "CallableAdapter","majority_class_baseline"]
