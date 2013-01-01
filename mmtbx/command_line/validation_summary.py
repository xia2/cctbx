
"""
Convenience tool for collecting validation statistics with minimal overhead.
"""

from __future__ import division
from libtbx import slots_getstate_setstate, Auto
from libtbx.utils import Sorry, Usage
from libtbx import str_utils
from libtbx import easy_mp
import cStringIO
import os
import sys

class summary (object) :
  """
  Very basic MolProbity statistics for a refinement result, plus R-factors and
  RMS(bonds)/RMS(angles) if they can be extracted from REMARK records in the
  PDB header.  Suitable for benchmarking or collecting statistics, but not a
  substitute for full validation.
  """
  def __init__ (self, pdb_hierarchy=None, pdb_file=None, sites_cart=None,
      keep_hydrogens=False) :
    if (pdb_hierarchy is None) :
      assert (pdb_file is not None)
      from iotbx import file_reader
      pdb_in = file_reader.any_file(pdb_file, force_type="pdb")
      pdb_in.assert_file_type("pdb")
      pdb_hierarchy = pdb_in.file_object.construct_hierarchy()
      pdb_hierarchy.atoms().reset_i_seq()
    if (sites_cart is not None) :
      pdb_hierarchy.atoms().set_xyz(sites_cart)
    from mmtbx.validation import ramalyze, rotalyze, cbetadev, clashscore
    log = cStringIO.StringIO()
    rama = ramalyze.ramalyze()
    rama.analyze_pdb(hierarchy=pdb_hierarchy)
    if (rama.numtotal > 0) :
      rama_out_count, rama_out_percent = rama.get_outliers_count_and_fraction()
      rama_fav_count, rama_fav_percent = rama.get_favored_count_and_fraction()
      self.rama_fav = rama_fav_percent * 100.0
      self.rama_out = rama_out_percent * 100.0
    else :
      self.rama_fav = None
      self.rama_out = None
    rota = rotalyze.rotalyze()
    rota.analyze_pdb(hierarchy=pdb_hierarchy)
    if (rota.numtotal > 0) :
      rota_count, rota_perc = rota.get_outliers_count_and_fraction()
      self.rota_out = rota_perc * 100.0
    else :
      self.rota_out = None
    cs = clashscore.clashscore()
    clash_dict, clash_list = cs.analyze_clashes(hierarchy=pdb_hierarchy,
      keep_hydrogens=keep_hydrogens)
    self.clashscore = clash_dict['']
    cbeta = cbetadev.cbetadev()
    cbeta_txt, cbeta_summ, cbeta_list = cbeta.analyze_pdb(
      hierarchy=pdb_hierarchy,
      outliers_only=True)
    self.mpscore = None
    if (not None in [self.rota_out, self.rama_fav, self.clashscore]) :
      from mmtbx.validation.utils import molprobity_score
      self.mpscore = molprobity_score(
        clashscore=self.clashscore,
        rota_out=self.rota_out,
        rama_fav=self.rama_fav)
    # TODO leave self.cbeta_out as None if not protein
    self.cbeta_out = len(cbeta_list)
    self.r_work = None
    self.r_free = None
    self.rms_bonds = None
    self.rms_angles = None
    self.d_min = None
    if (pdb_file is not None) :
      from iotbx.pdb import extract_rfactors_resolutions_sigma
      published_results = extract_rfactors_resolutions_sigma.extract(
        file_name=pdb_file)
      if (published_results is not None) :
        self.r_work = published_results.r_work
        self.r_free = published_results.r_free
        self.d_min   = published_results.high
      lines = open(pdb_file).readlines()
      for line in lines :
        if (line.startswith("REMARK Final:")) :
          fields = line.strip().split()
          self.rms_bonds = float(fields[-4])
          self.rms_angles = float(fields[-1])
          break

  def show (self, out=sys.stdout, prefix="  ") :
    def fs (format, value) :
      return str_utils.format_value(format, value, replace_none_with=("(none)"))
    print >> out, "%sRamachandran outliers = %s %%" % (prefix,
      fs("%6.2f", self.rama_out))
    print >> out, "%s             favored  = %s %%" % (prefix,
      fs("%6.2f", self.rama_fav))
    print >> out, "%sRotamer outliers      = %s %%" % (prefix,
      fs("%6.2f", self.rota_out))
    print >> out, "%sC-beta deviations     = %s" % (prefix,
      fs("%6d", self.cbeta_out))
    print >> out, "%sClashscore            = %6.2f" % (prefix, self.clashscore)
    if (self.mpscore is not None) :
      print >> out, "%sMolprobity score      = %6.2f" % (prefix, self.mpscore)
    if (self.r_work is not None) :
      print >> out, "%sR-work                = %8.4f" % (prefix, self.r_work)
    if (self.r_free is not None) :
      print >> out, "%sR-free                = %8.4f" % (prefix, self.r_free)
    if (self.rms_bonds is not None) :
      print >> out, "%sRMS(bonds)            = %8.4f" % (prefix, self.rms_bonds)
    if (self.rms_angles is not None) :
      print >> out, "%sRMS(angles)           = %6.2f" % (prefix,
        self.rms_angles)
    if (self.d_min is not None) :
      print >> out, "%sHigh resolution       = %6.2f" % (prefix, self.d_min)

class parallel_driver (object) :
  """
  Simple wrapper for passing to easy_mp.pool_map.
  """
  def __init__ (self, pdb_hierarchy, xray_structures) :
    self.pdb_hierarchy = pdb_hierarchy
    self.xray_structures = xray_structures

  def __call__ (self, i_model) :
    sites_cart = self.xray_structures[i_model].sites_cart()
    pdb_hierarchy = self.pdb_hierarchy.deep_copy()
    return summary(pdb_hierarchy=pdb_hierarchy, sites_cart=sites_cart)

class ensemble (slots_getstate_setstate) :
  """
  MolProbity validation results for an ensemble of models.
  """
  __slots__ = [
    "rama_out",
    "rama_fav",
    "rota_out",
    "cbeta_out",
    "clashscore",
    "mpscore",
  ]
  __slot_labels__ = [
    "Ramachandran outliers",
    "Ramachandran favored",
    "Rotamer outliers",
    "C-beta outliers",
    "Clashscore",
    "MolProbity score",
  ]
  def __init__ (self, pdb_hierarchy, xray_structures, nproc=Auto) :
    assert (len(pdb_hierarchy.models()) == 1)
    validate = parallel_driver(pdb_hierarchy, xray_structures)
    summaries = easy_mp.pool_map(
      processes=nproc,
      fixed_func=validate,
      args=range(len(xray_structures)))
    for name in self.__slots__ :
      array = []
      for s in summaries :
        array.append(getattr(s, name))
      setattr(self, name, array)

  def show (self, out=None, prefix="") :
    if (out is None) :
      out = sys.stdout
    def min_max_mean (array) :
      if (len(array) == 0) or (array.count(None) == len(array)) :
        return (None, None, None)
      else :
        return min(array), max(array), sum(array) / len(array)
    def fs (format, value) :
      return str_utils.format_value(format, value, replace_none_with=("(none)"))
    def format_all (format, array) :
      min, max, mean = min_max_mean(array)
      return "%s %s %s" % (fs(format, min), fs(format, max), fs(format, mean))
    print >> out, "%s                           min    max   mean" % prefix
    print >> out, "%sRamachandran outliers = %s %%" % (prefix,
      format_all("%6.2f", self.rama_out))
    print >> out, "%s             favored  = %s %%" % (prefix,
      format_all("%6.2f", self.rama_fav))
    print >> out, "%sRotamer outliers      = %s %%" % (prefix,
      format_all("%6.2f", self.rota_out))
    print >> out, "%sC-beta deviations     = %s" % (prefix,
      format_all("%6d", self.cbeta_out))
    print >> out, "%sClashscore            = %s" % (prefix,
      format_all("%6.2f", self.clashscore))
    if (self.mpscore is not None) :
      print >> out, "%sMolprobity score      = %s" % (prefix,
        format_all("%6.2f", self.mpscore))

def run (args, out=sys.stdout) :
  if (len(args) == 0) :
    raise Usage("""
mmtbx.validation_summary model.pdb

Prints a brief summary of validation criteria, including Ramachandran
statistics, rotamer outliers, clashscore, C-beta deviations, plus R-factors
and RMS(bonds)/RMS(angles) if found in PDB header.  (This is primarily used
for evaluating the output of refinement tests; general users are advised to
run phenix.model_vs_data or the validation GUI.)
""")
  pdb_file = args[0]
  if (not os.path.isfile(pdb_file)) :
    raise Sorry("Not a file: %s" % pdb_file)
  from iotbx.file_reader import any_file
  pdb_in = any_file(pdb_file, force_type="pdb").check_file_type("pdb")
  hierarchy = pdb_in.file_object.construct_hierarchy()
  xrs = pdb_in.file_object.xray_structures_simple()
  s = None
  extra = ""
  if (len(xrs) == 1) :
    s = summary(pdb_hierarchy=hierarchy)
  else :
    import iotbx.pdb.hierarchy
    new_hierarchy = iotbx.pdb.hierarchy.root()
    single_model = hierarchy.models()[0].detached_copy()
    single_model.id = ""
    new_hierarchy.append_model(single_model)
    s = ensemble(pdb_hierarchy=new_hierarchy,
      xray_structures=xrs)
    extra = " (%d models)" % len(xrs)
  print >> out, ""
  print >> out, "Validation summary for %s%s:" % (pdb_file, extra)
  s.show(out=out, prefix="  ")
  print >> out, ""
  return s

if (__name__ == "__main__") :
  run(sys.argv[1:])
