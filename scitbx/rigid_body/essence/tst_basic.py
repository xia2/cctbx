import featherstone
import joint_lib
import utils

matrix = featherstone.matrix
if (featherstone.scitbx is not None):
  from libtbx.test_utils import approx_equal
else:
  def approx_equal(a1, a2): return True
  print "libtbx.test_utils not available: approx_equal() disabled"
  def sum(l):
    result = 0
    for e in l: result += e
    return result

import sys

def exercise_basic():
  fs = featherstone
  assert approx_equal(sum(fs.Xrot((1,2,3,4,5,6,7,8,9))), 90)
  assert approx_equal(sum(fs.Xtrans((1,2,3))), 6)
  assert approx_equal(
    sum(fs.T_as_X(T=matrix.rt(((1,2,3,4,5,6,7,8,9), (1,2,3))))), 90)
  assert approx_equal(sum(fs.crm((1,2,3,4,5,6))), 0)
  assert approx_equal(sum(fs.crf((1,2,3,4,5,6))), 0)
  I_spatial = fs.mcI(
    m=1.234,
    c=matrix.col((1,2,3)),
    I=matrix.sym(sym_mat3=(2,3,4,0.1,0.2,0.3)))
  assert approx_equal(sum(I_spatial), 21.306)
  assert approx_equal(fs.kinetic_energy(
    I_spatial=I_spatial, v_spatial=matrix.col((1,2,3,4,5,6))), 75.109)
  #
  mass_points = utils.mass_points(
    masses=[2.34, 3.56, 1.58],
    sites=matrix.col_list([
      (0.949, 2.815, 5.189),
      (0.405, 3.954, 5.917),
      (0.779, 5.262, 5.227)]))
  assert approx_equal(mass_points.sum_masses(), 7.48)
  assert approx_equal(mass_points.center_of_mass(),
    [0.654181818182, 3.87397058824, 5.54350802139])
  assert approx_equal(mass_points._sum_masses, 7.48)
  assert approx_equal(
    mass_points.inertia(pivot=matrix.col((0.9,-1.3,0.4))),
    [404.7677928, 10.04129606, 10.09577652,
     10.04129606, 199.7384559, -199.3511949,
     10.09577652, -199.3511949, 206.8314171])

class six_dof_body(object):

  def __init__(O):
    sites = matrix.col_list([
      (0.949, 2.815, 5.189),
      (0.405, 3.954, 5.917),
      (0.779, 5.262, 5.227)])
    mass_points = utils.mass_points(sites=sites, masses=[1.0, 1.0, 1.0])
    O.A = joint_lib.six_dof_alignment(
      center_of_mass=mass_points.center_of_mass())
    O.I = mass_points.spatial_inertia(alignment_T=O.A.T0b)
    qE = matrix.col((0.18, 0.36, 0.54, -0.73)).normalize()
    qr = matrix.col((-0.1,0.3,0.2))
    O.J = joint_lib.six_dof(qE=qE, qr=qr)
    O.qd = matrix.col((0.18,-0.02,-0.16,-0.05,-0.19,0.29))
    O.parent = -1

class spherical_body(object):

  def __init__(O):
    sites = matrix.col_list([
      (0.04, -0.16, 0.19),
      (0.10, -0.15, 0.18)])
    mass_points = utils.mass_points(sites=sites, masses=[1.0, 1.0])
    O.A = joint_lib.spherical_alignment(
      center_of_mass=mass_points.center_of_mass())
    O.I = mass_points.spatial_inertia(alignment_T=O.A.T0b)
    qE = matrix.col((-0.50, -0.33, 0.67, -0.42)).normalize()
    O.J = joint_lib.spherical(qE=qE)
    O.qd = matrix.col((0.12, -0.08, 0.11))
    O.parent = 0

class revolute_body(object):

  def __init__(O):
    pivot = matrix.col((0.779, 5.262, 5.227))
    normal = matrix.col((0.25, 0.86, -0.45)).normalize()
    sites = matrix.col_list([(-0.084, 6.09, 4.936)])
    mass_points = utils.mass_points(sites=sites, masses=[1.0])
    O.A = joint_lib.revolute_alignment(pivot=pivot, normal=normal)
    O.I = mass_points.spatial_inertia(alignment_T=O.A.T0b)
    O.J = joint_lib.revolute(qE=matrix.col([0.26]))
    O.qd = matrix.col([-0.19])
    O.parent = 1

class translational_body(object):

  def __init__(O):
    sites = [matrix.col((0.949, 2.815, 5.189))]
    mass_points = utils.mass_points(sites=sites, masses=[1.0])
    O.A = joint_lib.translational_alignment(
      center_of_mass=mass_points.center_of_mass())
    O.I = mass_points.spatial_inertia(alignment_T=O.A.T0b)
    qr = matrix.col((-0.1,0.3,0.2))
    O.J = joint_lib.translational(qr=qr)
    O.qd = matrix.col((-0.05,-0.19,0.29))
    O.parent = -1

def exercise_system_model():
  model = featherstone.system_model(bodies=[
    six_dof_body(),
    spherical_body(),
    revolute_body(),
    translational_body()])
  assert approx_equal(model.e_kin(), 5.10688665235)
  assert approx_equal(model.qd_e_kin_scales(), [
    0.1036643, 0.1054236, 0.1187526, 0.5773503, 0.5773503, 0.5773503,
    0.1749883, 0.2830828, 0.2225619,
    1.334309,
    1.414214, 1.414214, 1.414214])
  #
  qdd = matrix.col_list([
    (-0.04,0.05,0.23,-0.01,-0.08,0.04),
    (0.08,-0.08,-0.01),
    (0.14,),
    (-0.01, -0.34, 0.28)])
  f_ext = matrix.col_list([
    (-0.10, 0.30, -0.01, -0.01, 0.01, 0.06),
    (0.28, 0.09, 0.14, 0.23, 0.00, 0.07),
    (-0.11, 0.03, -0.07, -0.11, 0.06, 0.08),
    (-0.16, 0.14, -0.33, 0.35, -0.02, -0.20)])
  grav_accn = matrix.col((0.02, -0.13, 0.15, 0.26, -0.16, 0.14))
  #
  tau = model.ID(qdd=qdd)
  assert approx_equal(tau, [
    (-28.4935967396, -13.9449610757, 37.119813341,
     3.09036984758, -3.29209848977, 1.51871803584),
    (22.0723956539, 1.85204188959, -1.96550741514),
    (0.526685445884,),
    (-0.01,-0.34,0.28)])
  qdd2 = model.FDab(tau=tau)
  assert approx_equal(qdd2, qdd)
  #
  tau = model.ID(qdd=qdd, f_ext=f_ext)
  assert approx_equal(tau, [
    (-28.2069898504, -14.1650076325, 38.2656278316,
     3.24402886492, -3.30833610224, 1.36344785723),
    (22.6135703212, 2.25806832722, -2.77922603881),
    (0.596685445884,),
    (-0.36,-0.32,0.48)])
  qdd2 = model.FDab(tau=tau, f_ext=f_ext)
  assert approx_equal(qdd2, qdd)
  #
  tau = model.ID(qdd=qdd, f_ext=f_ext, grav_accn=grav_accn)
  assert approx_equal(tau, [
    (29.0716177639, 1.548329665, -9.90799285557,
     -2.51132634591, 5.78686348626, -3.77518591503),
    (-4.70390288163, -1.2432778965, 1.1909533225),
    (-0.354638347024,),
    (0.54782, -0.17957, 0.16733)])
  qdd2 = model.FDab(tau=tau, f_ext=f_ext, grav_accn=grav_accn)
  assert approx_equal(qdd2, qdd)
  #
  new_q = [
    B.J.time_step_position(qd=B.qd, delta_t=0.01).get_q()
      for B in model.bodies]
  assert approx_equal(new_q, [
    (0.18036749, 0.36210928, 0.54329229, -0.7356480,
     -0.10189282, 0.29788946, 0.2020574),
    (-0.50329486, -0.33273860, 0.67548709, -0.4239072),
    (0.2581,),
    (-0.1005, 0.2981, 0.2029)])
  new_qd = [
    B.J.time_step_velocity(qd=B.qd, qdd=qdd_i, delta_t=0.01)
      for B,qdd_i in zip(model.bodies, qdd)]
  assert approx_equal(new_qd, [
    (0.1796, -0.0195, -0.1577, -0.0501, -0.1908, 0.2904),
    (0.1208, -0.0808, 0.1099),
    (-0.1886,),
    (-0.0501, -0.1934, 0.2928)])
  for B,q in zip(model.bodies, [(1,2,3,4,5,6,7),(8,9,10,11),(12,)]):
    assert approx_equal(B.J.new_q(q=q).get_q(), q)
  #
  qdd = []
  for B in model.bodies:
    B.qd = B.J.qd_zero
    qdd.append(B.J.qdd_zero)
  tau = model.ID(qdd=qdd, f_ext=f_ext)
  assert approx_equal(tau, [
    (0.286606889188, -0.220046556736, 1.14581449056,
     0.153659017347, -0.0162376124727, -0.155270178613),
    (0.541174667239, 0.406026437633, -0.813718623664),
    (0.07,),
    (-0.35,0.02,0.2)])
  tau0 = model.ID0(f_ext=f_ext)
  assert approx_equal(tau0, tau)
  d_pot_d_q = model.d_pot_d_q(f_ext=f_ext)
  assert approx_equal(d_pot_d_q, [
    (1.71580350518, 1.02634150274, -1.33166855821, -0.0558540404302,
     -0.0617881846156, 0.169686256436, -0.123985388881),
    (-0.87738271052, -1.30081275182, -1.40884161215, -0.1808674209),
    (0.07,),
    (-0.35,0.02,0.2)])

def run(args):
  assert len(args) == 0
  exercise_basic()
  exercise_system_model()
  print "OK"

if (__name__ == "__main__"):
  run(sys.argv[1:])
