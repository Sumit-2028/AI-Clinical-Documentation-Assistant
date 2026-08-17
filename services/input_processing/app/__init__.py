from pathlib import Path

# Keep the production layout under services/input-processing while allowing
# normal imports from orchestration code and tests.
__path__ = [
    str(Path(__file__).resolve().parents[2] / "input-processing" / "app")
]
