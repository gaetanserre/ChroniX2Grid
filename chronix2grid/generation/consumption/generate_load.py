import os
import json

# Other Python libraries
import pandas as pd
import numpy as np

# Libraries developed for this module
import generation.consumption.consumption_utils as conso


def main(i, destination_folder, seed, params, loads_charac, load_weekly_pattern):
    """
    This is the load generation function, it allows you to generate consumption chronics based on demand nodes characteristics and on weekly demand patterns.

    Parameters
    ----------
    i (int): scenario number
    destination_folder (string): where results are written
    seed (int): random seed of the scenario
    params (dict): system params such as timestep or mesh characteristics
    loads_charac (pandas.DataFrame): characteristics of loads node such as Pmax and type of demand
    load_weekly_pattern (pandas.DataFrame): 5 minutes weekly load chronic that represent specificity of the demand context


    Returns
    -------
    pandas.DataFrame: loads chronics generated at every node with additional gaussian noise
    pandas.DataFrame: loads chronics forecasted for the scenario without additional gaussian noise
    """

    np.random.seed(seed)

    # Define datetime indices
    datetime_index = pd.date_range(
        start=params['start_date'],
        end=params['end_date'],
        freq=str(params['dt']) + 'min')

    # Generate GLOBAL temperature noise
    print('Computing global auto-correlated spatio-temporal noise for thermosensible demand...')
    ## temperature is simply to reflect the fact that loads is correlated spatially, and so is the
    ## real "temperature". It is not the real temperature.
    temperature_noise = conso.generate_coarse_noise(params, 'temperature')

    print('Computing loads ...')
    loads_series = conso.compute_loads(loads_charac, temperature_noise, params, load_weekly_pattern)
    loads_series['datetime'] = datetime_index

    # Save files
    print('Saving files in zipped csv')
    scenario_destination_path = os.path.join(destination_folder, 'Scenario_'+str(i))
    if not os.path.exists(scenario_destination_path):
        os.mkdir(scenario_destination_path)
    load_forecasted = conso.create_csv(loads_series, os.path.join(scenario_destination_path, 'load_p_forecasted.csv.bz2'),
                  reordering=True,
                  shift=True)
    load = conso.create_csv(loads_series, os.path.join(scenario_destination_path, 'load_p.csv.bz2'),
                  reordering=True,
                  noise=params['planned_std'])
    
    return load, load_forecasted



    