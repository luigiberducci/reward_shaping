import numpy as np
from lark import Transformer


class HPRSTransformer(Transformer):
    list = list

    def gt(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '>', float(val))

    def lt(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '<', float(val))

    def ge(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '>=', float(val))

    def le(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '<=', float(val))

    def eq(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '==', float(val))

    def ne(self, s):
        var, val = s
        var = var.replace('"', '')
        return (var, '!=', float(val))

    def number(self, n):
        (n,) = n
        return float(n)
