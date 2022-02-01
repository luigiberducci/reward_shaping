from reward_shaping.core.helper_fns import DefaultReward

_registry = {}


def get_reward(name: str):
    return _registry[name]


def register_reward(name: str, reward):
    if name not in _registry.keys():
        _registry[name] = reward


# Baselines
register_reward('default', reward=DefaultReward)

# TL-based
#register_reward('tltl', reward=CPOSTLReward)  # evaluation on complete episode
#register_reward('bhnr', reward=CPOSTLReward)  # evaluation with a moving window

# Multi-objectivization solved via linear scalarization
#register_reward('morl_uni', reward=CPOUniformScalarizedMultiObjectivization)
#register_reward('morl_dec', reward=CPODecreasingScalarizedMultiObjectivization)

# Hierarchical Potential Shaping
#register_reward('hrs_pot', reward=CPOHierarchicalPotentialShaping)

# Evaluation
#
register_reward('eval', reward=...)