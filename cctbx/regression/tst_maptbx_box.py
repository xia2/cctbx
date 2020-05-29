import iotbx.pdb
from libtbx.test_utils import approx_equal
from cctbx.sgtbx import space_group_info
from cctbx.development import random_structure
import cctbx.maptbx.box
from libtbx import group_args
import iotbx.pdb

def get_random_structure_and_map():
  xrs = random_structure.xray_structure(
    space_group_info = space_group_info(19),
    volume_per_atom  = 25.,
    elements         = ('C', 'N', 'O', 'H')*10,
    min_distance     = 1.5)
  fc = xrs.structure_factors(d_min=2).f_calc()
  fft_map = fc.fft_map(resolution_factor=0.25)
  fft_map.apply_volume_scaling()
  ph = iotbx.pdb.input(
    source_info=None, lines=xrs.as_pdb_file()).construct_hierarchy()
  return group_args(
    xray_structre = xrs,
    pdb_hierarchy = ph,
    map_data      = fft_map.real_map_unpadded())

def exercise_around_model():
  mm = get_random_structure_and_map()
  box1 = cctbx.maptbx.box.around_model(
    map_data       = mm.map_data,
    xray_structure = mm.xray_structre,
    cushion        = 5)
  box2 = cctbx.maptbx.box.around_model(
    map_data       = mm.map_data,
    pdb_hierarchy  = mm.pdb_hierarchy,
    crystal_symmetry = mm.xray_structre.crystal_symmetry(),
    cushion        = 5)
  assert approx_equal(
    box1.xray_structure.sites_cart(),
    box2.pdb_hierarchy.atoms().extract_xyz(),
    0.001) # because pdb_hierarchy obtained from xray_structure via PDB file
  assert approx_equal(box1.map_data, box2.map_data)

if (__name__ == "__main__"):
  exercise_around_model()