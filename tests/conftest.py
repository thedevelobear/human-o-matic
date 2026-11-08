import os

from hypothesis import HealthCheck, settings

# Rendering a long song can be slow, so no deadline. CI runs more examples, derandomized.
settings.register_profile("dev", max_examples=50, deadline=None)
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
