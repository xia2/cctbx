from __future__ import division

# TODO: regression testing
# TODO: merge/expand to compatible point groups
# TODO: confirm old_test_flag_value if ambiguous

import sys, os, string
from iotbx import reflection_file_reader, reflection_file_utils, file_reader
from iotbx.reflection_file_utils import get_r_free_flags_scores
import iotbx.phil
from cctbx import crystal, miller
from scitbx.array_family import flex
from libtbx.phil.command_line import argument_interpreter
from libtbx.utils import Sorry
from libtbx import adopt_init_args

# XXX: note that extend=True in the Phenix GUI
master_phil = iotbx.phil.parse("""
show_arrays = False
  .type = bool
  .help = Command-line option, prints out a list of the arrays in each file
  .style = hidden
dry_run = False
  .type = bool
  .help = Print out final configuration and output summary, but don't write \
          the output file
  .style = hidden
verbose = True
  .type = bool
  .help = Print extra debugging information
  .style = hidden
hkltools
{
  crystal_symmetry
  {
    unit_cell = None
      .type = unit_cell
      .style = bold
    space_group = None
      .type = space_group
      .style = bold
    force_symmetry = False
      .type = bool
      .help = If specified symmetry is different than that of the miller \
              arrays, this parameter will cause them to be merged or expanded \
              as necessary.  CURRENTLY UNIMPLEMENTED
  }
  d_max = None
    .type = float
    .short_caption = Low resolution
    .style = bold renderer:draw_hkltools_resolution_widget
  d_min = None
    .type = float
    .short_caption = High resolution
    .style = bold renderer:draw_hkltools_resolution_widget
  output_file = None
    .type = path
    .short_caption = Output file
    .style = file_type:mtz new_file bold noauto
  edit_final_labels = False
    .type = bool
    .short_caption = Edit column labels before writing file (will prompt for \
      new labels after clicking "Run")
    .help = GUI-only option
    .style = bold
  resolve_label_conflicts = False
    .type = bool
    .help = Updates label names as necessary to avoid conflicts
    .style = hidden
  miller_array
    .multiple = True
  {
    file_name = None
      .type = path
    labels = None
      .type = str
    d_min = None
      .type = float
    d_max = None
      .type = float
    output_label = None
      .type = str
      .multiple = True
      .optional = True
      .help = Most Miller arrays have more than one label, and there must be \
              exactly as many new labels as the number of labels in the \
              old array.  (See caveat in Phenix manual about Scalepack files.)
  }
  r_free_flags
    .short_caption = R-free flags generation
    .style = menu_item auto_align box
  {
    generate = True
      .type = bool
      .short_caption = Generate R-free flags if not already present
      .style = bold
    force_generate = False
      .type = bool
      .short_caption = Generate R-free flags even if they are already present
    new_label = FreeR_flag
      .type = str
      .short_caption = Output label for new R-free flags
      .style = bold
    use_resolution_shells = False
      .type = bool
      .short_caption = Use thin shells for R-free
      .style = noauto
    fraction = 0.05
      .type = float
      .short_caption = Percent of reflections to flag
    max_free = 2000
      .type = int
      .short_caption = Maximum number of reflections in test set
    use_lattice_symmetry = True
      .type = bool
      .expert_level = 2
    lattice_symmetry_max_delta = 5
      .type = int
      .expert_level = 2
      .short_caption = Lattice symmetry max. delta
    use_dataman_shells = False
      .type = bool
      .short_caption = Assign test set in thin resolution shells
      .help = Used to avoid biasing of the test set by certain types of \
        non-crystallographic symmetry.
    n_shells = 20
      .type = int
      .short_caption = Number of resolution shells
    extend = None
      .type = bool
      .short_caption = Extend existing R-free array(s) to full resolution range
      .style = bold noauto
    old_test_flag_value = None
      .type = int
      .short_caption = Original test flag value
      .help = Overrides automatic guess of test flag value from existing set. \
        This will usually be 1 for reflection files generated by Phenix, and \
        0 for reflection files from CCP4.  Do not change unless you're sure \
        you know what flag to use!
  }
}""")

# XXX: params.hkltools.miller_array values will be ignored here, since the
# arrays and file names should have already been extracted
class process_arrays (object) :
  def __init__ (self, miller_arrays, file_names, params, log=sys.stderr,
      accumulation_callback=None) :
    adopt_init_args(self, locals())
    if len(miller_arrays) == 0 :
      raise Sorry("No Miller arrays have been selected for the output file.")
    assert len(miller_arrays) == len(file_names)
    if None in [params.hkltools.crystal_symmetry.space_group,
                params.hkltools.crystal_symmetry.unit_cell] :
      raise Sorry("Missing or incomplete symmetry information.")
    sg = params.hkltools.crystal_symmetry.space_group.group()
    derived_sg = sg.build_derived_point_group()
    uc = params.hkltools.crystal_symmetry.unit_cell
    self.symm = crystal.symmetry(unit_cell=uc, space_group=sg)
    force_symmetry = params.hkltools.crystal_symmetry.force_symmetry
    for file_name, miller_array in zip(file_names, miller_arrays) :
      array_symm = miller_array.crystal_symmetry()
      if array_symm is None :
        continue
      array_sg = array_symm.space_group()
      array_uc = array_symm.unit_cell()
      if (array_sg is not None and not force_symmetry and
          array_sg.build_derived_point_group() != derived_sg) :
        raise Sorry(("The point group for the Miller array %s:%s (%s) does "+
          "not match the point group of the output space group (%s).") %
          (file_name, miller_array.info().label_string(),str(array_sg),str(sg)))
      if (array_uc is not None and not force_symmetry and
          not array_uc.is_similar_to(uc, 1.e-3, 1.e-3)) :
        raise Sorry(("The unit cell for the Miller array %s:%s (%s) is "+
          "significantly different than the output unit cell (%s).") %
          (file_name, miller_array.info().label_string(),str(array_uc),str(uc)))
    labels = ["H", "K", "L"]
    label_files = [None, None, None]
    i = 1
    self.extend = False
    self.created_r_free = False
    have_r_free_array = False
    self.final_arrays = []
    self.mtz_dataset = None
    if len(miller_arrays) > 25 :
      raise Sorry("Only 25 or fewer arrays may be used.")
    i = 0
    (d_max, d_min) = get_best_resolution(miller_arrays)
    if params.hkltools.d_max is not None and params.hkltools.d_max < d_max :
      d_max = params.hkltools.d_max
    if params.hkltools.d_min is not None and params.hkltools.d_min > d_min :
      d_min = params.hkltools.d_min

    # XXX: main loop
    for i, old_array in enumerate(miller_arrays) :
      info = old_array.info()
      output_labels = info.labels
      # TODO: convert to higher/lower symmetry
      array_copy = old_array.customized_copy(
        crystal_symmetry=self.symm).map_to_asu()
      current_params = None
      # XXX: workaround for scalepack files with anomalous data
      if array_copy.anomalous_flag() and info.labels == ["i_obs","sigma"] :
        output_labels = ["I(+)", "SIGI(+)", "I(-)", "SIGI(-)"]
      for array_params in params.hkltools.miller_array :
        if (array_params.labels == info.label_string() and
            array_params.file_name == file_names[i]) :
          current_params = array_params
      if current_params is None :
        raise Sorry("Parameters for Miller array %s not found!" %
          info.label_string())
      # XXX: array-specific resolution limits are applied first, then
      # the global limits
      new_array = array_copy.resolution_filter(d_min=current_params.d_min,
        d_max=current_params.d_max).resolution_filter(
          d_min=params.hkltools.d_min,
          d_max=params.hkltools.d_max)
      if len(current_params.output_label) == 0 :
        current_params.output_label = output_labels
      elif len(array_info.labels) != len(current_params.output_label) :
        if info.labels==["i_obs","sigma"] and array_copy.anomalous_flag() :
          if len(current_params.output_label) == 4 :
            output_labels = current_params.output_label
          else :
            raise Sorry("For scalepack files containing anomalous data, "+
                   "you must specify exactly four column labels (e.g. I(+), "+
                   "SIGI(+),I(-),SIGI(-)).")
      else :
        raise Sorry(("Number of user-specified labels for %s:%s does not "+
          "match the number of labels in the output file.") %
            (file_names[i], info.label_string()))
      # XXX: R-free flags handling
      if ((new_array.is_integer_array() or new_array.is_bool_array()) and
           reflection_file_utils.looks_like_r_free_flags_info(info)) :
        flag_scores = get_r_free_flags_scores(miller_arrays=[new_array],
           test_flag_value=None)
        test_flag_value = flag_scores.test_flag_values[0]
        r_free_flags = new_array.array(data=new_array.data()==test_flag_value)
        fraction_free = (r_free_flags.data().count(True) /
                         r_free_flags.data().size())
        print >>log, "%s: fraction_free=%.3f" % (info.labels[0], fraction_free)
        missing_set = r_free_flags.complete_set(d_min=d_min,
          d_max=d_max).lone_set(r_free_flags.map_to_asu())
        n_missing = missing_set.indices().size()
        print >>log, "%s: missing %d reflections" % (info.labels[0], n_missing)
        if n_missing != 0 and params.hkltools.r_free_flags.extend :
          if n_missing <= 20 :
            # FIXME: MASSIVE CHEAT necessary for tiny sets
            missing_flags = missing_set.array(data=flex.bool(n_missing,False))
          else :
            if accumulation_callback is not None :
              if not accumulation_callback(miller_array=new_array,
                                           test_flag_value=test_flag_value,
                                           n_missing=n_missing,
                                           column_label=info.labels[0]) :
                continue
            missing_flags = missing_set.generate_r_free_flags(
              fraction=fraction_free,
              max_free=None,
              use_lattice_symmetry=True)
          output_array = r_free_flags.concatenate(other=missing_flags)
        else :
          output_array = r_free_flags
        have_r_free_array = True
      else :
        output_array = new_array
      fake_label = 2 * string.uppercase[i]
      if self.mtz_dataset is None :
        self.mtz_dataset = output_array.as_mtz_dataset(
                             column_root_label=fake_label)
      else :
        self.mtz_dataset.add_miller_array(
          miller_array=output_array,
          column_root_label=fake_label)
      for label in output_labels :
        labels.append(label)
        label_files.append(file_names[i])
      self.final_arrays.append(output_array)
    if ((params.hkltools.r_free_flags.generate and not have_r_free_array) or
        params.hkltools.r_free_flags.force_generate) :
      (d_max, d_min) = get_best_resolution(self.final_arrays)
      complete_set = miller.build_set(crystal_symmetry=self.symm,
                                      anomalous_flag=False,
                                      d_min=d_min,
                                      d_max=d_max)
      r_free_params = params.hkltools.r_free_flags
      new_r_free_array = complete_set.generate_r_free_flags(
        fraction=r_free_params.fraction,
        max_free=r_free_params.max_free,
        lattice_symmetry_max_delta=r_free_params.lattice_symmetry_max_delta,
        use_lattice_symmetry=r_free_params.use_lattice_symmetry,
        use_dataman_shells=r_free_params.use_dataman_shells,
        n_shells=r_free_params.n_shells)
      if r_free_params.new_label is None or r_free_params.new_label == "" :
        r_free_params.new_label = "FreeR_flag"
      self.mtz_dataset.add_miller_array(
        miller_array=new_r_free_array,
        column_root_label=r_free_params.new_label)
      labels.append(r_free_params.new_label)
      label_files.append("(new array)")
      self.created_r_free = True
    mtz_object = self.mtz_dataset.mtz_object()
    if mtz_object.n_columns() != len(labels) :
      raise Sorry("Wrong number of columns or labels!")
    self.labels = labels
    self.label_changes = []
    self.label_files = label_files
    self.params = params
    self.mtz_object = mtz_object
    self.apply_new_labels(labels,
      resolve_conflicts=params.hkltools.resolve_label_conflicts)

  # In the GUI, this will be done at the end.
  def apply_new_labels (self, labels, resolve_conflicts=False) :
    assert len(labels) == self.mtz_object.n_columns() == len(self.label_files)
    i = 0
    used = dict([ (label, 0) for label in labels ])
    label_files = self.label_files
    final_labels = []
    for column in self.mtz_object.columns() :
      if column.label() != labels[i] :
        label = labels[i]
        if used[labels[i]] > 0 :
          if resolve_conflicts :
            if label.endswith("(+)") or label.endswith("(-)") :
              label = label[0:-3] + ("_%d" % (used[labels[i]]+1)) + label[-3:]
            else :
              label += "_%d" % (used[labels[i]] + 1)
            self.label_changes.append((label_files[i], labels[i], label))
          else :
            raise Sorry(("Duplicate column label '%s'.  Specify "+
              "resolve_label_conflicts=True to automatically generate "+
              "non-redundant labels, or edit the parameters to provide your"+
              "own choice of labels.") % labels[i])
        column.set_label(label)
        final_labels.append(label)
        used[labels[i]] += 1
      else :
        final_labels.append(labels[i])
      i += 1
    self.labels = final_labels

  def show (self, out=sys.stdout) :
    if self.mtz_object is not None :
      print >> out, ""
      print >> out, ("=" * 20) + " Summary of output file " + ("=" * 20)
      self.mtz_object.show_summary(out=out, prefix="  ")
      print >> out, ""

  def finish (self) :
    assert self.mtz_object is not None
    if self.params.verbose :
      self.show(out=self.log)
    self.mtz_object.write(file_name=self.params.hkltools.output_file)
    del self.mtz_object
    self.mtz_object = None

def get_r_free_stats (miller_array, test_flag_value) :
  array = get_r_free_as_bool(miller_array, test_flag_value)
  n_free = array.data().count(True)
  accu =  array.sort(by_value="resolution").r_free_flags_accumulation()
  lr = flex.linear_regression(accu.reflection_counts.as_double(),
                              accu.free_fractions)
  assert lr.is_well_defined()
  slope = lr.slope()
  y_ideal = accu.reflection_counts.as_double() * slope
  sse = 0
  n_bins = 0
  n_ref_last = 0
  sse = flex.sum(flex.pow(y_ideal - accu.free_fractions, 2))
  for x in accu.reflection_counts :
    if x > (n_ref_last + 1) :
      n_bins += 1
    n_ref_last = x
  return (n_bins, n_free, sse, accu)

def get_best_resolution (miller_arrays) :
  best_d_min = None
  best_d_max = None
  for array in miller_arrays :
    try :
      (d_max, d_min) = array.d_max_min()
      if best_d_max is None or d_max > best_d_max :
        best_d_max = d_max
      if best_d_min is None or d_min < best_d_min :
        best_d_min = d_min
    except Exception, e :
      pass
  return (best_d_max, best_d_min)

#-----------------------------------------------------------------------
def usage (out=sys.stdout, attributes_level=0) :
  print >> out, """
# usage: iotbx.reflection_file_editor [file1.mtz ...] [parameters.eff]
#            --help      (print this message)
#            --details   (show parameter help strings)
# Dumping default parameters:
"""
  master_phil.show(out=out, attributes_level=attributes_level)

def generate_params (file_name, miller_arrays) :
  params = []
  for miller_array in miller_arrays :
    param_str = """hkltools.miller_array {
  file_name = %s
  labels = %s
""" % (file_name, miller_array.info().label_string())
    try :
      (d_max, d_min) = miller_array.d_max_min()
      param_str += """  d_max = %.5f\n  d_min = %.5f\n""" % (d_max, d_min)
    except Exception :
      pass
    param_str += "}"
    params.append(param_str)
  return "\n".join(params)

def run (args, out=sys.stdout) :
  crystal_symmetry_from_pdb = None
  crystal_symmetries_from_hkl = []
  reflection_files = []
  user_phil = []
  all_arrays = []
  if len(args) == 0 :
    usage()
  interpreter = argument_interpreter(master_phil=master_phil,
                                     home_scope=None)
  for arg in args :
    if arg in ["--help", "--options", "--details"] :
      usage(attributes_level=args.count("--details"))
      return True
    elif os.path.isfile(arg) :
      full_path = os.path.abspath(arg)
      try :
        file_phil = iotbx.phil.parse(file_name=full_path)
      except Exception :
        pass
      else :
        user_phil.append(file_phil)
        continue
      input_file = file_reader.any_file(full_path)
      if input_file.file_type == "hkl" :
        miller_arrays = input_file.file_object.as_miller_arrays()
        for array in miller_arrays :
          symm = array.crystal_symmetry()
          if symm is not None :
            crystal_symmetries_from_hkl.append(symm)
            break
        reflection_files.append(input_file)
      elif input_file.file_type == "pdb" :
        symm = input_file.file_object.crystal_symmetry()
        if symm is not None :
          crystal_symmetry_from_pdb = symm
    else :
      try :
        cmdline_phil = interpreter.process(arg=arg)
      except Exception :
        pass
      else :
        user_phil.append(cmdline_phil)
  cached_files = {}
  for input_file in reflection_files :
    cached_files[input_file.file_name] = input_file
    file_arrays = input_file.file_object.as_miller_arrays()
    file_params_str= generate_params(input_file.file_name, file_arrays)
    user_phil.append(iotbx.phil.parse(file_params_str))

  working_phil = master_phil.fetch(sources=user_phil)
  params = working_phil.extract()
  if crystal_symmetry_from_pdb is not None :
    params.hkltools.crystal_symmetry.space_group = \
      crystal_symmetry_from_pdb.space_group_info()
    params.hkltools.crystal_symmetry.unit_cell = \
      crystal_symmetry_from_pdb.unit_cell()
  elif None in [params.hkltools.crystal_symmetry.space_group,
                params.hkltools.crystal_symmetry.unit_cell] :
    for i, symm in enumerate(crystal_symmetries_from_hkl) :
      params.hkltools.crystal_symmetry.space_group = symm.space_group_info()
      params.hkltools.crystal_symmetry.unit_cell = symm.unit_cell()
      break
  if params.hkltools.output_file is None :
    n = 0
    for file_name in os.listdir(os.getcwd()) :
      if file_name.startswith("reflections_") and file_name.endswith(".mtz") :
        n += 1
    params.hkltools.output_file = "reflections_%d.mtz" % (n+1)
  params.hkltools.output_file = os.path.abspath(params.hkltools.output_file)
  miller_arrays = []
  file_names = []
  for array_params in params.hkltools.miller_array :
    input_file = cached_files.get(array_params.file_name)
    if input_file is None :
      input_file = file_reader.any_file(array_params.file_name)
      input_file.assert_file_type("hkl")
      cached_files[input_file.file_name] = input_file
    for miller_array in input_file.file_object.as_miller_arrays() :
      array_info = miller_array.info()
      label_string = array_info.label_string()
      if label_string == array_params.labels :
        miller_arrays.append(miller_array)
        file_names.append(input_file.file_name)

  if params.show_arrays :
    shown_files = []
    for file_name, miller_array in zip(file_names, miller_arrays) :
      if not file_name in shown_files :
        print >> out, "%s:" % file_name
        shown_files.append(file_name)
      print >> out, "  %s" % miller_array.info().label_string()
    return True
  if len(miller_arrays) == 0 :
    raise Sorry("No Miller arrays picked for output.")
  process = process_arrays(miller_arrays, file_names, params, log=out)
  if process.extend :
    process.extend_r_free_flags()
  if params.dry_run :
    print >> out, "# showing final parameters"
    master_phil.format(python_object=params).show(out=out)
    if params.verbose :
      process.show(out=out)
    return process
  process.finish()
  print >> out, "Data written to %s" % params.hkltools.output_file
  return process

if __name__ == "__main__" :
  run(sys.argv[1:])

#---end
