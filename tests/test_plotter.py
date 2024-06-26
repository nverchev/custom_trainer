import pytest
import pandas as pd
from dry_torch.plotting import VisdomPlotter
from dry_torch.plotting import PlotlyPlotter
from dry_torch.plotting import plotter_closure

DEFAULT_DATAFRAME = pd.DataFrame({'Criterion': [0, 1]})


def test_PlotlyPlotter():
    plotter = PlotlyPlotter()
    plotter.plot(DEFAULT_DATAFRAME, DEFAULT_DATAFRAME)


def test_VisdomPlotter():
    plotter = VisdomPlotter('test')
    plotter.plot(DEFAULT_DATAFRAME, DEFAULT_DATAFRAME)


def test_plotter_backend():
    get_plotter = plotter_closure()

    # this tests depends on the system metadata
    plotter = get_plotter(backend='auto', env='')
    print(type(plotter))

    # test caching
    assert plotter is get_plotter(backend='auto', env='test')
