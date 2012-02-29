import os
import sys

from libtbx import easy_mp
from libtbx import easy_pickle
from libtbx.option_parser import option_parser
from scitbx.array_family import flex
import scitbx.math

from xfel.command_line import view_pixel_histograms # XXX
from xfel.cxi.cspad_ana import cspad_tbx
from xfel.cxi.cspad_ana import xes_finalise

def run(args):
  command_line = (option_parser()
                  .option("--output_dirname", "-o",
                          type="string",
                          help="Directory for output files.")
                  .option("--roi",
                          type="string",
                          help="Region of interest for summing up histograms"
                          "from neighbouring pixels.")
                  .option("--gain_map_path",
                          type="string",
                          help="Path to a gain map that will be used instead of"
                          "fitting the one photon peak to estimate the gain.")
                  .option("--estimated_gain",
                          type="float",
                          default=30,
                          help="The approximate position of the one photon peak.")
                  .option("--nproc", "-p",
                          type="int",
                          help="Number of processors to use.")
                  .option("--photon_threshold",
                          type="float",
                          default=2/3,
                          help="Threshold for counting photons (as a fraction of"
                          "the distance between the zero and one photon peaks.")
                  .option("--sum_adu",
                          action="store_true",
                          default=False,
                          help="Sum the ADUs instead of counting photons.")
                  ).process(args=args)
  args = command_line.args
  assert len(args) == 1
  output_dirname = command_line.options.output_dirname
  roi = cspad_tbx.getOptROI(command_line.options.roi)
  gain_map_path = command_line.options.gain_map_path
  estimated_gain = command_line.options.estimated_gain
  nproc = command_line.options.nproc
  photon_threshold = command_line.options.photon_threshold
  if command_line.options.sum_adu:
    method = "sum_adu"
  else:
    method = "photon_counting"
  print output_dirname
  if output_dirname is None:
    output_dirname = os.path.join(os.path.dirname(args[0]), "finalise")
    print output_dirname
  hist_d = easy_pickle.load(args[0])
  if roi is not None:
    for ij, hist in hist_d.items():
      i, j = ij
    for (i, j), hist in hist_d.items():
      if (   i < roi[2]
          or i > roi[3]
          or j < roi[0]
          or j > roi[1]):
        del hist_d[(i,j)]
  pixel_histograms = view_pixel_histograms.pixel_histograms(
    hist_d, estimated_gain=estimated_gain)
  xes_from_histograms(pixel_histograms, output_dirname=output_dirname,
                      gain_map_path=gain_map_path, estimated_gain=estimated_gain,
                      method=method, nproc=nproc,
                      photon_threshold=photon_threshold)

def xes_from_histograms(pixel_histograms, output_dirname=".", gain_map_path=None,
                        method="photon_counting", estimated_gain=30, nproc=None,
                        photon_threshold=2/3):
  assert method in ("sum_adu", "photon_counting")
  sum_img = flex.double(flex.grid(370,391), 0) # XXX define the image size some other way?
  gain_img = flex.double(sum_img.accessor(), 0)

  if gain_map_path is not None:
    d = easy_pickle.load(gain_map_path)
    gain_map = d["DATA"]
  else:
    gain_map = None

  two_photon_threshold = photon_threshold + 1

  mask = flex.int(sum_img.accessor(), 0)

  start_row = 370
  end_row = 0
  print len(pixel_histograms.histograms)

  pixels = list(pixel_histograms.pixels())
  if gain_map is None:
    fixed_func = pixel_histograms.fit_one_histogram
  else:
    def fixed_func(pixel):
      return pixel_histograms.fit_one_histogram(pixel, n_gaussians=1)
  results = None
  if nproc is None: nproc = easy_mp.Auto
  nproc = easy_mp.get_processes(nproc)
  print "nproc: ", nproc

  stdout_and_results = easy_mp.pool_map(
    processes=nproc,
    fixed_func=fixed_func,
    args=pixels,
    func_wrapper="buffer_stdout_stderr")
  results = [r for so, r in stdout_and_results]

  gains = flex.double()

  for i, pixel in enumerate(pixels):
    #print i
    start_row = min(start_row, pixel[0])
    end_row = max(end_row, pixel[0])
    n_photons = 0
    if results is None:
      # i.e. not multiprocessing
      try:
        gaussians = pixel_histograms.fit_one_histogram(pixel)
      except RuntimeError, e:
        print "Error fitting pixel %s" %pixel
        print str(e)
        mask[pixel] = 1
        continue
    else:
      gaussians = results[i]
    hist = pixel_histograms.histograms[pixel]
    if gaussians is None:
      # Presumably the peak fitting failed in some way
      print "Skipping pixel %s" %str(pixel)
      continue
    zero_peak_diff = gaussians[0].params[1]
    if gain_map is None:
      if len(gaussians) < 2:
        print "bad pixel!!!!!", pixel
        mask[pixel] = 1
        continue
      gain = gaussians[1].params[1] - gaussians[0].params[1]
      if 0 and estimated_gain is not None and abs(gain - estimated_gain) > 0.5 * estimated_gain:
        print "bad gain!!!!!", pixel, gain
        mask[pixel] = 1
        continue
      elif gaussians[1].sigma < (0.5 * gaussians[0].sigma):
        print "bad sigma!!!!!", pixel, gaussians[1].sigma
        mask[pixel] = 1
        continue
      elif gain < (4 * gaussians[0].sigma):
        print "bad gain!!!!!", pixel, gain
        mask[pixel] = 1
        continue
      elif gain > (20 * gaussians[0].sigma): # XXX is 20 to low?
        print "bad gain!!!!!", pixel, gain
        mask[pixel] = 1
        continue
      gain_img[pixel] = gain
      gain_ratio = gain/estimated_gain
    else:
      gain = gain_map[pixel]
      if gain == 0:
        print "bad gain!!!!!", pixel
        continue
      gain_ratio = 1/gain
    gains.append(gain)
    #for g in gaussians:
      #sigma = abs(g.params[2])
      #if sigma < 1 or sigma > 10:
        #print "bad sigma!!!!!", pixel, sigma
        #mask[pixel] = 1
        #continue
    if method == "sum_adu":
      #print "summing adus"
      sum_adu = 0
      one_photon_cutoff, two_photon_cutoff = [
        (threshold * gain + zero_peak_diff)
        for threshold in (photon_threshold, two_photon_threshold)]
      i_one_photon_cutoff = hist.get_i_slot(one_photon_cutoff)
      slots = hist.slots().as_double()
      slot_centers = hist.slot_centers()
      slots -= gaussians[0](slot_centers)
      for j in range(i_one_photon_cutoff, len(slots)):
        center = slot_centers[j]
        sum_adu += slots[j] * (center - zero_peak_diff) * 30/gain
      sum_img[pixel] = sum_adu
    elif method == "photon_counting":
      #print "counting photons"
      one_photon_cutoff, two_photon_cutoff = [
        (threshold * gain + zero_peak_diff)
        for threshold in (photon_threshold, two_photon_threshold)]
      #print "cutoffs: %s %.2f, %.2f" %(pixel, one_photon_cutoff, two_photon_cutoff)
      i_one_photon_cutoff = hist.get_i_slot(one_photon_cutoff)
      i_two_photon_cutoff = hist.get_i_slot(two_photon_cutoff)
      slots = hist.slots()
      for j in range(i_one_photon_cutoff, len(slots)):
        if j == i_one_photon_cutoff:
          center = hist.slot_centers()[j]
          upper = center + 0.5 * hist.slot_width()
          n_photons += int(round((upper - one_photon_cutoff)/hist.slot_width() * slots[j]))
        elif j == i_two_photon_cutoff:
          center = hist.slot_centers()[j]
          upper = center + 0.5 * hist.slot_width()
          n_photons += 2 * int(round((upper - two_photon_cutoff)/hist.slot_width() * slots[j]))
        elif j < i_two_photon_cutoff:
          n_photons += int(round(slots[j]))
        else:
          n_photons += 2 * int(round(slots[j]))
      sum_img[pixel] = n_photons

  stats = scitbx.math.basic_statistics(gains)
  print "gain statistics:"
  stats.show()

  mask.set_selected(sum_img == 0, 1)
  unbound_pixel_mask = xes_finalise.cspad_unbound_pixel_mask()
  mask.set_selected(unbound_pixel_mask > 0, 1)

  for row in range(sum_img.all()[0]):
    sum_img[row:row+1,:].count(0)

  spectrum_focus = sum_img[start_row:end_row,:]
  mask_focus = mask[start_row:end_row,:]

  print "Estimated no. photons counted: %i" %flex.sum(spectrum_focus)

  d = cspad_tbx.dpack(
    data=spectrum_focus,
    distance=1,
    ccd_image_saturation=2e8, # XXX
  )
  cspad_tbx.dwritef(d, output_dirname, 'sum_')

  if gain_map is None:
    gain_map = flex.double(gain_img.accessor(), 0)
    img_sel = (gain_img > 0).as_1d()
    d = cspad_tbx.dpack(
      data=gain_img,
      distance=1
    )
    cspad_tbx.dwritef(d, output_dirname, 'raw_gain_map_')
    gain_map.as_1d().set_selected(img_sel.iselection(), 1/gain_img.as_1d().select(img_sel))
    gain_map /= flex.mean(gain_map.as_1d().select(img_sel))
    d = cspad_tbx.dpack(
      data=gain_map,
      distance=1
    )
    cspad_tbx.dwritef(d, output_dirname, 'gain_map_')

  xes_finalise.output_spectrum(spectrum_focus.iround(), mask_focus=mask_focus,
                               output_dirname=output_dirname)

  xes_finalise.output_matlab_form(spectrum_focus, "%s/sum.m" %output_dirname)


if __name__ == '__main__':
  run(sys.argv[1:])
