import argparse
import pathlib
import time
import warnings
from typing import Dict, List, Any, Callable, Tuple

import matplotlib.axes
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plotting.custom_evaluations import get_custom_evaluation


FIGSIZE = (15, 4)

COLORS = {
    'default': '#377eb8',
    'tltl': '#4daf4a',
    'bhnr': '#984ea3',
    'morl_uni': '#a65628',
    'morl_dec': '#ff7f00',
    'hrs_pot': '#e41a1c'
}

REWARD_LABELS = {
    'default': 'Default',
    'tltl': 'TLTL',
    'bhnr': 'BHNR',
    'morl_uni': 'MORL (unif.)',
    'morl_dec': 'MORL (decr.)',
    'hrs_pot': 'Hier. Shaping'
}

ENV_LABELS = {
    "cart_pole_obst_fixed_height": "Cartpole+Obstacle",
    "bipedal_walker_forward": "Bipedal Walker",
    "bipedal_walker_hardcore": "Bipedal Walker (Hardcore)",
    "lunar_lander_land": "Lunar Lander",
}
HLINES = {
    1.5: "Safety+Target"
}


def get_files(logdir, regex):
    return logdir.glob(f"{regex}/evaluations*.npz")


def parse_env_task(filepath: str):
    env, task = None, None
    for env_name in ["cart_pole_obst", "bipedal_walker", "lunar_lander", "racecar"]:
        if env_name in filepath:
            env = env_name
            break
    for task_name in ["fixed_height", "forward", "hardcore", "land", "drive"]:
        if task_name in filepath:
            task = task_name
            break
    if not env or not task:
        raise ValueError(f"not able to parse env/task in {filepath}")
    return env, task


def parse_reward(filepath: str):
    for reward in ["default", "tltl", "bhnr", "morl_uni", "morl_dec", "hrs_pot"]:
        if reward in filepath:
            return reward
    raise ValueError(f"reward not found in {filepath}")


def get_evaluations(logdir: pathlib.Path, regex: str, gby: Callable) -> Dict[str, List[Dict[str, Any]]]:
    """ look for evaluations.npz in the subdirectories and return is content """
    evaluations = {}
    for eval_file in get_files(logdir, regex):
        data = dict(np.load(eval_file))
        data["filepath"] = str(eval_file)
        # group-by
        group = gby(str(eval_file))
        if group in evaluations:
            evaluations[group].append(data)
        else:
            evaluations[group] = [data]
    if len(evaluations) == 0:
        warnings.warn(f"cannot find any file for `{logdir}/{regex}/evaluations.npz`", UserWarning)
    return evaluations


def aggregate_evaluations(evaluations: List[Dict[str, np.ndarray]], params: Dict) -> Dict[str, np.ndarray]:
    """ aggregate data in the list to produce overall figure """
    # make flat collection of x,y data
    xx, yy = [], []
    for evaluation in evaluations:
        assert params['x'] in evaluation, f"{params['x']} is not in evaluation keys ({evaluation.keys()})"
        assert params['y'] in evaluation, f"{params['y']} is not in evaluation keys ({evaluation.keys()})"
        xx.append(evaluation[params['x']])
        yy.append(np.mean(evaluation[params['y']], axis=-1))  # eg, average results over multiple eval episodes
    xx = np.concatenate(xx, axis=0)
    yy = np.concatenate(yy, axis=0)
    assert xx.shape == yy.shape, f"xx, yy dimensions don't match (xx shape:{xx.shape}, yy shape:{yy.shape}"
    # aggregate
    df = pd.DataFrame({'x': xx, 'y': yy})
    bins = np.arange(0, max(xx) + params['binning'], params['binning'])
    df['xbin'] = pd.cut(df['x'], bins=bins, labels=bins[:-1])
    aggregated = df.groupby("xbin").agg(['mean', 'std'])['y'].reset_index()
    return {'x': aggregated['xbin'].values,
            'mean': aggregated['mean'].values,
            'std': aggregated['std'].values}


def plot_data(data: Dict[str, np.ndarray], ax: plt.Axes, title="", color=None, label=None, **kwargs):
    assert all([key in data for key in ['x', 'mean', 'std']]), f'x, mean, std not found in data (keys: {data.keys()})'
    ax.plot(data['x'], data['mean'], color=color, label=label, **kwargs)
    ax.fill_between(data['x'], data['mean'] - data['std'], data['mean'] + data['std'], alpha=0.25, color=color)
    ax.set_title(title)


def plot_file_info(args):
    for regex in args.regex:
        files = [f for f in get_files(args.logdir, regex)]
        print(f"regex: {regex}, nr files: {len(files)}")
        for f in files:
            data = dict(np.load(f))
            keys = [k for k in data.keys()]
            print(f"  file: {f.stem}, keys: {keys}")


def extend_with_custom_evaluation(evaluations, y):
    custom_fn = get_custom_evaluation(y)
    for i in range(len(evaluations)):
        if y in evaluations[i]:
            continue
        env_name, task_name = parse_env_task(evaluations[i]["filepath"])
        evaluations[i][y] = custom_fn(data=evaluations[i], env_name=env_name)
    return evaluations


def make_gby_extractor(gby: str) -> Tuple[Callable, Dict[str, str]]:
    if gby is None:
        fn = lambda filepath: "all"
        titles = ["all"]
    elif gby == "env":
        fn = lambda filepath: '_'.join(parse_env_task(filepath))
        titles = ENV_LABELS
    elif gby == "reward":
        fn = lambda filepath: parse_reward(filepath)
        titles = REWARD_LABELS
    else:
        raise NotImplementedError(f"gby function not found {gby}")
    return fn, titles


def plot_secondaries(ax, xlabel, ylabel, hlines, minx, maxx):
    # draw horizonal lines
    for value in hlines:
        ax.hlines(value, minx, maxx,
                  color='k', alpha=1.0,
                  linestyles='dashed', label=HLINES[value])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(0.0, 2.0)


def main(args):
    # only print info on files
    if args.info:
        plot_file_info(args)
        exit(0)
    # prepare plot
    gby_fn, titles = make_gby_extractor(args.gby)
    fig, axes = plt.subplots(nrows=1, ncols=len(titles), figsize=FIGSIZE)
    axes = [axes] if isinstance(axes, plt.Axes) else axes  # when 1 col then not list returned
    xlabel, ylabel = args.x.capitalize(), args.y.capitalize()
    minxs, maxxs = [np.Inf] * len(axes), [-np.Inf] * len(axes)
    # plot data
    for regex in args.regex:
        evaluations_grouped = get_evaluations(args.logdir, regex, gby=gby_fn)
        if not evaluations_grouped:
            continue
        for i, (gby, evaluations) in enumerate(evaluations_grouped.items()):
            if any([args.y not in evaluation.keys() for evaluation in evaluations]):
                evaluations = extend_with_custom_evaluation(evaluations, args.y)
            data = aggregate_evaluations(evaluations, params={'x': args.x, 'y': args.y, 'binning': args.binning})
            # assume all evaluations have same env and reward
            reward = parse_reward(evaluations[0]["filepath"])
            title = titles[gby]
            i = list(titles.keys()).index(gby)
            ax = axes[i]
            color, label = COLORS[reward], REWARD_LABELS[reward]
            plot_data(data, ax, title=title, label=label, color=color)
            # update min/max x
            minxs[i] = min(minxs[i], min(data["x"]))
            maxxs[i] = max(maxxs[i], max(data["x"]))
    # add secodnary stuff
    for i, ax in enumerate(axes):
        if i == 0:
            plot_secondaries(ax, xlabel="", ylabel=ylabel, hlines=args.hlines, minx=minxs[i], maxx=maxxs[i])
        else:
            plot_secondaries(ax, xlabel="", ylabel="", hlines=args.hlines, minx=minxs[i], maxx=maxxs[i])
    if args.legend:
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=len(handles), framealpha=1.0)
        fig.tight_layout()
    # save
    if args.save:
        plot_dir = args.logdir / "plots"
        plot_dir.mkdir(exist_ok=True, parents=True)
        outfile = plot_dir / f"plot_{int(time.time())}.pdf"
        plt.savefig(outfile)
        print(f"[Info] Figure saved in {outfile}")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--logdir", type=pathlib.Path, required=True)
    parser.add_argument("--regex", type=str, default="**", nargs="+",
                        help="for each regex, group data for `{logdir}/{regex}/evaluations*.npz`")
    parser.add_argument("--binning", type=int, default=15000)
    parser.add_argument("--gby", choices=["env", "reward"], default=None)
    parser.add_argument("--x", type=str, default="timesteps")
    parser.add_argument("--y", type=str, default="results")
    parser.add_argument("--hlines", type=float, nargs='*', default=[], help="horizontal lines in plot, eg. y=0")
    parser.add_argument("-save", action="store_true")
    parser.add_argument("-legend", action="store_true")
    parser.add_argument("-info", action="store_true")
    args = parser.parse_args()
    main(args)