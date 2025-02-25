"""
The utils module handles helper routines for equilibrium calculation.
"""
import warnings

import pycalphad.variables as v
from pycalphad.core.halton import halton
from pycalphad.core.constants import MIN_SITE_FRACTION
from pycalphad.property_framework.units import Q_
from symengine import Symbol
import numpy as np
import operator
import functools
import itertools
import collections
from collections.abc import Iterable, Mapping, KeysView


def point_sample(comp_count, pdof=10):
    """
    Sample 'pdof * (sum(comp_count) - len(comp_count))' points in
    composition space for the sublattice configuration specified
    by 'comp_count'. Points are sampled quasi-randomly from a Halton sequence.
    A Halton sequence is like a uniform random distribution, but the
    result will always be the same for a given 'comp_count' and 'pdof'.
    Note: For systems with only one component, only one point will be
    returned, regardless of 'pdof'. This is because the degrees of freedom
    are zero for that case.

    Parameters
    ----------
    comp_count : list
        Number of components in each sublattice.
    pdof : int
        Number of points to sample per degree of freedom.

    Returns
    -------
    ndarray of generated points satisfying the mass balance.

    Examples
    --------
    >>> comps = [8,1] # 8 components in sublattice 1; only 1 in sublattice 2
    >>> pts = point_sample(comps, pdof=20) # 7 d.o.f, returns a 140x7 ndarray
    """
    # Generate Halton sequence with appropriate dimensions and size
    pts = halton(sum(comp_count),
                 pdof * (sum(comp_count) - len(comp_count)), scramble=True)
    # Convert low-discrepancy sequence to normalized exponential
    # This will be uniformly distributed over the simplices
    pts = -np.log(pts)
    cur_idx = 0
    for ctx in comp_count:
        end_idx = cur_idx + ctx
        pts[:, cur_idx:end_idx] /= pts[:, cur_idx:end_idx].sum(axis=1)[:, None]
        cur_idx = end_idx

    if len(pts) == 0:
        pts = np.atleast_2d([1] * len(comp_count))
    return pts


def sizeof_fmt(num, suffix='B'):
    """
    Human-readable string for a number of bytes.
    http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    """
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1000.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1000.0
    return "%.1f%s%s" % (num, 'Y', suffix)

def unpack_condition(tup):
    """
    Convert a condition to a list of values.

    Notes
    -----
    Rules for keys of conditions dicts:
    (1) If it's numeric, treat as a point value
    (2) If it's a tuple with one element, treat as a point value
    (3) If it's a tuple with two elements, treat as lower/upper limits and guess a step size.
    (4) If it's a tuple with three elements, treat as lower/upper/step
    (5) If it's a list, ndarray or other non-tuple ordered iterable, use those values directly.

    """
    if isinstance(tup, tuple):
        if len(tup) == 1:
            return [float(tup[0])]
        elif len(tup) == 2:
            return np.arange(tup[0], tup[1], dtype=np.float64)
        elif len(tup) == 3:
            return np.arange(tup[0], tup[1], tup[2], dtype=np.float64)
        else:
            raise ValueError('Condition tuple is length {}'.format(len(tup)))
    elif isinstance(tup, Q_):
        return tup
    elif isinstance(tup, Iterable) and np.ndim(tup) != 0:
        return [float(x) for x in tup]
    else:
        return [float(tup)]

def unpack_phases(phases):
    "Convert a phases list/dict into a sorted list."
    active_phases = None
    if isinstance(phases, (list, tuple, set, KeysView)):
        active_phases = sorted(phases)
    elif isinstance(phases, dict):
        active_phases = sorted(phases.keys())
    elif type(phases) is str:
        active_phases = [phases]
    else:
        raise ValueError(f'Cannot unpack phases into recognizable input. Got {phases} of type {type(phases)}')
    return active_phases

def generate_dof(phase, active_comps):
    """
    Accept a Phase object and a set() of the active components.
    Return a tuple of variable names and the sublattice degrees of freedom.
    """
    msg = "generate_dof is deprecated and will be removed in a future version "
    msg += "of pycalphad. The correct way to determine the degrees of freedom "
    msg += "of a particular 'active' phase is to use Model.constituents."
    warnings.warn(msg, FutureWarning)
    variables = []
    sublattice_dof = []
    for idx, sublattice in enumerate(phase.constituents):
        dof = 0
        for component in sorted(set(sublattice).intersection(active_comps)):
            variables.append(v.SiteFraction(phase.name.upper(), idx, component))
            dof += 1
        sublattice_dof.append(dof)
    return variables, sublattice_dof

def endmember_matrix(dof, vacancy_indices=None):
    """
    Accept the number of components in each sublattice.
    Return a matrix corresponding to the compositions of all endmembers.

    Parameters
    ----------
    dof : list of int
        Number of components in each sublattice.
    vacancy_indices, list of list of int, optional
        If vacancies are present in every sublattice, specify their indices
        in each sublattice to ensure the "pure vacancy" endmembers are excluded.

    Examples
    --------
    Sublattice configuration like: `(AL, NI, VA):(AL, NI, VA):(VA)`
    >>> endmember_matrix([3,3,1], vacancy_indices=[[2], [2], [0]])
    """
    total_endmembers = functools.reduce(operator.mul, dof, 1)
    res_matrix = np.empty((total_endmembers, sum(dof)), dtype=np.float64)
    dof_arrays = [np.eye(d).tolist() for d in dof]
    row_idx = 0
    for row in itertools.product(*dof_arrays):
        res_matrix[row_idx, :] = np.concatenate(row, axis=0)
        row_idx += 1
    if vacancy_indices is not None and len(vacancy_indices) == len(dof):
        dof_adj = np.array([sum(dof[0:i]) for i in range(len(dof))])
        for vacancy_em in itertools.product(*vacancy_indices):
            indices = np.array(vacancy_em) + dof_adj
            row_idx_to_delete = np.where(np.all(res_matrix[:, indices] == 1,
                                                axis=1))
            res_matrix = np.delete(res_matrix, (row_idx_to_delete), axis=0)
    # Adjust site fractions to the numerical limit
    cur_idx = 0
    res_matrix[res_matrix == 0] = MIN_SITE_FRACTION
    for ctx in dof:
        end_idx = cur_idx + ctx
        res_matrix[:, cur_idx:end_idx] /= res_matrix[:, cur_idx:end_idx].sum(axis=1)[:, None]
        cur_idx = end_idx
    return res_matrix

def unpack_kwarg(kwarg_obj, default_arg=None):
    """
    Keyword arguments in pycalphad can be passed as a constant value, a
    dict of phase names and values, or a list containing both of these. If
    the latter, then the dict is checked first; if the phase of interest is not
    there, then the constant value is used.

    This function is a way to construct defaultdicts out of keyword arguments.

    Parameters
    ----------
    kwarg_obj : dict, iterable, or None
        Argument to unpack into a defaultdict
    default_arg : object
        Default value to use if iterable isn't specified

    Returns
    -------
    defaultdict for the keyword argument of interest

    Examples
    --------
    >>> test_func = lambda **kwargs: print(unpack_kwarg('opt'))
    >>> test_func(opt=100)
    >>> test_func(opt={'FCC_A1': 50, 'BCC_B2': 10})
    >>> test_func(opt=[{'FCC_A1': 30}, 200])
    >>> test_func()
    >>> test_func2 = lambda **kwargs: print(unpack_kwarg('opt', default_arg=1))
    >>> test_func2()
    """
    new_dict = collections.defaultdict(lambda: default_arg)

    if isinstance(kwarg_obj, Mapping):
        new_dict.update(kwarg_obj)
    # kwarg_obj is a list containing a dict and a default
    # For now at least, we don't treat ndarrays the same as other iterables
    # ndarrays are assumed to be numeric arrays containing "default values", so don't match here
    elif isinstance(kwarg_obj, Iterable) and not isinstance(kwarg_obj, np.ndarray):
        for element in kwarg_obj:
            if isinstance(element, Mapping):
                new_dict.update(element)
            else:
                # element=element syntax to silence var-from-loop warning
                new_dict = collections.defaultdict(
                    lambda element=element: element, new_dict)
    elif kwarg_obj is None:
        pass
    else:
        new_dict = collections.defaultdict(lambda: kwarg_obj)

    return new_dict


def unpack_components(dbf, comps):
    """

    Parameters
    ----------
    dbf : Database
        Thermodynamic database containing elements and species.
    comps : list
        Names of components to consider in the calculation.

    Returns
    -------
    set
        Set of Species objects
    """
    # Constrain possible components to those within phase's d.o.f
    # Assume for the moment that comps contains a list of pure element strings
    # We want to add all the species which can be created by a combination of
    # the user-specified pure elements
    species_dict = {s.name: s for s in dbf.species}
    possible_comps = {v.Species(species_dict.get(x, x)) for x in comps}
    desired_active_pure_elements = [list(x.constituents.keys()) for x in possible_comps]
    # Flatten nested list
    desired_active_pure_elements = [el.upper() for constituents in desired_active_pure_elements for el in constituents]
    eligible_species_from_database = {x for x in dbf.species if
                                      set(x.constituents.keys()).issubset(desired_active_pure_elements)}
    return eligible_species_from_database


def get_pure_elements(dbf, comps):
    """
    Return a list of pure elements in the system.

    Parameters
    ----------
    dbf : Database
        A Database object
    comps : list
        A list of component names (species and pure elements)

    Returns
    -------
    list
        A list of pure elements in the Database
    """
    comps = sorted(unpack_components(dbf, comps))
    components = [x for x in comps]
    desired_active_pure_elements = [list(x.constituents.keys()) for x in components]
    desired_active_pure_elements = [el.upper() for constituents in desired_active_pure_elements for el in constituents]
    pure_elements = sorted(set([x for x in desired_active_pure_elements if x != 'VA']))
    return pure_elements


def filter_phases(dbf, comps, candidate_phases=None):
    """Return phases that are valid for equilibrium calculations for the given database and components

    Filters out phases that
    * Have no active components in any sublattice of a phase
    * Are disordered phases in an order-disorder model

    Parameters
    ----------
    dbf : Database
        Thermodynamic database containing the relevant parameters.
    comps : list of v.Species
        Species to consider in the calculation.
    candidate_phases : list
        Names of phases to consider in the calculation, if not passed all phases from DBF will be considered
    Returns
    -------
    list
        Sorted list of phases that are valid for the Database and components
    """
    # TODO: filter phases that can not charge balance

    def all_sublattices_active(comps, phase):
        active_sublattices = [len(set(comps).intersection(subl)) > 0 for
                              subl in phase.constituents]
        return all(active_sublattices)
    if candidate_phases == None:
        candidate_phases = dbf.phases.keys()
    else:
        candidate_phases = set(candidate_phases).intersection(dbf.phases.keys())
    disordered_phases = [dbf.phases[phase].model_hints.get('disordered_phase') for phase in candidate_phases]
    phases = [phase for phase in candidate_phases if
                all_sublattices_active(comps, dbf.phases[phase]) and
                (phase not in disordered_phases or (phase in disordered_phases and
                dbf.phases[phase].model_hints.get('ordered_phase') not in candidate_phases))]
    return sorted(phases)


def extract_parameters(parameters):
    """
    Extract symbols and values from parameters.

    Parameters
    ----------
    parameters : dict
        Dictionary of parameters

    Returns
    -------
    tuple
        Tuple of parameter symbols (list) and parameter values (parameter_array_length, # parameters)
    """
    parameter_array_lengths = set(np.atleast_1d(val).size for val in parameters.values())
    if len(parameter_array_lengths) > 1:
        raise ValueError('parameters kwarg does not contain arrays of equal length')
    if len(parameters) > 0:
        param_symbols, param_values = zip(*[(wrap_symbol(key), val) for key, val in sorted(parameters.items(),
                                                                              key=operator.itemgetter(0))])
        param_values = np.atleast_2d(np.ascontiguousarray(np.asarray(param_values, dtype=np.float64).T))
    else:
        param_symbols = []
        param_values = np.empty(0)
    return param_symbols, param_values


def instantiate_models(dbf, comps, phases, model=None, parameters=None, symbols_only=True):
    """

    Parameters
    ----------
    dbf : Database
        Database used to construct the Model instances.
    comps : Iterable
        Names of components to consider in the calculation.
    phases : Iterable
        Names of phases to consider in the calculation.
    model : Model class, a dict of phase names to Model, or a Iterable of both
        Model class to use for each phase.
    parameters : dict, optional
        Maps SymEngine Symbol to numbers, for overriding the values of parameters in
        the Database.
    symbols_only : bool
        If True, symbols will be extracted from the parameters dict and used to
        construct the Model instances.

    Returns
    -------
    dict
        Dictionary of Model instances corresponding to the passed phases.
    """
    from pycalphad import Model  # avoid cyclic imports
    parameters = parameters if parameters is not None else {}
    if symbols_only:
        parameters, _ = extract_parameters(parameters)
    if isinstance(model, Model):  # Check that this instance is compatible with phases
        if len(phases) > 1:
            raise ValueError("Cannot instantiate models for multiple phases ({}) using a Model instance ({}, phase: {})".format(phases, model, model.phase_name))
        else:
            if phases[0] != model.phase_name:
                raise ValueError("Cannot instantiate models because the desired {} phase does not match the Model instance () {} phase.".format(phases[0], model.phase_name, model))
    models_defaultdict = unpack_kwarg(model, Model)
    models_dict = {}
    for name in phases:
        mod = models_defaultdict[name]
        if isinstance(mod, type):
            models_dict[name] = mod(dbf, comps, name, parameters=parameters)
        else:
            models_dict[name] = mod
    return models_dict


def get_state_variables(models=None, conds=None):
    """
    Return a set of StateVariables defined Model instances and/or conditions.

    Parameters
    ----------
    models : dict, optional
        Dictionary mapping phase names to instances of Model objects
    conds : Iterable[v.StateVariable]
        An iterable of StateVariables or a dictionary mapping pycalphad StateVariables to values

    Returns
    -------
    set
        State variables that are defined in the models and or conditions.

    Examples
    --------
    >>> from pycalphad import variables as v
    >>> from pycalphad.core.utils import get_state_variables
    >>> get_state_variables(conds={v.P: 101325, v.N: 1, v.X('AL'): 0.2}) == {v.P, v.N, v.T}
    True
    """
    state_vars = set()
    if models is not None:
        for mod in models.values():
            state_vars.update(mod.state_variables)
    if conds is not None:
        for c in conds:
            # StateVariable instances are ok (e.g. P, T, N, V, S),
            # however, subclasses (X, Y, MU, NP) are not ok.
            if isinstance(c, (v.IndependentPotential, v.SystemMolesType)):
                state_vars.add(c)
    return state_vars


def wrap_symbol(obj):
    if isinstance(obj, Symbol):
        return obj
    else:
        return Symbol(obj)


def recursive_tuplify(x):
    """Recursively convert a nested list to a tuple"""
    def _tuplify(y):
        if isinstance(y, list) or isinstance(y, tuple):
            return tuple(_tuplify(i) if isinstance(i, (list, tuple)) else i for i in y)
        else:
            return y
    return tuple(map(_tuplify, x))


def canonical_sort_key(x):
    """
    Wrap strings in tuples so they'll sort.

    Parameters
    ----------
    x : list
        List of strings to sort

    Returns
    -------
    tuple
        tuple of strings that can be sorted
    """
    return [tuple(i) if isinstance(i, (tuple, list)) else (i,) for i in x]


def generate_symmetric_group(configuration, symmetry):
    """
    For a particular configuration and list of sublattices that are symmetric,
    generate all the symmetrically equivalent configurations.

    Parameters
    ----------
    configuration : Sequence[Any]
        Typically a constituent array. The length should correspond to the number of
        sublattices in the phase.
    symmetry : Union[None, Sequence[Sequence[int]]]
        A list of lists giving the indices of symmetrically equivalent sublattices.
        For example: a symmetry of `[[0, 1, 2, 3]]` means that the first four
        sublattices are symmetric to each other. If multiple sublattices are given, the
        sublattices are internally equivalent and the sublattices themselves are assumed
        interchangeble. That is, for a symmetry of `[[0, 1], [2, 3]]`, sublattices
        0 and 1 are equivalent to each other (i.e. `[0, 1] == [1, 0]`) and similarly for
        sublattices 2 and 3. It also implies that the sublattices are interchangeable,
        (i.e. `[[0, 1], [2, 3]] == [[2, 3], [0, 1]]`), but note that constituents cannot
        change sublattices (i.e. `[[0, 1], [2, 3]] != [[0, 3], [2, 1]]`).
        If `symmetry=None` is given, no new configurations are generated.

    Returns
    -------
    tuple
        Tuple of configuration tuples that are all symmetrically equivalent.

    Notes
    -----
    In the general case, equivalency between sublattices, for example
    (`[[0, 1], [2, 3]] == [[2, 3], [0, 1]]`), is not necessarily required. It
    could be that sublattices 0 and 1 represent equivalent substitutional
    sublattices, while 2 and 3 represent equivalent interstitial sites.
    Interchanging sublattices between substitutional sublattices is allowed, but
    the substitutional sites would not be interchangeable with the interstitial
    sites. To achieve this kind of effect with this function, you would need to
    call it once with the equivalent substitutional sublattices, then for each
    generated configuration, call this function again, giving the unique
    configurations for symmetric interstitial sublattices.
    """
    # recursively casting sequences to tuples ensures that the generated configurations are hashable
    configuration = recursive_tuplify(configuration)
    sublattice_indices = list(range(len(configuration)))
    if symmetry is None:
        return [configuration]
    seen_subl_indices = sorted([i for equiv_subl in symmetry for i in equiv_subl])
    # fixed_subl_indices were not given, they are assumed to be inequivalent and constant
    fixed_subl_indices = sorted(set(sublattice_indices) - set(seen_subl_indices))

    # permute within each sublattice, i.e. [0, 1] -> [[0, 1], [1, 0]]
    intra_sublattice_permutations = (itertools.permutations(equiv_subl) for equiv_subl in symmetry)
    # product, combining all internal sublattice permutations, i.e.
    # [[0, 1], [1, 0]] and [[2, 3], [3, 2]] become [ ([0, 1], [2, 3]), ... ]
    sublattice_products = itertools.product(*intra_sublattice_permutations)
    # finally, swap sets of equivalent sublattices, i.e.
    # [ ([0, 1], [2, 3]), ... ] -> [[ ([0, 1], [2, 3]),  ([2, 3], [0, 1]) ], ... ]
    inter_sublattice_permutations = (itertools.permutations(x) for x in sublattice_products)

    symmetrically_distinct_configurations = set()
    # chain.from_iterable calls flatten out nested permutation lists, i.e.
    # ([0, 1], [2, 3]) -> [0, 1, 2, 3]
    for proposed_distinct_indices in itertools.chain.from_iterable(inter_sublattice_permutations):
        new_config = list(configuration[i] for i in itertools.chain.from_iterable(proposed_distinct_indices))
        # The configuration only contains indices for symmetric sublattices. For the
        # inequivalent sublattices, we need to insert them at their proper indices.
        # Indices _must_ be in sorted order because we are changing the array size on insertion.
        for fixed_idx in fixed_subl_indices:
            new_config.insert(fixed_idx, configuration[fixed_idx])
        symmetrically_distinct_configurations.add(tuple(new_config))
    return sorted(symmetrically_distinct_configurations, key=canonical_sort_key)

