"""Pure bit-set similarity behavior.

@author cylovelife
"""

import pytest

from aidd_agent.domain.molecules import tanimoto


def test_bit_similarity_is_symmetric_and_uses_union():
    a, b = frozenset([1, 2]), frozenset([2, 3, 4])
    assert tanimoto(a, b) == tanimoto(b, a) == 0.25
    assert tanimoto(a, a) == 1
    assert tanimoto(a, frozenset([7])) == 0
    with pytest.raises(ValueError, match="empty"):
        tanimoto(frozenset(), frozenset())
