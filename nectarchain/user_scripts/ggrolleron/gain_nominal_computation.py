import logging
import sys
import os
from pathlib import Path
import pandas as pd
import time

#import pandas as pd
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import getopt
os.makedirs(os.environ.get('NECTARCHAIN_LOG'),exist_ok = True)

#to quiet numba
logging.getLogger("numba").setLevel(logging.WARNING)

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',level=logging.INFO,filename = f"{os.environ.get('NECTARCHAIN_LOG')}/{Path(__file__).stem}_{os.getpid()}.log")
log = logging.getLogger(__name__)
##tips to add message to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

import argparse
import json

#import seaborn as sns
from nectarchain.calibration.container import ChargeContainer
from nectarchain.calibration.NectarGain import NectarGainSPESingleSignalStd,NectarGainSPESingleSignal,NectarGainSPESinglePed,NectarGainSPECombinedNoPed,NectarGainSPESingleSignalfromHHVFit

parser = argparse.ArgumentParser(
                    prog = 'gain_nominal_computation.py',
                    description = 'compute high gain with SPE fit for one run at nominal voltage')

#run numbers
parser.add_argument('-r', '--run_number',
                    help='spe run',
                    type=int)

parser.add_argument('--overwrite',
                    action='store_true',
                    default=False,
                    help='to force overwrite files on disk'
                    )
parser.add_argument('--reduced',
                    action='store_true',
                    default=False,
                    help='to use reduced run'
                    )

#pixels selected
parser.add_argument('-p','--pixels',
                    nargs="+",
                    default=None,
                    help='pixels selected',
                    type=int)


#multiprocessing args
parser.add_argument('--multiproc',
                    action='store_true',
                    default=False,
                    help='to use multiprocessing'
                    )
parser.add_argument('--nproc',
                    help='nproc used for multiprocessing',
                    type=int)
parser.add_argument('--chunksize',
                    help='chunksize used for multiprocessing',
                    type=int)


#extractor arguments
parser.add_argument('--chargeExtractorPath',
                    help='charge extractor path where charges are saved',
                    type=str
                    )

#for VVH combined fit
parser.add_argument('--combined',
                    action='store_true',
                    default=False,
                    help='to perform a combined fit of VVH and nominal data'
                    )
parser.add_argument('--VVH_fitted_results',
                    help='previoulsy fitted VVH data path for nominal SPE fit by fixing some shared parameters',
                    type=str
                    )
parser.add_argument('--same_luminosity',
                    action='store_true',
                    default=False,
                    help='if luminosity for VVH and nominal data is the same'
                    )


def main(args) : 
    figpath = os.environ.get('NECTARCHAIN_FIGURES')

    reduced = "_reduced" if args.reduced else ""
    multipath = "MULTI-" if args.multiproc else ""

    charge_run = ChargeContainer.from_file(f"{os.environ.get('NECTARCAMDATA')}/charges{reduced}/{args.chargeExtractorPath}/",args.run_number)

    if args.combined : 
        raise NotImplementedError("combined fit not implemented yet")
    else : 
        gain_Std = NectarGainSPESingleSignalfromHHVFit(signal = charge_run,
                                    nectarGainSPEresult=args.VVH_fitted_results,
                                    same_luminosity=args.same_luminosity
                                    )
        t = time.time()
        gain_Std.run(pixel = args.pixels, multiproc = args.multiproc, nproc = args.nproc, chunksize = args.chunksize, figpath = figpath+f"/{multipath}nominal-SPEStd-{args.run_number}-{args.chargeExtractorPath}")
        log.info(f"fit time =  {time.time() - t } sec")
        gain_Std.save(f"{os.environ.get('NECTARCAMDATA')}/../SPEfit/data{reduced}/{multipath}nominal-SPEStd-{args.run_number}-{args.chargeExtractorPath}/",overwrite = args.overwrite)
        log.info(f"convergence rate : {len(gain_Std._output_table[gain_Std._output_table['is_valid']])/gain_Std.npixels}")

if __name__ == "__main__":
    args = parser.parse_args()
    main(args)