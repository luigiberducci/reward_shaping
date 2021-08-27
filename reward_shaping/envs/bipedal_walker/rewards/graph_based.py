from abc import ABC, abstractmethod
import reward_shaping.envs.bipedal_walker.rewards.subtask_rewards as fns

from reward_shaping.core.helper_fns import ThresholdIndicator, MinAggregatorReward, \
    ProdAggregatorReward
from reward_shaping.core.utils import get_normalized_reward


class GraphRewardConfig(ABC):

    def __init__(self, **kwargs):
        pass

    @property
    @abstractmethod
    def nodes(self):
        pass

    @property
    @abstractmethod
    def topology(self):
        pass


class GraphWithContinuousScoreBinaryIndicator(GraphRewardConfig):
    """
    rew(R) = Sum_{r in R} (Product_{r' in R st. r' <= r} sigma(r')) * rho(r)
    with sigma returns binary value {0,1}
    """

    def __init__(self, env_params):
        self._env_params = env_params

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'angle_hull_limit': self._env_params['angle_hull_limit'],
                'speed_y_limit': self._env_params['speed_y_limit'],
                'angle_vel_limit': self._env_params['angle_vel_limit'],
                'speed_x_target': self._env_params['speed_x_target']}

        # safety rules
        fun = fns.BinaryFalldownReward(falldown_penalty=-1.0, no_falldown_bonus=0.0)
        nodes["S_fall"] = (fun, ThresholdIndicator(fun))

        # define target rule: speed_x >= speed__xtarget
        nodes["T_move"] = get_normalized_reward(fns.SpeedTargetReward(),  # this is already normalized in +-1
                                                min_r_state=[0] * 2 + [info['speed_x_target']] + [0] * 21,
                                                max_r_state=[0] * 2 + [1] + [0] * 21,
                                                info=info,
                                                threshold=info['speed_x_target'])

        # define comfort rules
        # note: for comfort rules, the indicators do not necessarly need to reflect the satisfaction
        # since they are last layer in the hierarchy, we do not care (for simplicity)
        nodes["C_angle"] = get_normalized_reward(fns.ContinuousHullAngleReward(),
                                                 min_r_state=[info['angle_hull_limit']] + [0.0] * 23,
                                                 max_r_state=[0.0] + [0.0] * 23,
                                                 info=info,
                                                 threshold=info['angle_hull_limit'])
        nodes["C_v_y"] = get_normalized_reward(fns.ContinuousVerticalSpeedReward(),
                                               min_r_state=[0.0] * 3 + [info['']] + [0.0] * 20,
                                               max_r_state=[0.0] * 24,
                                               info=info,
                                               threshold=info['speed_y_limit'])
        nodes["C_angle_vel"] = get_normalized_reward(fns.ContinuousHullAngleVelocityReward(),
                                                     min_r_state=[0.0] + [info['angle_vel_limit']] + [0.0] * 22,
                                                     max_r_state=[0.0] * 24,
                                                     info=info,
                                                     threshold=info['angle_vel_limit'])

        return nodes

    @property
    def topology(self):
        """
                          / Comfort: Hull Angle
        Safety -- Target  - Comfort: Hull Angle Vel.
                          \ Comfort: Vertical Speed
        """
        topology = {
            'S_fall': ['T_move'],
            'T_move': ['C_angle', 'C_angle_vel', 'C_v_y']
        }
        return topology


class ChainGraph(GraphRewardConfig):
    """
    graph-based with 1 node for each level of the hierarchy
    """

    def __init__(self, env_params):
        self._env_params = env_params

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'angle_hull_limit': self._env_params['angle_hull_limit'],
                'speed_y_limit': self._env_params['speed_y_limit'],
                'angle_vel_limit': self._env_params['angle_vel_limit'],
                'speed_x_target': self._env_params['speed_x_target']}

        # safety rules
        fun = fns.BinaryFalldownReward(falldown_penalty=-1.0, no_falldown_bonus=0.0)
        nodes["S_fall"] = (fun, ThresholdIndicator(fun))

        # define target rule: speed_x >= speed__xtarget
        nodes["T_move"] = get_normalized_reward(fns.SpeedTargetReward(),  # this is already normalized in +-1
                                                min_r_state=[0] * 2 + [info['speed_x_target']] + [0] * 21,
                                                max_r_state=[0] * 2 + [1] + [0] * 21,
                                                info=info,
                                                threshold=info['speed_x_target'])

        # define comfort rules
        # note: for comfort rules, the indicators do not necessarly need to reflect the satisfaction
        # since they are last layer in the hierarchy, we do not care (for simplicity)
        angle_fn, angle_sat = get_normalized_reward(fns.ContinuousHullAngleReward(),
                                                    min_r_state=[info['angle_hull_limit']] + [0.0] * 23,
                                                    max_r_state=[0.0] + [0.0] * 23,
                                                    info=info,
                                                    threshold=info['angle_hull_limit'])
        vy_fn, vy_sat = get_normalized_reward(fns.ContinuousVerticalSpeedReward(),
                                              min_r_state=[0.0] * 3 + [info['']] + [0.0] * 20,
                                              max_r_state=[0.0] * 24,
                                              info=info,
                                              threshold=info['speed_y_limit'])
        angle_vel_fn, angle_vel_sat = get_normalized_reward(fns.ContinuousHullAngleVelocityReward(),
                                                            min_r_state=[0.0] + [info['angle_vel_limit']] + [0.0] * 22,
                                                            max_r_state=[0.0] * 24,
                                                            info=info,
                                                            threshold=info['angle_vel_limit'])
        # define single comfort rule as conjunction of the three
        funs = [angle_fn, vy_fn, angle_vel_fn]
        sats = [angle_sat, vy_sat, angle_vel_sat]
        nodes["C_all"] = (MinAggregatorReward(funs), ProdAggregatorReward(sats))

        return nodes

    @property
    def topology(self):
        """
        Safety -- Target  - Comfort: Hull Angle AND Hull Angle Vel AND Vertical Speed
        """
        topology = {
            'S_fall': ['T_move'],
            'T_move': ['C_all']
        }
        return topology
