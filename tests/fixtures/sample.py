import os
from collections import OrderedDict

class Foo:
    def bar(self, x):
        return helper(x)

def helper(x):
    return os.path.join(x)
