#!/usr/bin/env python

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

from __future__ import print_function, division

import os
import yaml

import lsst.afw.geom as afwGeom
import lsst.afw.coord as afwCoord


def averageRaDec(ra, dec):
    """Calculate average RA, Dec from input lists using spherical geometry.

    Inputs
    ------
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

def averageRaFromCat(cat):
    meanRa, meanDec = averageRaDecFromCat(cat)
    return meanRa

def averageDecFromCat(cat):
    meanRa, meanDec = averageRaDecFromCat(cat)
    return meanDec


def getCcdKeyName(dataid):
    """Return the key in a dataId that's referring to the CCD or moral equivalent.

    Inputs
    ------
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


def loadDataIdsAndParameters(configFile):
    """Load data IDs, magnitude range, and expected metrics from a yaml file.

    Inputs
    ------
    configFile : str
        YAML file that stores visit, filter, ccd,
        good_mag_limit, medianAstromscatterRef, medianPhotoscatterRef, matchRef

    Returns
    -------
    dict, float, float, float
        dataIds, good_mag_limit, medianRef, matchRef
    """
    stream = open(configFile, mode='r')
    data = yaml.load(stream)

    ccdKeyName = getCcdKeyName(data)
    visitDataIds = constructDataIds(data['filter'], data['visits'],
                                    data[ccdKeyName], ccdKeyName)

    return (visitDataIds,
            data['good_mag_limit'],
            data['medianAstromscatterRef'],
            data['medianPhotoscatterRef'],
            data['matchRef'],
           )


def constructDataIds(filter, visits, ccds, ccdKeyName='ccd'):
    """Returns a list of dataIds consisting of every combination of visit & ccd for each filter.

    Inputs
    ------
    filter : str
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

    Note
    -----
    Currently assumes `filter` is a scalar string, e.g., 'g' or 'r-1692 CFHT'.
    This isn't fundamentally necessary, but one would need to define logic
    such that filter="ugriz" and filter="r-1692 CFHT" are each processed correctly.
    """
    visitDataIds = [{'visit': v, 'filter': filter, ccdKeyName: c}
                    for v in visits
                    for c in ccds]

    return visitDataIds


def loadRunList(configFile):
    """Load run list from a YAML file.

    Inputs
    ------
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

    Inputs
    ------
    filter : str
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
    Currently ignores `filter`
    """
    runList = ["--id visit=%d %s=%s" % (v, ccdKeyName, "^".join([str(c) for c in ccds]))
               for v in visits]

    return runList


def calcOrNone(func, x, ErrorClass):
    """Calculate the `func` and return result.  If it raises ErrorClass, return None."""
    try:
        out = func(x)
    except ErrorClass as e:
        print(e)
        out = None

    return out
