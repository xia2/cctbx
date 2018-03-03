from __future__ import absolute_import, division, print_function

import fable.equivalence
import pytest
import random

def fem_array_alignment(members_size, i_mbr_byte_offset_pairs):
  fueaa = fable.fem_utils_equivalence_array_alignment(
    members_size=members_size)
  for p0, p1 in i_mbr_byte_offset_pairs:
    i0, a0 = p0
    i1, a1 = p1
    fueaa.add_anchor(i0=i0, a0=a0, i1=i1, a1=a1)
  return fueaa.infer_diffs0_from_diff_matrix()

def check_array_alignment(array_alignment, n, pairs):
  diffs0 = array_alignment(
    members_size=n,
    i_mbr_byte_offset_pairs=pairs)
  for p0, p1 in pairs:
    i0, a0 = p0
    i1, a1 = p1
    assert diffs0[i1] - diffs0[i0] == a0 - a1
  return diffs0

@pytest.mark.parametrize("array_alignment", [
    fable.equivalence.array_alignment,
    pytest.param(fem_array_alignment,
        marks=pytest.mark.skipif(not fable.ext,
                                 reason="test depends on C++ library")),
])
@pytest.mark.parametrize("n", range(2,6))
def test_given_members_size(array_alignment, n, n_trials=10):
  random.seed(0)
  i_mbrs = range(n)
  for i_trial in xrange(n_trials):
    random.shuffle(i_mbrs)
    #
    pair0 = i_mbrs[0], random.randrange(n+5)
    pairs = []
    for i in xrange(1,n):
      pair1 = i_mbrs[i], random.randrange(n+5)
      if (random.random() < 0.5):
        pairs.append((pair0, pair1))
      else:
        pairs.append((pair1, pair0))
    diffs0 = check_array_alignment(array_alignment, n, pairs)
    for i_redundant in xrange(3):
      i = random.randrange(n)
      j = random.randrange(n)
      d = random.randrange(n+5)
      pairs.append(((i,diffs0[j]-diffs0[i]+d), (j,d)))
    diffs0_r = check_array_alignment(array_alignment, n, pairs)
    assert diffs0 == diffs0_r
    #
    diffs_in = [0]
    for i in xrange(n-1):
      diffs_in.append(random.randrange(n+5))
    random.shuffle(diffs_in)
    all_pairs = []
    for i in xrange(n):
      for j in xrange(3):
        sh = random.randrange(n+5)
        all_pairs.append(((i,sh), (i,sh)))
    for i in xrange(n-1):
      for j in xrange(i+1,n):
        sh = random.randrange(n+5)
        i0 = i_mbrs[i]
        a0 = diffs_in[i0] + sh
        i1 = i_mbrs[j]
        a1 = diffs_in[i1] + sh
        all_pairs.append(((i0,a0), (i1,a1)))
        all_pairs.append(((i1,a1), (i0,a0)))
    random.shuffle(all_pairs)
    check_array_alignment(array_alignment, n, all_pairs)
  #
  # non-sensical inputs to exercise stability
  # these may cause RuntimeErrors, but must not cause
  # any other exceptions (e.g. asserts)
  for i_trial in xrange(n_trials):
    pairs = []
    for i_pair in xrange(n+2):
      i0 = random.randrange(n)
      o0 = random.randrange(n+5)
      i1 = random.randrange(n)
      o1 = random.randrange(n+5)
      pairs.append(((i0,o0), (i1,o1)))
      try:
        check_array_alignment(array_alignment, n, pairs)
      except RuntimeError:
        pass # these are to be expected


@pytest.mark.parametrize("array_alignment", [
    fable.equivalence.array_alignment,
    pytest.param(fem_array_alignment,
        marks=pytest.mark.skipif(not fable.ext,
                                 reason="test depends on C++ library")),
])
def test_exceptions(array_alignment):
  for n,pairs in [
        (2, [((0,0),(0,1))]),
        (2, [((0,0),(1,0)), ((0,0),(1,1))])]:

    with pytest.raises(RuntimeError) as e:
      array_alignment(n, pairs)
    assert str(e.value).endswith("directly conflicting input")

  for n,pairs in [
        (3, [((0,0),(1,0)), ((2,0),(1,1)), ((2,0),(0,0))]),
        (4, [((1,4),(2,8)), ((3,3),(1,4)), ((3,6),(2,6)), ((0,0),(2,4))])]:
    with pytest.raises(RuntimeError) as e:
      array_alignment(n, pairs)
    assert str(e.value).endswith("indirectly conflicting input")

  with pytest.raises(RuntimeError) as e:
    array_alignment(3, [((0,0),(1,0))])
  assert str(e.value).endswith("insufficient input")

def test_cluster_unions():
  cu = fable.equivalence.cluster_unions()
  cu.add(("a", "b"))
  assert cu.unions == [["a", "b"]]
  cu.add(("a", "b"))
  assert cu.unions == [["a", "b"]]
  cu.add(("c", "d"))
  assert cu.unions == [["a", "b"], ["c", "d"]]
  cu.add(("b", "c"))
  assert cu.unions == [["a", "b", "c", "d"], None]
  cu.add(("e", "f"))
  assert cu.unions == [["a", "b", "c", "d"], None, ["e", "f"]]
  cu.add(("g", "e"))
  assert cu.unions == [["a", "b", "c", "d"], None, ["e", "f", "g"], None]
  cu.add(("a", "g"))
  assert cu.unions == [["a", "b", "c", "d", "e", "f", "g"], None, None, None]
  cu.add(("h", "i"))
  assert cu.unions == [["a", "b", "c", "d", "e", "f", "g"], None, None, None,
    ["h", "i"]]
  assert cu.indices == {
    "a": 0, "c": 0, "b": 0, "e": 0, "d": 0, "g": 0, "f": 0, "i": 4, "h": 4}
  cu.tidy()
  assert cu.unions == [["a", "b", "c", "d", "e", "f", "g"], ["h", "i"]]
  assert cu.indices == {
    "a": 0, "c": 0, "b": 0, "e": 0, "d": 0, "g": 0, "f": 0, "i": 1, "h": 1}
  cu.add(("h", "j"))
  assert cu.unions == [["a", "b", "c", "d", "e", "f", "g"], ["h", "i", "j"]]
