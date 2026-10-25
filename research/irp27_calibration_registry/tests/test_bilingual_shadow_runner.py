from bilingual_shadow_runner import normalise_answer, state_for


def test_choice_normalization():
    question = {"type": "choice", "criteria": {"a": "A", "b": "B"}}
    distribution, prediction = normalise_answer({"choice": "a", "probabilities": {"a": 2, "b": 1}}, question)
    assert abs(sum(distribution.values()) - 1) < 1e-12
    assert prediction == "a"


def test_state_uses_requested_language():
    pair = {"claim_es": "reclamo", "claim_en": "claim", "passage_es": "pasaje", "passage_en": "passage", "passage_source_id": "S", "domain": "fiscal", "translation_status": "pending"}
    assert "reclamo" in state_for(pair, "es")
    assert "claim" in state_for(pair, "en")
