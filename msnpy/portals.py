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


from typing import Sequence

import networkx as nx
from networkx.readwrite import json_graph


def save_trees(trees: Sequence[nx.classes.ordered.OrderedDiGraph], filename: str, format: str = "json"):

    """

    :param trees:
    :param filename:
    :param format:
    :return:
    """

    with open(filename, "w") as out:
        for t in trees:
            tc = t.copy()  # required to not update Graph
            for i, e in enumerate(tc.edges()):
                tc[e[0]][e[1]]["order"] = i
            for i, n in enumerate(tc.nodes()):
                tc.nodes[n]["order"] = i
            if format == "json":
                out.write(str(nx.readwrite.json_graph.node_link_data(tc)) + "\n")
            elif format == "gml":
                for i, n in enumerate(tc.edges()):
                    if "mf" in tc[n[0]][n[1]]:
                        tc[n[0]][n[1]]["mf"] = str(tc[n[0]][n[1]]["mf"])
                for i, n in enumerate(tc.nodes()):
                    for k in ["scanids", "ioninjectiontimes", "mf", "coltype", "template"]:
                        if k in tc.nodes[n]:
                            tc.nodes[n][k] = str(tc.nodes[n][k])
                for line in nx.readwrite.generate_gml(tc):
                    out.write((line + "\n"))

            else:
                raise ValueError("Incorrect format - json or gml")


def load_trees(filename: str, format: str = "json"):

    """

    :param filename:
    :param format:
    :return:
    """

    def sort_graph(G_):
        G_sort = nx.OrderedDiGraph()
        G_sort.graph["id"] = G_.graph["id"]
        G_sort.add_nodes_from(sorted(G_.nodes(data=True), key=lambda x: x[1]['order']))
        G_sort.add_edges_from(sorted(G_.edges(data=True), key=lambda x: x[2]['order']))
        return G_sort

    def remove_attr(G_, atr):
        for n_ in G_.nodes():
            del G_.nodes[n_][atr]
        for e in G_.edges():
            del G_[e[0]][e[1]][atr]
        return G_

    with open(filename, "r") as inp:
        graphs = []
        if format == "json":
            for line in inp.readlines():
                G = json_graph.node_link_graph(eval(line))
                graphs.append(remove_attr(sort_graph(G), "order"))
            return graphs
        elif format == "gml":
            for gml_str in inp.read().split("graph")[1:]:
                G = nx.readwrite.parse_gml("graph" + gml_str)
                for n in G.nodes():
                    if "coltype" in G.nodes[n]:
                        if G.nodes[n]["coltype"] == "None":
                            G.nodes[n]["coltype"] = None
                    for k in ["scanids", "ioninjectiontimes", "mf", "template"]:
                        if k in G.nodes[n]:
                            G.nodes[n][k] = eval(G.nodes[n][k])
                graphs.append(remove_attr(sort_graph(G), "order"))
            return graphs
        else:
            raise ValueError("Incorrect graph format - json or gml")


def save_groups(groups: Sequence[nx.classes.ordered.OrderedDiGraph], filename: str, format: str = "json"):

    """

    :param groups:
    :param filename:
    :param format:
    :return:
    """

    save_trees(trees=groups, filename=filename, format=format)
    return


def load_groups(filename: str, format: str = "json"):

    """

    :param filename:
    :param format:
    :return:
    :rtype: list of NetworkX Graphs
    """

    return load_trees(filename=filename, format=format)

