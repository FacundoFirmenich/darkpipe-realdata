from bilingual_shadow_runner import compile_questions_for_laya, normalise_answer, state_for


def test_choice_normalization():
    question = {"type": "choice", "criteria": {"a": "A", "b": "B"}}
    distribution, prediction = normalise_answer({"choice": "a", "probabilities": {"a": 2, "b": 1}}, question)
    assert abs(sum(distribution.values()) - 1) < 1e-12
    assert prediction == "a"


def test_score_compiles_to_ordered_laya_levels_and_back():
    canonical = {
        "strength": {
            "type": "score",
            "instructions": "rate strength",
            "criteria": {"none": "no authority", "context": "context only", "whole": "whole claim"},
        },
        "supports": {
            "type": "noul",
            "instructions": "direct support?",
            "criteria": {"true": "yes", "false": "no"},
        },
    }
    compiled = compile_questions_for_laya(canonical)
    assert compiled["strength"]["criteria"] == [
        "none: no authority",
        "context: context only",
        "whole: whole claim",
    ]
    assert "criteria" not in compiled["supports"]
    distribution, prediction = normalise_answer(
        {"type": "score", "score": 1.2, "probabilities": {"0": 0.1, "1": 0.7, "2": 0.2}},
        canonical["strength"],
    )
    assert distribution == {"none": 0.1, "context": 0.7, "whole": 0.2}
    assert prediction == "context"


def test_state_uses_requested_language():
    pair = {"claim_es": "reclamo", "claim_en": "claim", "passage_es": "pasaje", "passage_en": "passage", "passage_source_id": "S", "domain": "fiscal", "translation_status": "pending"}
    assert "reclamo" in state_for(pair, "es")
    assert "claim" in state_for(pair, "en")
