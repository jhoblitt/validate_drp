# LSST Data Management System
# Copyright 2008-2016 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.
"""Miscellaneous functions to support lsst.validate.drp."""

from __future__ import print_function, division

import os
import math

import numpy as np
import scipy.stats
import yaml

import lsst.daf.persistence as dafPersist
import lsst.pipe.base as pipeBase
import lsst.afw.geom as afwGeom
import lsst.afw.coord as afwCoord


def averageRaDec(ra, dec):
    """Calculate average RA, Dec from input lists using spherical geometry.

    Parameters
    ----------
    ra : list of float
        RA in [radians]
    dec : list of float
        Dec in [radians]

    Returns
    -------
    float, float
       meanRa, meanDec -- Tuple of average RA, Dec [radians]
    """
    assert(len(ra) == len(dec))

    angleRa = [afwGeom.Angle(r, afwGeom.radians) for r in ra]
    angleDec = [afwGeom.Angle(d, afwGeom.radians) for d in dec]
    coords = [afwCoord.IcrsCoord(ar, ad) for (ar, ad) in zip(angleRa, angleDec)]

    meanRa, meanDec = afwCoord.averageCoord(coords)

    return meanRa.asRadians(), meanDec.asRadians()


def averageRaDecFromCat(cat):
    return averageRaDec(cat.get('coord_ra'), cat.get('coord_dec'))


def getCcdKeyName(dataid):
    """Return the key in a dataId that's referring to the CCD or moral equivalent.

    Parameters
    ----------
    dataid : dict
        A dictionary that will be searched for a key that matches
        an entry in the hardcoded list of possible names for the CCD field.

    Notes
    -----
    Motiviation: Different camera mappings use different keys to indicate
      the different amps/ccds in the same exposure.  This function looks
      through the reference dataId to locate a field that could be the one.
    """
    possibleCcdFieldNames = ['ccd', 'ccdnum', 'camcol']

    for name in possibleCcdFieldNames:
        if name in dataid:
            return name
    else:
        return 'ccd'


def repoNameToPrefix(repo):
    """Generate a base prefix for plots based on the repo name.

    Examples
    --------
    >>> repoNameToPrefix('a/b/c')
    'a_b_c_'
    >>> repoNameToPrefix('/bar/foo/')
    'bar_foo_'
    >>> repoNameToPrefix('CFHT/output')
    'CFHT_output_'
    >>> repoNameToPrefix('./CFHT/output')
    'CFHT_output_'
    >>> repoNameToPrefix('.a/CFHT/output')
    'a_CFHT_output_'
    """

    return repo.lstrip('\.').strip(os.sep).replace(os.sep, "_") + "_"


def discoverDataIds(repo, **kwargs):
    """Retrieve a list of all dataIds in a repo.

    Parameters
    ----------
    repo : str
        Path of a repository with 'src' entries.

    Returns
    -------
    list
        dataIds in the butler that exist.

    Notes
    -----
    May consider making this an iterator if large N becomes important.
    However, will likely need to know things like, "all unique filters"
    of a data set anyway, so would need to go through chain at least once.
    """
    butler = dafPersist.Butler(repo)
    thisSubset = butler.subset(datasetType='src', **kwargs)
    # This totally works, but would be better to do this as a TaskRunner?
    dataIds = [dr.dataId for dr in thisSubset
               if dr.datasetExists(datasetType='src') and dr.datasetExists(datasetType='calexp')]
    # Make sure we have the filter information
    for dId in dataIds:
        response = butler.queryMetadata(datasetType='src', format=['filter'], dataId=dId)
        filterForThisDataId = response[0]
        dId['filter'] = filterForThisDataId

    return dataIds


def loadParameters(configFile):
    """Load configuration parameters from a yaml file.

    Parameters
    ----------
    configFile : str
        YAML file that stores visit, filter, ccd,
        good_mag_limit, medianAstromscatterRef, medianPhotoscatterRef, matchRef
        and other parameters

    Returns
    -------
    pipeBase.Struct
        with configuration parameters
    """
    with open(configFile, mode='r') as stream:
        data = yaml.load(stream)

    return pipeBase.Struct(**data)


def loadDataIdsAndParameters(configFile):
    """Load data IDs, magnitude range, and expected metrics from a yaml file.

    Parameters
    ----------
    configFile : str
        YAML file that stores visit, filter, ccd,
        and additional configuration parameters such as
        brightSnr, medianAstromscatterRef, medianPhotoscatterRef, matchRef

    Returns
    -------
    pipeBase.Struct
        with attributes of
        dataIds - dict
        and configuration parameters
    """
    parameters = loadParameters(configFile).getDict()

    ccdKeyName = getCcdKeyName(parameters)
    try:
        dataIds = constructDataIds(parameters['filter'], parameters['visits'],
                                   parameters[ccdKeyName], ccdKeyName)
    except KeyError:
        # If the above parameters are not in the `parameters` dict,
        # presumably because they were not in the configFile
        # then we return no dataIds.
        dataIds = []

    return pipeBase.Struct(dataIds=dataIds, **parameters)


def constructDataIds(filters, visits, ccds, ccdKeyName='ccd'):
    """Returns a list of dataIds consisting of every combination of visit & ccd for each filter.

    Parameters
    ----------
    filters : str or list
        If str, will be interpreted as one filter to be applied to all visits.
    visits : list of int
    ccds : list of int
    ccdKeyName : str, optional
        Name to distinguish different parts of a focal plane.
        Generally 'ccd', but might be 'ccdnum', or 'amp', or 'ccdamp'.
        Refer to your `obs_*/policy/*Mapper.paf`.

    Returns
    -------
    list
        dataIDs suitable to be used with the LSST Butler.

    Examples
    --------
    >>> dataIds = constructDataIds('r', [100, 200], [10, 11, 12])
    >>> print(dataIds)
    [{'filter': 'r', 'visit': 100, 'ccd': 10}, {'filter': 'r', 'visit': 100, 'ccd': 11}, {'filter': 'r', 'visit': 100, 'ccd': 12}, {'filter': 'r', 'visit': 200, 'ccd': 10}, {'filter': 'r', 'visit': 200, 'ccd': 11}, {'filter': 'r', 'visit': 200, 'ccd': 12}]
    """
    if isinstance(filters, str):
        filters = [filters for _ in visits]

    assert len(filters) == len(visits)
    dataIds = [{'filter': f, 'visit': v, ccdKeyName: c}
               for (f, v) in zip(filters, visits)
               for c in ccds]

    return dataIds


def loadRunList(configFile):
    """Load run list from a YAML file.

    Parameters
    ----------
    configFile : str
        YAML file that stores visit, filter, ccd,

    Returns
    -------
    list
        run list lines.

    Examples
    --------
    An example YAML file would include entries of (for some CFHT data)
        visits: [849375, 850587]
        filter: 'r'
        ccd: [12, 13, 14, 21, 22, 23]
    or (for some DECam data)
        visits: [176837, 176846]
        filter: 'z'
        ccdnum: [10, 11, 12, 13, 14, 15, 16, 17, 18]

    Note 'ccd' for CFHT and 'ccdnum' for DECam.  These entries will be used to build
    dataIds, so these fields should be as the camera mapping defines them.

    `visits` and `ccd` (or `ccdnum`) must be lists, even if there's only one element.
    """
    stream = open(configFile, mode='r')
    data = yaml.load(stream)

    ccdKeyName = getCcdKeyName(data)
    runList = constructRunList(data['filter'], data['visits'],
                               data[ccdKeyName], ccdKeyName=ccdKeyName)

    return runList


def constructRunList(filter, visits, ccds, ccdKeyName='ccd'):
    """Construct a comprehensive runList for processCcd.py.

    Parameters
    ----------
    filter : str or list
    visits : list of int
    ccds : list of int

    Returns
    -------
    list
        list of strings suitable to be used with the LSST Butler.

    Examples
    --------
    >>> runList = constructRunList([100, 200], 'r', [10, 11, 12])
    >>> print(runList)
    ['--id visit=100 ccd=10^11^12', '--id visit=200 ccd=10^11^12']
    >>> runList = constructRunList([100, 200], 'r', [10, 11, 12], ccdKeyName='ccdnum')
    >>> print(runList)
    ['--id visit=100 ccdnum=10^11^12', '--id visit=200 ccdnum=10^11^12']

    Note
    -----
    The LSST parsing convention is to use '^' as list separators
        for arguments to `--id`.  While surprising, this convention
        allows for CCD names to include ','.  E.g., 'R1,2'.
    Currently ignores `filter` because `visit` should be unique w.r.t filter.
    """
    runList = ["--id visit=%d %s=%s" % (v, ccdKeyName, "^".join([str(c) for c in ccds]))
               for v in visits]

    return runList


def calcOrNone(func, x, ErrorClass, **kwargs):
    """Calculate the `func` and return result.  If it raises ErrorClass, return None."""
    try:
        out = func(x, **kwargs)
    except ErrorClass as e:
        print(e)
        out = None

    return out


def getRandomDiffRmsInMas(array):
    """Calculate the RMS difference in mmag between a random pairs of magnitudes.

    Input
    -----
    array : list or np.array
        Magnitudes from which to select the pair  [mag]

    Returns
    -------
    float
        RMS difference

    Notes
    -----
    The LSST SRD recommends computing repeatability from a histogram of
    magnitude differences for the same star measured on two visits
    (using a median over the magDiffs to reject outliers).
    Because we have N>=2 measurements for each star, we select a random
    pair of visits for each star.  We divide each difference by sqrt(2)
    to obtain RMS about the (unknown) mean magnitude,
    instead of obtaining just the RMS difference.

    See Also
    --------
    getRandomDiff : Get the difference

    Examples
    --------
    >>> mag = [24.2, 25.5]
    >>> rms = getRandomDiffRmsInMas(mag)
    >>> print(rms)
    212.132034
    """
    # For scalars, math.sqrt is several times faster than numpy.sqrt.
    return (1000/math.sqrt(2)) * getRandomDiff(array)


def getRandomDiff(array):
    """Get the difference between two randomly selected elements of an array.

    Input
    -----
    array : list or np.array

    Returns
    -------
    float or int
        Difference between two random elements of the array.

    Notes
    -----
    * As implemented the returned value is the result of subtracting
        two elements of the input array.  In all of the imagined uses
        that's going to be a scalar (float, maybe int).
        In principle, however the code as implemented returns the result
        of subtracting two elements of the array, which could be any
        arbitrary object that is the result of the subtraction operator
        applied to two elements of the array.
    * This is not the most efficient way to extract a pair,
        but it's the easiest to write.
    * Shuffling works correctly for low N (even N=2), where a naive
        random generation of entries would result in duplicates.
    * In principle it might be more efficient to shuffle the indices,
        then extract the difference.  But this probably only would make a
        difference for arrays whose elements were objects that were
        substantially larger than a float.  And that would only make
        sense for objects that had a subtraction operation defined.
    """
    copy = array.copy()
    np.random.shuffle(copy)
    return copy[0] - copy[1]


def computeWidths(array):
    """Compute the RMS and the scaled inter-quartile range of an array.

    Input
    -----
    array : list or np.array

    Returns
    -------
    float, float
        RMS and scaled inter-quartile range (IQR).

    Notes
    -----
    We estimate the width of the histogram in two ways:
       using a simple RMS,
       using the interquartile range (IQR)
    The IQR is scaled by the IQR/RMS ratio for a Gaussian such that it
       if the array is Gaussian distributed, then the scaled IQR = RMS.
    """
    rmsSigma = math.sqrt(np.mean(array**2))
    iqrSigma = np.subtract.reduce(np.percentile(array, [75, 25])) / (scipy.stats.norm.ppf(0.75)*2)
    return rmsSigma, iqrSigma
