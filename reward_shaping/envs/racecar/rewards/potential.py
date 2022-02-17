from typing import List

import numpy as np

from reward_shaping.core.reward import RewardFunction
from reward_shaping.core.utils import clip_and_norm
from reward_shaping.envs.f1tenth.specs import get_all_specs

gamma = 1.0


def safety_collision_potential(state, info):
    assert "wall_collision" in state
    return int(state["wall_collision"] <= 0.0)


def safety_reverse_potential(state, info):
    assert "wrong_way" in state
    return int(state["wrong_way"] <= 0.0)


def target_potential(state, info):
    assert "progress" in state
    return clip_and_norm(state["progress"], 0, info["progress_target"])


def comfort_speed_potential(state, info):
    assert "speed" in state and "norm_speed_limit" in info and "norm_max_speed" in info
    return 1.0 - clip_and_norm(state["speed"][0], info["norm_speed_limit"], info["norm_max_speed"])  # 0 > threshold


def comfort_steering_potential(state, info):
    assert "steering" in state and "norm_comf_steering" in info and "norm_max_steering" in info
    return 1.0 - clip_and_norm(abs(state["steering"][0]), info["norm_comf_steering"], info["norm_max_steering"])


def comfort_keep_right_potential(state, info):
    assert "dist_to_wall" in state and "comf_dist_to_wall" in info and "tolerance_margin" in info
    error_ref_dist = abs(state["dist_to_wall"][0] - info["comf_dist_to_wall"])
    return 1.0 - clip_and_norm(error_ref_dist, info["tolerance_margin"], 1.0)  # assume max cross-track error is 1.0 m


def simple_base_reward(state, info):
    assert "lap" in info
    base_reward = 1.0 if info["lap"] - 1 >= 0.001 else 0.0
    return base_reward


class RacecarHierarchicalPotentialShaping(RewardFunction):

    @staticmethod
    def _safety_potential(state, info):
        collision_reward = safety_collision_potential(state, info)
        reverse_reward = safety_reverse_potential(state, info)
        return collision_reward + reverse_reward

    def _target_potential(self, state, info):
        safety_w = safety_collision_potential(state, info) * safety_reverse_potential(state, info)
        return safety_w * target_potential(state, info)

    def _comfort_potential(self, state, info):
        comfort_speed = comfort_speed_potential(state, info)
        comfort_steering = comfort_steering_potential(state, info)
        comfort_keep_right = comfort_keep_right_potential(state, info)
        # hierarchical weights
        safety_w = safety_collision_potential(state, info) * safety_reverse_potential(state, info)
        target_w = target_potential(state, info)
        return safety_w * target_w * (comfort_speed + comfort_steering + comfort_keep_right)

    def __call__(self, state, action=None, next_state=None, info=None) -> float:
        # base reward
        base_reward = simple_base_reward(next_state, info)
        # shaping
        if info["done"]:
            return base_reward
        shaping_safety = gamma * self._safety_potential(next_state, info) - self._safety_potential(state, info)
        shaping_target = gamma * self._target_potential(next_state, info) - self._target_potential(state, info)
        shaping_comfort = gamma * self._comfort_potential(next_state, info) - self._comfort_potential(state, info)
        return base_reward + shaping_safety + shaping_target + shaping_comfort


class RacecarScalarizedMultiObjectivization(RewardFunction):

    def __init__(self, weights: List[float], **kwargs):
        assert len(weights) == len(get_all_specs()), f"nr weights ({len(weights)}) != nr reqs {len(get_all_specs())}"
        assert (sum(weights) - 1.0) <= 0.0001, f"sum of weights ({sum(weights)}) != 1.0"
        self._weights = weights

    def __call__(self, state, action=None, next_state=None, info=None) -> float:
        base_reward = simple_base_reward(next_state, info)
        if info["done"]:
            return base_reward
        # evaluate individual shaping functions
        shaping_coll = gamma * safety_collision_potential(next_state, info) - safety_collision_potential(state, info)
        shaping_reverse = gamma * safety_reverse_potential(next_state, info) - safety_reverse_potential(state, info)
        shaping_target = gamma * target_potential(next_state, info) - target_potential(state, info)
        shaping_comf_speed = gamma * comfort_speed_potential(next_state, info) - comfort_speed_potential(state, info)
        shaping_comf_steer = gamma * comfort_steering_potential(next_state, info) - comfort_steering_potential(state,
                                                                                                               info)
        shaping_comf_right = gamma * comfort_keep_right_potential(next_state, info) - comfort_keep_right_potential(state, info)
        # linear scalarization of the multi-objectivized requirements
        reward = base_reward
        for w, f in zip(self._weights,
                        [shaping_coll, shaping_reverse, shaping_target,
                         shaping_comf_speed, shaping_comf_steer, shaping_comf_right]):
            reward += w * f
        return reward


class RacecarUniformScalarizedMultiObjectivization(RacecarScalarizedMultiObjectivization):

    def __init__(self, **kwargs):
        weights = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        weights /= np.sum(weights)
        super(RacecarUniformScalarizedMultiObjectivization, self).__init__(weights=weights, **kwargs)


class RacecarDecreasingScalarizedMultiObjectivization(RacecarScalarizedMultiObjectivization):

    def __init__(self, **kwargs):
        weights = np.array([1.0, 1.0, 0.5, 0.25, 0.25, 0.25])
        weights /= np.sum(weights)
        super(RacecarDecreasingScalarizedMultiObjectivization, self).__init__(weights=weights, **kwargs)