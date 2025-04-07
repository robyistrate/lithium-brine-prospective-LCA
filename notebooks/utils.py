""""
Functions to perform LCA results analysis
"""

from pathlib import Path
import pandas as pd
import brightway2 as bw
import bw2analyzer as bwa
import bw2calc as bc
import bw2data as bd
from bw2io.utils import activity_hash
import json
from copy import deepcopy
import pycountry


def create_biosphere_water_regionalized(
        bio_db_name,
        reg_bio_db_name,
        locations,
        **kwargs
):
    """
    This function creates a new biosphere database that contains
    regionalized water flows for use with the AWARE CFs based on a list of locations.

    Only the water flows that are used in the EF3.1 water use method are considered.
    A copy of these flows is created to add irrigation flow.

    From: https://github.com/ecological-systems-design/Geothermal_brines/blob/main/src/BW2_calculations/lci_method_aware.py
    """
    
    if bio_db_name not in bw.databases:
        raise ValueError(f"{bio_db_name} database not found")
    
    # The EF 3.1 water use method implemented in ecoinvent only accounts for
    # emissions of water to air
    bio_acts = [act for act in bw.Database(bio_db_name) 
                if "water" in act['name'].lower() and 'air' in act['categories']]
    
    # combine locations with original water biosphere flows
    biosphere_data = {}
    for bio_act in bio_acts:
        for loc in locations :
            bio_act_data = deepcopy(bio_act.as_dict())
            bio_act_data['location'] = loc  # Add location
            bio_act_data.pop('database')  # Remove database key
            dbname_code = (reg_bio_db_name, activity_hash(bio_act_data))
            biosphere_data[dbname_code] = bio_act_data
    # Add water emission flows for irrigation
    for bio_act in bio_acts:
        for loc in locations:
            bio_act_data = deepcopy(bio_act.as_dict())
            bio_act_data['location'] = loc  # Add location
            bio_act_data.pop('database')  # Remove database key
            bio_act_data['name'] += ', irrigation'
            dbname_code = (reg_bio_db_name, activity_hash(bio_act_data))
            biosphere_data[dbname_code] = bio_act_data

    if reg_bio_db_name in bw.databases:
        del bw.databases[reg_bio_db_name]

    new_bio_db = bd.Database(reg_bio_db_name)
    new_bio_db.write(biosphere_data)
    print(f"{reg_bio_db_name} was created.")


def create_aware_method(
        bio_db_name,
        reg_bio_db_name,
):  
    """
    This function creates the AWARE method with regionalized CFs.

    Annual aggregated characterization factor for:
     1. Agg_CF_irri: agricultural/irrigation water consumption on basin level
     2. Agg_CF_non_irri: all water consumption sectors except irrigation/agriculture on basin level

    It uses the water flows from the standard biosphere database for the world average CF
    and the regionalized water flows for the site-specific CFs

    Agg_CF_non_irri is assumed as the world average characterization factor.

    From: https://github.com/ecological-systems-design/Geothermal_brines/blob/main/src/BW2_calculations/lci_method_aware.py

    """
    # Import biosphere and regionalized biosphere databases
    if bio_db_name not in bd.databases:
        raise ValueError(f"{bio_db_name} database does not exist")
    bio_db = bd.Database(bio_db_name)

    if reg_bio_db_name not in bd.databases:
        raise ValueError(f"{reg_bio_db_name} database does not exist")
    reg_bio_db = bd.Database(reg_bio_db_name)

    # Import regionalized AWARE CFs
    AWARE_CFs_DIR = Path(r"..\inventories\AWARE_regionalized_CFs\AWARE_country_regions_Corrected_online_20230113-1.xlsx")
    cf_aware = pd.read_excel(AWARE_CFs_DIR, engine='openpyxl', sheet_name='AWARE-annual')

    flows_list = []
    unlinked_loc = []

    for flow in reg_bio_db:
        loc_flow = flow.get('location')
        try:
            loc_aware = cf_aware[cf_aware["Ecoinvent_match"] == loc_flow]["Country"].values[0]
        except:
            try:
                # Country name can be identified by ISO2 code
                country_name = pycountry.countries.get(alpha_2=loc_flow).name
                loc_aware = cf_aware[cf_aware["Country"] == country_name]["Country"].values[0]
            except:
                loc_aware = False

        if loc_aware == False:
            if loc_flow not in unlinked_loc :
                unlinked_loc.append(loc_flow)
        else:
            if 'irrigation' in flow.get('name') :
                aware_score = cf_aware.loc[cf_aware.Country == loc_aware, "Agg_CF_irri"].iloc[0]
            else:
                aware_score = cf_aware.loc[cf_aware.Country == loc_aware, "Agg_CF_non_irri"].iloc[0]

            flows_list.append([flow.key, aware_score])

    # Add global average CFs for unspecified
    for flow in bio_db:
        if "water" in flow['name'].lower() and 'air' in flow['categories']:
            aware_score = cf_aware.loc[cf_aware.Ecoinvent_match == "GLO", "Agg_CF_non_irri"].iloc[0]
            flows_list.append([flow.key, aware_score])

    # Write new BW method
    aware_tuple = ('AWARE regionalized', 'Annual', 'All')
    aware_method = bd.Method(aware_tuple)
    aware_method.register()

    # Add metadata
    aware_method.metadata["unit"] = 'm3 world Eq'
    aware_method.metadata["description"] = 'Regionalized CFs from AWARE method'

    aware_method.validate(flows_list)
    aware_method.register()
    aware_method.write(flows_list)
    print("AWARE method created!")


def relink_to_regionalized_water(bio_reg, ds, location):
    """
    Function to link to regionalized water flows within a LCI 
    """
    biosphere = lambda x: x["type"] == "biosphere"

    for exc in filter(biosphere, ds["exchanges"]):
        if "Water" in exc["name"]:
            water_flow = [flow for flow in bio_reg if flow["name"] == exc["name"] 
                          and flow["categories"] == exc["categories"] 
                          and flow["location"] == location]
            if len(water_flow)==0:
                pass
            else:
                exc.update(
                    {"input": water_flow[0].key}
                )

def mapping_scenario_variables_to_ids(scenario_data):
    """
    Map scenario variables to variable ID.
    The dict structure is varaiable id: variable
    """
    scenario_variables_to_ids = {i.split('|')[-1]: i for i in list(set(scenario_data["variables"]))}
    return scenario_variables_to_ids


def populate_prod_pathaways(config_file, var_id, var_lci, var_product, in_ecoinvent, regionalize, new_dataset, var):
    config_file["production pathways"].pop(var_id, None)

    config_file["production pathways"].update({
        var_id: {
            "ecoinvent alias":{
                "exists in original database": in_ecoinvent,
                "name": var_lci,
                "reference product": var_product,
                "regionalize": regionalize,
                "new dataset": new_dataset
            },
            "production volume":{
                "variable": var
            }
        }
    })

def recursive_calculation_cumulative_flows(
        activity,
        foreground_activities,
        amount=1,
        cumulative_flows=None):
    """
    Adapted from https://github.com/brightway-lca/brightway2/blob/master/notebooks/Contribution%20analysis%20and%20comparison.ipynb
    
    This function calculates the required cumulative amounts of each LCI flow within
    the foreground activities. This data will be used to perform process contribution later.

    :activity:
    :foreground_activities: list of foreground activities
    :amount:
    :cumulative_flows:
    """
    if cumulative_flows is None:
        cumulative_flows = {}

    # Creat dictionary of LCI flows with their cumulative amounts
    for exc in activity.exchanges():

        # Avoid double-counting; we only consider input flows from the background system
        if exc.input in foreground_activities:
            continue
        
        exc_amount = exc["amount"] * amount
        if exc.input in cumulative_flows:
            cumulative_flows[exc.input] += exc_amount
        else:
            cumulative_flows[exc.input] = exc_amount

    for actv in activity.technosphere():
        if actv.input in foreground_activities:

            recursive_calculation_cumulative_flows(
                    activity=actv.input,
                    foreground_activities=foreground_activities,
                    amount=amount * actv['amount'],
                    cumulative_flows=cumulative_flows
                    )
    
    return cumulative_flows


def init_simple_lca(calculation_setup: dict[str, list[dict[str, float]]]) -> bc.LCA:
    """
    Initialize the LCA object with the given calculation setup
    """
    lca = bc.LCA(
        demand=calculation_setup["inventories"][0], 
        method=calculation_setup["methods"][0]
    )
    lca.lci()
    return lca


def mlca(
    lca, 
    calculation_setup, 
    result_dict: dict = None, 
    scenario_name: str = None
    ) -> dict[tuple[str, tuple], dict[str, float]]:
    """
    Simple LCA calculation class to calculate scores for multiple activities and multiple methods.

    lca: LCA object
    calculation_setup: dict
        {"inv": list of dicts, "ia": list of methods}
    result_dict: dict
        dictionary to store results in
        format is: (activity key) -> {method: score}
    """
    if not result_dict:
        result_dict = {}

    # start actual calculation
    methods = calculation_setup["methods"]

    for i, demand in enumerate(calculation_setup["inventories"]):
        key = list(demand.keys())[0]

        # calculate the supply array and inventory for this demand
        lca.redo_lci(demand)

        # perform LCIA calculation for all methods in list, return dict of scores
        mthd_scores = {}
        for method in methods:
            lca.switch_method(method)
            lca.lcia_calculation()
            mthd_scores[method] = lca.score
    
        # calculate the scores and top process contributors
        result_dict[(key, scenario_name)] = mthd_scores

    return result_dict