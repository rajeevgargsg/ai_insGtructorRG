"""
Multi-agent instructional design pipeline.

Agents: ArchitectAgent, ContentAgent, SimulatedStudentAgent, LessonController

Prompts are intentionally SHORT to stay within Groq free-tier token limits.
Source text is truncated to 2500 chars per call.
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

SRC_LIMIT  = 2500   # max source chars sent per prompt
BLU_LIMIT  = 1000   # max blueprint chars sent to content agents


# ---------------------------------------------------------------------------
# Architect Agent
# ---------------------------------------------------------------------------

class ArchitectAgent:
    SYSTEM = (
        "You are an expert instructional designer. "
        "Return ONLY valid JSON -- no markdown, no extra text."
    )

    def __init__(self, client, cfg):
        self.client = client
        self.cfg    = cfg

    def create_outline(self, source: str, revision: Optional[str] = None) -> str:
        rev = f"\nREVISION NEEDED:\n{revision[:600]}\n" if revision else ""
        profile_desc = PROFILE_DESCRIPTIONS.get(self.cfg.learner_profile, "")
        prompt = f"""{rev}
Create a lesson blueprint JSON for:
  Topic  : {self.cfg.topic_title}
  Level  : {self.cfg.learner_profile.value} -- {profile_desc}
  Source : {source[:SRC_LIMIT]}

Return ONLY this JSON (no extra text):
{{
  "learning_objectives": ["obj1","obj2","obj3"],
  "key_concepts": ["concept1","concept2","concept3","concept4"],
  "prerequisite_knowledge": ["prereq1","prereq2"],
  "gagnes_events": {{
    "gain_attention":"...",
    "objectives":"...",
    "prior_recall":"...",
    "content":"...",
    "guidance":"...",
    "practice":"...",
    "feedback":"...",
    "assessment":"...",
    "retention":"..."
  }},
  "merrills": {{
    "problem":"...",
    "activation":"...",
    "demonstration":"...",
    "application":"...",
    "integration":"..."
  }},
  "pass_threshold": {self.cfg.pass_threshold},
  "total_marks": 20
}}"""
        logger.info("[Architect] Creating outline ...")
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)


# ---------------------------------------------------------------------------
# Content Agent
# ---------------------------------------------------------------------------

class ContentAgent:
    SYSTEM = (
        "You are an expert instructional content writer. "
        "Write clear, professional lesson materials in markdown."
    )

    def __init__(self, client, cfg):
        self.client = client
        self.cfg    = cfg

    def generate_lesson_plan(self, outline: str, source: str) -> str:
        logger.info("[Content] Lesson plan ...")
        prompt = f"""Write a TEACHER LESSON PLAN in markdown.

Blueprint: {outline[:BLU_LIMIT]}
Source: {source[:SRC_LIMIT]}
Level: {self.cfg.learner_profile.value}
Topic: {self.cfg.topic_title}

Sections:
# Lesson Plan -- {self.cfg.topic_title}
## Session Overview (level, duration, materials)
## Learning Objectives (3-4 bullet points)
## Lesson Flow (Gagne's 9 events as a table: Time | Event | Teacher | Student)
## Key Concepts (3 concepts with explanations from source)
## Worked Example (1 step-by-step example)
## Discussion Questions (3 questions)
## Common Misconceptions"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_student_handout(self, outline: str, source: str) -> str:
        logger.info("[Content] Student handout ...")
        prompt = f"""Write a PRE-CLASS STUDENT HANDOUT in markdown.

Blueprint: {outline[:BLU_LIMIT]}
Source: {source[:SRC_LIMIT]}
Level: {self.cfg.learner_profile.value}
Topic: {self.cfg.topic_title}

Sections:
# Student Handout -- {self.cfg.topic_title}
## Why This Matters (1 paragraph)
## Key Vocabulary (5 terms with definitions)
## Core Concepts (3 concepts, plain language)
## Analogy (1 real-world analogy)
## Warm-Up Questions (3 questions to think about before class)"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_quiz(self, outline: str, lesson_plan: str) -> str:
        logger.info("[Content] Quiz ...")
        prompt = f"""Write a STUDENT QUIZ in markdown.

Blueprint: {outline[:BLU_LIMIT]}
Topic: {self.cfg.topic_title}
Level: {self.cfg.learner_profile.value}
Pass mark: {int(self.cfg.pass_threshold * 20)}/20

RULES:
- Section A: exactly 5 MCQ questions (2 pts each = 10 pts)
  Mark correct answer with [CORRECT]:
  Q1. Question?
  a) Wrong
  b) Right [CORRECT]
  c) Wrong
  d) Wrong
- Section B: exactly 2 short-answer questions (3 pts each = 6 pts)
- Section C: 1 application task (4 pts)
- Total: 20 pts. Pass: {int(self.cfg.pass_threshold * 20)}/20"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)

    def generate_answer_key(self, quiz: str, outline: str) -> str:
        logger.info("[Content] Answer key ...")
        prompt = f"""Write a TEACHER ANSWER KEY in markdown for this quiz.

Quiz: {quiz[:2000]}

Sections:
# Teacher Answer Key -- {self.cfg.topic_title}
## Section A: MCQ Answers (letter + 1-sentence explanation each)
## Section B: Model Short Answers (with 3/2/1/0 rubric)
## Section C: Model Application Answer (with rubric)
## Score Guide: 18-20 Excellent | 15-17 Good | 12-14 Satisfactory | <12 Reteach"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM)


# ---------------------------------------------------------------------------
# Simulated Student Agent
# ---------------------------------------------------------------------------

class SimulatedStudentAgent:
    SYSTEM_STUDENT = (
        "You are a student. Answer only from what you studied. "
        "Return ONLY valid JSON, no markdown."
    )
    SYSTEM_GRADER = (
        "You are a quiz grader. "
        "Return ONLY valid JSON, no markdown."
    )

    def __init__(self, client, cfg):
        self.client = client
        self.cfg    = cfg

    def attempt_quiz(self, quiz: str, handout: str) -> AssessmentResult:
        logger.info("[Student] Attempting quiz ...")
        student_json = self._answer(quiz, handout)
        return self._grade(student_json, quiz)

    def _answer(self, quiz: str, handout: str) -> str:
        prompt = f"""You are a {self.cfg.learner_profile.value} student.
Study material: {handout[:2000]}
Quiz: {quiz[:1500]}

Return ONLY this JSON:
{{
  "section_a": ["b","a","c","d","b"],
  "section_b": ["answer1","answer2"],
  "section_c": "application answer",
  "confused_topics": ["topic if any"],
  "content_gaps": ["gap if any"],
  "suggestions": ["improvement if any"]
}}"""
        return groq_chat(self.client, self.cfg, prompt, self.SYSTEM_STUDENT)

    def _grade(self, student_json: str, quiz: str) -> AssessmentResult:
        logger.info("[Student] Grading ...")
        prompt = f"""Grade this student's quiz answers.

Student answers (JSON): {student_json}
Quiz (with [CORRECT] markers): {quiz[:2000]}

Scoring: Section A = 2pts per correct MCQ (match [CORRECT]). Section B = 0-3pts each. Section C = 0-4pts.

Return ONLY this JSON:
{{
  "section_a_score": 6,
  "section_b_score": 4,
  "section_c_score": 3,
  "total": 13,
  "max": 20,
  "pct": 65.0,
  "passed": false,
  "failed_areas": ["area1"],
  "feedback": "one paragraph summary"
}}"""
        raw          = groq_chat(self.client, self.cfg, prompt, self.SYSTEM_GRADER)
        grade        = extract_json(raw)
        student_data = extract_json(student_json)

        pct    = float(grade.get("pct", 0))
        passed = pct / 100.0 >= self.cfg.pass_threshold

        fb_lines = [
            f"Score: {pct:.1f}%  ({grade.get('total','?')}/{grade.get('max',20)})",
            f"Passed: {passed}  | Threshold: {int(self.cfg.pass_threshold*100)}%",
            "",
            grade.get("feedback", ""),
            "",
            "Gaps: " + ", ".join(student_data.get("content_gaps", [])),
            "Suggestions: " + ", ".join(student_data.get("suggestions", [])),
        ]

        return AssessmentResult(
            score=pct / 100.0,
            passed=passed,
            feedback="\n".join(fb_lines),
            failed_areas=grade.get("failed_areas", []),
        )


# ---------------------------------------------------------------------------
# Lesson Controller
# ---------------------------------------------------------------------------

class LessonController:
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
        def _log(msg):
            logger.info(msg)
            if progress_cb:
                progress_cb(msg)

        artifacts     = LessonArtifacts()
        iteration_log = []
        revision_fb   = None

        for attempt in range(self.cfg.max_retries + 1):
            entry = {"attempt": attempt + 1}
            t0    = time.time()

            _log(f"ARCHITECT_START|Attempt {attempt+1}: building blueprint ...")
            artifacts.architect_outline = self.architect.create_outline(
                source_content, revision_fb)
            _log("ARCHITECT_DONE|Blueprint ready")

            _log("CONTENT_LP_START|Writing lesson plan ...")
            artifacts.lesson_plan = self.content.generate_lesson_plan(
                artifacts.architect_outline, source_content)
            _log("CONTENT_LP_DONE|Lesson plan done")

            _log("CONTENT_SH_START|Writing student handout ...")
            artifacts.student_handout = self.content.generate_student_handout(
                artifacts.architect_outline, source_content)
            _log("CONTENT_SH_DONE|Handout done")

            _log("CONTENT_QZ_START|Writing quiz ...")
            artifacts.quiz = self.content.generate_quiz(
                artifacts.architect_outline, artifacts.lesson_plan)
            _log("CONTENT_QZ_DONE|Quiz done")

            _log("CONTENT_AK_START|Writing answer key ...")
            artifacts.teacher_answer_key = self.content.generate_answer_key(
                artifacts.quiz, artifacts.architect_outline)
            _log("CONTENT_AK_DONE|Answer key done")

            _log("STUDENT_START|Simulated student taking quiz ...")
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
                _log(f"PIPELINE_PASS|Passed -- {result.score*100:.1f}%")
                break
            elif attempt < self.cfg.max_retries:
                _log(f"PIPELINE_RETRY|Score {result.score*100:.1f}% below threshold -- revising ...")
                revision_fb = result.feedback
            else:
                _log(f"PIPELINE_MAXRETRY|Max retries reached. Final: {result.score*100:.1f}%")

        return artifacts, iteration_log
