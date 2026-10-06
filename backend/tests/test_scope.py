import pytest

from app.modules.assessment.scope import check_scope, starting_difficulty_for_pain


@pytest.mark.parametrize("region", ["lower_back", "shoulder", "knee", "ankle"])
def test_supported_regions_in_scope(region, t):
    assert check_scope(region, 4, [], t).in_scope


@pytest.mark.parametrize("region", ["neck", "hip", "wrist", "other"])
def test_unsupported_region_referred(region, t):
    r = check_scope(region, 3, [], t)
    assert not r.in_scope
    assert r.referral_reasons == [f"unsupported_region:{region}"]
    assert r.starting_difficulty is None


@pytest.mark.parametrize("pain,in_scope", [(6, True), (7, False), (10, False), (0, True)])
def test_pain_boundary(pain, in_scope, t):
    assert check_scope("knee", pain, [], t).in_scope is in_scope


@pytest.mark.parametrize("flag", ["numbness", "swelling", "loss_of_function", "pain_unrelated_to_activity"])
def test_any_red_flag_referred(flag, t):
    r = check_scope("knee", 2, [flag], t)
    assert not r.in_scope and f"red_flag:{flag}" in r.referral_reasons


def test_multiple_reasons_all_reported(t):
    r = check_scope("neck", 9, ["numbness"], t)
    assert len(r.referral_reasons) == 3


@pytest.mark.parametrize("pain,level", [(6, 1), (5, 1), (4, 2), (3, 2), (2, 3), (0, 3)])
def test_starting_difficulty_bands(pain, level, t):
    assert starting_difficulty_for_pain(pain, t) == level
    assert check_scope("shoulder", pain, [], t).starting_difficulty == level
