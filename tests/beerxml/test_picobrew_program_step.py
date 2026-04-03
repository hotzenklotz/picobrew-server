import pytest

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep


def make_step(name: str, temp: float, time: float, location: str, drain: float) -> PicoBrewProgramStep:
    step = PicoBrewProgramStep()
    step.name = name
    step.temp = temp
    step.time = time
    step.location = location
    step.drain = drain
    return step


class TestSerialize:
    def test_passthrough_location(self):
        step = make_step("Heat to Temp", 152.0, 0.0, "PassThrough", 0.0)
        assert step.serialize() == "Heat to Temp,152,0,0,0"

    def test_mash_location(self):
        step = make_step("Mash", 67.0, 90.0, "Mash", 8.0)
        assert step.serialize() == "Mash,67,90,1,8"

    def test_adjunct1_location(self):
        step = make_step("Boil", 97.0, 60.0, "Adjunct1", 5.0)
        assert step.serialize() == "Boil,97,60,2,5"

    def test_adjunct2_location(self):
        step = make_step("Hop 2", 97.0, 10.0, "Adjunct2", 0.0)
        assert step.serialize() == "Hop 2,97,10,3,0"

    def test_adjunct3_location(self):
        step = make_step("Hop 3", 97.0, 2.0, "Adjunct3", 0.0)
        assert step.serialize() == "Hop 3,97,2,4,0"

    def test_adjunct4_location(self):
        step = make_step("Hop 4", 97.0, 5.0, "Adjunct4", 0.0)
        assert step.serialize() == "Hop 4,97,5,5,0"

    def test_pause_location(self):
        step = make_step("Connect Chiller", 18.0, 0.0, "Pause", 0.0)
        assert step.serialize() == "Connect Chiller,18,0,6,0"

    def test_float_values_are_truncated_not_rounded(self):
        # int() truncates towards zero, not rounds
        step = make_step("Step", 67.9, 90.7, "Mash", 8.9)
        assert step.serialize() == "Step,67,90,1,8"

    def test_name_with_ellipsis(self):
        step = make_step("Heat to Single S...", 67.0, 0.0, "PassThrough", 0.0)
        assert step.serialize() == "Heat to Single S...,67,0,0,0"


class TestSerializeMissingFieldsRaise:
    def test_missing_name_raises(self):
        step = make_step("x", 67.0, 0.0, "Mash", 0.0)
        step.name = None
        with pytest.raises(AssertionError):
            step.serialize()

    def test_missing_temp_raises(self):
        step = make_step("x", 67.0, 0.0, "Mash", 0.0)
        step.temp = None
        with pytest.raises(AssertionError):
            step.serialize()

    def test_missing_time_raises(self):
        step = make_step("x", 67.0, 0.0, "Mash", 0.0)
        step.time = None
        with pytest.raises(AssertionError):
            step.serialize()

    def test_missing_location_raises(self):
        step = make_step("x", 67.0, 0.0, "Mash", 0.0)
        step.location = None
        with pytest.raises(AssertionError):
            step.serialize()

    def test_missing_drain_raises(self):
        step = make_step("x", 67.0, 0.0, "Mash", 0.0)
        step.drain = None
        with pytest.raises(AssertionError):
            step.serialize()

    def test_all_fields_none_on_fresh_instance_raises(self):
        step = PicoBrewProgramStep()
        with pytest.raises(AssertionError):
            step.serialize()
