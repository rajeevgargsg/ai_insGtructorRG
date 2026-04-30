"""
Data models for the Algorithmic Instructional Designer.
"""

from dataclasses import dataclass, field
from enum import Enum


class LearnerProfile(Enum):
    BEGINNER        = "beginner"
    MSC_STUDENT     = "msc_student"
    PRODUCT_MANAGER = "product_manager"


PROFILE_DESCRIPTIONS = {
    LearnerProfile.BEGINNER: (
        "Undergraduate first AI/CS course. Prior knowledge: basic Python, "
        "high-school algebra, no prior NLP. Session duration ~120 min."
    ),
    LearnerProfile.MSC_STUDENT: (
        "Graduate-level MSc Generative AI intermediate practitioner. "
        "Prior knowledge: linear algebra, neural networks, transformer "
        "architecture, attention mechanisms, tokenisation, LLMs."
    ),
    LearnerProfile.PRODUCT_MANAGER: (
        "Non-technical product manager. Needs conceptual understanding, "
        "business applications, semantic search intuition, awareness of "
        "bias/drift — no mathematical depth required."
    ),
}

PROFILE_LABELS = {
    "Beginner":        LearnerProfile.BEGINNER,
    "MSc Student":     LearnerProfile.MSC_STUDENT,
    "Product Manager": LearnerProfile.PRODUCT_MANAGER,
}


@dataclass
class LessonArtifacts:
    architect_outline:  str = ""
    lesson_plan:        str = ""
    student_handout:    str = ""
    quiz:               str = ""
    teacher_answer_key: str = ""


@dataclass
class AssessmentResult:
    score:        float = 0.0
    passed:       bool  = False
    feedback:     str   = ""
    failed_areas: list  = field(default_factory=list)


@dataclass
class GenerationConfig:
    groq_model:         str            = "llama-3.3-70b-versatile"
    max_tokens:         int            = 2048
    topic_title:        str            = "Embeddings and Vector Databases"
    topic_description:  str            = (
        "How text is encoded as dense numeric vectors, how cosine similarity "
        "works, and how vector databases enable semantic search at scale."
    )
    learner_profile:    LearnerProfile = LearnerProfile.MSC_STUDENT
    pass_threshold:     float          = 0.80
    max_retries:        int            = 2
