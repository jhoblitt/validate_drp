from lsst.meas.astrom import ANetAstrometryTask
config.calibrate.astrometry.retarget(ANetAstrometryTask)

config.calibrate.astrometry.solver.sipOrder=3

config.calibrate.repair.cosmicray.nCrPixelMax=1000000
config.calibrate.photocal.fluxField='base_PsfFlux_flux'
config.calibrate.photocal.magLimit=20.0
config.calibrate.photocal.sigmaMax=0.05  # default 0.25
config.calibrate.photocal.applyColorTerms = False
config.calibrate.photocal.photoCatName="e2v"
config.calibrate.photocal.badFlags=['base_PixelFlags_flag_edge', 'base_PixelFlags_flag_interpolated', 'base_PixelFlags_flag_saturated', 'base_PixelFlags_flag_crCenter']