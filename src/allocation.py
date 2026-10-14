"""Transparent scenario allocation in million US gallons per month."""
import numpy as np
import pandas as pd
from scipy.optimize import linprog

SECTORS = ['Residential', 'Commercial', 'Large volume', 'Municipal']
MINIMUM = np.array([.70, .35, .30, .90])
PRIORITY = np.array([4., 2., 1., 5.])

def allocate(demand, supply, policy='Priority', capacity=None):
    demand = np.asarray(demand, dtype=float)
    if demand.shape != (4,) or not np.isfinite(demand).all() or (demand < 0).any():
        raise ValueError('Four finite nonnegative sector demands are required.')
    if not np.isfinite(supply) or supply < 0:
        raise ValueError('Supply must be finite and nonnegative.')
    if policy not in ['Priority', 'Proportional']:
        raise ValueError('Unknown allocation policy.')
    cap = demand.copy() if capacity is None else np.asarray(capacity, dtype=float)
    if cap.shape != (4,) or not np.isfinite(cap).all() or (cap < 0).any():
        raise ValueError('Four finite nonnegative capacity values are required.')
    upper = np.minimum(demand, cap)
    floors = MINIMUM * demand
    feasible = bool(supply + 1e-8 >= floors.sum() and np.all(upper + 1e-8 >= floors))
    if feasible:
        if policy == 'Priority':
            result = linprog(-PRIORITY, A_ub=np.ones((1,4)), b_ub=[supply],
                             bounds=list(zip(floors, upper)), method='highs')
            if not result.success:
                raise RuntimeError(result.message)
            allocated = result.x
        else:
            # Equal fraction of remaining eligible demand above each service floor.
            spare = upper - floors
            fraction = min(1., max(0., supply-floors.sum()) / max(spare.sum(), 1e-12))
            allocated = floors + fraction * spare
        action = 'Maintain minimum service; conserve nonessential use and review sector shortfalls.'
    else:
        # Emergency fallback is explicitly a minimum-service violation, not a feasible solution.
        eligible = np.minimum(floors, upper)
        allocated = eligible * min(1., supply/max(eligible.sum(),1e-12))
        action = 'EMERGENCY: minimum service infeasible. Escalate for tankers, backup supply or capacity restoration.'
    table = pd.DataFrame({'sector':SECTORS, 'demand_mg':demand,
                          'capacity_mg':cap, 'minimum_mg':floors,
                          'allocated_mg':allocated, 'shortfall_mg':demand-allocated,
                          'minimum_violation_mg':np.maximum(floors-allocated,0)})
    return table, {'feasible':feasible, 'action':action,
                   'unused_supply_mg':float(max(supply-allocated.sum(),0))}
