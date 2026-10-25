from shadow_benchmark import ece, stability


def test_ece_perfect():
    assert ece([1, 1], [1, 1]) == 0


def test_stability():
    base=[{'id':'x','question_id':'q','predicted':'a','correct':1}]
    variant=[{'id':'x','question_id':'q','predicted':'b','correct':0}]
    result=stability(base,variant,'flip')
    assert result['harmful_flips']==1
    assert result['prediction_stability']==0
