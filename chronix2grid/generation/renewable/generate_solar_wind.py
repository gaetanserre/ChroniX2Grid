import os
import json

# Other Python libraries
import pandas as pd
import numpy as np

# Libraries developed for this module
import generation.renewable.solar_wind_utils as swutils


def main(i, destination_folder, seed, params, prods_charac, solar_pattern):
    """
    This is the solar and wind production generation function, it allows you to generate consumption chronics based on
    production nodes characteristics and on a solar typical yearly production patterns.

    Parameters
    ----------
    i (int): scenario number
    destination_folder (string): where results are written
    seed (int): random seed of the scenario
    params (dict): system params such as timestep or mesh characteristics
    prods_charac (pandas.DataFrame): characteristics of production nodes such as Pmax and type of production
    solar_pattern (pandas.DataFrame): hourly solar production pattern for a year. It represent specificity of the production region considered
    smoothdist (float): parameter for smoothing


    Returns
    -------
    pandas.DataFrame: solar and wind production chronics generated at every node with additional gaussian noise
    pandas.DataFrame: solar and wind production chronics forecasted for the scenario without additional gaussian noise
    """

    np.random.seed(seed)
    smoothdist = params['smoothdist']

    # Define datetime indices
    datetime_index = pd.date_range(
        start=params['start_date'],
        end=params['end_date'],
        freq=str(params['dt']) + 'min')

    # Generate GLOBAL temperature noise
    print('Computing global auto-correlated spatio-temporal noise for sun and wind...')
    solar_noise = swutils.generate_coarse_noise(params, 'solar')
    long_scale_wind_noise = swutils.generate_coarse_noise(params, 'long_wind')
    medium_scale_wind_noise = swutils.generate_coarse_noise(params, 'medium_wind')
    short_scale_wind_noise = swutils.generate_coarse_noise(params, 'short_wind')

    # Compute Wind and solar series of scenario
    print('Generating solar and wind production chronics')
    prods_series = {}
    for name in prods_charac['name']:
        mask = (prods_charac['name'] == name)
        if prods_charac[mask]['type'].values == 'solar':
            locations = [prods_charac[mask]['x'].values[0], prods_charac[mask]['y'].values[0]]
            Pmax = prods_charac[mask]['Pmax'].values[0]
            prods_series[name] = swutils.compute_solar_series(
                locations,
                Pmax,
                solar_noise,
                params, solar_pattern, smoothdist,
                time_scale=params['solar_corr'])

        elif prods_charac[mask]['type'].values == 'wind':
            locations = [prods_charac[mask]['x'].values[0], prods_charac[mask]['y'].values[0]]
            Pmax = prods_charac[mask]['Pmax'].values[0]
            prods_series[name] = swutils.compute_wind_series(
                locations,
                Pmax,
                long_scale_wind_noise,
                medium_scale_wind_noise,
                short_scale_wind_noise,
                params, smoothdist)

    # Séparation ds séries solaires et éoliennes
    solar_series = {}
    wind_series = {}
    for name in prods_charac['name']:
        mask = (prods_charac['name'] == name)
        if prods_charac[mask]['type'].values == 'solar':
            solar_series[name] = prods_series[name]
        elif prods_charac[mask]['type'].values == 'wind':
            wind_series[name] = prods_series[name]

    # Time index
    prods_series['datetime'] = datetime_index
    solar_series['datetime'] = datetime_index
    wind_series['datetime'] = datetime_index

    # Save files
    print('Saving files in zipped csv')
    scenario_destination_path = os.path.join(destination_folder, 'Scenario_' + str(i))
    if not os.path.exists(scenario_destination_path):
        os.mkdir(scenario_destination_path)
    prod_solar_forecasted = swutils.create_csv(solar_series, os.path.join(scenario_destination_path, 'solar_p_forecasted.csv.bz2'),
                  reordering=True,
                  shift=True,
                  with_pdb=True)

    prod_solar = swutils.create_csv(solar_series, os.path.join(scenario_destination_path, 'solar_p.csv.bz2'),
                  reordering=True,
                  noise=params['planned_std'])

    prod_wind_forecasted = swutils.create_csv(wind_series,
                                               os.path.join(scenario_destination_path, 'wind_p_forecasted.csv.bz2'),
                                               reordering=True,
                                               shift=True,
                                               with_pdb=True)

    prod_wind = swutils.create_csv(wind_series, os.path.join(scenario_destination_path, 'wind_p.csv.bz2'),
                                    reordering=True,
                                    noise=params['planned_std'])
    
    return prod_solar, prod_solar_forecasted, prod_wind, prod_wind_forecasted