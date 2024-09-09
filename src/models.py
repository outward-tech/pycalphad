import numpy as np

def calc_gm_mixing(constituent_mol_amounts):
    gm_mix = 0
    for i in constituent_mol_amounts:
        if i > 0:
            gm_mix = gm_mix + i * np.log(i)

    return gm_mix


def calc_gm_ref(constintuent_mol_amonuts, param_results):
    gm_ref = 0

    for i, mol_amount in enumerate(constintuent_mol_amonuts):
        gm_ref = gm_ref + param_results[i] * mol_amount

    return gm_ref


class Ideal_solution_model:

    def __init__(self):
        pass

    def initate_in_a_phase(
            self, 
            temperature, 
            constituent_list, 
            param_values, 
            param_names
    ):
        
        self.temperature = temperature
        self.constituents = constituent_list
        self.param_names, self.param_values = self._select_params(param_names, param_values)


    def _select_params(self, param_names, param_results):
        temp_param_names = []
        temp_param_results = []
        
        for i, param_name in enumerate(param_names):
            if len(param_name[1]) == 1:
                temp_param_names.append(param_name)
                temp_param_results.append(param_results[i])

        return temp_param_names, temp_param_results
    

    def calc_g(self, molar_amouts, param_values):
        
        G_mix = calc_gm_mixing(molar_amouts)

        G_ref = calc_gm_ref(molar_amouts, param_values)

        return G_ref + G_mix