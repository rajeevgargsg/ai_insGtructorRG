"""
Multi-agent instructional design pipeline.

Agents
------
ArchitectAgent        — maps raw docs → JSON lesson blueprint
ContentAgent          — generates lesson plan / handout / quiz / answer key
SimulatedStudentAgent — attempts the quiz; drives the revision loop
LessonController      — orchestrates the full pipeline
"""

import logging
import time
from typing import Callable, Optional

from groq import Groq

from .models import (
    AssessmentResult,
    GenerationConfig,
    LessonArtifacts,
    PROFILE_DESCRIPTIONS,
)
from .utils import extract_json, groq_chat

logger = logging.getLogger("aid.agents")


# ─────────────────────────────────────────────────────────────────────────────
# Architect Agent
# ─────────────────────────────────────────────────────────────────────────────

class ArchitectAgent:
    """
    Maps raw source documentation to Gagne's Nine Events of Instruction
    and Merrill's First Principles. Returns a JSON lesson blueprint.
    """

    GAGNES_EVENTS = [
        "1. Gain Attention", "2. Inform Learners of Objectives",
        "3. Stimulate Recall of Prior Learning", "4. Present the Content",
        "5. Provide Learning Guidance", "6. Elicit Performance (Practice)",
        "7. Provide Feedback", "8. Assess Performance",
        "9. Enhance Retention and Transfer",
    ]

    MERRILLS_PRINCIPLES = [
        "Problem-Centred Learning", "Activation of Prior Knowledge",
        "Demonstration of Skills", "Application by Learners",
        "Integration into Real World",
    ]

    SYSTEM = (
        "You are an expert instructional designer. "
        "Produce precise, structured JSON lesson blueprints. "
        "Return ONLY valid JSON — no markdown fences, no preamble."
    )

    def __init__(self, client: Groq, cfg: GenerationConfig):
        self.client = client
        self.cfg    = cfg

    def create_outline(self, source: str,
                       revision_feedback: Optional[str] = None) -> str:
        revision_block = ""
        if revision_feedback:
            revision_block = (
                "\n=== REVISION MODE ===\n"
                "Previous lesson FAILED quality assessment.\n"
                f"Failure Analysis:\n{revision_feedback}\n"
                "Revised outline MUST address every gap above.\n"
                "===================\n"
            )

        profile_desc = PROFILE_DESCRIPTIONS.get(self.cfg.learner_profile, "")

        prompt = f"""{revision_block}
Analyse the source documentation and output a lesson blueprint as valid JSON
using BOTH frameworks below.

Gagne's Nine Events : {' | '.join(self.GAGNES_EVENTS)}
Merrill's Principles: {' | '.join(self.MERRILLS_PRINCIPLES)}

Session Context
  Learner Profile : {self.cfg.learner_profile.value}
  Profile Details : {profile_desc}
  Topic           : {self.cfg.topic_title}
  Description     : {self.cfg.topic_description}
  Pass Threshold  : {int(self.cfg.pass_threshold * 100)}%

Source Documentation (first 5000 chars):
{source[:5000]}

Return ONLY this JSON — no extra text:
{{
  "topic": "...",
  "learner_profile": "...",
  "estimated_duration_minutes": 90,
  "learning_objectives": ["SMART objective 1", "..."],
  "prerequisite_knowledge": ["...", "..."],
  "key_concepts": ["concept 1", "..."],
  "difficulty_calibration": "brief note",
  "gagnes_events": {{
    "gain_attention": "...", "objectives_statement": "...",
    "prior_recall": "...", "content_presentation": "...",
    "learning_guidance": "...", "practice_elicitation": "...",
    "feedback_strategy": "...", "assessment_design": "...",
    "retention_transfer": "..."
  }},
  "merrills_alignment": {{
    "problem_scenario": "...", "activation_strategy": "...",
    "demonstration_approach": "...",
    "application_exercises": ["ex 1", "ex 2"],
    "integration_activity": "..."
  }},
  "assessment_criteria": {{
    "pass_threshold": {self.cfg.pass_threshold},
    "total_marks": 30,
    "section_breakdown": {{"multiple_choice": 10, "short_answer": 12, "application": 8}},
    "bloom_levels_targeted": ["remember", "understand", "apply", "analyse"]
  }}
}}"""

        logger.info("[Architect] Creating outline (revision=%s)", bool(revision_feedback))
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)


# ─────────────────────────────────────────────────────────────────────────────
# Content Agent
# ─────────────────────────────────────────────────────────────────────────────

class ContentAgent:
    """
    Generates four lesson artefacts from the Architect's blueprint:
    lesson plan, student handout, quiz, teacher answer key.
    """

    SYSTEM = (
        "You are an expert instructional content writer. "
        "Produce clear, professional, pedagogically sound lesson materials "
        "formatted with markdown headings and bullet points."
    )

    def __init__(self, client: Groq, cfg: GenerationConfig):
        self.client = client
        self.cfg    = cfg

    def generate_lesson_plan(self, outline: str, source: str) -> str:
        logger.info("[Content] Generating lesson plan …")
        prompt = f"""Create a TEACHER LESSON PLAN using the blueprint and source below.

Blueprint JSON:
{outline[:1500]}

Source material (first 4000 chars):
{source[:4000]}

Structure:
# LESSON PLAN — {self.cfg.topic_title}
## Session Overview (topic, level, duration, materials needed)
## SMART Learning Objectives (4–5 objectives)
## Minute-by-Minute Lesson Flow (Gagne's 9 Events as a markdown table)
## Core Concepts with Explanations (minimum 3 concepts grounded in source)
## Worked Examples (minimum 2 step-by-step examples)
## Guided Discussion Questions (4 questions with facilitation tips)
## Common Misconceptions to Address
## Differentiation for {self.cfg.learner_profile.value}

Write at least 550 words. Use markdown headings and tables."""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_student_handout(self, outline: str, source: str) -> str:
        logger.info("[Content] Generating student handout …")
        prompt = f"""Create a PRE-CLASS STUDENT HANDOUT for a {self.cfg.learner_profile.value}.

Blueprint JSON:
{outline[:1200]}

Source material (first 4000 chars):
{source[:4000]}

Structure:
# Student Handout — {self.cfg.topic_title}
## Why This Matters (1-paragraph context and motivation)
## Key Vocabulary (6–8 terms with clear definitions)
## Core Concepts Explained (clear prose, minimum 3 concepts)
## Mental Models & Analogies (2 real-world analogies)
## Visual Representation (ASCII diagram or structured text illustration)
## Pre-Class Warm-Up Questions (3 priming questions)
## Further Reading

Write at least 500 words. Keep tone engaging and student-friendly."""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_quiz(self, outline: str, lesson_plan: str) -> str:
        logger.info("[Content] Generating quiz …")
        prompt = f"""Create a STUDENT QUIZ for level: {self.cfg.learner_profile.value}.

Blueprint JSON:
{outline[:1200]}

Lesson plan excerpt (first 2000 chars):
{lesson_plan[:2000]}

STRICT FORMATTING RULES:
Section A: EXACTLY 10 Multiple Choice questions.
  Mark the correct option with [CORRECT]:
  Q1. Question text?
  a) Wrong option
  b) Correct option [CORRECT]
  c) Wrong option
  d) Wrong option

Section B: EXACTLY 4 Short Answer questions (3 pts each = 12 pts)
Section C: 1 Application Exercise (8 pts)

End with:
| Section | Items | Marks |
|---------|-------|-------|
| A — Multiple Choice | 10 | 10 |
| B — Short Answer | 4 | 12 |
| C — Application | 1 | 8 |
| **Total** | | **30** |
Pass mark: {int(self.cfg.pass_threshold * 30)}/30 ({int(self.cfg.pass_threshold * 100)}%)

Topic: {self.cfg.topic_title}. Mix Bloom's levels: Remember to Analyse."""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_answer_key(self, quiz: str, outline: str, source: str) -> str:
        logger.info("[Content] Generating teacher answer key …")
        prompt = f"""Create a TEACHER ANSWER KEY for the quiz below.

Quiz:
{quiz[:2500]}

Source material (first 2000 chars):
{source[:2000]}

Structure:
# Teacher Answer Key — {self.cfg.topic_title}
## Section A: MCQ Answers
  For each Q: correct letter + WHY correct + why distractors are wrong.
## Section B: Model Short Answers
  For each Q: full model answer with 3pt/2pt/1pt/0pt rubric.
## Section C: Model Application Solution
  Step-by-step solution with marking rubric.
## Score Interpretation
  | 90-100% Excellent | 80-89% Good | 70-79% Satisfactory | <70% Reteach |
## Teaching Notes (common errors + discussion facilitation tips)"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)


# ─────────────────────────────────────────────────────────────────────────────
# Simulated Student Agent
# ─────────────────────────────────────────────────────────────────────────────

class SimulatedStudentAgent:
    """
    Simulates a learner of the configured profile attempting the quiz.
    Uses a separate context (only sees what a real student would see).
    Returns a structured failure analysis when below the pass threshold.
    """

    SYSTEM_STUDENT = (
        "You are a realistic student. Answer only from what you studied. "
        "If something is unclear or missing, show that uncertainty. "
        "Return ONLY valid JSON, no markdown fences."
    )

    SYSTEM_GRADER = (
        "You are an impartial quiz grader. "
        "Grade objectively based on [CORRECT] markers and rubrics provided. "
        "Return ONLY valid JSON, no markdown fences."
    )

    def __init__(self, client: Groq, cfg: GenerationConfig):
        self.client = client
        self.cfg    = cfg

    def attempt_quiz(self, quiz: str, handout: str) -> AssessmentResult:
        logger.info("[Student] Simulated student attempting quiz …")
        student_json_text = self._answer(quiz, handout)
        return self._grade(student_json_text, quiz)

    def _answer(self, quiz: str, handout: str) -> str:
        prompt = f"""You are a {self.cfg.learner_profile.value} student.
You have studied ONLY this material:
{handout[:3000]}

Attempt every question honestly. If something was unclear in your study
material, note it. QUIZ:
{quiz[:2500]}

Return ONLY this JSON:
{{
  "section_a_answers": ["b","c","a","d","b","c","a","d","b","c"],
  "section_b_answers": ["answer1","answer2","answer3","answer4"],
  "section_c_answer": "full application answer here",
  "self_assessment": {{
    "confident_topics": ["topic A"],
    "confused_topics":  ["topic X"],
    "unclear_questions": ["Q3 unclear because ..."],
    "estimated_score_pct": 72
  }},
  "failure_analysis": {{
    "content_gaps": ["gap 1","gap 2"],
    "confusing_sections": ["section X was hard because ..."],
    "missing_examples": ["an example showing ... would help"],
    "suggestions_for_improvement": ["specific improvement 1"]
  }}
}}"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM_STUDENT)

    def _grade(self, student_json_text: str, quiz: str) -> AssessmentResult:
        logger.info("[Student] Grading …")
        grade_prompt = f"""Grade the student's answers against the quiz.

STUDENT ANSWERS (JSON):
{student_json_text}

QUIZ (check [CORRECT] markers for MCQ):
{quiz[:2500]}

Scoring:
  Section A: 1 pt per answer matching [CORRECT] marker.
  Section B: 0-3 pts per question (accuracy + depth).
  Section C: 0-8 pts (correctness of approach).

Return ONLY this JSON:
{{
  "section_a_score": 7,
  "section_b_score": 9,
  "section_c_score": 6,
  "total_score": 22,
  "max_score": 30,
  "percentage": 73.3,
  "passed": false,
  "failed_areas": ["Q3 incorrect","B2 incomplete"],
  "grader_feedback": "paragraph on strengths and weaknesses"
}}"""

        raw          = groq_chat(self.client, self.cfg, grade_prompt, self.SYSTEM_GRADER)
        grade_data   = extract_json(raw)
        student_data = extract_json(student_json_text)

        percentage = float(grade_data.get("percentage", 0))
        score_frac = percentage / 100.0
        passed     = score_frac >= self.cfg.pass_threshold

        fa = student_data.get("failure_analysis", {})
        feedback_parts = [
            f"Score: {percentage:.1f}%  "
            f"({grade_data.get('total_score','?')}/{grade_data.get('max_score',30)})",
            f"Passed: {passed}  |  Threshold: {int(self.cfg.pass_threshold*100)}%",
            "",
            "Grader Feedback:",
            grade_data.get("grader_feedback", "N/A"),
            "",
            "Content Gaps:",
            *[f"  • {g}" for g in fa.get("content_gaps", [])],
            "Confusing Sections:",
            *[f"  • {s}" for s in fa.get("confusing_sections", [])],
            "Missing Examples:",
            *[f"  • {e}" for e in fa.get("missing_examples", [])],
            "Revision Suggestions:",
            *[f"  • {s}" for s in fa.get("suggestions_for_improvement", [])],
        ]

        return AssessmentResult(
            score=score_frac,
            passed=passed,
            feedback="\n".join(feedback_parts),
            failed_areas=grade_data.get("failed_areas", []),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Lesson Controller
# ─────────────────────────────────────────────────────────────────────────────

class LessonController:
    """
    Orchestrates the full multi-agent pipeline with optional revision loop.

    Flow:
        Source ──► Architect ──► ContentAgent ──► SimulatedStudent
                       ▲                                │
                       │    (if score < threshold)      │
                       └────── revision feedback ───────┘
    """

    def __init__(self, api_key: str, cfg: GenerationConfig):
        self.client    = Groq(api_key=api_key)
        self.cfg       = cfg
        self.architect = ArchitectAgent(self.client, cfg)
        self.content   = ContentAgent(self.client, cfg)
        self.student   = SimulatedStudentAgent(self.client, cfg)

    def run(
        self,
        source_content: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> tuple:
        """
        Execute the pipeline.
        Returns (LessonArtifacts, list[dict] iteration_log).
        """
        def _log(msg: str):
            logger.info(msg)
            if progress_cb:
                progress_cb(msg)

        artifacts     = LessonArtifacts()
        iteration_log = []
        revision_fb   = None

        for attempt in range(self.cfg.max_retries + 1):
            entry = {"attempt": attempt + 1}
            t0    = time.time()

            _log(f"ARCHITECT_START|Attempt {attempt+1}: Creating lesson blueprint …")
            artifacts.architect_outline = self.architect.create_outline(
                source_content, revision_fb)
            _log(f"ARCHITECT_DONE|Blueprint ready")

            _log(f"CONTENT_LP_START|Generating lesson plan …")
            artifacts.lesson_plan = self.content.generate_lesson_plan(
                artifacts.architect_outline, source_content)
            _log(f"CONTENT_LP_DONE|Lesson plan complete")

            _log(f"CONTENT_SH_START|Generating student handout …")
            artifacts.student_handout = self.content.generate_student_handout(
                artifacts.architect_outline, source_content)
            _log(f"CONTENT_SH_DONE|Handout complete")

            _log(f"CONTENT_QZ_START|Generating quiz …")
            artifacts.quiz = self.content.generate_quiz(
                artifacts.architect_outline, artifacts.lesson_plan)
            _log(f"CONTENT_QZ_DONE|Quiz complete")

            _log(f"CONTENT_AK_START|Generating answer key …")
            artifacts.teacher_answer_key = self.content.generate_answer_key(
                artifacts.quiz, artifacts.architect_outline, source_content)
            _log(f"CONTENT_AK_DONE|Answer key complete")

            _log(f"STUDENT_START|Simulated student taking quiz …")
            result = self.student.attempt_quiz(
                artifacts.quiz, artifacts.student_handout)
            _log(f"STUDENT_DONE|Score: {result.score*100:.1f}%")

            entry.update({
                "score_pct":     round(result.score * 100, 1),
                "passed":        result.passed,
                "feedback":      result.feedback,
                "total_seconds": round(time.time() - t0, 1),
            })
            iteration_log.append(entry)

            if result.passed:
                _log(f"PIPELINE_PASS|Passed — {result.score*100:.1f}% >= "
                     f"{self.cfg.pass_threshold*100:.0f}%")
                break
            elif attempt < self.cfg.max_retries:
                _log(f"PIPELINE_RETRY|Score {result.score*100:.1f}% below threshold — "
                     f"revision {attempt+1}/{self.cfg.max_retries} …")
                revision_fb = result.feedback
            else:
                _log(f"PIPELINE_MAXRETRY|Max retries reached. "
                     f"Final: {result.score*100:.1f}%")

        return artifacts, iteration_log
