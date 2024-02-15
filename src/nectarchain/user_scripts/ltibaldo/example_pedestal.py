import logging
import os
import pathlib

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)
log.handlers = logging.getLogger("__main__").handlers

from nectarchain.makers.calibration import (
    PedestalNectarCAMCalibrationTool,
)

run_number = 3938
max_events= 100
outfile = "/Users/ltibaldo/tmp/test_pedestal/pedestal_{}.h5".format(run_number)

tool = PedestalNectarCAMCalibrationTool(
    progress_bar=True,
    run_number=run_number,
    max_events=max_events,
    log_level=20,
    reload_events=False,
    output_path=outfile,
    overwrite = True,
    ucts_tmin = 1674462932650000000,
    filter_method = "ChargeDistributionFilter",
)

tool.initialize()
tool.setup()

tool.start()
output = tool.finish(return_output_component=True)