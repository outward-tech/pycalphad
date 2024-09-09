from src.functions import thermo_func
from src.parameter import Parameter
from src.helper_functions import *
from src.phase import Phase
from src.models import Ideal_solution_model

import re

class System:
    def __init__(self, string):
        self.database_string = remove_comments(string)
        self.database_lines = split_lines(self.database_string)

        self.function_list, self.param_list, self.phase_list = self._parse_database(self.database_lines)

    def _parse_database(self, lines):
        
        temp_function_list = []
        temp_param_list = []
        temp_phase_list = []

        for line in lines:
            if 'FUNCTION' in line:
                temp_function_list.append(thermo_func(line))
        for line in lines:
            if 'PARAMETER' in line:
                # print('Parameter: ', line)
                temp_param_list.append(Parameter(line, temp_function_list))
        for line in lines:
            if 'PHASE' in line:
                match = re.search(r'\s?+PHASE\s(\S+):?([G, A, Y, L, I, F, B])?\s+(\S+)\s+(\d)\s+(.+)\s+', line)
                sublattice_match = re.findall(r'\d+\.\d+', line)
                if match:
                    if sublattice_match:
                        phase_name = match.group(1)
                        g_phase_type_code = match.group(2)
                        data_type_code = match.group(3)
                        num_sub_lattices = match.group(4)
                        sub_lattice_sites_list = sublattice_match

                        temp_phase_list.append(
                            Phase(
                                phase_name,
                                g_phase_type_code,
                                data_type_code,
                                num_sub_lattices,
                                sub_lattice_sites_list,
                                temp_param_list
                            )
                        )

                        # print('test', temp_function_list)

            if 'CONSTITUENT' in line:
                print('Constitituent: ', line)
                match = re.search(r'\s+?CONSTITUENT\s{}\s:(\S+):'.format(temp_phase_list[-1].name), line)
                
                species_list = []
                if match:
                        species = match.group(1)
                        species = species.split(':')
                        sub_lattice = []

                        for i in species:
                            sub_lattice = i.split(',')
                            # print(sub_lattice)
                            species_list.append(sub_lattice)
                
                temp_phase_list[-1].set_species(species_list)
        

        return temp_function_list, temp_param_list, temp_phase_list


    def set_models(self, model_list):
        for i, phase in enumerate(self.phase_list):
            phase.set_model(model_list[i], self.T)


    def set_conditions(self, temperature, pressure):

        self.T = temperature
        self.P = pressure
        for phase in self.phase_list:
            phase.calc_parameters(temperature)

    def calc_gibbs(self, const_list):
        self.gibbs = 0

        for i, phase in enumerate(self.phase_list):
            self.gibbs = self.gibbs + (phase.calc_model(const_list[i]))

        return self.gibbs


