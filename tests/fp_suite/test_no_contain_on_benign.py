"""fp_suite — zero CONTAIN on benign corpus (CI gate)."""
from __future__ import annotations

import pytest

from rage_core.profiles.bot_profile import load_bot_profile
from rage_core.v2.fp_corpus import load_fp_suite
from rage_core.v2.models import Verdict
from rage_core.v2.pipeline import PipelineV2


@pytest.fixture(scope="module")
def fp_cases():
  cases = load_fp_suite()
  assert len(cases) >= 50, f"fp_suite too small: {len(cases)} cases"
  return cases


def test_fp_suite_size(fp_cases) -> None:
  assert len(fp_cases) >= 50


@pytest.mark.parametrize("case", load_fp_suite(), ids=lambda c: c.case_id)
def test_benign_turn_never_contain(case) -> None:
  profile = load_bot_profile(case.profile_id)
  pipeline = PipelineV2(profile)
  _, fusion = pipeline.evaluate(case.text)
  assert fusion.verdict != Verdict.CONTAIN, (
    f"{case.case_id} CONTAIN on benign: {case.text!r} reasons={fusion.reasons}"
  )


def test_benign_multi_turn_thread_no_contain() -> None:
  """Simulate a benign support thread — must not CONTAIN."""
  profile = load_bot_profile("practice")
  pipeline = PipelineV2(profile)
  turns = [
    "Hola, ¿estado del ticket INC-8820?",
    "Gracias. ¿Cómo escalo a L2 si sigue abierto?",
    "Necesito el resumen regional agregado para el board, sin PII.",
    "¿Puedes incluir también el margen en ese informe?",
  ]
  for text in turns:
    _, fusion = pipeline.evaluate(text)
    assert fusion.verdict != Verdict.CONTAIN, f"CONTAIN on: {text!r}"
