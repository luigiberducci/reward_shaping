import reward_shaping.envs.cart_pole_obst.rewards.subtask_rewards as fns
from reward_shaping.core.configs import GraphRewardConfig
from reward_shaping.core.helper_fns import ThresholdIndicator, NormalizedReward, MinAggregatorReward, \
    ProdAggregatorReward
import numpy as np


def get_cartpole_topology(task):
    # just to avoid to rewrite it all the times
    if task == "fixed_height":
        topology = {
            'S_coll': ['T_origin'],
            'S_fall': ['T_origin'],
            'S_exit': ['T_origin'],
            'T_origin': ['T_bal'],
        }
    elif task == "random_height":
        topology = {
            'S_coll': ['H_feas', 'H_nfeas'],
            'S_fall': ['H_feas', 'H_nfeas'],
            'S_exit': ['H_feas', 'H_nfeas'],
            'H_feas': ['T_origin'],
            'H_nfeas': ['T_bal'],
            'T_origin': ['C_bal'],
        }
    else:
        raise NotImplemented(f"no reward-topology for task {task}")
    return topology


def get_normalized_reward(fun, min_r=None, max_r=None, min_r_state=None, max_r_state=None, info=None,
                          threshold=0.0, include_zero=True):
    assert min_r is None or min_r_state is None, 'if min/max_r defined, then min/max_r_state must NOT be defined'
    assert min_r_state is None or min_r is None, 'if min/max_r_state defined, then min/max_r must NOT be defined'
    assert min_r_state is None or info is not None, 'if min/max_r_state is given, info must be given to eval fun'
    # compute normalization bounds
    if min_r_state is not None and max_r_state is not None:
        min_r = fun(min_r_state, info=info, next_state=min_r_state)
        max_r = fun(max_r_state, info=info, next_state=max_r_state)
    elif min_r is not None and max_r is not None:
        pass
    else:
        raise AttributeError("either min_r and max_r defined, or min_state_r and max_state_r defined")
    # normalize reward and def indicator
    norm_fun = NormalizedReward(fun, min_r, max_r)
    indicator_fun = ThresholdIndicator(fun, threshold=threshold, include_zero=include_zero)
    return norm_fun, indicator_fun


class GraphWithContinuousScoreBinaryIndicator(GraphRewardConfig):
    """
    rew(R) = Sum_{r in R} (Product_{r' in R st. r' <= r} sigma(r')) * rho(r)
    with sigma returns binary value {0,1}
    """

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'x_limit': self._env_params['x_limit'],
                'x_target': self._env_params['x_target'],
                'x_target_tol': self._env_params['x_target_tol'],
                'theta_limit': np.deg2rad(self._env_params['theta_limit']),
                'theta_target': np.deg2rad(self._env_params['theta_target']),
                'theta_target_tol': np.deg2rad(self._env_params['theta_target_tol'])}

        # define safety rules
        # collision
        fun = fns.ContinuousCollisionReward()
        # note: defining the min/max robustness bounds depend on the obstacle position (not known a priori)
        #       Then, the reward is normalized with approx. bounds
        min_r, max_r = -0.5, 2.5
        nodes["S_coll"] = get_normalized_reward(fun, min_r, max_r, info=info)

        # falldown
        fun = fns.ContinuousFalldownReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': 0.0}
        nodes["S_fall"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # outside
        fun = fns.ContinuousOutsideReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': 0.0}
        nodes["S_exit"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define target rules
        fun = fns.ReachTargetReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': info['x_target']}
        nodes["T_origin"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define comfort rules
        fun = fns.BalanceReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
        nodes["T_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        if self._env_params['task'] == "random_height":
            # for random env, additional comfort node
            fun = fns.BalanceReward()
            min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
            nodes["C_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)
            # conditional nodes (ie, to check env conditions)
            zero_fn = lambda _: 0.0  # this is a static condition, do not score for it (depends on the env)
            feas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nfeas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility(), negate=True)
            nodes["H_feas"] = (zero_fn, feas_ind)
            nodes["H_nfeas"] = (zero_fn, nfeas_ind)
        return nodes

    @property
    def topology(self):
        topology = get_cartpole_topology(self._env_params['task'])
        return topology


class GraphWithContinuousScoreContinuousIndicator(GraphRewardConfig):
    """
        rew(R) = Sum_{r in R} (Product_{r' in R st. r' <= r} rho(r')) * rho(r)
    """

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'x_limit': self._env_params['x_limit'],
                'x_target': self._env_params['x_target'],
                'x_target_tol': self._env_params['x_target_tol'],
                'theta_limit': np.deg2rad(self._env_params['theta_limit']),
                'theta_target': np.deg2rad(self._env_params['theta_target']),
                'theta_target_tol': np.deg2rad(self._env_params['theta_target_tol'])}

        # define safety rules
        # collision
        fun = fns.ContinuousCollisionReward()
        # note: defining the min/max robustness bounds depend on the obstacle position (not known a priori)
        #       Then, the reward is normalized with approx. bounds
        min_r, max_r = -0.5, 2.5
        nodes["S_coll"] = (NormalizedReward(fun, min_r, max_r), NormalizedReward(fun, min_r, max_r))

        # falldown
        fun = fns.ContinuousFalldownReward()
        min_r_state = {'theta': info['theta_limit']}
        max_r_state = {'theta': 0.0}
        min_r, max_r = fun(min_r_state, info=info, next_state=min_r_state), fun(max_r_state, info=info,
                                                                                next_state=max_r_state)
        nodes["S_fall"] = (NormalizedReward(fun, min_r, max_r), NormalizedReward(fun, min_r, max_r))

        # outside
        fun = fns.ContinuousOutsideReward()
        min_r_state = {'x': info['x_limit']}
        max_r_state = {'x': 0.0}
        min_r, max_r = fun(min_r_state, info=info, next_state=min_r_state), fun(max_r_state, info=info,
                                                                                next_state=max_r_state)
        nodes["S_exit"] = (NormalizedReward(fun, min_r, max_r), NormalizedReward(fun, min_r, max_r))

        # define target rules
        fun = fns.ReachTargetReward()
        min_r_state = {'x': info['x_limit']}
        max_r_state = {'x': info['x_target']}
        min_r, max_r = fun(min_r_state, info=info, next_state=min_r_state), fun(max_r_state, info=info,
                                                                                next_state=max_r_state)
        nodes["T_origin"] = (NormalizedReward(fun, min_r, max_r), NormalizedReward(fun, min_r, max_r))

        # define comfort rules
        fun = fns.BalanceReward()
        min_r_state = {'theta': info['theta_limit']}
        max_r_state = {'theta': info['theta_target']}
        min_r, max_r = fun(min_r_state, info=info, next_state=min_r_state), fun(max_r_state, info=info,
                                                                                next_state=max_r_state)
        balance_reward_fn = NormalizedReward(fun, min_r, max_r)
        nodes["T_bal"] = (balance_reward_fn, balance_reward_fn)

        if self._env_params['task'] == "random_height":
            # for random env, additional comfort node
            nodes["C_bal"] = (balance_reward_fn, balance_reward_fn)
            # conditional nodes (ie, to check env conditions)
            zero_fn = lambda _: 0.0  # this is a static condition, do not score for it (depends on the env)
            feas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nfeas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nodes["H_feas"] = (zero_fn, feas_ind)
            nodes["H_nfeas"] = (zero_fn, nfeas_ind)
        return nodes

    @property
    def topology(self):
        topology = get_cartpole_topology(self._env_params['task'])
        return topology


class GraphWithProgressScoreBinaryIndicator(GraphRewardConfig):
    """
    rew(R) = Sum_{r in R} (Product_{r' in R st. r' <= r} sigma(r')) * rho(r)
    with sigma returns binary value {0,1}
    """

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'x_limit': self._env_params['x_limit'],
                'x_target': self._env_params['x_target'],
                'x_target_tol': self._env_params['x_target_tol'],
                'theta_limit': np.deg2rad(self._env_params['theta_limit']),
                'theta_target': np.deg2rad(self._env_params['theta_target']),
                'theta_target_tol': np.deg2rad(self._env_params['theta_target_tol'])}

        # define safety rules
        # collision
        fun = fns.ContinuousCollisionReward()
        # note: defining the min/max robustness bounds depend on the obstacle position (not known a priori)
        #       Then, the reward is normalized with approx. bounds
        min_r, max_r = -0.5, 2.5
        nodes["S_coll"] = get_normalized_reward(fun, min_r, max_r, info=info)

        # falldown
        fun = fns.ContinuousFalldownReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': 0.0}
        nodes["S_fall"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # outside
        fun = fns.ContinuousOutsideReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': 0.0}
        nodes["S_exit"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define target rules
        fun = fns.ProgressToTargetReward(progress_coeff=1.0)
        nodes["T_origin"] = (fun, ThresholdIndicator(fun, include_zero=False))

        # define comfort rules
        fun = fns.BalanceReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
        nodes["T_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        if self._env_params['task'] == "random_height":
            # for random env, additional comfort node
            fun = fns.BalanceReward()
            min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
            nodes["C_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)
            # conditional nodes (ie, to check env conditions)
            zero_fn = lambda _: 0.0  # this is a static condition, do not score for it (depends on the env)
            feas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nfeas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility(), negate=True)
            nodes["H_feas"] = (zero_fn, feas_ind)
            nodes["H_nfeas"] = (zero_fn, nfeas_ind)
        return nodes

    @property
    def topology(self):
        topology = get_cartpole_topology(self._env_params['task'])
        return topology


class GraphWithBinarySafetyScoreBinaryIndicator(GraphRewardConfig):
    """
    the safety properties return -1 (violation) or 0 (sat)
    """

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'x_limit': self._env_params['x_limit'],
                'x_target': self._env_params['x_target'],
                'x_target_tol': self._env_params['x_target_tol'],
                'theta_limit': np.deg2rad(self._env_params['theta_limit']),
                'theta_target': np.deg2rad(self._env_params['theta_target']),
                'theta_target_tol': np.deg2rad(self._env_params['theta_target_tol'])}

        # define safety rules
        # collision
        fun = fns.CollisionReward(collision_penalty=-1.0, no_collision_bonus=0.0)
        nodes["S_coll"] = (fun, ThresholdIndicator(fun))

        # falldown
        fun = fns.FalldownReward(falldown_penalty=-1.0, no_falldown_bonus=0.0)
        nodes["S_fall"] = (fun, ThresholdIndicator(fun))

        # outside
        fun = fns.OutsideReward(exit_penalty=-1.0, no_exit_bonus=0.0)
        nodes["S_exit"] = (fun, ThresholdIndicator(fun))

        # define target rules
        fun = fns.ReachTargetReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': info['x_target']}
        nodes["T_origin"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define comfort rules
        fun = fns.BalanceReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
        nodes["T_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        if self._env_params['task'] == "random_height":
            # for random env, additional comfort node
            fun = fns.BalanceReward()
            min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
            nodes["C_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)
            # conditional nodes (ie, to check env conditions)
            zero_fn = lambda _: 0.0  # this is a static condition, do not score for it (depends on the env)
            feas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nfeas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility(), negate=True)
            nodes["H_feas"] = (zero_fn, feas_ind)
            nodes["H_nfeas"] = (zero_fn, nfeas_ind)
        return nodes

    @property
    def topology(self):
        topology = get_cartpole_topology(self._env_params['task'])
        return topology


class GraphWithSingleConjunctiveSafetyNode(GraphRewardConfig):
    """
    all the safety requirements are evaluated as a single conjunction
    """

    @property
    def nodes(self):
        nodes = {}
        # prepare env info
        info = {'x_limit': self._env_params['x_limit'],
                'x_target': self._env_params['x_target'],
                'x_target_tol': self._env_params['x_target_tol'],
                'theta_limit': np.deg2rad(self._env_params['theta_limit']),
                'theta_target': np.deg2rad(self._env_params['theta_target']),
                'theta_target_tol': np.deg2rad(self._env_params['theta_target_tol'])}

        # define safety rules
        # collision
        fun = fns.ContinuousCollisionReward()
        # note: defining the min/max robustness bounds depend on the obstacle position (not known a priori)
        #       Then, the reward is normalized with approx. bounds
        min_r, max_r = -0.5, 2.5
        collision_fn, collision_sat = get_normalized_reward(fun, min_r, max_r, info=info)

        # falldown
        fun = fns.ContinuousFalldownReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': 0.0}
        falldown_fn, falldown_sat = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # outside
        fun = fns.ContinuousOutsideReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': 0.0}
        outside_fn, outside_sat = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define single safety rule as conjunction of the three
        funs = [collision_fn, falldown_fn, outside_fn]
        sats = [collision_sat, falldown_sat, outside_sat]
        nodes["S_all"] = (MinAggregatorReward(funs), ProdAggregatorReward(sats))

        # define target rules
        fun = fns.ReachTargetReward()
        min_r_state, max_r_state = {'x': info['x_limit']}, {'x': info['x_target']}
        nodes["T_origin"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        # define comfort rules
        fun = fns.BalanceReward()
        min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
        nodes["T_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)

        if self._env_params['task'] == "random_height":
            # for random env, additional comfort node
            fun = fns.BalanceReward()
            min_r_state, max_r_state = {'theta': info['theta_limit']}, {'theta': info['theta_target']}
            nodes["C_bal"] = get_normalized_reward(fun, min_r_state=min_r_state, max_r_state=max_r_state, info=info)
            # conditional nodes (ie, to check env conditions)
            zero_fn = lambda _: 0.0  # this is a static condition, do not score for it (depends on the env)
            feas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility())
            nfeas_ind = ThresholdIndicator(fns.CheckOvercomingFeasibility(), negate=True)
            nodes["H_feas"] = (zero_fn, feas_ind)
            nodes["H_nfeas"] = (zero_fn, nfeas_ind)
        return nodes

    @property
    def topology(self):
        # just to avoid to rewrite it all the times
        if self._env_params['task'] == "fixed_height":
            topology = {
                'S_all': ['T_origin'],
                'T_origin': ['T_bal'],
            }
        elif self._env_params['task'] == "random_height":
            topology = {
                'S_all': ['H_feas', 'H_nfeas'],
                'H_feas': ['T_origin'],
                'H_nfeas': ['T_bal'],
                'T_origin': ['C_bal'],
            }
        else:
            raise NotImplemented(f"no reward-topology for task {self._env_params['task']}")
        return topology
