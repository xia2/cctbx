from __future__ import absolute_import, division, print_function
#!/usr/bin/env python
#
# Biostruct-X Data Reduction Use Case 1.2:
#
# Validate reflection data from test integration code against data from XDS,
# by means of computing a correlaton coefficient between the two.

import math
import sys
import random
from cctbx.array_family import flex
from annlib_ext import AnnAdaptor as ann_adaptor
from scitbx import matrix
from six.moves import range

def meansd(values):

    assert(len(values) > 3)

    mean = sum(values) / len(values)
    var = sum([(v - mean) * (v - mean) for v in values]) / (len(values) - 1)

    return mean, math.sqrt(var)

def cc(a, b):

    assert(len(a) == len(b))

    ma, sa = meansd(a)
    mb, sb = meansd(b)

    r = (1 / (len(a) - 1)) * sum([((a[j] - ma) / sa) * ((b[j] - mb) / sb)
                                  for j in range(len(a))])

    return r

def work_cc():

    a = [random.random() + 0.01 * j for j in range(1000)]
    b = [random.random() + 0.01 * j for j in range(1000)]

    return cc(a, b)

def test_ann():

    reference = flex.double()

    for j in range(3 * 100):
        reference.append(random.random())

    query = flex.double()

    for j in range(3 * 10):
        query.append(random.random())

    ann = ann_adaptor(data = reference, dim = 3, k = 1)
    ann.query(query)

    # workout code - see how far separated on average they are - which should
    # in principle decrease as the number of positions in the reference set
    # increases

    offsets = []

    for j in range(10):
        q = matrix.col([query[3 * j + k] for k in range(3)])
        r = matrix.col([reference[3 * ann.nn[j] + k] for k in range(3)])
        offsets.append((q - r).length())

    return meansd(offsets)

def read_integrate_hkl(integrate_hkl):

    observations = []

    for record in open(integrate_hkl):
        if '!' in record[:1]:
            continue
        values = record.split()
        hkl = [int(h) for h in values[:3]]
        xyz = [float(x) for x in  values[5:8]]
        isigma = [float(x) for x in values[3:5]]

        observations.append((hkl, xyz, isigma))

    return observations

def read_uc1_2(uc1_2):
    predictions = []

    for record in open(uc1_2):
        values = record.split()
        hkl = [int(h) for h in values[1:4]]
        xyz = float(values[7]), float(values[8]), float(values[5])
        isigma = float(values[10]), float(values[12])

        predictions.append((hkl, xyz, isigma))

    return predictions

def validate_predictions(integrate_hkl, uc1_2):

    observations = read_integrate_hkl(integrate_hkl)
    predictions = read_uc1_2(uc1_2)

    reference = flex.double()
    query = flex.double()

    for hkl, xyz, isigma in observations:
        reference.append(xyz[0])
        reference.append(xyz[1])
        reference.append(xyz[2])

    for hkl, xyz, isigma in predictions:
        query.append(xyz[0])
        query.append(xyz[1])
        query.append(xyz[2])

    ann = ann_adaptor(data = reference, dim = 3, k = 1)
    ann.query(query)

    dxs = []
    dys = []
    dzs = []
    ivalues_o = []
    ivalues_p = []

    for j in range(len(predictions)):
        c = ann.nn[j]
        if observations[c][0] == predictions[j][0]:
            xyz = observations[c][1]
            dx = observations[c][1][0] - predictions[j][1][0]
            dy = observations[c][1][1] - predictions[j][1][1]
            dz = observations[c][1][2] - predictions[j][1][2]

            dxs.append(dx)
            dys.append(dy)
            dzs.append(dz)
            ivalues_o.append(observations[c][2][0])
            ivalues_p.append(predictions[j][2][0])
            print(observations[c][2][0], predictions[j][2][0])

    return meansd(dxs), meansd(dys), meansd(dzs), cc(ivalues_o, ivalues_p)

if __name__ == '__main__':
    dx, dy, dz, cc = validate_predictions(sys.argv[1], sys.argv[2])
    print('X: %.4f %.4f' % dx)
    print('Y: %.4f %.4f' % dy)
    print('Z: %.4f %.4f' % dz)
    print('CC: %.4f' % cc)
