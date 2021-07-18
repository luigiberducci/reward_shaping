from collections import defaultdict
from time import sleep
from typing import List, Callable, Tuple

import networkx as nx
import numpy as np
import matplotlib.pyplot as plt


class HierarchicalGraph(nx.DiGraph):
    """
        It is a DAG where each node has associated:
            - a score function (s: S->R),
            - an valuation function (v: S->B).
        The reward is then defined as the sum of scores of enabled nodes.
        A node is enabled iff FORALL parents p . p.v(state) == True.
    """

    def __init__(self, labels: List[str], score_functions: List[Callable[..., float]],
                 val_functions: List[Callable[..., bool]], edge_list: List[Tuple[str, str]]):
        super(HierarchicalGraph, self).__init__()
        assert len(set(labels)) == len(labels), \
            f"labels must be unique identifiers, {labels}"
        assert all([e[0] in labels and e[1] in labels for e in edge_list]), \
            f"edge list must only use existing labels, {edge_list}"
        # define nodes
        self.labels = np.array(labels)
        self.score = score_functions
        self.valuation = val_functions
        self.add_nodes_from(self.labels)
        # define edges
        self.add_edges_from(edge_list)
        assert nx.is_directed_acyclic_graph(self)
        # utilities
        self.lab2id = {l: n for n, l in enumerate(labels)}
        self.id2lab = {n: l for n, l in enumerate(labels)}
        # topological sort
        self.top_sorting = list(nx.topological_sort(self))
        layers = {}
        for node in self.top_sorting:
            preds = list(self.predecessors(node))
            if len(preds) == 0:
                layers[node] = 0
            else:
                layers[node] = max([layers[pred] for pred in preds]) + 1
        nx.set_node_attributes(self, layers, "layer")

    def render(self, colors=None):
        positioning = nx.multipartite_layout(self, subset_key="layer")
        pos_labels = {node: (pos[0], pos[1] - .1) for node, pos in positioning.items()}
        if colors is None:
            nx.draw(self, pos=positioning)
        else:
            plt.clf()
            color_map = {color: [] for color in colors.values()}
            for node, color in colors.items():
                color_map[color].append(node)
            for color, node_list in color_map.items():
                nx.draw_networkx_nodes(self, positioning, nodelist=node_list, node_color=color)
        nx.draw_networkx_edges(self, positioning)
        nx.draw_networkx_labels(self, pos_labels)
        plt.pause(0.001)

def test_1():
    expected_result = False
    try:
        labels = ["a", "b", "c", "a"]
        f = lambda x: 0
        v = lambda x: False
        scores = [f] * len(labels)
        values = [v] * len(labels)
        edges = []
        g = HierarchicalGraph(labels, scores, values, edges)
        result = True
    except Exception as e:
        print(e)
        result = False
    return result == expected_result


def test_2():
    expected_result = False
    try:
        labels = ["a", "b", "c"]
        f = lambda x: 0
        v = lambda x: True
        scores = [f] * len(labels)
        values = [v] * len(labels)
        edges = [("a", "b"), ("a", "d")]
        g = HierarchicalGraph(labels, scores, values, edges)
        result = True
    except Exception as e:
        print(e)
        result = False
    return result == expected_result


def test_3():
    expected_result = True
    try:
        labels = ["S1", "S2", "S3", "T1", "C1"]
        f = lambda x: 0
        v = lambda x: True
        scores = [f] * len(labels)
        values = [v] * len(labels)
        edges = [("S1", "T1"), ("S2", "T1"), ("S3", "T1"), ("T1", "C1")]
        g = HierarchicalGraph(labels, scores, values, edges)
        g.render()
        result = True
    except Exception as e:
        print(e)
        result = False
    return result == expected_result


def test_4():
    expected_result = True
    try:
        labels = ["S1", "S2", "S3", "T1", "C1"]
        f = lambda x: 0
        v = lambda x: True
        scores = [f] * len(labels)
        values = [v] * len(labels)
        edges = [("S1", "T1"), ("S2", "T1"), ("S3", "T1"), ("T1", "C1")]
        g = HierarchicalGraph(labels, scores, values, edges)
        print("Topological Sorting: ", g.top_sorting)
        result = True
    except Exception as e:
        print(e)
        result = False
    return result == expected_result


if __name__ == "__main__":
    tests = [test_1, test_2, test_3, test_4]
    for i, test in enumerate(tests):
        result = test()
        print(f"Test {i}: {result}\n")