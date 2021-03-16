import os

import pandas as pd

from chronix2grid import constants
from chronix2grid import utils
from chronix2grid.generation import generation_utils
from chronix2grid.generation.dispatch import generate_dispatch, EconomicDispatch

class GeneratorBackend:
    """
    Class that gathers the Backends of the different generation processes.
    It will allow to generate each step successively, thanks to its method :func:`GeneratorBackend.run`.
    It will load and check the parameters for each step thanks to instances of :class:`chronix2grid.config.ConfigManager`
    It will then do the proper generation thanks to its methods :func:`GeneratorBackend.do_l`, :func:`GeneratorBackend.do_r`,
    :func:`GeneratorBackend.do_d` and :func:`GeneratorBackend.do_t`. This methods rely on other specific backends.

    All the attributes are static variables passed via module :class:`chronix2grid.constants`

    Attributes
    ----------
    general_config_manager: :class:`chronix2grid.config.ConfigManager`
        Class inheriting from ConfigManager that loads and checks the general parameters of the overall generation process, such as time resolution.
    """
    def __init__(self):
        self.general_config_manager = constants.GENERAL_CONFIG
        self.load_config_manager = constants.LOAD_GENERATION_CONFIG
        self.res_config_manager = constants.RENEWABLE_GENERATION_CONFIG
        self.loss_config_manager = constants.LOSS_GENERATION_CONFIG
        self.dispatch_config_manager = constants.DISPATCH_GENERATION_CONFIG

        self.consumption_backend_class = constants.LOAD_GENERATION_BACKEND
        self.dispatch_backend_class = constants.DISPATCH_GENERATION_BACKEND
        self.hydro_backend_class = constants.HYDRO_GENERATION_BACKEND
        self.renewable_backend_class = constants.RENEWABLE_GENERATION_BACKEND
        self.loss_backend_class = constants.LOSS_GENERATION_BACKEND

    # Call generation scripts n_scenario times with dedicated random seeds
    def run(self, case, n_scenarios, input_folder, output_folder, scen_names,
            time_params, mode='LRTK', scenario_id=None,
            seed_for_loads=None, seed_for_res=None, seed_for_disp=None):
        """
        Main function for chronics generation. It works with three steps: load generation, renewable generation (solar and wind)
        and then dispatch computation to get the whole energy mix. It writes the resulting chronics in the output_path in zipped csv format

        Parameters
        ----------
        case: ``str``
            name of case to study (must be a folder within input_folder)
        n_scenarios: ``int``
            number of desired scenarios to generate for the same timescale
        input_folder: ``str``
            path of folder containing inputs
        output_folder: ``str``
            path where outputs will be written (intermediate folder case/year/scenario will be used)
        mode: ``str``
            options to launch certain parts of the generation process : L load R renewable T thermal
        scenario_id: ``int`` or ``None``
            Id of scenario
        seed_for_loads: ``int`` or ``None``
            seed for the load generation process
        seed_for_res: ``int`` or ``None``
            seed for the renewable generation process
        seed_for_disp: ``int`` or ``None``
            seed for the dispatch generation process

        Returns
        -------
        params: ``dict``
            general parameters
        loads_charac: :class: ``pandas.DataFrame``
            characteristics of consumption nodes in the grid used in generation
        prods_charac: :class: ``pandas.DataFrame``
            characteristics of production nodes in the grid used in generation
        """

        utils.check_scenario(n_scenarios, scenario_id)

        print('=====================================================================================================================================')
        print('============================================== CHRONICS GENERATION ==================================================================')
        print('=====================================================================================================================================')

        # in multiprocessing, n_scenarios=1 here
        if n_scenarios >= 2:
            seeds_for_loads, seeds_for_res, seeds_for_disp = generation_utils.generate_seeds(
                n_scenarios, seed_for_loads, seed_for_res, seed_for_disp
            )
        else:
            seeds_for_loads = [seed_for_loads]
            seeds_for_res = [seed_for_res]
            seeds_for_disp = [seed_for_disp]

        # dispatch_input_folder, dispatch_input_folder_case, dispatch_output_folder = gu.make_generation_input_output_directories(input_folder, case, year, output_folder)
        general_config_manager = self.general_config_manager(
            name="Global Generation",
            root_directory=input_folder,
            input_directories=dict(case=case),
            required_input_files=dict(case=['params.json']),
            output_directory=output_folder
        )
        general_config_manager.validate_configuration()
        params = general_config_manager.read_configuration()

        params.update(time_params)
        params = generation_utils.updated_time_parameters_with_timestep(params, params['dt'])

        load_config_manager = self.load_config_manager(
            name="Loads Generation",
            root_directory=input_folder,
            input_directories=dict(case=case, patterns='patterns'),
            required_input_files=dict(case=['loads_charac.csv', 'params_load.json'],
                                      patterns=['load_weekly_pattern.csv']),
            output_directory=output_folder
        )
        load_config_manager.validate_configuration()
        params_load, loads_charac = load_config_manager.read_configuration()
        params_load.update(params)

        res_config_manager = self.res_config_manager(
            name="Renewables Generation",
            root_directory=input_folder,
            input_directories=dict(case=case, patterns='patterns'),
            required_input_files=dict(case=['prods_charac.csv', 'params_res.json'],
                                      patterns=['solar_pattern.npy']),
            output_directory=output_folder
        )
        params_res, prods_charac = res_config_manager.read_configuration()
        params_res.update(params)

        dispath_config_manager = self.dispatch_config_manager(
            name="Dispatch",
            root_directory=input_folder,
            output_directory=output_folder,
            input_directories=dict(params=case),
            required_input_files=dict(params=['params_opf.json'])
        )
        dispath_config_manager.validate_configuration()
        params_opf = dispath_config_manager.read_configuration()
        grid_folder = os.path.join(input_folder, case)
        grid_path = os.path.join(grid_folder, constants.GRID_FILENAME)
        dispatcher = EconomicDispatch.init_dispatcher_from_config(grid_path, input_folder)
        loss = None

        ## Launch proper scenarios generation
        seeds_iterator = zip(seeds_for_loads, seeds_for_res, seeds_for_disp)

        for i, (seed_load, seed_res, seed_disp) in enumerate(seeds_iterator):

            if n_scenarios > 1:
                scenario_name = scen_names(i)
            else:
                scenario_name = scen_names(scenario_id)

            scenario_folder_path = os.path.join(output_folder, scenario_name)

            print("================ Generating " + scenario_name + " ================")
            if 'L' in mode:
                load, load_forecasted = self.do_l(scenario_folder_path, seed_load, params_load, loads_charac, load_config_manager)
                params.update(params_load)
            if 'R' in mode:
                prod_solar, prod_solar_forecasted, prod_wind, prod_wind_forecasted = self.do_r(scenario_folder_path, seed_res, params_res,
                                                                                               prods_charac,
                                                                                               res_config_manager)
                params.update(params_res)
            if 'D' in mode:
                loss_config_manager = self.loss_config_manager(
                    name="Loss",
                    root_directory=input_folder,
                    output_directory=output_folder,
                    input_directories=dict(params=case),
                    required_input_files=dict(params=['params_loss.json'])
                )

                self.do_d(input_folder, scenario_folder_path,
                                     load, prod_solar, prod_wind,
                                     params, loss_config_manager)
            if 'T' in mode:
                dispatch_results = self.do_t(dispatcher, scenario_name, load, prod_solar, prod_wind,
                                             grid_folder, scenario_folder_path, seed_disp, params, params_opf, loss)
            print('\n')
        return params, loads_charac, prods_charac

    def do_l(self, scenario_folder_path, seed_load, params, loads_charac, load_config_manager):
        """
        Generates load chronics thanks to the backend in ``self.consumption_backend_class``

        Parameters
        ----------
        scenario_folder_path
        seed_load
        params
        loads_charac
        load_config_manager

        Returns
        -------
        loads: :class: `pandas.DataFrame`
            generated loads chronics
        prods_charac: :class: `pandas.DataFrame`
            generated forecasted loads chronics (currently loads chronics with gaussian noise)
        """
        generator_loads = self.consumption_backend_class(scenario_folder_path, seed_load, params, loads_charac, load_config_manager,
                                                         write_results=True)
        load, load_forecasted = generator_loads.run()
        return load, load_forecasted

    def do_r(self, scenario_folder_path, seed_res, params, prods_charac, res_config_manager):
        """
        Generates load chronics thanks to the backend in ``self.renewable_backend_class``

        Parameters
        ----------
        scenario_folder_path
        seed_res
        params
        prods_charac
        res_config_manager

        Returns
        -------
        prod_solar: :class: `pandas.DataFrame`
            generated solar chronics
        prod_solar_forecasted: :class: `pandas.DataFrame`
            generated forecasted solar chronics
        prod_wind: :class: `pandas.DataFrame`
            generated wind chronics
        prod_wind_forecasted: :class: `pandas.DataFrame`
            generated forecasted wind chronics
        """
        generator_enr = self.renewable_backend_class(scenario_folder_path, seed_res, params,
                                                     prods_charac,
                                                     res_config_manager, write_results=True)

        prod_solar, prod_solar_forecasted, prod_wind, prod_wind_forecasted = generator_enr.run()
        return prod_solar, prod_solar_forecasted, prod_wind, prod_wind_forecasted

    def do_d(self, input_folder, scenario_folder_path,
                                     load, prod_solar, prod_wind,
                                     params, loss_config_manager):
        """
        Generates load chronics thanks to the backend in ``self.renewable_backend_class``

        Parameters
        ----------
        input_folder
        scenario_folder_path
        load
        prod_solar
        prod_wind
        params
        loss_config_manager

        Returns
        -------
        loss: :class: `pandas.DataFrame`
            generated loss chronics
        """

        generator_loss = self.loss_backend_class(input_folder, scenario_folder_path,
                                     load, prod_solar, prod_wind,
                                     params, loss_config_manager)
        loss = generator_loss.run()
        return loss

    def do_t(self, dispatcher, scenario_name, load, prod_solar, prod_wind, grid_folder,
             scenario_folder_path, seed_disp, params, params_opf, loss):
        """
        Computes production chronics based on a dispatch computation. It uses a dispatcher object as an environment for simulation and
        ``self.dispatch_backend_class`` for computation

        Parameters
        ----------
        dispatcher
        scenario_name
        load
        prod_solar
        prod_wind
        grid_folder
        scenario_folder_path
        seed_disp
        params
        params_opf
        loss

        Returns
        -------
        dispatch_results: :class: `collection.namedtuple`
            contains resulting production chronics and terminal conditions from the optimization engine
        """
        prods = pd.concat([prod_solar, prod_wind], axis=1)
        res_names = dict(wind=prod_wind.columns, solar=prod_solar.columns)
        dispatcher.chronix_scenario = EconomicDispatch.ChroniXScenario(load, prods, res_names,
                                                                       scenario_name, loss)

        generator_dispatch = self.dispatch_backend_class(dispatcher, scenario_folder_path,
                                                 grid_folder, seed_disp, params, params_opf)
        dispatch_results = generator_dispatch.run()
        # dispatch_results = generate_dispatch.main(dispatcher, scenario_folder_path,
        #                                          scenario_folder_path, grid_folder,
        #                                           seed_disp, params, params_opf)
        return dispatch_results