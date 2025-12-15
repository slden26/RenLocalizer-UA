import pytest

from src.core import rpyc_reader as rr


def test_fake_pycode_setstate_various_forms():
    states = [
        {"source": "print('hi')", "location": (1, 2), "mode": "exec", "py": 1},
        (None, "print('a')", (10, 20), "eval", 2),
        ({"source": "s1"}, {"location": (3, 4), "mode": "exec"}),
        ["x", "some source", (5, 6), "exec", 3],
    ]

    for st in states:
        pc = rr.FakePyCode()
        # Should not raise
        pc.__setstate__(st)
        # After setting state, attributes should exist and bytecode should be cleared
        assert hasattr(pc, "source")
        assert pc.bytecode is None


def test_fake_argument_and_parameter_info_setstate():
    ai = rr.FakeArgumentInfo()
    ai.__setstate__(({"arguments": [("a", 1)]},))
    assert isinstance(ai.arguments, list)

    pi = rr.FakeParameterInfo()
    pi.__setstate__(({"parameters": [("p", None)]},))
    assert isinstance(pi.parameters, list)
