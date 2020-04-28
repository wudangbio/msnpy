#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2019-2020 Ralf Weber
#
# This file is part of MSnPy.
#
# MSnPy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MSnPy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MSnPy.  If not, see <https://www.gnu.org/licenses/>.
#


import itertools
import os
import re

import numpy as np
from dimspy.models.peaklist import PeakList
from dimspy.portals.hdf5_portal import save_peaklists_as_hdf5
from dimspy.process.peak_alignment import align_peaks
from six import iteritems

from .portals import load_trees


def get_mf_details(pd: dict):

    mf_details_mass = []
    mf_details_adduct = []
    mf_details_mf = []

    for mfid, mfd in iteritems(pd['mf']):
        mf_details_mass.append(mfd['mass'])
        mf_details_adduct.append(mfd['adduct'])
        mf_details_mf.append(mfd['mf'])

    mf_details = {}
    mf_details['mass'] = np.median(mf_details_mass)
    mf_details['adduct'] = ','.join(mf_details_adduct)
    mf_details['mf'] = ','.join(mf_details_mf)

    return mf_details


def sort_lists(l1, *argv):
    lall = [l1]
    for l in argv:
        lall.append(l)
    return zip(*sorted(zip(*lall)))


def tree2peaklist(tree_pth, adjust_mz=True, merge=True, ppm=5, ms1=True, skip_sim=True,
                  out_pth='', name=''):
    ###########################################################################
    # Extract peaklists from msnpy
    ###########################################################################
    trees = load_trees(tree_pth)
    plsd = {}
    all_ms1_precursors = {}
    convert_id = 1

    # get peaklist for each header
    for tree in trees:

        plsd[tree.graph['id']] = []

        # For each tree we look at each "header" e.g. the same mass
        # spectrometry data (processed prior by dimspy-msnpy)
        # And create a peaklist for each header. (....probably a better way
        # of doing this perhaps iterating through
        # the tree instead?). Anyway this seems to work OK.
        its = tree.nodes.items()
        # add id to tree values
        [i[1].update({'id': i[0]}) for i in its]
        tv = [i[1] for i in its]
        # requires sorting for itertools.groupby to work properly
        tv = sorted(tv, key=lambda i: i['header'])

        for header, group in itertools.groupby(tv, key=lambda x: x['header']):
            # get mz, intensity, mass, molecular formula, adduct
            mtch = re.search('(.*Full ms .*)|(.*SIM ms.*)', header)
            if mtch:
                # full scan or sim window (we do not process)
                continue

            precursor_detail_track = []

            mz = []
            intensity = []
            mass = []
            mf = []
            adduct = []

            metad = {'tree_id': tree.graph['id'],
                     'header': header,
                     'parent': {}}

            for d in list(group):

                metad['mslevel'] = d['mslevel']

                # get precursor details for each level
                for n in tree.predecessors(d['id']):

                    pd = tree.nodes.get(n)

                    # check if we already have this precursor details
                    #if pd['mslevel'] in precursor_detail_track:
                    #    continue

                    metad['parent'][pd['mslevel']] = {}
                    metad['parent'][pd['mslevel']]['mz'] = pd['mz']
                    metad['parent'][pd['mslevel']]['ID'] = "{} {}".format(
                        tree.graph['id'], pd['header'])

                    if 'mf' in pd:
                        mf_details_p = get_mf_details(pd)
                        metad['parent'][pd['mslevel']]['mass'] = mf_details_p['mass']
                        metad['parent'][pd['mslevel']]['adduct'] = mf_details_p['adduct']
                        metad['parent'][pd['mslevel']]['mf'] = mf_details_p['mf']

                    precursor_detail_track.append(pd['mslevel'])

                    if ms1:

                        all_ms1_precursors[pd['mz']] = pd['intensity']

                mz.append(d['mz'])
                intensity.append(d['intensity'])

                if 'mf' in d:
                    mf_details = get_mf_details(d)
                    mass.append(mf_details['mass'])
                    mf.append(mf_details['mf'])
                    adduct.append(mf_details['adduct'])

            if len(mz)<1:
                continue

            if adjust_mz:
                mza = mass
            else:
                mza = mz

            # create dimspy array object
            if mf:
                mza, intensity, mass, mf, adduct = sort_lists(mza, intensity, mass, mf, adduct)
            else:
                mza, intensity = sort_lists(mza, intensity)

            pl = PeakList(ID='{} {}'.format(tree.graph['id'], header),
                          mz=mza,
                          intensity=intensity,
                          **metad)

            pl.metadata['convert_id'] = convert_id
            convert_id += 1

            if mf:
                pl.add_attribute('mass', mass)
                pl.add_attribute('mz_original', mz)
                pl.add_attribute('mf', mf)
                pl.add_attribute('adduct', adduct)

            plsd[tree.graph['id']].append(pl)

    pls = [y for x in list(plsd.values()) for y in x]

    if out_pth:
        save_peaklists_as_hdf5(pls, os.path.join(out_pth, '{}_non_merged_pls.hdf5'.format(name)))

    # Merge
    if merge:
        merged_pls = []
        for (key, plsi) in iteritems(plsd):

            if not plsi:
                continue
            merged_id = "<#>".join([pl.ID for pl in plsi])
            pm = align_peaks(plsi, ppm=ppm)
            plm = pm.to_peaklist(ID=merged_id)
            plm.metadata['parent'] = {1: plsi[0].metadata['parent'][1]}

            plm.metadata['convert_id'] = convert_id
            convert_id += 1

            merged_pls.append(plm)

        if out_pth:
            save_peaklists_as_hdf5(merged_pls, os.path.join(out_pth, '{}_merged_pls.hdf5'.format(name)))
    else:
        merged_pls = ''

    if ms1:
        mz, intensity = sort_lists(list(all_ms1_precursors.keys()), list(all_ms1_precursors.values()))
        default_values = [1]*len(mz)
        ms1_precursors_pl = [PeakList(ID='ms1_precursors', mz=mz,
                                      intensity=intensity,
                                      )]
        ms1_precursors_pl[0].add_attribute('present', default_values)
        ms1_precursors_pl[0].add_attribute('fraction', default_values)
        ms1_precursors_pl[0].add_attribute('occurrence', default_values)
        ms1_precursors_pl[0].add_attribute('purity', default_values)

        ms1_precursors_pl[0].metadata['convert_id'] = convert_id

        if out_pth:
            save_peaklists_as_hdf5(ms1_precursors_pl, os.path.join(out_pth, '{}_ms1_precursors_pl.hdf5'.format(name)))
    else:
        ms1_precursors_pl = ''

    return pls, merged_pls, ms1_precursors_pl



def peaklist2msp(pls, out_pth, msp_type='massbank', polarity='positive', msnpy_annotations=True, include_ms1=False):

    msp_params = {}

    if msp_type == 'massbank':
        msp_params['name'] = 'RECORD_TITLE:'
        msp_params['polarity'] = 'AC$MASS_SPECTROMETRY: ION_MODE'
        msp_params['precursor_mz'] = 'MS$FOCUSED_ION: PRECURSOR_M/Z '
        msp_params['precursor_type'] = 'MS$FOCUSED_ION: PRECURSOR_TYPE'
        msp_params['num_peaks'] = 'PK$NUM_PEAK:'
        msp_params['cols'] = 'PK$PEAK: m/z int. rel.int.'
        msp_params['ms_level'] = 'AC$MASS_SPECTROMETRY: MS_TYPE '
        msp_params['resolution'] = 'AC$MASS_SPECTROMETRY: RESOLUTION '
        msp_params['fragmentation_mode'] = 'AC$MASS_SPECTROMETRY: FRAGMENTATION_MODE'
        msp_params['collision_energy'] = 'AC$MASS_SPECTROMETRY: COLLISION_ENERGY'
        msp_params['mf'] = 'CH$FORMULA:'
    else:
        msp_params['name'] = 'NAME:'
        msp_params['polarity'] = 'POLARITY:'
        msp_params['precursor_mz'] = 'PRECURSOR_MZ:'
        msp_params['precursor_type'] = 'PRECURSOR_TYPE:'
        msp_params['num_peaks'] = 'Num Peaks:'
        msp_params['cols'] = ''
        msp_params['ms_level'] = 'MS_LEVEL:'
        msp_params['resolution'] = 'RESOLUTION:'
        msp_params['fragmentation_mode'] = 'FRAGMENTATION_MODE:'


    with open(out_pth, "w+") as f:
        # Loop through peaklist
        idi = 0
        for pl in pls:
            idi += 1
            dt = pl.dtable[pl.flags]
            if dt.shape[0] == 0:
                continue

            if not include_ms1 and (re.search('.*Full ms .*', pl.ID) and ms_level == 1):
                continue
            if 'convert_id' in pl.metadata:
                convert_id = pl.metadata['convert_id']
            else:
                convert_id = idi
            f.write('{} header {} | msnpy_convert_id {}\n'.format(msp_params['name'], pl.ID, convert_id))
            f.write('msnpy_convert_id: {}\n'.format(convert_id))
            f.write('{} {}\n'.format(msp_params['polarity'], polarity))

            if msnpy_annotations and not include_ms1:
                if pl.metadata['parent']:
                    parent_metadata = pl.metadata['parent'][min(pl.metadata['parent'].keys())]
                    f.write('{} {}\n'.format(msp_params['precursor_mz'], parent_metadata['mz']))
                    if 'mf' in parent_metadata:
                        f.write('{} {}\n'.format(msp_params['precursor_type'], parent_metadata['adduct']))
                        f.write('{} {}\n'.format(msp_params['mf'], parent_metadata['mf']))

            else:
                mtch = re.search('.*Full ms(\d+).*', str(pl.ID))
                if mtch:
                    f.write('{} {}\n'.format(msp_params['ms_level'], mtch.group(1)))

                mtch = re.search('.*Full ms\d+ (.*) \[.*', pl.ID)
                if mtch:
                    dl = mtch.group(1).split(" ")
                    # get the last detail
                    detail = dl[-1]
                    mtch = re.search('(\d+.\d+)@(\D+)(.*)', detail)
                    if mtch:
                        f.write('{} {}\n'.format(msp_params['precursor_mz'], mtch.group(1)))

            mtch = re.findall('\d+.\d+@(\D+)(\d+.\d+)', pl.ID)
            if mtch:
                mtchz = list(zip(*mtch))
                ce = sorted(set(mtchz[1]))
                f.write('{} {}\n'.format(msp_params['fragmentation_mode'], ', '.join(set(mtchz[0]))))
                f.write('{} {}\n'.format(msp_params['collision_energy'], ', '.join(ce)))



            mz = dt['mz']
            intensity = dt['intensity']
            ra = dt['intensity'] / np.max(dt['intensity']) * 100

            if msp_type == 'massbank':
                if 'mf' in dt.dtype.names:
                    mf = dt['mf']
                    adduct = dt['adduct']
                    mass = dt['mass']
                    f.write('PK$ANNOTATION: m/z tentative_formula formula_count adduct\n')

                    for i in range(0, len(mz)):
                        f.write('{}\t{}\t{}\n'.format(mz[i], mf[i], mass[i], adduct[i]))

            f.write('{} {}\n'.format(msp_params['num_peaks'], dt.shape[0]))

            if msp_params['cols']:
                f.write('{}\n'.format(msp_params['cols']))

            for i in range(0, len(mz)):
                if msp_type == 'massbank':
                    f.write('{}\t{}\t{}\n'.format(mz[i], intensity[i], ra[i]))
                else:
                    f.write('{}\t{}\n'.format(mz[i], ra[i]))
            f.write('\n')
