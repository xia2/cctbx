from __future__ import division
# LIBTBX_SET_DISPATCHER_NAME phenix.model_map

import sys
import iotbx.pdb
from libtbx.utils import Sorry
from cctbx import maptbx
from mmtbx.maps import fem
import mmtbx.real_space

legend = """phenix.model_map: Given PDB file calculate model map

How to run:
  phenix.model_map model.pdb
"""

master_params_str = """
grid_step=0.3
  .type=float
output_file_name_prefix = None
  .type=str
"""

def master_params():
  return iotbx.phil.parse(master_params_str)

def run(args, log=sys.stdout):
  print >> log, "-"*79
  print >> log, legend
  print >> log, "-"*79
  inputs = mmtbx.utils.process_command_line_args(args = args,
    master_params = master_params())
  file_names = inputs.pdb_file_names
  if(len(file_names) != 1): raise Sorry("A PDB file is expected.")
  xrs = iotbx.pdb.input(file_name =
    file_names[0]).xray_structure_simple().expand_to_p1(sites_mod_positive=True)
  params = inputs.params.extract()
  #
  crystal_gridding = maptbx.crystal_gridding(
    unit_cell        = xrs.unit_cell(),
    space_group_info = xrs.space_group_info(),
    symmetry_flags   = maptbx.use_space_group_symmetry,
    step             = params.grid_step)
  m = mmtbx.real_space.sampled_model_density(
    xray_structure = xrs,
    n_real         = crystal_gridding.n_real())
  map_data = m.data()
  #
  prefix = "model_map"
  if(params.output_file_name_prefix is not None):
    prefix = params.output_file_name_prefix
  #
  m.write_as_xplor_map(file_name = "%s.xplor"%prefix)
  fem.ccp4_map(cg=crystal_gridding, file_name="%s.ccp4"%prefix,
    map_data=map_data)

if (__name__ == "__main__"):
  run(args=sys.argv[1:])
