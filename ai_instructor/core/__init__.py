"""Algorithmic Instructional Designer — core package."""

from .models import (
    AssessmentResult,
    GenerationConfig,
    LearnerProfile,
    LessonArtifacts,
    PROFILE_DESCRIPTIONS,
    PROFILE_LABELS,
)
from .agents import (
    ArchitectAgent,
    ContentAgent,
    LessonController,
    SimulatedStudentAgent,
)
from .pdf_generator import artifact_to_bytes, artifacts_to_pdf_bytes, artifacts_to_pdfs

__all__ = [
    "AssessmentResult",
    "GenerationConfig",
    "LearnerProfile",
    "LessonArtifacts",
    "PROFILE_DESCRIPTIONS",
    "PROFILE_LABELS",
    "ArchitectAgent",
    "ContentAgent",
    "LessonController",
    "SimulatedStudentAgent",
    "artifact_to_bytes",
    "artifacts_to_pdf_bytes",
    "artifacts_to_pdfs",
]
