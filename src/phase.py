class Phase:
    def __init__(
            self, 
            name, 
            gibbs_phase_type, 
            data_type, 
            num_sublattice, 
            site_lattice_sites_list, 
            params_list 
    ):     
        
        self.name = name
        self.gibbs_phase_type = gibbs_phase_type
        self.data_type = data_type
        self.num_sublattice = num_sublattice
        self.site_lattice_sites_list = site_lattice_sites_list
        # self.species_list = species
        self.param_list = self._select_parameters(params_list)
        
    
    def set_species(self, species_list):
        self.species_sublattice_specific = species_list
        self.species_set =  set(item for sublist in species_list for item in sublist)

    def set_params(self, temperature):
        self.param_values, self.param_names = self.calc_parameters(temperature)


    def set_model(self, model, temperature):
        model.initate_in_a_phase( 
            temperature, 
            self.species_set,
            self.param_values,
            self.param_names
        )

        self.model = model


    def _select_parameters(self, list):
        temp_param_list = []

        for i in list:
            if i.phase in self.name:
                temp_param_list.append(i)

        return temp_param_list
    

    def calc_parameters(self, temperature):
        temp_values = []
        temp_names = []

        self.temperature = temperature

        for i in self.param_list:
            temp_values.append(i.evaluate_parameter(temperature))
            temp_names.append([i.phase, i.species, i.order])

        self.param_values = temp_values
        self.param_names = temp_names
        return temp_values, temp_names
    

    def calc_model(self, species_molar_amount):

        self.G = self.model.calc_g(species_molar_amount, self.param_values)

        return self.G
        